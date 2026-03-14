"""
classifier.py — Uses Gemini to classify incoming emails into known order event types.
"""

import os
from google import genai

VALID_TYPES = [
    "order_confirmed",
    "order_shipped",
    "delivery_confirmed",
    "delivery_delayed",
    "return_requested_confirmation",
    "return_pickup_confirmed",
    "refund_initiated",
    "refund_rejected",
    "ambiguous_vendor_update",
    "bank_credit_alert",
]

CLASSIFY_PROMPT = """You are an email classifier for an order tracking system.

Classify the following email into exactly one of these types:
order_confirmed, order_shipped, delivery_confirmed, delivery_delayed,
return_requested_confirmation, return_pickup_confirmed, refund_initiated,
refund_rejected, ambiguous_vendor_update, bank_credit_alert

Rules:
- bank_credit_alert: only for bank/UPI credit notifications, not merchant refund emails
- refund_initiated: merchant says refund has been processed (not yet bank credit)
- ambiguous_vendor_update: vague status emails that don't fit other categories

Return only the classification label. Nothing else.

Email:
{email_content}"""


def classify_email(email: dict) -> str:
    """
    Classifies an email dict (with 'subject' and 'body' keys) into one of VALID_TYPES.
    Falls back to 'ambiguous_vendor_update' if the model response is not recognized.
    """
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    email_content = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
    prompt = CLASSIFY_PROMPT.format(email_content=email_content)

    try:
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        result = response.text.strip().lower()

        # Clean up any surrounding punctuation or whitespace
        result = result.strip(".,;:\"' \n\t")

        if result in VALID_TYPES:
            return result
        else:
            print(f"  [classifier] Unrecognized type '{result}', defaulting to ambiguous_vendor_update")
            return "ambiguous_vendor_update"

    except Exception as e:
        print(f"  [classifier] Error calling Gemini: {e}")
        return "ambiguous_vendor_update"
