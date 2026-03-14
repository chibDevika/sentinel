#!/usr/bin/env python3
"""
main.py — Process emails from mock_emails.json by scenario.

Usage:
    python main.py --scenario refund_overdue   # process next email in that scenario
    python main.py --all                       # process all remaining emails across all scenarios
    python main.py --reset                     # reset all pointers and database
    python main.py --check                     # run overdue check on all active orders
"""

import os
import sys
import json
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

load_dotenv()

from pipeline import state_manager, classifier, extractor, policy_checker, decision_engine, email_sender, notifier

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOCK_EMAILS_PATH = os.path.join(BASE_DIR, "data", "mock_emails.json")
POINTER_PATH = os.path.join(BASE_DIR, "data", "pointer.json")

EMAIL_TYPE_TO_STATE = {
    "order_confirmed": "ORDER_CONFIRMED",
    "order_shipped": "ORDER_SHIPPED",
    "delivery_confirmed": "DELIVERED",
    "delivery_delayed": "DELIVERY_DELAY_COMMUNICATED",
    "return_requested_confirmation": "RETURN_REQUESTED",
    "return_pickup_confirmed": "RETURN_PICKED_UP",
    "refund_initiated": "REFUND_CLAIMED",
    "refund_rejected": "REFUND_REJECTED",
    "ambiguous_vendor_update": "AMBIGUOUS_VENDOR_RESPONSE",
    "bank_credit_alert": None,
}


# ---------------------------------------------------------------------------
# Pointer helpers (per-scenario)
# ---------------------------------------------------------------------------

def load_pointer() -> dict:
    if os.path.exists(POINTER_PATH):
        with open(POINTER_PATH, "r") as f:
            return json.load(f)
    return {}


def save_pointer(pointer: dict):
    os.makedirs(os.path.dirname(POINTER_PATH), exist_ok=True)
    with open(POINTER_PATH, "w") as f:
        json.dump(pointer, f, indent=2)


def reset_pointer():
    save_pointer({})
    db_path = os.path.join(BASE_DIR, "data", "orders.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print("🗑  Database cleared.")
    empty_state = {
        "lastUpdated": None,
        "summary": {"total_orders": 0, "active_alerts": 0, "resolved": 0, "pending_refund_value": 0},
        "orders": [], "alerts": [],
        "analytics": {"return_rate_by_merchant": [], "flagged_merchants": []}
    }
    state_path = os.path.join(BASE_DIR, "data", "dashboard_state.json")
    with open(state_path, "w") as f:
        json.dump(empty_state, f, indent=2)
    print("✅ Pipeline reset. Pointer, database and dashboard state cleared.")


def get_scenario_emails(emails: list, scenario: str) -> list:
    """Returns list of emails belonging to a scenario, preserving original list order."""
    return [e for e in emails if e.get("scenario") == scenario]


def get_ordered_scenarios(emails: list) -> list:
    """Returns unique scenarios in the order they first appear in mock_emails.json."""
    seen = []
    for e in emails:
        s = e.get("scenario")
        if s and s not in seen:
            seen.append(s)
    return seen


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_overdue_check(email: dict, index: int, total: int):
    email_date = email.get("date", "")
    ref_date = None
    if email_date:
        try:
            ref_date = datetime.strptime(email_date[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    if not ref_date:
        ref_date = date.today()

    print(f"\n{'='*70}")
    print(f"🔍 Email {index+1}/{total}: [overdue_check] Running overdue check — reference date: {ref_date}")
    print(f"{'='*70}")

    active_orders = state_manager.get_all_active_orders()
    print(f"  Found {len(active_orders)} active order(s).")

    for order in active_orders:
        order_id = order["order_id"]
        print(f"  Checking {order_id} (state: {order['state']})...")
        existing_alert_types = {
            a["alert_type"] for a in state_manager.get_active_alerts()
            if a["order_id"] == order_id
        }
        alerts = decision_engine.evaluate_order(
            order, state_manager, notifier, email_sender, reference_date=ref_date
        )
        if alerts:
            for alert in alerts:
                print(f"    🚨 {alert}")
            new_alert_types = {
                a["alert_type"] for a in state_manager.get_active_alerts()
                if a["order_id"] == order_id
            } - existing_alert_types
            if new_alert_types:
                state_manager.log_check_event(order_id, "overdue check", email_date)
        else:
            print(f"    ✅ No alerts.")

    state_manager.log_email(
        email_id=email.get("email_id", f"check_{index}"),
        email_date=email_date,
        from_addr=email.get("from", "system@refundtracker"),
        subject=email.get("subject", "RefundTracker: Daily Overdue Check"),
        order_id="",
        classified_type="overdue_check",
    )
    print(f"\n✅ Overdue check complete (simulation date → {ref_date}).")


def process_email(email: dict, index: int, total: int):
    """Processes a single email through the full pipeline."""

    if email.get("email_type") == "overdue_check":
        process_overdue_check(email, index, total)
        return

    print(f"\n{'='*70}")
    print(f"📧 Processing email {index+1}/{total}: [{email.get('email_type', 'unknown')}] {email.get('subject', '')}")
    print(f"{'='*70}")

    email_date = email.get("date", "")

    email_type = classifier.classify_email(email)
    print(f"🔍 Classified as: {email_type}")

    fields = extractor.extract_fields(email, email_type)
    print(f"📋 Extracted fields: {json.dumps(fields, indent=2, default=str)}")

    order_id = fields.get("order_id") or email.get("order_id")
    if not order_id:
        print("  ⚠️  No order_id extracted. Skipping this email.")
        return

    existing_order = state_manager.get_order(order_id)
    new_state = EMAIL_TYPE_TO_STATE.get(email_type)

    upsert_fields = {"order_id": order_id}

    field_map = {
        "merchant": "merchant",
        "product": "product",
        "amount": "amount",
        "order_date": "order_date",
        "expected_delivery_date": "expected_delivery_date",
        "actual_delivery_date": "actual_delivery_date",
        "expected_pickup_date": "expected_pickup_date",
        "actual_pickup_date": "actual_pickup_date",
        "expected_refund_date": "expected_refund_date",
        "refund_amount": "expected_refund_amount",
        "bank_credit_amount": "bank_credit_amount",
        "refund_reference": "refund_reference",
        "rejection_reason": "rejection_reason",
        "new_eta": "updated_eta",
        "policy_days": "policy_days",
    }
    for src_key, dst_key in field_map.items():
        if src_key in fields:
            upsert_fields[dst_key] = fields[src_key]

    if email_type == "order_shipped":
        if new_state:
            upsert_fields["state"] = new_state
            state_manager.upsert_order(upsert_fields, event_date=email_date)
            print(f"🔄 State set to: {new_state}")
            state_manager.transition_state(order_id, "DELIVERY_EXPECTED", "shipment email processed", event_date=email_date)
            upsert_fields["state"] = "DELIVERY_EXPECTED"

    elif email_type == "return_requested_confirmation":
        if new_state:
            upsert_fields["state"] = new_state
            upsert_fields["return_requested_date"] = email_date[:10] if email_date else date.today().isoformat()
            state_manager.upsert_order(upsert_fields, event_date=email_date)
            print(f"🔄 State set to: {new_state}")
            state_manager.transition_state(order_id, "RETURN_PICKUP_PENDING", "return confirmation email processed", event_date=email_date)
            upsert_fields["state"] = "RETURN_PICKUP_PENDING"

    elif email_type == "return_pickup_confirmed":
        if new_state:
            upsert_fields["state"] = new_state
            actual_pickup = fields.get("actual_pickup_date") or email_date[:10] if email_date else date.today().isoformat()
            upsert_fields["actual_pickup_date"] = actual_pickup
            state_manager.upsert_order(upsert_fields, event_date=email_date)
            print(f"🔄 State set to: {new_state}")
            policy_days_val = (
                fields.get("policy_days")
                or (existing_order.get("policy_days") if existing_order else None)
                or 7
            )
            try:
                from datetime import datetime as dt
                pickup_date_obj = dt.strptime(actual_pickup, "%Y-%m-%d").date()
                expected_refund = (pickup_date_obj + timedelta(days=int(policy_days_val))).isoformat()
            except Exception:
                expected_refund = None

            state_manager.transition_state(order_id, "REFUND_PENDING", "pickup confirmed email processed", event_date=email_date)
            upsert_fields["state"] = "REFUND_PENDING"
            if expected_refund:
                state_manager.upsert_order({"order_id": order_id, "expected_refund_date": expected_refund}, event_date=email_date)
                print(f"  📅 Expected refund date set to: {expected_refund}")

    elif email_type == "delivery_delayed":
        upsert_fields["has_delay_communication"] = 1
        if "new_eta" in fields:
            upsert_fields["updated_eta"] = fields["new_eta"]
        if new_state:
            upsert_fields["state"] = new_state

    elif email_type == "bank_credit_alert":
        bank_amount = fields.get("bank_credit_amount")
        upsert_fields["bank_credit_date"] = email_date[:10] if email_date else date.today().isoformat()
        if bank_amount is not None:
            upsert_fields["bank_credit_amount"] = bank_amount

        expected_amount = None
        if existing_order:
            expected_amount = (
                existing_order.get("expected_refund_amount")
                or existing_order.get("amount")
            )
        if not expected_amount:
            expected_amount = fields.get("refund_amount") or fields.get("amount")

        if bank_amount is not None and expected_amount is not None:
            if abs(float(bank_amount) - float(expected_amount)) <= 1.0:
                upsert_fields["state"] = "RESOLVED"
                print("🔄 Bank credit matches expected amount → RESOLVED")
            else:
                upsert_fields["state"] = "AMOUNT_MISMATCH"
                upsert_fields["expected_refund_amount"] = expected_amount
                print(f"🚨 Amount mismatch: expected ₹{expected_amount}, got ₹{bank_amount} → AMOUNT_MISMATCH")
        else:
            upsert_fields["state"] = "RESOLVED"
            print("🔄 Bank credit received → RESOLVED (amount unverified)")

    elif email_type == "refund_initiated":
        upsert_fields["refund_claim_date"] = email_date[:10] if email_date else date.today().isoformat()
        if new_state:
            upsert_fields["state"] = new_state

    else:
        if new_state:
            upsert_fields["state"] = new_state

    updated_order = state_manager.upsert_order(upsert_fields, event_date=email_date)
    print(f"🔄 Order state saved: {updated_order.get('state') if updated_order else 'unknown'}")

    if email_type == "order_confirmed":
        merchant = updated_order.get("merchant") or fields.get("merchant")
        if merchant:
            print(f"  🔍 Fetching refund policy for {merchant}...")
            policy = policy_checker.fetch_refund_policy(merchant)

            if policy.get("policy_unknown"):
                msg = (
                    f"[RefundTracker] Could not find refund policy for {merchant}. "
                    f"Verify return eligibility before purchasing."
                )
                notifier.send_whatsapp(msg)
                state_manager.add_alert(order_id, "POLICY_UNKNOWN", msg)
                print(f"  ⚠️  Policy unknown for {merchant}. Alert raised.")
            else:
                policy_update = {
                    "order_id": order_id,
                    "policy_days": policy["policy_days"],
                    "policy_refundable": 1 if policy["refundable"] else 0,
                }
                state_manager.upsert_order(policy_update, event_date=email_date)
                print(f"  📋 Policy: refundable={policy['refundable']}, days={policy['policy_days']}")

                if not policy["refundable"]:
                    state_manager.transition_state(order_id, "NON_REFUNDABLE", "policy check: non-refundable", event_date=email_date)
                    updated_order = state_manager.get_order(order_id)

    if updated_order:
        ref_date = None
        if email_date:
            try:
                ref_date = datetime.strptime(email_date[:10], "%Y-%m-%d").date()
            except Exception:
                pass
        alerts = decision_engine.evaluate_order(
            updated_order,
            state_manager,
            notifier,
            email_sender,
            reference_date=ref_date,
        )
        if alerts:
            for alert in alerts:
                print(f"🚨 Alert: {alert}")
        else:
            print("✅ No alerts triggered.")

    order_id_for_log = email.get("order_id", "")
    state_manager.log_email(
        email_id=email.get("email_id", f"email_{index}"),
        email_date=email.get("date", ""),
        from_addr=email.get("from", ""),
        subject=email.get("subject", ""),
        order_id=order_id_for_log,
        classified_type=email_type,
    )

    print(f"\n✅ Email {index+1} processed successfully.")


def run_overdue_check():
    """Runs the decision engine on all active orders (no email processing)."""
    print("\n🔍 Running overdue check on all active orders...")
    active_orders = state_manager.get_all_active_orders()
    print(f"  Found {len(active_orders)} active order(s).")

    for order in active_orders:
        print(f"\n  Checking order {order['order_id']} (state: {order['state']})...")
        alerts = decision_engine.evaluate_order(
            order,
            state_manager,
            notifier,
            email_sender,
        )
        for alert in alerts:
            print(f"  🚨 {alert}")

    print("\n✅ Overdue check complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    state_manager.init_db()

    args = sys.argv[1:]

    if "--reset" in args:
        reset_pointer()
        return

    if "--check" in args:
        run_overdue_check()
        state_manager.write_dashboard_state()
        return

    if not os.path.exists(MOCK_EMAILS_PATH):
        print(f"❌ mock_emails.json not found at {MOCK_EMAILS_PATH}")
        sys.exit(1)

    with open(MOCK_EMAILS_PATH, "r") as f:
        emails = json.load(f)

    pointer = load_pointer()

    if "--scenario" in args:
        scenario_idx = args.index("--scenario") + 1
        if scenario_idx >= len(args):
            print("❌ --scenario requires a scenario name argument.")
            sys.exit(1)
        scenario = args[scenario_idx]

        scenario_emails = get_scenario_emails(emails, scenario)
        if not scenario_emails:
            print(f"❌ No emails found for scenario '{scenario}'.")
            sys.exit(1)

        total = len(scenario_emails)
        current = pointer.get(scenario, 0)

        if current >= total:
            print(f"✅ All {total} email(s) for scenario '{scenario}' already processed.")
            return

        email = scenario_emails[current]
        process_email(email, current, total)
        pointer[scenario] = current + 1
        save_pointer(pointer)
        state_manager.write_dashboard_state()
        print(f"\n  📊 Scenario '{scenario}': {pointer[scenario]}/{total} emails processed.")

    elif "--all" in args:
        ordered_scenarios = get_ordered_scenarios(emails)
        total_processed = 0

        for scenario in ordered_scenarios:
            scenario_emails = get_scenario_emails(emails, scenario)
            current = pointer.get(scenario, 0)
            if current >= len(scenario_emails):
                continue
            for i in range(current, len(scenario_emails)):
                process_email(scenario_emails[i], i, len(scenario_emails))
                pointer[scenario] = i + 1
                save_pointer(pointer)
                total_processed += 1

        state_manager.write_dashboard_state()
        if total_processed == 0:
            print("✅ All emails already processed. Run with --reset to start over.")
        else:
            print(f"\n✅ {total_processed} remaining email(s) processed across all scenarios.")

    else:
        print("Usage: python main.py --scenario <name> | --all | --reset | --check")
        print("\nAvailable scenarios:")
        ordered_scenarios = get_ordered_scenarios(emails)
        for s in ordered_scenarios:
            s_emails = get_scenario_emails(emails, s)
            current = pointer.get(s, 0)
            print(f"  {s}: {current}/{len(s_emails)} processed")


if __name__ == "__main__":
    main()
