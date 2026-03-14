"""
policy_checker.py — Fetches merchant refund policy using Tavily web search.
"""

import os
import re
from tavily import TavilyClient

# Hardcoded overrides for demo merchants — bypasses Tavily for deterministic results
POLICY_OVERRIDES = {
    # Unknown policy — raises POLICY_UNKNOWN alert
    "ShopKart": {"refundable": None, "policy_days": None, "policy_unknown": True, "policy_text": ""},
    # Non-refundable — raises NON_REFUNDABLE alert
    "Meesho": {"refundable": False, "policy_days": 0, "policy_text": "Ethnic and printed apparel items are non-returnable as per Meesho supplier policy."},
    # Standard refundable merchants — hardcoded to avoid Tavily returning false negatives
    "TATA CLiQ": {"refundable": True, "policy_days": 7, "policy_text": "TATA CLiQ offers a 7-day return policy on most products."},
    "Nykaa": {"refundable": True, "policy_days": 15, "policy_text": "Nykaa offers a 15-day return policy."},
    "Myntra": {"refundable": True, "policy_days": 15, "policy_text": "Myntra offers a 15-day return/exchange policy."},
    "Amazon India": {"refundable": True, "policy_days": 10, "policy_text": "Amazon India offers a 10-day return window for most products."},
    "Flipkart": {"refundable": True, "policy_days": 7, "policy_text": "Flipkart offers a 7-day return policy for most products."},
    "AJIO": {"refundable": True, "policy_days": 15, "policy_text": "AJIO offers a 15-day return policy on apparel."},
    "H&M": {"refundable": True, "policy_days": 30, "policy_text": "H&M offers a 30-day return policy."},
}


def fetch_refund_policy(merchant: str) -> dict:
    """
    Searches the web for the merchant's refund/return policy.

    Returns a dict with keys:
        - refundable (bool)
        - policy_days (int) — days for refund processing, default 7
        - policy_text (str) — raw snippet from search results

    Returns default values {'refundable': True, 'policy_days': 7, 'policy_text': ''}
    if search fails or no useful results are found.
    """
    if merchant in POLICY_OVERRIDES:
        return POLICY_OVERRIDES[merchant]

    default = {"refundable": True, "policy_days": 7, "policy_text": ""}

    try:
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        query = f"{merchant} India refund return policy days"
        results = client.search(query=query, max_results=3)

        combined_text = ""
        for result in results.get("results", []):
            combined_text += " " + result.get("content", "") + " " + result.get("snippet", "")

        combined_lower = combined_text.lower()

        # Determine refundability
        non_refundable_indicators = ["no return", "non-refundable", "no refund", "not refundable"]
        refundable = not any(phrase in combined_lower for phrase in non_refundable_indicators)

        # Extract policy_days — look for patterns like "7 days", "5-7 business days", "10 working days"
        policy_days = 7  # default
        day_patterns = [
            r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:business|working)?\s*days?",
            r"(\d+)\s*(?:business|working)?\s*days?",
        ]
        for pattern in day_patterns:
            match = re.search(pattern, combined_lower)
            if match:
                groups = match.groups()
                # If range like "5-7", take the higher number
                try:
                    nums = [int(g) for g in groups if g is not None]
                    if nums:
                        policy_days = max(nums)
                        break
                except ValueError:
                    pass

        # Grab a reasonable snippet for display
        policy_text = combined_text[:500].strip() if combined_text.strip() else ""

        return {
            "refundable": refundable,
            "policy_days": policy_days,
            "policy_text": policy_text,
        }

    except Exception as e:
        print(f"  [policy_checker] Error fetching policy for '{merchant}': {e}")
        return default


def fetch_support_email(merchant: str) -> str:
    """
    Returns the support email for a merchant.
    In this prototype, returns DEMO_EMAIL from environment.
    """
    return os.getenv("DEMO_EMAIL", "")
