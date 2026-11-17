"""
database.py
===========
Thread-safe SQLite persistence for AITADZ Teacher Assistant Bot:
  - Stores all Telegram user profiles (user_id, chat_id, username, first/last name, language)
  - Tracks per-user credit tokens & full credit transaction audit log
  - Logs every generated lesson plan (grade, sequence, section, session, topic)
  - Provides real-time usage statistics (/stats) and CSV user export (/export_users)
"""

from __future__ import annotations

import csv
import io
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from docx_builder import normalize_template_id


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_today_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class Database:
    """Thread-safe SQLite store for users, credit tokens, and lesson plan stats."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        default_credits: Optional[int] = None,
    ) -> None:
        self.db_path = (db_path or os.environ.get("DB_PATH") or "aitadz_bot.db").strip()
        if default_credits is not None:
            self.default_credits = int(default_credits)
        else:
            try:
                self.default_credits = int(os.environ.get("DEFAULT_USER_CREDITS", "5"))
            except ValueError:
                self.default_credits = 5

        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
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
                    preferred_template TEXT NOT NULL DEFAULT 'classic',
                    created_at TEXT NOT NULL,
                    last_active_at TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    grade TEXT NOT NULL,
                    sequence_id TEXT NOT NULL,
                    section_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    template_id TEXT NOT NULL DEFAULT 'classic',
                    credits_used INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    balance_after INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    admin_id INTEGER,
                    created_at TEXT NOT NULL
                );
                """
            )
            # Safe schema migrations for databases created before template selection.
            user_cols = {
                row["name"]
                for row in cur.execute("PRAGMA table_info(users);").fetchall()
            }
            if "preferred_template" not in user_cols:
                cur.execute(
                    "ALTER TABLE users ADD COLUMN preferred_template TEXT NOT NULL DEFAULT 'classic';"
                )
            gen_cols = {
                row["name"]
                for row in cur.execute("PRAGMA table_info(generations);").fetchall()
            }
            if "template_id" not in gen_cols:
                cur.execute(
                    "ALTER TABLE generations ADD COLUMN template_id TEXT NOT NULL DEFAULT 'classic';"
                )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -----------------------------------------------------------------------
    # USER MANAGEMENT
    # -----------------------------------------------------------------------

    def upsert_user(
        self,
        user_id: int,
        chat_id: Optional[int] = None,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        language_code: str = "",
        is_admin: bool = False,
    ) -> Dict[str, Any]:
        now = _utc_now_iso()
        resolved_chat = chat_id if chat_id is not None else user_id
        uname = (username or "").strip().lstrip("@")
        fname = (first_name or "").strip()
        lname = (last_name or "").strip()
        lang = (language_code or "").strip()

        with self._lock:
            cur = self._conn.cursor()
            existing = cur.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()

            if existing is None:
                cur.execute(
                    """
                    INSERT INTO users (
                        user_id, chat_id, username, first_name, last_name,
                        language_code, credits, total_generated, is_admin,
                        is_banned, created_at, last_active_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?)
                    """,
                    (
                        int(user_id),
                        int(resolved_chat),
                        uname,
                        fname,
                        lname,
                        lang,
                        self.default_credits,
                        1 if is_admin else 0,
                        now,
                        now,
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions (
                        user_id, delta, balance_after, reason, admin_id, created_at
                    ) VALUES (?, ?, ?, ?, NULL, ?)
                    """,
                    (int(user_id), self.default_credits, self.default_credits, "welcome_bonus", now),
                )
            else:
                new_admin = 1 if (is_admin or existing["is_admin"]) else 0
                cur.execute(
                    """
                    UPDATE users
                    SET chat_id = ?,
                        username = ?,
                        first_name = ?,
                        last_name = ?,
                        language_code = ?,
                        is_admin = ?,
                        last_active_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        int(resolved_chat),
                        uname or existing["username"],
                        fname or existing["first_name"],
                        lname or existing["last_name"],
                        lang or existing["language_code"],
                        new_admin,
                        now,
                        int(user_id),
                    ),
                )

            self._conn.commit()
            row = cur.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()
            return dict(row)

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        clean = (username or "").strip().lstrip("@").lower()
        if not clean:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM users WHERE LOWER(username) = ?", (clean,)
            ).fetchone()
            return dict(row) if row else None

    def set_admin(self, user_id: int, is_admin: bool = True) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE users SET is_admin = ? WHERE user_id = ?",
                (1 if is_admin else 0, int(user_id)),
            )
            self._conn.commit()

    def get_preferred_template(self, user_id: int) -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT preferred_template FROM users WHERE user_id = ?",
                (int(user_id),),
            ).fetchone()
            return normalize_template_id(row["preferred_template"]) if row else "classic"

    def set_preferred_template(self, user_id: int, template_id: str) -> str:
        resolved = normalize_template_id(template_id)
        now = _utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "UPDATE users SET preferred_template = ?, last_active_at = ? WHERE user_id = ?",
                (resolved, now, int(user_id)),
            )
            if cur.rowcount == 0:
                cur.execute(
                    """
                    INSERT INTO users (
                        user_id, chat_id, credits, total_generated, is_admin,
                        is_banned, preferred_template, created_at, last_active_at
                    ) VALUES (?, ?, ?, 0, 0, 0, ?, ?, ?)
                    """,
                    (
                        int(user_id),
                        int(user_id),
                        self.default_credits,
                        resolved,
                        now,
                        now,
                    ),
                )
            self._conn.commit()
            return resolved

    # -----------------------------------------------------------------------
    # CREDIT TOKEN MANAGEMENT
    # -----------------------------------------------------------------------

    def get_credits(self, user_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT credits FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()
            return int(row["credits"]) if row else 0

    def consume_credit(
        self,
        user_id: int,
        amount: int = 1,
        reason: str = "lesson_plan_generation",
        bypass_for_admin: bool = True,
    ) -> Tuple[bool, int]:
        """
        Atomically check and deduct `amount` credits from `user_id`.
        Returns (allowed, remaining_credits).
        """
        now = _utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT credits, is_admin FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()
            if row is None:
                return False, 0

            current_credits = int(row["credits"])
            if bypass_for_admin and int(row["is_admin"]) == 1:
                return True, current_credits

            if current_credits < amount:
                return False, current_credits

            new_balance = current_credits - amount
            cur.execute(
                "UPDATE users SET credits = ?, last_active_at = ? WHERE user_id = ?",
                (new_balance, now, int(user_id)),
            )
            cur.execute(
                """
                INSERT INTO credit_transactions (
                    user_id, delta, balance_after, reason, admin_id, created_at
                ) VALUES (?, ?, ?, ?, NULL, ?)
                """,
                (int(user_id), -amount, new_balance, reason, now),
            )
            self._conn.commit()
            return True, new_balance

    def add_credits(
        self,
        user_id: int,
        amount: int,
        reason: str = "admin_grant",
        admin_id: Optional[int] = None,
    ) -> int:
        """Adjust a user's credit balance (clamped at >= 0) and record audit trail."""
        now = _utc_now_iso()
        with self._lock:
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT credits FROM users WHERE user_id = ?", (int(user_id),)
            ).fetchone()
            if row is None:
                # Create user record if admin grants credits before user ran /start
                new_balance = max(0, int(amount))
                cur.execute(
                    """
                    INSERT INTO users (
                        user_id, chat_id, username, first_name, last_name,
                        language_code, credits, total_generated, is_admin,
                        is_banned, created_at, last_active_at
                    ) VALUES (?, ?, '', '', '', '', ?, 0, 0, 0, ?, ?)
                    """,
                    (int(user_id), int(user_id), new_balance, now, now),
                )
            else:
                new_balance = max(0, int(row["credits"]) + int(amount))
                cur.execute(
                    "UPDATE users SET credits = ? WHERE user_id = ?",
                    (new_balance, int(user_id)),
                )

            cur.execute(
                """
                INSERT INTO credit_transactions (
                    user_id, delta, balance_after, reason, admin_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (int(user_id), int(amount), new_balance, reason, admin_id, now),
            )
            self._conn.commit()
            return new_balance

    # -----------------------------------------------------------------------
    # GENERATION LOGS & STATISTICS
    # -----------------------------------------------------------------------

    def record_generation(
        self,
        user_id: int,
        grade: str,
        sequence_id: str,
        section_id: str,
        session_id: str,
        topic: str,
        credits_used: int = 1,
        template_id: str = "classic",
    ) -> None:
        now = _utc_now_iso()
        resolved_tpl = normalize_template_id(template_id)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO generations (
                    user_id, grade, sequence_id, section_id, session_id, topic,
                    template_id, credits_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    grade,
                    sequence_id,
                    section_id,
                    session_id,
                    topic,
                    resolved_tpl,
                    int(credits_used),
                    now,
                ),
            )
            cur.execute(
                """
                UPDATE users
                SET total_generated = total_generated + 1,
                    last_active_at = ?
                WHERE user_id = ?
                """,
                (now, int(user_id)),
            )
            self._conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        today = _utc_today_prefix()
        with self._lock:
            cur = self._conn.cursor()
            total_users = cur.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_today = cur.execute(
                "SELECT COUNT(*) FROM users WHERE last_active_at LIKE ?", (f"{today}%",)
            ).fetchone()[0]
            total_credits_remaining = (
                cur.execute("SELECT COALESCE(SUM(credits), 0) FROM users").fetchone()[0]
            )
            total_generations = cur.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
            generations_today = cur.execute(
                "SELECT COUNT(*) FROM generations WHERE created_at LIKE ?", (f"{today}%",)
            ).fetchone()[0]

            grade_rows = cur.execute(
                "SELECT grade, COUNT(*) AS cnt FROM generations GROUP BY grade"
            ).fetchall()
            by_grade = {"3PS": 0, "4PS": 0, "5PS": 0}
            for r in grade_rows:
                by_grade[r["grade"]] = int(r["cnt"])

            tpl_rows = cur.execute(
                "SELECT COALESCE(template_id, 'classic') AS tpl, COUNT(*) AS cnt "
                "FROM generations GROUP BY COALESCE(template_id, 'classic')"
            ).fetchall()
            by_template = {"classic": 0, "modern": 0}
            for r in tpl_rows:
                key = normalize_template_id(r["tpl"])
                by_template[key] = by_template.get(key, 0) + int(r["cnt"])

            top_users = [
                dict(r)
                for r in cur.execute(
                    """
                    SELECT user_id, username, first_name, credits, total_generated, is_admin
                    FROM users
                    ORDER BY total_generated DESC, last_active_at DESC
                    LIMIT 5
                    """
                ).fetchall()
            ]

            recent_generations = [
                dict(r)
                for r in cur.execute(
                    """
                    SELECT g.grade, g.topic, g.created_at, u.username, u.first_name
                    FROM generations g
                    LEFT JOIN users u ON u.user_id = g.user_id
                    ORDER BY g.id DESC
                    LIMIT 5
                    """
                ).fetchall()
            ]

            return {
                "total_users": int(total_users),
                "active_today": int(active_today),
                "total_credits_remaining": int(total_credits_remaining),
                "total_generations": int(total_generations),
                "generations_today": int(generations_today),
                "by_grade": by_grade,
                "by_template": by_template,
                "top_users": top_users,
                "recent_generations": recent_generations,
            }

    def list_users(self, limit: int = 30, offset: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT user_id, username, first_name, last_name, credits,
                       total_generated, is_admin, created_at, last_active_at
                FROM users
                ORDER BY last_active_at DESC
                LIMIT ? OFFSET ?
                """,
                (int(limit), int(offset)),
            ).fetchall()
            return [dict(r) for r in rows]

    def export_users_csv(self) -> str:
        users = self.list_users(limit=10000, offset=0)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "user_id",
                "username",
                "first_name",
                "last_name",
                "credits",
                "total_generated",
                "is_admin",
                "created_at",
                "last_active_at",
            ]
        )
        for u in users:
            writer.writerow(
                [
                    u["user_id"],
                    u["username"],
                    u["first_name"],
                    u["last_name"],
                    u["credits"],
                    u["total_generated"],
                    u["is_admin"],
                    u["created_at"],
                    u["last_active_at"],
                ]
            )
        return buf.getvalue()
