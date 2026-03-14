"""
notifier.py — Telegram Bot alert delivery (free, no credit card required).
"""

import os
import requests


def send_whatsapp(message: str) -> bool:
    """
    Sends a Telegram message to the configured chat.
    Function kept as send_whatsapp for compatibility — actually sends via Telegram.
    Respects DRY_RUN env flag — prints message instead of sending when true.
    Returns True on success.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print(f"\n[DRY RUN - Telegram] {message}")
        return True

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

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
