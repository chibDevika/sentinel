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

CLASSIFY_PROMPT = """You are an email classifier for an Indian e-commerce order tracking system.

Classify the following email into exactly one of these types:
order_confirmed, order_shipped, delivery_confirmed, delivery_delayed,
return_requested_confirmation, return_pickup_confirmed, refund_initiated,
refund_rejected, ambiguous_vendor_update, bank_credit_alert

Definitions and disambiguation rules:

order_confirmed — merchant acknowledges a new purchase; includes order ID, amount, expected delivery.

order_shipped — item has been dispatched; includes tracking number or courier details.

delivery_confirmed — item has been delivered to the customer's address.

delivery_delayed — merchant proactively communicates that delivery will be late; includes a new ETA.

return_requested_confirmation — merchant confirms they have RECEIVED and ACCEPTED a return request.
  The pickup has NOT happened yet. Key signals: "will pick up", "pickup scheduled for", "our partner
  will collect", future-tense pickup language. The item is still with the customer.

return_pickup_confirmed — the physical pickup HAS already happened. Key signals: "picked up
  successfully", "item collected", "our partner has collected", past-tense pickup language.
  Often mentions refund will be processed after QC.

refund_initiated — merchant says the refund has been PROCESSED on their end (not yet in bank).
  Signals: "refund initiated", "refund processed", "amount will be credited in X days".

refund_rejected — merchant denies the refund, often citing QC failure or policy.

bank_credit_alert — a bank or UPI app notification confirming money was credited to the customer's
  account. Sender is a bank (HDFC, ICICI, Kotak, SBI, Axis) or UPI app (PhonePe, GPay, Paytm).
  NOT a merchant refund email.

ambiguous_vendor_update — vague status update that does not clearly fit any of the above
  (e.g. "your request is under review", "being processed").

Critical distinctions:
- return_requested_confirmation vs return_pickup_confirmed: tense of pickup action is the key.
  "will pick up" = return_requested_confirmation. "has been picked up" = return_pickup_confirmed.
- refund_initiated vs bank_credit_alert: refund_initiated is from the merchant; bank_credit_alert
  is from a bank or payment app confirming actual account credit.
- delivery_delayed vs ambiguous_vendor_update: delivery_delayed must include a new ETA date.

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
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"thinking_config": {"thinking_budget": 0}},
        )
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
