"""
decision_engine.py — Core evaluation loop. Evaluates order state and generates alerts/actions.
"""

import os
from datetime import datetime, date


def parse_date(date_str) -> date | None:
    """
    Parses a date string defensively, trying multiple formats.
    Returns a date object or None if parsing fails.
    """
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%b-%y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d %B %Y",
        "%B %d, %Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(str(date_str).strip(), fmt).date()
        except (ValueError, TypeError):
            continue

    return None


def evaluate_order(order: dict, state_manager, notifier, email_sender, reference_date: date = None) -> list:
    """
    Evaluates one order's current state and generates alerts/actions.
    reference_date: the date to use as "today" (email date during processing, real today for --check).
    Returns a list of alert messages generated.
    """
    today = reference_date if reference_date else date.today()
    alerts = []

    order_id = order["order_id"]
    state = order["state"]

    if state == "ORDER_CONFIRMED":
        # Policy check happens in main.py after upsert, not here
        pass

    elif state in ("DELIVERY_EXPECTED", "DELIVERY_DELAY_COMMUNICATED"):
        if order.get("expected_delivery_date"):
            exp = parse_date(order["expected_delivery_date"])
            if exp and today > exp:
                if order.get("has_delay_communication"):
                    # Vendor already communicated the delay — log silently, no alert/SMS
                    print(f"  ℹ️  Vendor-communicated delay for {order['merchant']} (new ETA: {order.get('updated_eta')}). Logging silently.")
                else:
                    # Agent sends complaint email
                    draft = email_sender.draft_complaint_email(order)
                    state_manager.store_draft(
                        order_id, "complaint", draft["subject"], draft["body"]
                    )
                    auto_send = os.getenv("AUTO_SEND_EMAILS", "false").lower() == "true"
                    if auto_send:
                        email_sender.send_email(draft["subject"], draft["body"])
                        msg = (
                            f"[RefundTracker] No delivery from {order['merchant']} "
                            f"(overdue {(today - exp).days}d). Complaint email sent."
                        )
                    else:
                        msg = (
                            f"[RefundTracker] No delivery from {order['merchant']} "
                            f"(overdue {(today - exp).days}d). Approve complaint email in dashboard."
                        )
                    notifier.send_whatsapp(msg)
                    state_manager.add_alert(order_id, "DELIVERY_OVERDUE", msg)
                    alerts.append(msg)

    elif state == "RETURN_PICKUP_PENDING":
        if order.get("expected_pickup_date"):
            exp = parse_date(order["expected_pickup_date"])
            if exp and today > exp:
                draft = email_sender.draft_pickup_followup_email(order)
                state_manager.store_draft(
                    order_id, "pickup_followup", draft["subject"], draft["body"]
                )
                auto_send = os.getenv("AUTO_SEND_EMAILS", "false").lower() == "true"
                if auto_send:
                    email_sender.send_email(draft["subject"], draft["body"])
                    msg = (
                        f"[RefundTracker] Return pickup overdue for {order['product']} "
                        f"({order['merchant']}). Follow-up email sent."
                    )
                else:
                    msg = (
                        f"[RefundTracker] Return pickup overdue for {order['product']} "
                        f"({order['merchant']}). Approve follow-up in dashboard."
                    )
                notifier.send_whatsapp(msg)
                state_manager.add_alert(order_id, "PICKUP_OVERDUE", msg)
                alerts.append(msg)

    elif state == "REFUND_PENDING":
        if order.get("expected_refund_date"):
            exp = parse_date(order["expected_refund_date"])
            if exp and today > exp:
                draft = email_sender.draft_escalation_email(order)
                state_manager.store_draft(
                    order_id, "escalation", draft["subject"], draft["body"]
                )
                auto_send = os.getenv("AUTO_SEND_EMAILS", "false").lower() == "true"
                if auto_send:
                    email_sender.send_email(draft["subject"], draft["body"])
                    msg = (
                        f"[RefundTracker] Refund of ₹{order['amount']} from {order['merchant']} "
                        f"overdue. Escalation email sent."
                    )
                else:
                    msg = (
                        f"[RefundTracker] Refund of ₹{order['amount']} from {order['merchant']} "
                        f"overdue. Approve escalation in dashboard."
                    )
                notifier.send_whatsapp(msg)
                state_manager.add_alert(order_id, "REFUND_OVERDUE", msg)
                alerts.append(msg)

    elif state == "REFUND_CLAIMED":
        if order.get("refund_claim_date"):
            claim_date = parse_date(order["refund_claim_date"])
            if claim_date:
                days_since = (today - claim_date).days
                if days_since > 5 and not order.get("bank_credit_date"):
                    msg = (
                        f"[RefundTracker] Vendor claims ₹{order['amount']} refund processed "
                        f"({order['merchant']}) but no bank credit after {days_since} days. Verify."
                    )
                    notifier.send_whatsapp(msg)
                    state_manager.add_alert(order_id, "REFUND_NO_BANK_CREDIT", msg)
                    alerts.append(msg)

    elif state == "REFUND_REJECTED":
        msg = (
            f"[RefundTracker] Refund rejected by {order['merchant']}: "
            f"{order['rejection_reason']}. Manual review needed."
        )
        notifier.send_whatsapp(msg)
        state_manager.add_alert(order_id, "REFUND_REJECTED", msg)
        alerts.append(msg)

    elif state == "AMOUNT_MISMATCH":
        expected = order.get("expected_refund_amount") or order.get("amount") or 0
        received = order.get("bank_credit_amount") or 0
        shortfall = expected - received
        msg = (
            f"[RefundTracker] Amount mismatch from {order['merchant']}. "
            f"Expected ₹{expected} but got ₹{received}. Shortfall: ₹{shortfall:.2f}."
        )
        notifier.send_whatsapp(msg)
        state_manager.add_alert(order_id, "AMOUNT_MISMATCH", msg)
        alerts.append(msg)

    elif state == "NON_REFUNDABLE":
        msg = (
            f"[RefundTracker] {order['merchant']} order for {order['product']} is non-refundable. "
            f"Consider cancelling before it ships."
        )
        notifier.send_whatsapp(msg)
        state_manager.add_alert(order_id, "NON_REFUNDABLE", msg)
        alerts.append(msg)

    return alerts
