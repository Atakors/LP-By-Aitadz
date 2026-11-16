"""
bot.py
======
Interactive Telegram Bot wizard for AITADZ Teacher Assistant (aitadz.pro).

Provides a step-by-step inline keyboard workflow for Algerian Primary School
English teachers (3PS, 4PS, 5PS):
  Step 1: Select Grade Level (3PS, 4PS, 5PS)
  Step 2: Select Sequence -> Section -> Session (dynamically from didactic_rules.py)
  Step 3: Enter specific Lesson Topic / Vocabulary / Grammar focus (text or default)
  Step 4: Asynchronously invoke Cloudflare MCP Portal -> build A4 DOCX -> send_document()
          and immediately clean up temporary files.
"""

from __future__ import annotations

import concurrent.futures
import html
import logging
import os
import shutil
import tempfile
import threading
from typing import Any, Callable, Dict, Optional

import telebot
from telebot import types

from didactic_rules import (
    get_grade_meta,
    get_section_by_id,
    get_sections,
    get_sequence_by_id,
    get_sequences,
    get_session_blueprint,
    get_sessions,
)
from docx_builder import build_lesson_plan_docx, generate_clean_filename
from mcp_client import CloudflareMCPClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# THREAD-SAFE SESSION STATE & BACKGROUND WORKER POOL
# ---------------------------------------------------------------------------

_SESSION_LOCK = threading.Lock()
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}
GENERATION_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.environ.get("AITADZ_WORKERS", "4")),
    thread_name_prefix="aitadz-gen",
)

_DUMMY_TOKEN = "000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def is_bot_token_configured() -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    return bool(token and token != _DUMMY_TOKEN)


def get_session_state(chat_id: int) -> Dict[str, Any]:
    with _SESSION_LOCK:
        return dict(USER_SESSIONS.get(chat_id, {}))


def update_session_state(chat_id: int, **updates: Any) -> Dict[str, Any]:
    with _SESSION_LOCK:
        current = USER_SESSIONS.setdefault(chat_id, {})
        current.update(updates)
        return dict(current)


def reset_session_state(chat_id: int) -> None:
    with _SESSION_LOCK:
        USER_SESSIONS[chat_id] = {}


# ---------------------------------------------------------------------------
# INLINE KEYBOARD BUILDERS
# ---------------------------------------------------------------------------


def build_grade_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🟢 3PS - Year 3 Primary (Key Stage 1)", callback_data="grade:3PS"),
        types.InlineKeyboardButton("🔵 4PS - Year 4 Primary (Key Stage 1)", callback_data="grade:4PS"),
        types.InlineKeyboardButton("🟣 5PS - Year 5 Primary (Key Stage 3)", callback_data="grade:5PS"),
    )
    return kb


def build_sequence_keyboard(grade: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for seq in get_sequences(grade):
        kb.add(
            types.InlineKeyboardButton(
                f"📘 Seq {seq['number']}: {seq['title']}",
                callback_data=f"seq:{seq['id']}",
            )
        )
    kb.add(types.InlineKeyboardButton("⬅️ Back to Grades", callback_data="nav:grades"))
    return kb


def build_section_keyboard(grade: str, sequence_id: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for sec in get_sections(grade, sequence_id):
        kb.add(
            types.InlineKeyboardButton(
                f"📂 {sec['title']}",
                callback_data=f"sec:{sec['id']}",
            )
        )
    kb.add(types.InlineKeyboardButton("⬅️ Back to Sequences", callback_data="nav:seqs"))
    return kb


def build_session_keyboard(grade: str) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    for bp in get_sessions(grade):
        kb.add(
            types.InlineKeyboardButton(
                f"📝 {bp['title']}",
                callback_data=f"ses:{bp['id']}",
            )
        )
    kb.add(types.InlineKeyboardButton("⬅️ Back to Sections", callback_data="nav:secs"))
    return kb


def build_topic_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(
            "✨ Use Official Syllabus Topic & Generate Now",
            callback_data="topic:default",
        ),
        types.InlineKeyboardButton("⬅️ Back to Sessions", callback_data="nav:ses"),
    )
    return kb


def build_post_generation_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🔄 Generate Another Lesson Plan", callback_data="nav:restart"),
    )
    return kb


# ---------------------------------------------------------------------------
# ASYNC GENERATION PIPELINE (MCP -> DOCX -> TELEGRAM -> CLEANUP)
# ---------------------------------------------------------------------------


def run_generation_pipeline(
    bot_instance: telebot.TeleBot,
    chat_id: int,
    status_message_id: Optional[int],
    grade: str,
    sequence_id: str,
    section_id: str,
    session_id: str,
    topic: str,
    mcp_client: Optional[CloudflareMCPClient] = None,
) -> Optional[str]:
    """
    Execute lesson generation via Cloudflare MCP Portal, build the branded A4
    .docx file, deliver it via Telegram `send_document`, and delete the
    temporary file immediately after sending.
    """
    client = mcp_client or CloudflareMCPClient()
    tmp_dir: Optional[str] = None
    output_path: Optional[str] = None

    try:
        plan_data = client.generate_lesson_plan_sync(
            grade=grade,
            sequence_id=sequence_id,
            section_id=section_id,
            session_id=session_id,
            topic=topic,
        )

        meta = plan_data["meta"]
        bp = get_session_blueprint(grade, session_id)
        filename = generate_clean_filename(
            grade,
            int(meta["sequence_number"]),
            bp["short_title"],
        )

        tmp_dir = tempfile.mkdtemp(prefix="aitadz_tg_")
        output_path = os.path.join(tmp_dir, filename)
        build_lesson_plan_docx(plan_data, output_path=output_path)

        header = plan_data["header"]
        duration_str = header.get("duration", f"{meta.get('duration_minutes', 60)} mn")
        caption = (
            f"✅ <b>AITADZ Official Didactic Lesson Plan Ready!</b>\n\n"
            f"🎓 <b>Level:</b> {html.escape(header['level'])}\n"
            f"📘 <b>Sequence:</b> {html.escape(header['sequence'])}\n"
            f"📂 <b>Section:</b> {html.escape(header['section'])}\n"
            f"📝 <b>Session:</b> {html.escape(bp['title'])}\n"
            f"🎯 <b>Topic Focus:</b> {html.escape(meta['topic'])}\n"
            f"⏱️ <b>Duration:</b> {html.escape(duration_str)} (A4 Print-Ready • Didactic Guide Compliant)\n\n"
            f"<i>Generated by AITADZ Teacher Assistant (aitadz.pro)</i>"
        )

        with open(output_path, "rb") as doc_file:
            bot_instance.send_document(
                chat_id=chat_id,
                document=doc_file,
                visible_file_name=filename,
                caption=caption,
                parse_mode="HTML",
                reply_markup=build_post_generation_keyboard(),
            )

        if status_message_id is not None:
            try:
                bot_instance.delete_message(chat_id, status_message_id)
            except Exception:
                pass

        return filename

    except Exception as exc:
        logger.exception("Failed generating lesson plan for chat %s: %s", chat_id, exc)
        err_text = (
            "⚠️ Sorry, something went wrong while generating your lesson plan. "
            "Please tap /start to try again."
        )
        try:
            if status_message_id is not None:
                bot_instance.edit_message_text(err_text, chat_id, status_message_id)
            else:
                bot_instance.send_message(chat_id, err_text)
        except Exception:
            pass
        return None

    finally:
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# BOT FACTORY & HANDLER REGISTRATION
# ---------------------------------------------------------------------------


def _welcome_text() -> str:
    return (
        "🎓 <b>Welcome to AITADZ Teacher Assistant (aitadz.pro)</b>\n\n"
        "Automated <b>Algerian Primary School English</b> Lesson Plan Generator "
        "strictly aligned with the official Ministry / CNP Didactic Guides "
        "(<b>3PS, 4PS &amp; 5PS</b>).\n\n"
        "📄 Exports <b>print-ready A4 (.docx)</b> lesson plans featuring:\n"
        "• Official Didactic Metadata &amp; Competences\n"
        "• Official Stage-by-Stage Procedure Table (60 mn 3PS/4PS • 45 mn 5PS)\n"
        "• Non-Monetary Classroom Gamification (Stars &amp; Badges)\n"
        "• 3-Panel Visual Whiteboard Layout &amp; Self-Reflection\n\n"
        "👇 <b>Step 1: Select your Grade Level to begin:</b>"
    )


def create_bot(
    token: Optional[str] = None,
    mcp_client_factory: Optional[Callable[[], CloudflareMCPClient]] = None,
    async_dispatch: bool = True,
) -> telebot.TeleBot:
    """Create and configure the TeleBot instance with all wizard handlers."""
    resolved_token = (token or os.environ.get("TELEGRAM_BOT_TOKEN") or _DUMMY_TOKEN).strip()
    bot_instance = telebot.TeleBot(resolved_token, threaded=False)
    make_mcp = mcp_client_factory or CloudflareMCPClient

    def _safe_answer_cb(call: types.CallbackQuery, text: Optional[str] = None) -> None:
        try:
            bot_instance.answer_callback_query(call.id, text=text)
        except Exception:
            pass

    def _start_generation(chat_id: int, topic_text: str) -> None:
        state = get_session_state(chat_id)
        grade = state.get("grade")
        sequence_id = state.get("sequence_id")
        section_id = state.get("section_id")
        session_id = state.get("session_id")
        if not (grade and sequence_id and section_id and session_id):
            bot_instance.send_message(
                chat_id,
                "Please select your Grade, Sequence, Section, and Session first:",
                reply_markup=build_grade_keyboard(),
            )
            return

        update_session_state(chat_id, awaiting_topic=False, topic=topic_text)
        status_msg = bot_instance.send_message(
            chat_id,
            "⏳ Generating your Didactic-compliant DOCX lesson plan...",
        )
        status_id = getattr(status_msg, "message_id", None)
        client = make_mcp()

        if async_dispatch:
            GENERATION_EXECUTOR.submit(
                run_generation_pipeline,
                bot_instance,
                chat_id,
                status_id,
                grade,
                sequence_id,
                section_id,
                session_id,
                topic_text,
                client,
            )
        else:
            run_generation_pipeline(
                bot_instance,
                chat_id,
                status_id,
                grade,
                sequence_id,
                section_id,
                session_id,
                topic_text,
                client,
            )

    @bot_instance.message_handler(commands=["start", "plan", "help", "reset"])
    def handle_start(message: types.Message) -> None:
        reset_session_state(message.chat.id)
        bot_instance.send_message(
            message.chat.id,
            _welcome_text(),
            parse_mode="HTML",
            reply_markup=build_grade_keyboard(),
        )

    @bot_instance.callback_query_handler(func=lambda call: bool(call.data))
    def handle_callbacks(call: types.CallbackQuery) -> None:
        data = call.data or ""
        chat_id = call.message.chat.id
        msg_id = call.message.message_id

        if data in ("nav:grades", "nav:restart"):
            _safe_answer_cb(call)
            reset_session_state(chat_id)
            if data == "nav:restart":
                bot_instance.send_message(
                    chat_id,
                    _welcome_text(),
                    parse_mode="HTML",
                    reply_markup=build_grade_keyboard(),
                )
            else:
                bot_instance.edit_message_text(
                    _welcome_text(),
                    chat_id,
                    msg_id,
                    parse_mode="HTML",
                    reply_markup=build_grade_keyboard(),
                )
            return

        if data.startswith("grade:"):
            grade = data.split(":", 1)[1]
            meta = get_grade_meta(grade)
            update_session_state(
                chat_id,
                grade=grade,
                sequence_id=None,
                section_id=None,
                session_id=None,
                awaiting_topic=False,
            )
            _safe_answer_cb(call, f"Selected {grade}")
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(meta['label'])}\n"
                f"📖 <i>{html.escape(meta['guide_title'])} ({meta['guide_year']})</i>\n\n"
                f"👇 <b>Step 2A: Choose the Official Sequence:</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_sequence_keyboard(grade),
            )
            return

        if data == "nav:seqs":
            _safe_answer_cb(call)
            state = get_session_state(chat_id)
            grade = state.get("grade")
            if not grade:
                bot_instance.edit_message_text(
                    _welcome_text(),
                    chat_id,
                    msg_id,
                    parse_mode="HTML",
                    reply_markup=build_grade_keyboard(),
                )
                return
            meta = get_grade_meta(grade)
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(meta['label'])}\n\n"
                f"👇 <b>Step 2A: Choose the Official Sequence:</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_sequence_keyboard(grade),
            )
            return

        if data.startswith("seq:"):
            sequence_id = data.split(":", 1)[1]
            state = get_session_state(chat_id)
            grade = state.get("grade")
            if not grade:
                _safe_answer_cb(call, "Please select grade first.")
                return
            seq = get_sequence_by_id(grade, sequence_id)
            update_session_state(
                chat_id,
                sequence_id=seq["id"],
                section_id=None,
                session_id=None,
                awaiting_topic=False,
            )
            _safe_answer_cb(call, f"Sequence {seq['number']}")
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(grade)}\n"
                f"📘 <b>Sequence {seq['number']}:</b> {html.escape(seq['title'])}\n\n"
                f"👇 <b>Step 2B: Choose the Section:</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_section_keyboard(grade, seq["id"]),
            )
            return

        if data == "nav:secs":
            _safe_answer_cb(call)
            state = get_session_state(chat_id)
            grade = state.get("grade")
            sequence_id = state.get("sequence_id")
            if not (grade and sequence_id):
                return
            seq = get_sequence_by_id(grade, sequence_id)
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(grade)}\n"
                f"📘 <b>Sequence {seq['number']}:</b> {html.escape(seq['title'])}\n\n"
                f"👇 <b>Step 2B: Choose the Section:</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_section_keyboard(grade, seq["id"]),
            )
            return

        if data.startswith("sec:"):
            section_id = data.split(":", 1)[1]
            state = get_session_state(chat_id)
            grade = state.get("grade")
            sequence_id = state.get("sequence_id")
            if not (grade and sequence_id):
                _safe_answer_cb(call, "Please start from /start.")
                return
            sec = get_section_by_id(grade, sequence_id, section_id)
            duration_mn = int(get_grade_meta(grade)["session_duration_minutes"])
            update_session_state(
                chat_id,
                section_id=sec["id"],
                session_id=None,
                awaiting_topic=False,
            )
            _safe_answer_cb(call, sec["title"])
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(grade)}\n"
                f"📂 <b>Section:</b> {html.escape(sec['title'])}\n"
                f"🔤 <b>Phonics:</b> {html.escape(sec['phonics_target'])}\n\n"
                f"👇 <b>Step 2C: Select the Official Session Type ({duration_mn} mn):</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_session_keyboard(grade),
            )
            return

        if data == "nav:ses":
            _safe_answer_cb(call)
            state = get_session_state(chat_id)
            grade = state.get("grade")
            sequence_id = state.get("sequence_id")
            section_id = state.get("section_id")
            if not (grade and sequence_id and section_id):
                return
            sec = get_section_by_id(grade, sequence_id, section_id)
            duration_mn = int(get_grade_meta(grade)["session_duration_minutes"])
            update_session_state(chat_id, awaiting_topic=False)
            bot_instance.edit_message_text(
                f"🎓 <b>Grade:</b> {html.escape(grade)}\n"
                f"📂 <b>Section:</b> {html.escape(sec['title'])}\n\n"
                f"👇 <b>Step 2C: Select the Official Session Type ({duration_mn} mn):</b>",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_session_keyboard(grade),
            )
            return

        if data.startswith("ses:"):
            session_id = data.split(":", 1)[1]
            state = get_session_state(chat_id)
            grade = state.get("grade")
            sequence_id = state.get("sequence_id")
            section_id = state.get("section_id")
            if not (grade and sequence_id and section_id):
                _safe_answer_cb(call, "Session expired; tap /start.")
                return
            seq = get_sequence_by_id(grade, sequence_id)
            sec = get_section_by_id(grade, sequence_id, section_id)
            bp = get_session_blueprint(grade, session_id)
            update_session_state(chat_id, session_id=bp["id"], awaiting_topic=True)
            _safe_answer_cb(call, bp["short_title"])

            vocab_preview = ", ".join(sec["key_vocabulary"][:6])
            bot_instance.edit_message_text(
                f"✅ <b>Selection Summary</b>\n"
                f"• <b>Grade:</b> {html.escape(grade)}\n"
                f"• <b>Sequence {seq['number']}:</b> {html.escape(seq['title'])}\n"
                f"• <b>Section:</b> {html.escape(sec['title'])}\n"
                f"• <b>Session:</b> {html.escape(bp['title'])}\n"
                f"• <b>Key Lexis:</b> {html.escape(vocab_preview)}\n\n"
                f"✍️ <b>Step 3: Reply with your specific Lesson Topic, Target Vocabulary, "
                f"or Grammar structure</b> (e.g., <i>\"Rooms of the house &amp; Is there a...?\"</i>),\n"
                f"or tap the button below to use the official syllabus focus directly:",
                chat_id,
                msg_id,
                parse_mode="HTML",
                reply_markup=build_topic_keyboard(),
            )
            return

        if data == "topic:default":
            _safe_answer_cb(call, "Starting generation...")
            state = get_session_state(chat_id)
            grade = state.get("grade")
            sequence_id = state.get("sequence_id")
            section_id = state.get("section_id")
            if not (grade and sequence_id and section_id):
                return
            sec = get_section_by_id(grade, sequence_id, section_id)
            default_topic = sec["title"].replace(f"Section {sec['number']}: ", "")
            _start_generation(chat_id, default_topic)
            return

    @bot_instance.message_handler(
        func=lambda m: bool(m.text) and not m.text.startswith("/"),
        content_types=["text"],
    )
    def handle_topic_reply(message: types.Message) -> None:
        chat_id = message.chat.id
        state = get_session_state(chat_id)
        if state.get("awaiting_topic"):
            topic_text = (message.text or "").strip()
            _start_generation(chat_id, topic_text)
        else:
            bot_instance.send_message(
                chat_id,
                "👋 Use /start or select your Grade Level below to generate a new lesson plan:",
                reply_markup=build_grade_keyboard(),
            )

    return bot_instance


bot = create_bot()
