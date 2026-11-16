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
from typing import Optional

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
    active_bot = bot_instance or default_bot
    worker_pool = executor or WEBHOOK_EXECUTOR

    def _expected_secret() -> str:
        if webhook_secret is not None:
            return webhook_secret
        return resolve_webhook_secret(active_bot)

    @flask_app.route("/", methods=["GET"])
    @flask_app.route("/health", methods=["GET"])
    def health_check():
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

_bootstrap_lock = threading.Lock()
_bootstrapped = False


def bootstrap_webhook() -> None:
    """Register Telegram webhook in a background thread when running under Gunicorn."""
    global _bootstrapped
    with _bootstrap_lock:
        if _bootstrapped:
            return
        _bootstrapped = True

    base_url = resolve_webhook_base_url()
    secret = resolve_webhook_secret(default_bot)
    if not (is_bot_token_configured() and base_url and secret):
        logger.info(
            "Skipping automatic webhook registration (token_ok=%s, base_url=%r).",
            is_bot_token_configured(),
            base_url,
        )
        return

    def _register() -> None:
        time.sleep(0.5)
        webhook_url = f"{base_url}/webhook"
        try:
            default_bot.set_webhook(
                url=webhook_url,
                secret_token=secret,
                allowed_updates=["message", "callback_query"],
            )
            logger.info("Telegram webhook registered at %s", webhook_url)
        except Exception as exc:
            logger.warning("Automatic Telegram webhook registration failed: %s", exc)

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
