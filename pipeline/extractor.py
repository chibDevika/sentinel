"""
extractor.py — Uses Gemini to extract structured fields from order-related emails.
"""

import os
import json
from google import genai

EXTRACT_PROMPT = """You are an order data extractor for an Indian e-commerce order tracking system.

Given the following email of type "{email_type}", extract relevant fields as JSON.

Extract only fields that are clearly present. Do not guess.

Possible fields:
- order_id (string — look for order numbers, order IDs, # followed by digits/alphanumeric)
- merchant (string — the company/brand name sending the email)
- product (string — main product name, exclude free gifts)
- amount (number — paid amount in INR, numeric only, no ₹ symbol)
- order_date (string — ISO format YYYY-MM-DD if possible)
- expected_delivery_date (string — ISO format)
- actual_delivery_date (string — ISO format, only if email confirms delivery happened)
- expected_pickup_date (string — ISO format, only if return pickup is scheduled)
- actual_pickup_date (string — ISO format, only if pickup is confirmed as done)
- expected_refund_date (string — ISO format)
- refund_amount (number — numeric only)
- bank_credit_amount (number — numeric only)
- refund_reference (string — UTR, UPI ref, transaction reference)
- rejection_reason (string)
- delay_reason (string)
- new_eta (string — ISO format)
- policy_days (integer — number of days for refund processing mentioned)

Return only valid JSON. No explanation. No markdown code blocks.

Email type: {email_type}
Email:
{email_content}"""


def extract_fields(email: dict, email_type: str) -> dict:
    """
    Extracts structured fields from an email using Gemini.
    Returns a dict of extracted fields. All fields are optional.
    Returns {} on any error.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    email_content = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
    prompt = EXTRACT_PROMPT.format(
        email_type=email_type,
        email_content=email_content,
    )

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        raw = response.text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            lines = raw.splitlines()
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        extracted = json.loads(raw)

        if not isinstance(extracted, dict):
            print(f"  [extractor] Expected dict, got {type(extracted)}. Returning {{}}.")
            return {}

        return extracted

    except json.JSONDecodeError as e:
        print(f"  [extractor] JSON parse error: {e}. Raw response: {raw[:300]}")
        return {}
    except Exception as e:
        print(f"  [extractor] Error calling Gemini: {e}")
        return {}
