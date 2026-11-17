"""
app.py
======
Production Flask webhook & uptime keep-alive server for the AITADZ Telegram
Teacher Assistant Bot (aitadz.pro).

Endpoints:
  GET /health   -> 200 OK {"status": "ok", "service": "aitadz-lesson-bot"}
  GET /         -> 200 OK {"status": "ok", "service": "aitadz-lesson-bot"}
  POST /webhook -> Validates X-Telegram-Bot-Api-Secret-Token, immediately returns
                   200 OK, and processes Telegram updates asynchronously in a
                   background worker thread so Telegram never triggers retries.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Callable, Optional, Sequence

from dotenv import load_dotenv
from flask import Flask, jsonify, request
import telebot

load_dotenv()

from bot import bot as default_bot, is_bot_token_configured  # noqa: E402

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aitadz.app")

WEBHOOK_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.environ.get("AITADZ_WORKERS", os.environ.get("AITADZ_WEBHOOK_WORKERS", "4"))),
    thread_name_prefix="aitadz-webhook",
)


def resolve_webhook_base_url() -> str:
    """Resolve public webhook base URL from WEBHOOK_BASE_URL, WEBHOOK_URL, or RENDER_EXTERNAL_URL."""
    render_url = (os.environ.get("RENDER_EXTERNAL_URL") or "").strip().strip('"').strip("'").rstrip("/")
    manual_url = (
        (os.environ.get("WEBHOOK_BASE_URL") or os.environ.get("WEBHOOK_URL") or "")
        .strip()
        .strip('"')
        .strip("'")
        .rstrip("/")
    )
    if manual_url and not manual_url.startswith("<"):
        if manual_url.endswith("/webhook"):
            manual_url = manual_url[: -len("/webhook")]
        return manual_url
    return render_url


def resolve_webhook_secret(bot_instance: telebot.TeleBot = default_bot) -> str:
    """Resolve webhook secret from env, or derive a deterministic token-based secret."""
    explicit = (
        (os.environ.get("TELEGRAM_WEBHOOK_SECRET") or os.environ.get("WEBHOOK_SECRET") or "")
        .strip()
        .strip('"')
        .strip("'")
    )
    if explicit:
        return explicit
    token = getattr(bot_instance, "token", "") or ""
    if is_bot_token_configured() and token:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:48]
    return ""


def _process_update(bot_instance: telebot.TeleBot, update: telebot.types.Update) -> None:
    try:
        bot_instance.process_new_updates([update])
    except Exception as exc:
        logger.exception("Unhandled exception while processing Telegram update: %s", exc)


def create_app(
    bot_instance: Optional[telebot.TeleBot] = None,
    webhook_secret: Optional[str] = None,
    executor: Optional[concurrent.futures.ThreadPoolExecutor] = None,
) -> Flask:
    """Create and configure the Flask application for Render / Docker / UptimeRobot."""
    flask_app = Flask(__name__)
    is_default_app = bot_instance is None
    active_bot = bot_instance or default_bot
    worker_pool = executor or WEBHOOK_EXECUTOR

    def _expected_secret() -> str:
        if webhook_secret is not None:
            return webhook_secret
        return resolve_webhook_secret(active_bot)

    @flask_app.route("/", methods=["GET"])
    @flask_app.route("/health", methods=["GET"])
    def health_check():
        if (
            is_default_app
            and (os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))
            and not _webhook_registered
            and not _webhook_registering
            and (time.monotonic() - _last_webhook_attempt_ts) >= 60.0
        ):
            bootstrap_webhook()
        return jsonify({"status": "ok", "service": "aitadz-lesson-bot"}), 200

    @flask_app.route("/webhook", methods=["POST"])
    def telegram_webhook():
        expected = _expected_secret()
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not expected or not hmac.compare_digest(provided, expected):
            logger.warning("Rejected webhook request with invalid or missing secret token.")
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400

        update = telebot.types.Update.de_json(payload)
        if update is None:
            return jsonify({"ok": False, "error": "Invalid Telegram update"}), 400

        # Dispatch update processing in background thread and acknowledge immediately
        worker_pool.submit(_process_update, active_bot, update)
        return jsonify({"ok": True}), 200

    return flask_app


app = create_app()

DEFAULT_RETRY_DELAYS: tuple[float, ...] = (2.0, 5.0, 10.0, 20.0, 35.0, 60.0)

_bootstrap_lock = threading.Lock()
_webhook_registered = False
_webhook_registering = False
_last_webhook_attempt_ts = 0.0


def _is_non_retryable_telegram_error(exc: Exception) -> bool:
    """Return True for permanent Telegram 4xx client errors (400/401/404) where retrying is futile."""
    return getattr(exc, "error_code", None) in (400, 401, 404)


def register_webhook_with_retry(
    bot_instance: telebot.TeleBot = default_bot,
    base_url: Optional[str] = None,
    secret: Optional[str] = None,
    initial_delay: float = 2.0,
    retry_delays: Sequence[float] = DEFAULT_RETRY_DELAYS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> bool:
    """Register Telegram webhook with exponential-style backoff on transient 502/5xx/network errors."""
    resolved_base = (
        base_url if base_url is not None else resolve_webhook_base_url()
    ).strip().rstrip("/")
    resolved_secret = (
        secret if secret is not None else resolve_webhook_secret(bot_instance)
    ).strip()
    token_ok = True if bot_instance is not default_bot else is_bot_token_configured()

    if not (token_ok and resolved_base and resolved_secret):
        logger.info(
            "Skipping automatic webhook registration (token_ok=%s, base_url=%r).",
            token_ok,
            resolved_base,
        )
        return False

    if initial_delay > 0:
        sleep_fn(initial_delay)

    webhook_url = f"{resolved_base}/webhook"
    max_attempts = 1 + len(retry_delays)
    for attempt in range(max_attempts):
        try:
            bot_instance.set_webhook(
                url=webhook_url,
                secret_token=resolved_secret,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram webhook registered at %s", webhook_url)
            return True
        except Exception as exc:
            if _is_non_retryable_telegram_error(exc):
                logger.warning(
                    "Telegram webhook registration rejected (%s); not retrying.",
                    exc,
                )
                return False
            if attempt < len(retry_delays):
                delay = retry_delays[attempt]
                logger.warning(
                    "Automatic Telegram webhook registration attempt %s/%s failed (%s); retrying in %.1fs.",
                    attempt + 1,
                    max_attempts,
                    exc,
                    delay,
                )
                sleep_fn(delay)
            else:
                logger.warning(
                    "Automatic Telegram webhook registration failed after %s attempts: %s",
                    max_attempts,
                    exc,
                )
    return False


def bootstrap_webhook(force: bool = False) -> None:
    """Register Telegram webhook in a background thread when running under Gunicorn."""
    global _webhook_registered, _webhook_registering, _last_webhook_attempt_ts
    base_url = resolve_webhook_base_url()
    secret = resolve_webhook_secret(default_bot)
    if not (is_bot_token_configured() and base_url and secret):
        with _bootstrap_lock:
            _last_webhook_attempt_ts = time.monotonic()
        logger.info(
            "Skipping automatic webhook registration (token_ok=%s, base_url=%r).",
            is_bot_token_configured(),
            base_url,
        )
        return

    with _bootstrap_lock:
        if (_webhook_registered and not force) or _webhook_registering:
            return
        _webhook_registering = True
        _last_webhook_attempt_ts = time.monotonic()

    def _register() -> None:
        global _webhook_registered, _webhook_registering, _last_webhook_attempt_ts
        try:
            ok = register_webhook_with_retry(
                default_bot,
                base_url=base_url,
                secret=secret,
            )
            with _bootstrap_lock:
                _webhook_registered = bool(ok)
                _last_webhook_attempt_ts = time.monotonic()
        finally:
            with _bootstrap_lock:
                _webhook_registering = False

    threading.Thread(target=_register, name="aitadz-webhook-init", daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="AITADZ Primary ESL Telegram Bot Server")
    parser.add_argument(
        "--polling",
        action="store_true",
        help="Run in local long-polling mode instead of the Flask webhook server.",
    )
    args = parser.parse_args()

    if not is_bot_token_configured():
        logger.warning(
            "TELEGRAM_BOT_TOKEN is not configured. Set it in .env or environment variables."
        )

    if args.polling:
        logger.info("Starting AITADZ bot in long-polling mode...")
        try:
            default_bot.remove_webhook()
        except Exception as exc:
            logger.warning("Could not remove existing webhook before polling: %s", exc)
        default_bot.infinity_polling(skip_pending=True)
    else:
        bootstrap_webhook()
        port = int(os.environ.get("PORT", 3000))
        logger.info("Starting AITADZ Flask webhook server on 0.0.0.0:%s", port)
        app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
elif os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"):
    bootstrap_webhook()
