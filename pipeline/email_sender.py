"""
email_sender.py — Gmail SMTP email sending + Gemini-powered email drafting.
"""

import os
import smtplib
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google import genai


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def send_email(subject: str, body: str) -> bool:
    """
    Sends an email via Gmail SMTP to the DEMO_EMAIL address.
    Respects DRY_RUN env flag — prints preview instead of sending when true.
    Returns True on success.
    """
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    if dry_run:
        print(f"\n[DRY RUN] Would send email:")
        print(f"  To: {os.getenv('DEMO_EMAIL')}")
        print(f"  Subject: {subject}")
        print(f"  Body preview: {body[:200]}...")
        return True

    # Actual SMTP send
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("DEMO_EMAIL")

    if not gmail_user or not gmail_password or not recipient:
        print("  [email_sender] Missing Gmail credentials or DEMO_EMAIL in env.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = recipient
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, recipient, msg.as_string())

        print(f"  ✅ Email sent to {recipient}: {subject}")
        return True

    except Exception as e:
        print(f"  [email_sender] Failed to send email: {e}")
        return False


# ---------------------------------------------------------------------------
# Drafting helpers
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str) -> str:
    """Calls Gemini and returns the text response."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        return response.text.strip()
    except Exception as e:
        print(f"  [email_sender] Gemini error: {e}")
        return ""


def draft_escalation_email(order: dict) -> dict:
    """
    Uses Gemini to draft a refund escalation email.
    Returns {'subject': ..., 'body': ...}.
    """
    today = date.today().isoformat()
    pickup_date = order.get("actual_pickup_date", "N/A")
    expected_refund_date = order.get("expected_refund_date", "N/A")

    days_overdue = "unknown"
    if expected_refund_date and expected_refund_date != "N/A":
        try:
            from datetime import datetime
            exp = datetime.strptime(expected_refund_date, "%Y-%m-%d").date()
            days_overdue = str((date.today() - exp).days)
        except Exception:
            pass

    prompt = f"""Draft a firm but polite refund escalation email.
Merchant: {order.get('merchant', 'N/A')}, Order ID: {order.get('order_id', 'N/A')}, Product: {order.get('product', 'N/A')}
Amount: ₹{order.get('amount', 'N/A')}, Return pickup date: {pickup_date}
Expected refund by: {expected_refund_date}, Today: {today}, Days overdue: {days_overdue}
Write a concise email requesting immediate refund processing. Firm, professional, not aggressive.
Sign the email as "Devika Chib".
Return only the email body text (no subject line in body)."""

    body = _call_gemini(prompt)
    subject = f"Refund Request – Order {order.get('order_id', 'N/A')} – {order.get('merchant', 'N/A')}"

    return {"subject": subject, "body": body}


def draft_complaint_email(order: dict) -> dict:
    """
    Uses Gemini to draft a delivery complaint email.
    Returns {'subject': ..., 'body': ...}.
    """
    today = date.today().isoformat()
    expected_delivery_date = order.get("expected_delivery_date", "N/A")

    days_overdue = "unknown"
    if expected_delivery_date and expected_delivery_date != "N/A":
        try:
            from datetime import datetime
            exp = datetime.strptime(expected_delivery_date, "%Y-%m-%d").date()
            days_overdue = str((date.today() - exp).days)
        except Exception:
            pass

    prompt = f"""Draft a firm but polite delivery complaint email.
Merchant: {order.get('merchant', 'N/A')}, Order ID: {order.get('order_id', 'N/A')}, Product: {order.get('product', 'N/A')}
Amount: ₹{order.get('amount', 'N/A')}, Expected delivery: {expected_delivery_date}, Today: {today}, Days overdue: {days_overdue}
Request immediate update on delivery status and escalation if needed.
Sign the email as "Devika Chib".
Return only the email body text."""

    body = _call_gemini(prompt)
    subject = f"Delivery Issue – Order {order.get('order_id', 'N/A')} – {order.get('merchant', 'N/A')}"

    return {"subject": subject, "body": body}


def draft_pickup_followup_email(order: dict) -> dict:
    """
    Uses Gemini to draft a return pickup follow-up email.
    Returns {'subject': ..., 'body': ...}.
    """
    today = date.today().isoformat()
    expected_pickup_date = order.get("expected_pickup_date", "N/A")

    days_overdue = "unknown"
    if expected_pickup_date and expected_pickup_date != "N/A":
        try:
            from datetime import datetime
            exp = datetime.strptime(expected_pickup_date, "%Y-%m-%d").date()
            days_overdue = str((date.today() - exp).days)
        except Exception:
            pass

    prompt = f"""Draft a polite return pickup follow-up email.
Merchant: {order.get('merchant', 'N/A')}, Order ID: {order.get('order_id', 'N/A')}, Product: {order.get('product', 'N/A')}
Amount: ₹{order.get('amount', 'N/A')}, Pickup was promised by: {expected_pickup_date}, Today: {today}, Days overdue: {days_overdue}
Request immediate scheduling of return pickup.
Sign the email as "Devika Chib".
Return only the email body text."""

    body = _call_gemini(prompt)
    subject = f"Return Pickup Follow-Up – Order {order.get('order_id', 'N/A')} – {order.get('merchant', 'N/A')}"

    return {"subject": subject, "body": body}
