"""
tests/test_bot_suite.py
=======================
Comprehensive pytest verification suite for the AITADZ Primary School English
Teacher Assistant Bot (3PS, 4PS, 5PS).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from docx import Document
import httpx
import pytest

import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app as app_module  # noqa: E402
import bot as bot_module  # noqa: E402
import didactic_rules  # noqa: E402
import docx_builder  # noqa: E402
from mcp_client import CloudflareMCPClient, extract_json_payload  # noqa: E402


# ---------------------------------------------------------------------------
# 1. DIDACTIC RULES & COMPLIANCE TESTS
# ---------------------------------------------------------------------------


def test_curriculum_counts_and_level_timings():
    assert len(didactic_rules.get_sequences("3PS")) == 6
    assert len(didactic_rules.get_sequences("4PS")) == 5
    assert len(didactic_rules.get_sequences("5PS")) == 3

    assert len(didactic_rules.get_sessions("3PS")) == 4
    assert len(didactic_rules.get_sessions("4PS")) == 5
    assert len(didactic_rules.get_sessions("5PS")) == 9

    expected_minutes = {"3PS": 60, "4PS": 60, "5PS": 45}
    for grade, expected in expected_minutes.items():
        assert didactic_rules.get_grade_meta(grade)["session_duration_minutes"] == expected
        for bp in didactic_rules.get_sessions(grade):
            total = sum(stage["minutes"] for stage in bp["stages"])
            assert total == expected, (
                f"{grade} {bp['id']} summed to {total} mn instead of {expected} mn"
            )


def test_default_lesson_plan_headers_and_objective_formula():
    for grade, seq_id, sec_id, ses_id, expected_min in (
        ("3PS", "3ps-seq-1", "3ps-s1-1", "3ps-listen-repeat", 60),
        ("4PS", "4ps-seq-2", "4ps-s2-1", "4ps-read-write", 60),
        ("5PS", "5ps-seq-1", "5ps-s1-2", "5ps-learn-to-write", 45),
    ):
        plan = didactic_rules.build_default_lesson_plan(grade, seq_id, sec_id, ses_id, "Custom Topic")
        header = plan["header"]
        for req_key in (
            "class_profile",
            "level",
            "number_of_learners",
            "duration",
            "sequence",
            "section",
            "session",
            "domains",
            "target_competence",
            "session_objectives",
            "subsidiary_objectives",
            "phonics_focus",
            "core_values",
            "cross_curricular_competencies",
            "teaching_materials",
            "anticipated_problems",
            "solutions_plan_b",
        ):
            assert header.get(req_key), f"Missing header field {req_key} for {grade}"

        assert header["duration"] == f"{expected_min} mn"
        assert header["session_objectives"].startswith(
            "By the end of the session, learners will be able to"
        )
        assert sum(st["minutes"] for st in plan["stages"]) == expected_min


def test_red_flag_scrubber_removes_meta_terms_and_monetary_rewards():
    dirty_raw = {
        "header": {
            "session_objectives": "teach pupils to describe rooms",
            "teaching_materials": "Flashcards, toy money, coins, and tokens",
        },
        "stages": [
            {
                "minutes": 20,
                "stage": "Stage 1: Warm-up",
                "procedure": "Ask pupils to skim and scan for gist, make a prediction, and win cash, dollars, dinars, coins, and tokens!",
                "interaction": "T-Ls",
                "competency_materials": "Prize money chart",
            },
            {
                "minutes": 10,
                "stage": "Stage 2: Practice",
                "procedure": "Pair work with stickers.",
                "interaction": "Pair",
                "competency_materials": "Flashcards",
            },
        ],
        "gamification": {
            "title": "Classroom Cash & Coin Race",
            "rewards": ["Money", "Coins", "Tokens", "Gold Stars"],
            "description": "Students earn dollars and prize money for fast answers.",
        },
        "exit_ticket": "Share your prediction and gist before getting a coin.",
    }

    cleaned = didactic_rules.validate_and_normalize_lesson_plan(
        dirty_raw,
        grade="5PS",
        sequence_id="5ps-seq-2",
        section_id="5ps-s2-1",
        session_id="5ps-read-understand",
        topic="Town Amenities",
    )

    assert cleaned["header"]["session_objectives"].startswith(
        "By the end of the session, learners will be able to"
    )
    assert sum(st["minutes"] for st in cleaned["stages"]) == 45

    serialized = json.dumps(cleaned).lower()
    for banned_meta in ("skim", "scan", "gist", "prediction"):
        # Check stage procedures, exit_ticket, and whiteboard_layout
        proc_blob = " ".join(s["procedure"].lower() for s in cleaned["stages"])
        assert banned_meta not in proc_blob, f"Meta-term {banned_meta!r} leaked in procedure"
        assert banned_meta not in cleaned["exit_ticket"].lower()

    for banned_money in ("money", "cash", "coin", "token", "dollar", "dinar"):
        assert banned_money not in serialized, f"Monetary term {banned_money!r} leaked in plan"


# ---------------------------------------------------------------------------
# 2. CLOUDFLARE MCP PORTAL CLIENT TESTS
# ---------------------------------------------------------------------------


def test_mcp_client_sends_cf_access_headers_and_parses_response():
    import asyncio
    captured_headers = {}
    captured_payload = {}

    sample_model_json = {
        "header": {
            "session_objectives": "name school facilities and ask where they are.",
        },
        "stages": [
            {
                "minutes": 5,
                "stage": "Stage 1: Warm-up",
                "procedure": "Play a flashcard sound game with Team Points.",
                "interaction": "T-Ls",
                "competency_materials": "Oral Comp. | Flashcards",
            },
            {
                "minutes": 10,
                "stage": "Stage 2: Game Setup",
                "procedure": "Explain and demonstrate Board Race rules clearly.",
                "interaction": "T-Ls",
                "competency_materials": "Written Comp. | Board markers",
            },
            {
                "minutes": 25,
                "stage": "Stage 3: Structured Reading Game",
                "procedure": "All teams read school facility cards and win Gold Stars & Explorer Badges.",
                "interaction": "Group",
                "competency_materials": "Written Comp. | Star Chart",
            },
            {
                "minutes": 5,
                "stage": "Stage 4: Feedback (Exit Ticket)",
                "procedure": "Ticket to leave: decode one facility card.",
                "interaction": "Individual",
                "competency_materials": "Assessment | Stickers",
            },
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers, captured_payload
        captured_headers = dict(request.headers)
        captured_payload = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": captured_payload["id"],
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"```json\n{json.dumps(sample_model_json)}\n```",
                        }
                    ]
                },
            },
        )

    transport = httpx.MockTransport(handler)
    client = CloudflareMCPClient(
        portal_url="https://portal.aitadz.pro/mcp",
        cf_client_id="cf-id-123.access",
        cf_client_secret="cf-secret-xyz",
    )

    async def _run():
        async with httpx.AsyncClient(transport=transport) as mock_http:
            return await client.generate_lesson_plan(
                grade="4PS",
                sequence_id="4ps-seq-2",
                section_id="4ps-s2-1",
                session_id="4ps-read-enjoy",
                topic="School Library & Canteen",
                http_client=mock_http,
            )

    plan = asyncio.run(_run())

    assert captured_headers.get("cf-access-client-id") == "cf-id-123.access"
    assert captured_headers.get("cf-access-client-secret") == "cf-secret-xyz"
    assert captured_payload["method"] == "tools/call"
    assert captured_payload["params"]["arguments"]["grade"] == "4PS"
    assert captured_payload["params"]["arguments"]["duration_minutes"] == 60
    assert captured_payload["params"]["arguments"]["topic"] == "School Library & Canteen"

    assert plan["header"]["session_objectives"].startswith(
        "By the end of the session, learners will be able to"
    )
    assert plan["header"]["duration"] == "60 mn"
    assert sum(s["minutes"] for s in plan["stages"]) == 60
    assert "Board Race" in plan["stages"][1]["procedure"]


def test_mcp_client_offline_fallback():
    client = CloudflareMCPClient(portal_url="", cf_client_id="", cf_client_secret="")
    assert not client.is_configured()
    plan = client.generate_lesson_plan_sync(
        grade="3PS",
        sequence_id="3ps-seq-4",
        section_id="3ps-s4-1",
        session_id="3ps-read-write",
        topic="My Toys (Car & Kite)",
    )
    assert plan["meta"]["grade"] == "3PS"
    assert plan["header"]["duration"] == "60 mn"
    assert sum(s["minutes"] for s in plan["stages"]) == 60
    assert extract_json_payload('{"header": {"level": "3PS"}}') == {"header": {"level": "3PS"}}


# ---------------------------------------------------------------------------
# 3. BRANDED A4 DOCX BUILDER TESTS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "grade,seq_id,sec_id,ses_id",
    [
        ("3PS", "3ps-seq-1", "3ps-s1-1", "3ps-listen-repeat"),
        ("4PS", "4ps-seq-2", "4ps-s2-1", "4ps-read-enjoy"),
        ("5PS", "5ps-seq-3", "5ps-s3-1", "5ps-learn-to-write"),
    ],
)
def test_docx_a4_geometry_brand_palette_and_sections(tmp_path: Path, grade, seq_id, sec_id, ses_id):
    plan = didactic_rules.build_default_lesson_plan(grade, seq_id, sec_id, ses_id, f"{grade} Demo Topic")
    out_file = tmp_path / docx_builder.generate_clean_filename(grade, 1, "LessonPlan")
    saved_path = docx_builder.build_lesson_plan_docx(plan, output_path=str(out_file))

    assert os.path.exists(saved_path)
    doc = Document(saved_path)
    sec = doc.sections[0]

    # Strict A4 (210mm x 297mm) with 12.7mm (0.5 inch) margins
    assert abs(sec.page_width.mm - 210.0) < 0.2
    assert abs(sec.page_height.mm - 297.0) < 0.2
    assert abs(sec.top_margin.mm - 12.7) < 0.2
    assert abs(sec.bottom_margin.mm - 12.7) < 0.2
    assert abs(sec.left_margin.mm - 12.7) < 0.2
    assert abs(sec.right_margin.mm - 12.7) < 0.2

    # Check tables exist: Banner, Metadata, Procedure, Gamification/Exit Ticket, Whiteboard, Self-Reflection
    assert len(doc.tables) == 6

    expected_minutes = 60 if grade in ("3PS", "4PS") else 45
    assert f"{expected_minutes} MINUTES" in doc.tables[0].rows[1].cells[1].text
    assert f"{expected_minutes} mn" in doc.tables[2].rows[-1].cells[0].text
    assert f"{expected_minutes} minutes" in doc.tables[2].rows[-1].cells[1].text

    proc_header_texts = [c.text.strip() for c in doc.tables[2].rows[0].cells]
    assert proc_header_texts == [
        "Time",
        "Stage",
        "Procedure / Teacher & Learner Tasks",
        "Interaction",
        "Competency / Materials",
    ]

    wb_header_texts = [c.text.strip() for c in doc.tables[4].rows[0].cells]
    assert len(wb_header_texts) == 3
    assert "LEFT BOARD" in wb_header_texts[0]
    assert "CENTER BOARD" in wb_header_texts[1]
    assert "RIGHT BOARD" in wb_header_texts[2]

    sr_header_texts = [c.text.strip() for c in doc.tables[5].rows[0].cells]
    assert sr_header_texts == ["What worked", "What hindered", "Action plan"]

    # Footer verification
    footer_text = "".join(p.text for p in sec.footer.paragraphs)
    assert "Generated by AITADZ Teacher Assistant (aitadz.pro)" in footer_text
    footer_xml = sec.footer._element.xml
    assert "PAGE" in footer_xml
    assert "NUMPAGES" in footer_xml

    # Brand palette hex verification in document XML
    body_xml = doc.element.body.xml
    for hex_color in (
        docx_builder.HEX_DEEP_NAVY,
        docx_builder.HEX_PRIMARY_BLUE,
        docx_builder.HEX_SKY_BLUE,
        docx_builder.HEX_ACCENT_ORANGE,
        docx_builder.HEX_SOFT_GRAY,
    ):
        assert hex_color in body_xml, f"Missing brand hex color {hex_color}"


# ---------------------------------------------------------------------------
# 4. FLASK WEBHOOK, HEALTH CHECK & TELEGRAM WIZARD TESTS
# ---------------------------------------------------------------------------


def test_inline_keyboards_callback_data_under_64_bytes():
    for kb in [
        bot_module.build_grade_keyboard(),
        bot_module.build_templates_menu_keyboard(),
        bot_module.build_topic_keyboard(),
        bot_module.build_post_generation_keyboard(),
    ]:
        for row in kb.keyboard:
            for btn in row:
                assert len(btn.callback_data.encode("utf-8")) <= 64

    for grade in ("3PS", "4PS", "5PS"):
        for row in bot_module.build_sequence_keyboard(grade).keyboard:
            for btn in row:
                assert len(btn.callback_data.encode("utf-8")) <= 64
        for seq in didactic_rules.get_sequences(grade):
            for row in bot_module.build_section_keyboard(grade, seq["id"]).keyboard:
                for btn in row:
                    assert len(btn.callback_data.encode("utf-8")) <= 64
        for row in bot_module.build_session_keyboard(grade).keyboard:
            for btn in row:
                assert len(btn.callback_data.encode("utf-8")) <= 64


def test_flask_health_and_webhook_secret_validation():
    fake_bot = MagicMock()
    submitted = []

    class ImmediateExecutor:
        def submit(self, fn, *args, **kwargs):
            submitted.append((fn, args, kwargs))
            fn(*args, **kwargs)

    flask_app = app_module.create_app(
        bot_instance=fake_bot,
        webhook_secret="super-secret-token",
        executor=ImmediateExecutor(),
    )
    client = flask_app.test_client()

    # Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok", "service": "aitadz-lesson-bot"}

    # Missing secret -> 403
    bad_res = client.post("/webhook", json={"update_id": 1})
    assert bad_res.status_code == 403

    # Wrong secret -> 403
    wrong_res = client.post(
        "/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )
    assert wrong_res.status_code == 403

    # Valid secret -> 200 and background dispatch
    valid_update = {
        "update_id": 1001,
        "message": {
            "message_id": 10,
            "date": 1700000000,
            "chat": {"id": 999, "type": "private"},
            "from": {"id": 999, "is_bot": False, "first_name": "Amine"},
            "text": "/start",
        },
    }
    ok_res = client.post(
        "/webhook",
        json=valid_update,
        headers={"X-Telegram-Bot-Api-Secret-Token": "super-secret-token"},
    )
    assert ok_res.status_code == 200
    assert ok_res.get_json() == {"ok": True}
    assert len(submitted) == 1
    fake_bot.process_new_updates.assert_called_once()


def test_generation_pipeline_sends_docx_and_cleans_up_temp_file():
    sent_payloads = {}

    fake_bot = MagicMock()

    def capture_send_document(chat_id, document, visible_file_name=None, **kwargs):
        data = document.read()
        sent_payloads["chat_id"] = chat_id
        sent_payloads["filename"] = visible_file_name
        sent_payloads["bytes"] = data
        sent_payloads["path"] = getattr(document, "name", None)
        sent_payloads["caption"] = kwargs.get("caption", "")

    fake_bot.send_document.side_effect = capture_send_document

    offline_mcp = CloudflareMCPClient(portal_url="", cf_client_id="", cf_client_secret="")
    returned_filename = bot_module.run_generation_pipeline(
        bot_instance=fake_bot,
        chat_id=123456,
        status_message_id=42,
        grade="4PS",
        sequence_id="4ps-seq-2",
        section_id="4ps-s2-1",
        session_id="4ps-read-enjoy",
        topic="School Library",
        mcp_client=offline_mcp,
    )

    assert returned_filename is not None
    assert sent_payloads["chat_id"] == 123456
    assert sent_payloads["filename"].startswith("AITADZ_4PS_Seq2_")
    assert sent_payloads["filename"].endswith(".docx")
    assert sent_payloads["bytes"][:2] == b"PK"  # Valid .docx ZIP container
    assert "AITADZ" in sent_payloads["caption"]
    assert "60 mn" in sent_payloads["caption"]

    # Ensure temporary file and temp folder were immediately cleaned up
    assert sent_payloads["path"] is not None
    assert not os.path.exists(sent_payloads["path"])
    assert not os.path.exists(os.path.dirname(sent_payloads["path"]))
    fake_bot.delete_message.assert_called_once_with(123456, 42)


def test_bot_wizard_full_handler_flow(monkeypatch, tmp_path: Path):
    from database import Database

    sent_messages = []
    edited_messages = []
    sent_docs = []

    test_db = Database(db_path=str(tmp_path / "wizard.db"), default_credits=5)
    offline_mcp = CloudflareMCPClient(portal_url="", cf_client_id="", cf_client_secret="")
    test_bot = bot_module.create_bot(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        mcp_client_factory=lambda: offline_mcp,
        async_dispatch=False,
        db=test_db,
    )

    monkeypatch.setattr(
        test_bot,
        "send_message",
        lambda chat_id, text, **kwargs: (
            sent_messages.append((chat_id, text, kwargs)),
            SimpleNamespace(message_id=len(sent_messages)),
        )[1],
    )
    monkeypatch.setattr(
        test_bot,
        "edit_message_text",
        lambda text, chat_id, msg_id, **kwargs: edited_messages.append((chat_id, msg_id, text, kwargs)),
    )
    monkeypatch.setattr(
        test_bot,
        "answer_callback_query",
        lambda cb_id, text=None: True,
    )
    monkeypatch.setattr(
        test_bot,
        "delete_message",
        lambda chat_id, msg_id: True,
    )
    monkeypatch.setattr(
        test_bot,
        "send_document",
        lambda chat_id, document, visible_file_name=None, **kwargs: sent_docs.append(
            (chat_id, visible_file_name, document.read()[:2])
        ),
    )

    chat_id = 777001
    # Step 1: /start
    start_update = bot_module.telebot.types.Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1700000000,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "is_bot": False, "first_name": "Teacher"},
                "text": "/start",
            },
        }
    )
    test_bot.process_new_updates([start_update])
    assert "Step 1" in sent_messages[-1][1]

    # Step 2: Select Grade -> Sequence -> Section -> Session
    for uid, cb_data in enumerate(
        ["grade:5PS", "seq:5ps-seq-1", "sec:5ps-s1-1", "ses:5ps-listen-interact"], start=2
    ):
        cb_update = bot_module.telebot.types.Update.de_json(
            {
                "update_id": uid,
                "callback_query": {
                    "id": f"cb-{uid}",
                    "from": {"id": chat_id, "is_bot": False, "first_name": "Teacher"},
                    "message": {
                        "message_id": 1,
                        "date": 1700000001,
                        "chat": {"id": chat_id, "type": "private"},
                        "text": "menu",
                    },
                    "chat_instance": "inst",
                    "data": cb_data,
                },
            }
        )
        test_bot.process_new_updates([cb_update])

    assert bot_module.get_session_state(chat_id)["awaiting_topic"] is True

    # Step 3 & 4: Enter Lesson Topic via text reply
    topic_update = bot_module.telebot.types.Update.de_json(
        {
            "update_id": 6,
            "message": {
                "message_id": 2,
                "date": 1700000010,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "is_bot": False, "first_name": "Teacher"},
                "text": "Jobs in Algeria: Doctor, Teacher & Farmer",
            },
        }
    )
    test_bot.process_new_updates([topic_update])

    assert any("Generating your Didactic-compliant DOCX" in msg[1] for msg in sent_messages)
    assert len(sent_docs) == 1
    assert sent_docs[0][0] == chat_id
    assert sent_docs[0][1].startswith("AITADZ_5PS_Seq1_")
    assert sent_docs[0][2] == b"PK"


def test_resilient_env_token_and_webhook_url_resolution(monkeypatch):
    # Malformed token in env should fall back cleanly without crashing create_bot()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bad-token-without-colon")
    safe_bot = bot_module.create_bot()
    assert safe_bot.token == bot_module._DUMMY_TOKEN

    # Quotes / spaces around valid token are stripped cleanly
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", '  "123456:ABCDEF_valid"  ')
    valid_bot = bot_module.create_bot()
    assert valid_bot.token == "123456:ABCDEF_valid"

    # Webhook base URL resolves from RENDER_EXTERNAL_URL and strips /webhook suffix
    monkeypatch.delenv("WEBHOOK_BASE_URL", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://aitadz-lesson-bot.onrender.com/")
    assert app_module.resolve_webhook_base_url() == "https://aitadz-lesson-bot.onrender.com"

    monkeypatch.setenv("WEBHOOK_BASE_URL", '"https://custom.aitadz.pro/webhook/"')
    assert app_module.resolve_webhook_base_url() == "https://custom.aitadz.pro"


def test_database_credits_and_stats(tmp_path: Path):
    from database import Database

    db = Database(db_path=str(tmp_path / "stats.db"), default_credits=2)
    u1 = db.upsert_user(user_id=101, chat_id=101, username="teacher1", first_name="Nadia")
    assert u1["credits"] == 2

    ok, rem = db.consume_credit(101, 1)
    assert ok is True and rem == 1
    db.record_generation(101, "3PS", "3ps-seq-1", "3ps-s1-1", "3ps-listen-repeat", "Family")

    ok2, rem2 = db.consume_credit(101, 1)
    assert ok2 is True and rem2 == 0

    ok3, rem3 = db.consume_credit(101, 1)
    assert ok3 is False and rem3 == 0

    # Admin grant restores credits
    new_bal = db.add_credits(101, 5, reason="admin_grant", admin_id=999)
    assert new_bal == 5

    # Admin user bypasses deduction
    db.upsert_user(user_id=999, chat_id=999, username="sadek", first_name="Sadek", is_admin=True)
    ok_adm, _ = db.consume_credit(999, 1)
    assert ok_adm is True

    stats = db.get_stats()
    assert stats["total_users"] == 2
    assert stats["total_generations"] == 1
    assert stats["by_grade"]["3PS"] == 1
    assert "teacher1" in db.export_users_csv()
    db.close()


def test_admin_stats_and_credit_enforcement_in_bot(monkeypatch, tmp_path: Path):
    from database import Database

    monkeypatch.setenv("ADMIN_ID", "888888")
    test_db = Database(db_path=str(tmp_path / "bot_admin.db"), default_credits=1)
    sent_messages = []

    offline_mcp = CloudflareMCPClient(portal_url="", cf_client_id="", cf_client_secret="")
    test_bot = bot_module.create_bot(
        token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        mcp_client_factory=lambda: offline_mcp,
        async_dispatch=False,
        db=test_db,
    )
    monkeypatch.setattr(
        test_bot,
        "send_message",
        lambda chat_id, text, **kwargs: (
            sent_messages.append((chat_id, text)),
            SimpleNamespace(message_id=len(sent_messages)),
        )[1],
    )

    # Non-admin tries /stats -> denied
    non_admin_stats = bot_module.telebot.types.Update.de_json(
        {
            "update_id": 10,
            "message": {
                "message_id": 10,
                "date": 1700000000,
                "chat": {"id": 555, "type": "private"},
                "from": {"id": 555, "is_bot": False, "first_name": "Ali", "username": "ali"},
                "text": "/stats",
            },
        }
    )
    test_bot.process_new_updates([non_admin_stats])
    assert "Admin access only" in sent_messages[-1][1]

    # Admin runs /stats and /addcredits 555 4
    admin_stats = bot_module.telebot.types.Update.de_json(
        {
            "update_id": 11,
            "message": {
                "message_id": 11,
                "date": 1700000001,
                "chat": {"id": 888888, "type": "private"},
                "from": {"id": 888888, "is_bot": False, "first_name": "Sadek"},
                "text": "/stats",
            },
        }
    )
    test_bot.process_new_updates([admin_stats])
    assert "AITADZ Bot Statistics" in sent_messages[-1][1]

    admin_give = bot_module.telebot.types.Update.de_json(
        {
            "update_id": 12,
            "message": {
                "message_id": 12,
                "date": 1700000002,
                "chat": {"id": 888888, "type": "private"},
                "from": {"id": 888888, "is_bot": False, "first_name": "Sadek"},
                "text": "/addcredits 555 4",
            },
        }
    )
    test_bot.process_new_updates([admin_give])
    assert test_db.get_credits(555) == 5
    test_db.close()


def test_install_resources_stages_have_detailed_activities(tmp_path: Path):
    test_cases = [
        ("3PS", "3ps-seq-2", "3ps-s2-1", "3ps-listen-repeat", "School Bag & Pen"),
        ("3PS", "3ps-seq-4", "3ps-s4-1", "3ps-read-write", "My Toys"),
        ("4PS", "4ps-seq-2", "4ps-s2-1", "4ps-read-enjoy", "School Facilities"),
        ("4PS", "4ps-seq-4", "4ps-s4-2", "4ps-read-write", "Health Advice"),
        ("5PS", "5ps-seq-1", "5ps-s1-1", "5ps-read-understand", "Doctor & Teacher"),
        ("5PS", "5ps-seq-3", "5ps-s3-1", "5ps-learn-to-write", "Summer Holidays"),
    ]

    for grade, seq_id, sec_id, ses_id, topic in test_cases:
        sys_p, usr_p = didactic_rules.build_system_prompt(grade, seq_id, sec_id, ses_id, topic)
        assert "INSTALL RESOURCES & ACTIVITY DEPTH REQUIREMENTS" in sys_p
        assert "Activity 1" in sys_p
        assert "WITH 2-3 DETAILED ACTIVITIES IN EACH INSTALL RESOURCES STAGE" in usr_p

        plan = didactic_rules.build_default_lesson_plan(grade, seq_id, sec_id, ses_id, topic)
        install_stages = [
            s for s in plan["stages"]
            if any(k in s["stage"].lower() for k in ("install resources", "reading", "write", "pre-write", "stage 2", "stage 3"))
        ]
        assert install_stages, f"No install/core stages found for {grade} {ses_id}"
        for st in install_stages:
            proc = st["procedure"]
            assert "Activity 1" in proc, f"Missing Activity 1 in {grade} {ses_id} {st['stage']}"
            assert "Activity 2" in proc, f"Missing Activity 2 in {grade} {ses_id} {st['stage']}"
            assert len(proc.splitlines()) >= 3
            proc_lower = proc.lower()
            for banned_meta in ("skim", "scan", "gist", "prediction"):
                assert banned_meta not in proc_lower, f"Meta-term {banned_meta} leaked in {grade} {ses_id}"
            for banned_money in ("money", "cash", "coin", "token", "dollar", "dinar"):
                assert banned_money not in proc_lower, f"Monetary term {banned_money} leaked in {grade} {ses_id}"

        out_path = tmp_path / f"{grade}_{ses_id}.docx"
        saved = docx_builder.build_lesson_plan_docx(plan, output_path=str(out_path))
        doc = Document(saved)
        assert len(doc.tables) == 6
        proc_cells = [row.cells[2].text for row in doc.tables[2].rows[1:-1]]
        assert any("Activity 1" in txt and "Activity 2" in txt for txt in proc_cells)


# ---------------------------------------------------------------------------
# 6. LESSON PLAN TEMPLATE SELECTOR & VISUAL PREVIEWS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "grade,seq_id,sec_id,ses_id,topic,expected_total,expected_banner",
    [
        ("3PS", "3ps-seq-1", "3ps-s1-1", "3ps-listen-repeat", "Family Greetings", 60, "PRIMARY SCHOOL LESSON PLAN — 3 PS"),
        ("4PS", "4ps-seq-2", "4ps-s2-1", "4ps-read-enjoy", "School Library", 60, "PRIMARY SCHOOL LESSON PLAN — 4 PS"),
        ("5PS", "5ps-seq-1", "5ps-s1-1", "5ps-listen-interact", "Jobs & Occupations", 45, "PRIMARY SCHOOL LESSON PLAN — 5 PS"),
    ],
)
def test_modern_executive_template_docx_structure_and_timings(
    tmp_path: Path,
    grade: str,
    seq_id: str,
    sec_id: str,
    ses_id: str,
    topic: str,
    expected_total: int,
    expected_banner: str,
):
    import re

    plan = didactic_rules.build_default_lesson_plan(grade, seq_id, sec_id, ses_id, topic)
    out_path = tmp_path / f"modern_{grade}_{ses_id}.docx"
    saved = docx_builder.build_lesson_plan_docx(plan, output_path=str(out_path), template_id="modern")
    assert Path(saved).exists()

    doc = Document(saved)
    sec = doc.sections[0]
    assert sec.page_width.mm == pytest.approx(210.0, abs=1.0)
    assert sec.page_height.mm == pytest.approx(297.0, abs=1.0)
    assert sec.top_margin.mm == pytest.approx(12.7, abs=0.6)
    assert sec.left_margin.mm == pytest.approx(12.7, abs=0.6)

    assert len(doc.tables) == 6
    all_text = "\n".join(p.text for p in doc.paragraphs)
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                all_text += "\n" + cell.text

    assert expected_banner in all_text
    for heading in (
        "SESSION OBJECTIVES",
        "SUBSIDIARY OBJECTIVES",
        "ANTICIPATED PROBLEMS",
        "SOLUTIONS",
        "COMMUNICATION",
        "COLLABORATION",
        "CRITICAL THINKING",
        "CREATIVITY",
        "Presentation",
        "Practice",
        "Production",
        "Time / VARK",
        "What Worked Well?",
        "What Hindered? / Action Points",
    ):
        assert heading in all_text

    # Vertically merged "Installing resources" across Presentation, Practice, Production
    exec_tbl = doc.tables[4]
    assert len(exec_tbl.rows) == 6
    assert exec_tbl.rows[2].cells[0]._tc is exec_tbl.rows[3].cells[0]._tc
    assert exec_tbl.rows[3].cells[0]._tc is exec_tbl.rows[4].cells[0]._tc
    assert "Installing" in exec_tbl.rows[2].cells[0].text

    # Stage timing sum equals 60 mn (3PS/4PS) or 45 mn (5PS) and includes VARK letters
    total_mn = 0
    for row in exec_tbl.rows[1:]:
        tv_txt = row.cells[4].text
        m = re.search(r"(\d+)\s*mn", tv_txt)
        assert m, f"Missing duration in Time / VARK cell: {tv_txt!r}"
        total_mn += int(m.group(1))
        assert any(tag in tv_txt for tag in ("V", "A", "R", "K"))
    assert total_mn == expected_total

    # Dashed borders in Objectives divider and Reflection boxes
    assert 'w:val="dashed"' in doc.tables[2]._tbl.xml
    assert 'w:val="dashed"' in doc.tables[5]._tbl.xml

    # 3-part footer with PAGE / NUMPAGES fields
    footer_para = sec.footer.paragraphs[0]
    assert "Primary Education Standard Document" in footer_para.text
    assert "Lesson Plan Template" in footer_para.text
    footer_xml = sec.footer._element.xml
    assert "PAGE" in footer_xml and "NUMPAGES" in footer_xml


def test_template_previews_generate_valid_pngs():
    from PIL import Image
    import template_previews

    template_previews.ensure_preview_assets(force=True)
    assert set(template_previews.PREVIEW_PATHS.keys()) == {"classic", "modern", "both"}

    for kind in ("classic", "modern", "both"):
        p = Path(template_previews.get_preview_image_path(kind))
        assert p.exists()
        raw = p.read_bytes()
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"
        with Image.open(p) as im:
            w, h = im.size
            assert w >= (1200 if kind == "both" else 600)
            assert h >= 800


def test_database_template_preference_and_migration(tmp_path: Path):
    import sqlite3
    from database import Database

    # Legacy schema without preferred_template / template_id must migrate cleanly
    legacy_db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(legacy_db_path)
    conn.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            chat_id INTEGER NOT NULL,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            language_code TEXT DEFAULT '',
            credits INTEGER NOT NULL DEFAULT 5,
            total_generated INTEGER NOT NULL DEFAULT 0,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_banned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            grade TEXT NOT NULL,
            sequence_id TEXT NOT NULL,
            section_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            topic TEXT NOT NULL,
            credits_used INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    migrated = Database(db_path=legacy_db_path, default_credits=5)
    migrated.upsert_user(user_id=1001, chat_id=1001, first_name="Teacher")
    assert migrated.get_preferred_template(1001) == "classic"
    assert migrated.set_preferred_template(1001, "modern") == "modern"
    assert migrated.get_preferred_template(1001) == "modern"

    migrated.record_generation(
        user_id=1001,
        grade="5PS",
        sequence_id="5ps-seq-1",
        section_id="5ps-s1-1",
        session_id="5ps-listen-interact",
        topic="Jobs",
        credits_used=1,
        template_id="modern",
    )
    migrated.record_generation(
        user_id=1001,
        grade="3PS",
        sequence_id="3ps-seq-1",
        section_id="3ps-s1-1",
        session_id="3ps-listen-repeat",
        topic="Family",
        credits_used=1,
        template_id="classic",
    )
    stats = migrated.get_stats()
    assert stats["by_template"] == {"classic": 1, "modern": 1}
    migrated.close()


def test_bot_template_selector_preview_and_modern_generation(monkeypatch, tmp_path: Path):
    import io
    from database import Database

    bot_module._PREVIEW_FILE_IDS.clear()
    test_token = "999888:ABC-DEF1234ghIkl-zyx57W2v1u123ew99"
    test_db = Database(db_path=str(tmp_path / "tpl_bot.db"), default_credits=5)
    offline_mcp = CloudflareMCPClient(portal_url="", cf_client_id="", cf_client_secret="")
    test_bot = bot_module.create_bot(
        token=test_token,
        mcp_client_factory=lambda: offline_mcp,
        async_dispatch=False,
        db=test_db,
    )

    sent_messages = []
    edited_messages = []
    sent_photos = []
    sent_docs = []

    monkeypatch.setattr(
        test_bot,
        "send_message",
        lambda chat_id, text, **kwargs: (
            sent_messages.append((chat_id, text, kwargs)),
            SimpleNamespace(message_id=len(sent_messages)),
        )[1],
    )
    monkeypatch.setattr(
        test_bot,
        "edit_message_text",
        lambda text, chat_id, msg_id, **kwargs: edited_messages.append((chat_id, msg_id, text, kwargs)),
    )
    monkeypatch.setattr(test_bot, "answer_callback_query", lambda cb_id, text=None: True)
    monkeypatch.setattr(test_bot, "delete_message", lambda chat_id, msg_id: True)

    def capture_photo(chat_id, photo, **kwargs):
        if isinstance(photo, str):
            sent_photos.append(("file_id", photo, kwargs))
        else:
            sent_photos.append(("bytes", photo.read()[:8], kwargs))
        return SimpleNamespace(
            message_id=200 + len(sent_photos),
            photo=[SimpleNamespace(file_id="cached-preview-both")],
        )

    monkeypatch.setattr(test_bot, "send_photo", capture_photo)
    monkeypatch.setattr(
        test_bot,
        "send_document",
        lambda chat_id, document, visible_file_name=None, **kwargs: sent_docs.append(
            (chat_id, visible_file_name, document.read(), kwargs.get("caption", ""))
        ),
    )

    chat_id = 888002
    # 1. /templates command opens template menu
    test_bot.process_new_updates([
        bot_module.telebot.types.Update.de_json(
            {
                "update_id": 100,
                "message": {
                    "message_id": 1,
                    "date": 1700000000,
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": chat_id, "is_bot": False, "first_name": "Nadia"},
                    "text": "/templates",
                },
            }
        )
    ])
    assert "Template Selector" in sent_messages[-1][1]

    # 2. Preview comparison sends PNG first, then reuses cached file_id
    def make_cb(uid_num: int, data: str):
        return bot_module.telebot.types.Update.de_json(
            {
                "update_id": uid_num,
                "callback_query": {
                    "id": f"cb-{uid_num}",
                    "from": {"id": chat_id, "is_bot": False, "first_name": "Nadia"},
                    "message": {
                        "message_id": 1,
                        "date": 1700000001,
                        "chat": {"id": chat_id, "type": "private"},
                        "text": "menu",
                    },
                    "chat_instance": "inst",
                    "data": data,
                },
            }
        )

    test_bot.process_new_updates([make_cb(101, "preview:both")])
    assert sent_photos[0][0] == "bytes"
    assert sent_photos[0][1] == b"\x89PNG\r\n\x1a\n"

    test_bot.process_new_updates([make_cb(102, "preview:both")])
    assert sent_photos[1][0] == "file_id"
    assert sent_photos[1][1] == "cached-preview-both"

    # 3. Select modern template and verify DB persistence across /start reset
    test_bot.process_new_updates([make_cb(103, "tpl:modern")])
    assert test_db.get_preferred_template(chat_id) == "modern"

    test_bot.process_new_updates([
        bot_module.telebot.types.Update.de_json(
            {
                "update_id": 104,
                "message": {
                    "message_id": 2,
                    "date": 1700000002,
                    "chat": {"id": chat_id, "type": "private"},
                    "from": {"id": chat_id, "is_bot": False, "first_name": "Nadia"},
                    "text": "/start",
                },
            }
        )
    ])
    assert "Executive Standard (4Cs &amp; VARK)" in sent_messages[-1][1]

    # 4. Run wizard to generate DOCX with the selected modern template
    for uid_num, cb in enumerate(
        ["grade:5PS", "seq:5ps-seq-1", "sec:5ps-s1-1", "ses:5ps-listen-interact", "topic:default"],
        start=105,
    ):
        test_bot.process_new_updates([make_cb(uid_num, cb)])

    assert len(sent_docs) == 1
    doc_bytes = sent_docs[0][2]
    caption = sent_docs[0][3]
    assert doc_bytes[:2] == b"PK"
    assert "Executive Standard (4Cs &amp; VARK)" in caption

    generated_doc = Document(io.BytesIO(doc_bytes))
    assert "PRIMARY SCHOOL LESSON PLAN — 5 PS" in generated_doc.tables[0].rows[0].cells[0].text
    assert test_db.get_stats()["by_template"]["modern"] == 1

    bot_module._PREVIEW_FILE_IDS.clear()
    test_db.close()
