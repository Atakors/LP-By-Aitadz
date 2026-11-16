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
import io
import logging
import os
import shutil
import tempfile
import threading
from typing import Any, Callable, Dict, Optional, Set

import telebot
from telebot import types

from database import Database
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


def _resolve_bot_token(explicit_token: Optional[str] = None) -> str:
    """Resolve and sanitize TELEGRAM_BOT_TOKEN (or BOT_TOKEN) without crashing on import."""
    raw = (
        explicit_token
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("BOT_TOKEN")
        or ""
    )
    cleaned = raw.strip().strip('"').strip("'")
    if cleaned and ":" in cleaned and not any(ch.isspace() for ch in cleaned):
        return cleaned
    if cleaned:
        logger.error(
            "TELEGRAM_BOT_TOKEN appears malformed (expected '<id>:<secret>' with no spaces); "
            "using inactive fallback token until fixed."
        )
    return _DUMMY_TOKEN


def is_bot_token_configured() -> bool:
    return _resolve_bot_token() != _DUMMY_TOKEN


def get_configured_admin_ids() -> Set[int]:
    """Parse ADMIN_ID / ADMIN_IDS env vars (comma-separated Telegram user IDs)."""
    raw = f"{os.environ.get('ADMIN_ID', '')},{os.environ.get('ADMIN_IDS', '')}"
    ids: Set[int] = set()
    for part in raw.split(","):
        cleaned = part.strip().strip('"').strip("'")
        if cleaned:
            try:
                ids.add(int(cleaned))
            except ValueError:
                pass
    return ids


def get_configured_admin_usernames() -> Set[str]:
    """Parse ADMIN_USERNAME / ADMIN_USERNAMES env vars (comma-separated handles)."""
    raw = f"{os.environ.get('ADMIN_USERNAME', '')},{os.environ.get('ADMIN_USERNAMES', '')}"
    names: Set[str] = set()
    for part in raw.split(","):
        cleaned = part.strip().strip('"').strip("'").lstrip("@").lower()
        if cleaned:
            names.add(cleaned)
    return names


def is_admin_user(
    user_id: Optional[int],
    username: str = "",
    db_instance: Optional[Database] = None,
) -> bool:
    if user_id is not None and int(user_id) in get_configured_admin_ids():
        return True
    clean_uname = (username or "").strip().lstrip("@").lower()
    if clean_uname and clean_uname in get_configured_admin_usernames():
        return True
    if db_instance is not None and user_id is not None:
        row = db_instance.get_user(int(user_id))
        if row and int(row.get("is_admin", 0)) == 1:
            return True
    return False


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
    user_id: Optional[int] = None,
    db_instance: Optional[Database] = None,
    credit_deducted: bool = False,
    is_admin: bool = False,
) -> Optional[str]:
    """
    Execute lesson generation via Cloudflare MCP Portal, build the branded A4
    .docx file, deliver it via Telegram `send_document`, record stats, and
    delete the temporary file immediately after sending.
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

        credit_line = ""
        if db_instance is not None and user_id is not None:
            db_instance.record_generation(
                user_id=user_id,
                grade=grade,
                sequence_id=sequence_id,
                section_id=section_id,
                session_id=session_id,
                topic=meta["topic"],
                credits_used=0 if is_admin else (1 if credit_deducted else 0),
            )
            if is_admin:
                credit_line = "🎟️ <b>Credits:</b> Unlimited (Admin)\n"
            else:
                remaining = db_instance.get_credits(user_id)
                credit_line = f"🎟️ <b>Remaining Credits:</b> {remaining}\n"

        header = plan_data["header"]
        duration_str = header.get("duration", f"{meta.get('duration_minutes', 60)} mn")
        caption = (
            f"✅ <b>AITADZ Official Didactic Lesson Plan Ready!</b>\n\n"
            f"🎓 <b>Level:</b> {html.escape(header['level'])}\n"
            f"📘 <b>Sequence:</b> {html.escape(header['sequence'])}\n"
            f"📂 <b>Section:</b> {html.escape(header['section'])}\n"
            f"📝 <b>Session:</b> {html.escape(bp['title'])}\n"
            f"🎯 <b>Topic Focus:</b> {html.escape(meta['topic'])}\n"
            f"⏱️ <b>Duration:</b> {html.escape(duration_str)} (A4 Print-Ready • Didactic Guide Compliant)\n"
            f"{credit_line}\n"
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
        if credit_deducted and not is_admin and db_instance is not None and user_id is not None:
            try:
                db_instance.add_credits(user_id, 1, reason="refund_on_error")
            except Exception:
                pass
        err_text = (
            "⚠️ Sorry, something went wrong while generating your lesson plan. "
            "Your credit has been refunded. Please tap /start to try again."
            if credit_deducted and not is_admin
            else "⚠️ Sorry, something went wrong while generating your lesson plan. Please tap /start to try again."
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
    db: Optional[Database] = None,
) -> telebot.TeleBot:
    """Create and configure the TeleBot instance with all wizard, credit & admin handlers."""
    resolved_token = _resolve_bot_token(token)
    bot_instance = telebot.TeleBot(resolved_token, threaded=False, validate_token=False)
    make_mcp = mcp_client_factory or CloudflareMCPClient
    database = db if db is not None else Database()

    def _sync_user(from_user: Any, chat_id: int) -> tuple[Dict[str, Any], bool]:
        uid = getattr(from_user, "id", None) or chat_id
        uname = getattr(from_user, "username", "") or ""
        fname = getattr(from_user, "first_name", "") or ""
        lname = getattr(from_user, "last_name", "") or ""
        lang = getattr(from_user, "language_code", "") or ""
        admin_flag = is_admin_user(uid, uname, database)
        user_row = database.upsert_user(
            user_id=int(uid),
            chat_id=chat_id,
            username=uname,
            first_name=fname,
            last_name=lname,
            language_code=lang,
            is_admin=admin_flag,
        )
        return user_row, bool(admin_flag or int(user_row.get("is_admin", 0)) == 1)

    def _safe_answer_cb(call: types.CallbackQuery, text: Optional[str] = None) -> None:
        try:
            bot_instance.answer_callback_query(call.id, text=text)
        except Exception:
            pass

    def _start_generation(
        chat_id: int,
        topic_text: str,
        from_user: Any = None,
    ) -> None:
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

        user_row, admin_flag = _sync_user(from_user, chat_id)
        uid = int(user_row["user_id"])

        credit_deducted = False
        if not admin_flag:
            allowed, remaining = database.consume_credit(
                uid, amount=1, reason=f"lesson_plan:{grade}:{session_id}"
            )
            if not allowed:
                bot_instance.send_message(
                    chat_id,
                    f"🎟️ <b>Out of Lesson Plan Credits (0 remaining)</b>\n\n"
                    f"Each lesson plan export uses <b>1 credit token</b>.\n"
                    f"Your Telegram ID: <code>{uid}</code>\n"
                    f"Contact the AITADZ administrator with your ID to top up your credits, "
                    f"or check /credits anytime.",
                    parse_mode="HTML",
                )
                return
            credit_deducted = True

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
                uid,
                database,
                credit_deducted,
                admin_flag,
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
                uid,
                database,
                credit_deducted,
                admin_flag,
            )

    @bot_instance.message_handler(commands=["start", "plan", "help", "reset"])
    def handle_start(message: types.Message) -> None:
        user_row, admin_flag = _sync_user(message.from_user, message.chat.id)
        reset_session_state(message.chat.id)
        credits_badge = (
            "♾️ <b>Admin Unlimited</b>"
            if admin_flag
            else f"🎟️ <b>Available Credits:</b> {user_row['credits']}"
        )
        admin_hint = (
            "\n🛠️ <b>Admin Commands:</b> /stats • /users • /addcredits • /export_users"
            if admin_flag
            else "\n💡 Check /credits or /myid anytime."
        )
        bot_instance.send_message(
            message.chat.id,
            f"{_welcome_text()}\n\n{credits_badge}{admin_hint}",
            parse_mode="HTML",
            reply_markup=build_grade_keyboard(),
        )

    @bot_instance.message_handler(commands=["credits", "balance"])
    def handle_credits(message: types.Message) -> None:
        user_row, admin_flag = _sync_user(message.from_user, message.chat.id)
        balance_str = "♾️ Unlimited (Admin)" if admin_flag else f"{user_row['credits']} credit token(s)"
        bot_instance.send_message(
            message.chat.id,
            f"🎟️ <b>Your AITADZ Credit Balance</b>\n\n"
            f"• <b>Credits:</b> {balance_str}\n"
            f"• <b>Plans Generated:</b> {user_row['total_generated']}\n"
            f"• <b>Your User ID:</b> <code>{user_row['user_id']}</code>",
            parse_mode="HTML",
        )

    @bot_instance.message_handler(commands=["myid"])
    def handle_myid(message: types.Message) -> None:
        user_row, admin_flag = _sync_user(message.from_user, message.chat.id)
        role = "Admin 👑" if admin_flag else "Teacher"
        bot_instance.send_message(
            message.chat.id,
            f"🆔 <b>Your Telegram ID:</b> <code>{user_row['user_id']}</code>\n"
            f"👤 <b>Role:</b> {role}",
            parse_mode="HTML",
        )

    @bot_instance.message_handler(commands=["stats"])
    def handle_stats(message: types.Message) -> None:
        _, admin_flag = _sync_user(message.from_user, message.chat.id)
        if not admin_flag:
            bot_instance.send_message(message.chat.id, "⛔ Admin access only.")
            return

        st = database.get_stats()
        by_g = st["by_grade"]
        top_lines = []
        for idx, u in enumerate(st["top_users"], start=1):
            label = f"@{u['username']}" if u.get("username") else (u.get("first_name") or str(u["user_id"]))
            top_lines.append(
                f"  {idx}. {html.escape(label)} (<code>{u['user_id']}</code>) — "
                f"{u['total_generated']} plans | {u['credits']} credits"
            )
        top_block = "\n".join(top_lines) if top_lines else "  No users yet."

        bot_instance.send_message(
            message.chat.id,
            f"📊 <b>AITADZ Bot Statistics</b>\n\n"
            f"👥 <b>Total Users:</b> {st['total_users']} (Active today: {st['active_today']})\n"
            f"📄 <b>Total Lesson Plans:</b> {st['total_generations']} (Today: {st['generations_today']})\n"
            f"🎟️ <b>Credits in Circulation:</b> {st['total_credits_remaining']}\n\n"
            f"📚 <b>By Grade:</b> 3PS: {by_g['3PS']} | 4PS: {by_g['4PS']} | 5PS: {by_g['5PS']}\n\n"
            f"🏆 <b>Top Users:</b>\n{top_block}",
            parse_mode="HTML",
        )

    @bot_instance.message_handler(commands=["users"])
    def handle_users(message: types.Message) -> None:
        _, admin_flag = _sync_user(message.from_user, message.chat.id)
        if not admin_flag:
            bot_instance.send_message(message.chat.id, "⛔ Admin access only.")
            return

        users = database.list_users(limit=20)
        if not users:
            bot_instance.send_message(message.chat.id, "No users registered yet.")
            return

        lines = []
        for u in users:
            uname = f"@{u['username']}" if u.get("username") else "-"
            name = html.escape((u.get("first_name") or "") + (" " + u["last_name"] if u.get("last_name") else "")).strip() or "User"
            crown = " 👑" if int(u.get("is_admin", 0)) == 1 else ""
            lines.append(
                f"• <code>{u['user_id']}</code> {name} ({html.escape(uname)}){crown} — "
                f"{u['credits']} cr | {u['total_generated']} plans"
            )
        bot_instance.send_message(
            message.chat.id,
            "👥 <b>Recent Users (up to 20):</b>\n\n" + "\n".join(lines),
            parse_mode="HTML",
        )

    @bot_instance.message_handler(commands=["export_users"])
    def handle_export_users(message: types.Message) -> None:
        _, admin_flag = _sync_user(message.from_user, message.chat.id)
        if not admin_flag:
            bot_instance.send_message(message.chat.id, "⛔ Admin access only.")
            return

        csv_data = database.export_users_csv().encode("utf-8")
        buf = io.BytesIO(csv_data)
        buf.name = "aitadz_users.csv"
        bot_instance.send_document(
            message.chat.id,
            buf,
            visible_file_name="aitadz_users.csv",
            caption="📁 AITADZ Registered Users Export",
        )

    @bot_instance.message_handler(commands=["addcredits", "give"])
    def handle_add_credits(message: types.Message) -> None:
        admin_row, admin_flag = _sync_user(message.from_user, message.chat.id)
        if not admin_flag:
            bot_instance.send_message(message.chat.id, "⛔ Admin access only.")
            return

        parts = (message.text or "").split()
        if len(parts) < 3:
            bot_instance.send_message(
                message.chat.id,
                "Usage: <code>/addcredits &lt;user_id_or_@username&gt; &lt;amount&gt;</code>\n"
                "Example: <code>/addcredits 123456789 10</code>",
                parse_mode="HTML",
            )
            return

        target_raw = parts[1].strip()
        try:
            amount = int(parts[2].strip())
        except ValueError:
            bot_instance.send_message(message.chat.id, "❌ Amount must be an integer (e.g. 10 or -2).")
            return

        target_uid: Optional[int] = None
        if target_raw.startswith("@"):
            u = database.get_user_by_username(target_raw)
            if u:
                target_uid = int(u["user_id"])
        else:
            try:
                target_uid = int(target_raw)
            except ValueError:
                target_uid = None

        if target_uid is None:
            bot_instance.send_message(message.chat.id, "❌ User not found. Provide a valid numeric user_id or @username.")
            return

        new_balance = database.add_credits(
            target_uid,
            amount,
            reason="admin_grant",
            admin_id=int(admin_row["user_id"]),
        )
        bot_instance.send_message(
            message.chat.id,
            f"✅ Updated user <code>{target_uid}</code> by <b>{amount:+d}</b> credits.\n"
            f"New balance: <b>{new_balance}</b> credits.",
            parse_mode="HTML",
        )
        if amount > 0:
            try:
                bot_instance.send_message(
                    target_uid,
                    f"🎉 You received <b>+{amount}</b> AITADZ Lesson Plan credit(s)!\n"
                    f"Your new balance: <b>{new_balance}</b> credit(s).",
                    parse_mode="HTML",
                )
            except Exception:
                pass

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
            _start_generation(chat_id, default_topic, from_user=call.from_user)
            return

    @bot_instance.message_handler(
        func=lambda m: bool(m.text) and not m.text.startswith("/"),
        content_types=["text"],
    )
    def handle_topic_reply(message: types.Message) -> None:
        chat_id = message.chat.id
        _sync_user(message.from_user, chat_id)
        state = get_session_state(chat_id)
        if state.get("awaiting_topic"):
            topic_text = (message.text or "").strip()
            _start_generation(chat_id, topic_text, from_user=message.from_user)
        else:
            bot_instance.send_message(
                chat_id,
                "👋 Use /start or select your Grade Level below to generate a new lesson plan:",
                reply_markup=build_grade_keyboard(),
            )

    return bot_instance


bot = create_bot()
