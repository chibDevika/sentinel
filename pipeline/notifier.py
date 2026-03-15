"""
notifier.py — Telegram Bot alert delivery (free, no credit card required).
"""

import os
import requests


def _bot_token():
    return os.getenv("TELEGRAM_BOT_TOKEN")


def _chat_id():
    return os.getenv("TELEGRAM_CHAT_ID")


def send_whatsapp(message: str) -> bool:
    """
    Sends a plain Telegram message to the configured chat.
    Respects DRY_RUN env flag — prints message instead of sending when true.
    Returns True on success.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print(f"\n[DRY RUN - Telegram] {message}")
        return True

    bot_token = _bot_token()
    chat_id = _chat_id()

    if not bot_token or not chat_id:
        print("  [notifier] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  [notifier] Failed to send Telegram message: {e}")
        return False


def send_actionable(message: str, order_id: str, draft_type: str) -> bool:
    """
    Sends a Telegram message with an inline '✅ Approve & Send Email' button.
    Tapping the button triggers the email send via the polling loop in serve.py.
    Falls back to plain text in DRY_RUN mode.
    Returns True on success.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print(f"\n[DRY RUN - Telegram] {message}")
        print(f"  [DRY RUN] (would attach button: Approve & Send Email | {order_id}/{draft_type})")
        return True

    bot_token = _bot_token()
    chat_id = _chat_id()

    if not bot_token or not chat_id:
        print("  [notifier] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return False

    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "reply_markup": {
                "inline_keyboard": [[
                    {
                        "text": "✅ Approve & Send Email",
                        "callback_data": f"send|{order_id}|{draft_type}",
                    }
                ]]
            },
        }
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  [notifier] Failed to send actionable Telegram message: {e}")
        return False


def answer_callback(callback_query_id: str, text: str = "") -> None:
    """Acknowledges a Telegram callback query (removes the loading spinner)."""
    bot_token = _bot_token()
    if not bot_token:
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_query_id, "text": text}, timeout=10)
    except Exception:
        pass


def edit_message_text(chat_id: str, message_id: int, new_text: str) -> None:
    """Replaces the text of a sent message (used to show confirmation after send)."""
    bot_token = _bot_token()
    if not bot_token:
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        requests.post(
            url,
            json={"chat_id": chat_id, "message_id": message_id, "text": new_text},
            timeout=10,
        )
    except Exception:
        pass
