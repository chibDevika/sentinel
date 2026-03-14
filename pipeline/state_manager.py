"""
state_manager.py — SQLite-backed order state machine for the order tracking pipeline.
Database file: data/orders.db
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "orders.db")

VALID_STATES = [
    "ORDER_CONFIRMED",
    "ORDER_SHIPPED",
    "DELIVERY_EXPECTED",
    "DELIVERED",
    "RETURN_REQUESTED",
    "RETURN_PICKUP_PENDING",
    "RETURN_PICKED_UP",
    "REFUND_PENDING",
    "REFUND_CLAIMED",
    "RESOLVED",
    "DELIVERY_DELAY_COMMUNICATED",
    "REFUND_REJECTED",
    "AMOUNT_MISMATCH",
    "AMBIGUOUS_VENDOR_RESPONSE",
    "NON_REFUNDABLE",
]

TERMINAL_STATES = ["RESOLVED", "REFUND_REJECTED", "NON_REFUNDABLE"]

VALID_TRANSITIONS = {
    None: ["ORDER_CONFIRMED"],
    "ORDER_CONFIRMED": ["ORDER_SHIPPED", "NON_REFUNDABLE"],
    "ORDER_SHIPPED": ["DELIVERY_EXPECTED", "DELIVERY_DELAY_COMMUNICATED", "DELIVERED"],
    "DELIVERY_EXPECTED": ["DELIVERED", "DELIVERY_DELAY_COMMUNICATED"],
    "DELIVERY_DELAY_COMMUNICATED": ["DELIVERED", "DELIVERY_EXPECTED"],
    "DELIVERED": ["RETURN_REQUESTED"],
    "RETURN_REQUESTED": ["RETURN_PICKUP_PENDING"],
    "RETURN_PICKUP_PENDING": ["RETURN_PICKED_UP"],
    "RETURN_PICKED_UP": ["REFUND_PENDING"],
    "REFUND_PENDING": ["REFUND_CLAIMED", "REFUND_REJECTED"],
    "REFUND_CLAIMED": ["RESOLVED", "AMOUNT_MISMATCH"],
    "RESOLVED": [],
    "REFUND_REJECTED": [],
    "AMOUNT_MISMATCH": [],
    "NON_REFUNDABLE": [],
    "AMBIGUOUS_VENDOR_RESPONSE": ["ORDER_SHIPPED", "DELIVERED", "REFUND_CLAIMED"],
}


def _get_connection():
    """Returns a SQLite connection with row_factory set."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Creates all tables if they do not exist."""
    with _get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                merchant TEXT,
                product TEXT,
                amount REAL,
                state TEXT,
                order_date TEXT,
                expected_delivery_date TEXT,
                actual_delivery_date TEXT,
                return_requested_date TEXT,
                expected_pickup_date TEXT,
                actual_pickup_date TEXT,
                expected_refund_date TEXT,
                refund_claim_date TEXT,
                bank_credit_date TEXT,
                bank_credit_amount REAL,
                expected_refund_amount REAL,
                refund_reference TEXT,
                has_delay_communication INTEGER DEFAULT 0,
                updated_eta TEXT,
                rejection_reason TEXT,
                policy_days INTEGER DEFAULT 7,
                policy_refundable INTEGER DEFAULT 1,
                auto_send_enabled INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                from_state TEXT,
                to_state TEXT,
                trigger TEXT,
                timestamp TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                alert_type TEXT,
                message TEXT,
                resolved INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                draft_type TEXT,
                subject TEXT,
                body TEXT,
                sent INTEGER DEFAULT 0,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id TEXT UNIQUE,
                email_date TEXT,
                from_addr TEXT,
                subject TEXT,
                order_id TEXT,
                classified_type TEXT,
                processed_at TEXT
            )
        """)

        conn.commit()


def get_order(order_id: str) -> dict | None:
    """Returns order as a dict or None if not found."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def upsert_order(fields: dict, event_date: str = None) -> dict:
    """
    Insert or update an order. Logs an event to order_events if state changed.
    event_date: the email's actual date string (used as event timestamp instead of now).
    Returns the updated order dict.
    """
    order_id = fields.get("order_id")
    if not order_id:
        raise ValueError("upsert_order requires 'order_id' in fields")

    now = datetime.utcnow().isoformat()
    event_ts = event_date if event_date else now
    existing = get_order(order_id)

    with _get_connection() as conn:
        cursor = conn.cursor()

        if existing is None:
            # Insert new order
            fields["created_at"] = now
            fields["updated_at"] = now
            columns = ", ".join(fields.keys())
            placeholders = ", ".join(["?" for _ in fields])
            cursor.execute(
                f"INSERT INTO orders ({columns}) VALUES ({placeholders})",
                list(fields.values()),
            )
            conn.commit()

            # Log creation event if state is present
            new_state = fields.get("state")
            if new_state:
                cursor.execute(
                    """
                    INSERT INTO order_events (order_id, from_state, to_state, trigger, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (order_id, None, new_state, "order created", event_ts),
                )
                conn.commit()
        else:
            # Update existing order — only set fields that are provided
            prev_state = existing.get("state")
            new_state = fields.get("state", prev_state)

            update_fields = {k: v for k, v in fields.items() if k != "order_id"}
            update_fields["updated_at"] = now

            set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
            cursor.execute(
                f"UPDATE orders SET {set_clause} WHERE order_id = ?",
                list(update_fields.values()) + [order_id],
            )
            conn.commit()

            # Log state change event
            if new_state and new_state != prev_state:
                trigger = fields.get("trigger", "state updated")
                cursor.execute(
                    """
                    INSERT INTO order_events (order_id, from_state, to_state, trigger, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (order_id, prev_state, new_state, trigger, event_ts),
                )
                conn.commit()

    return get_order(order_id)


def transition_state(order_id: str, new_state: str, trigger: str, event_date: str = None) -> bool:
    """
    Validates state transition and updates the order state.
    Logs event to order_events on success.
    event_date: the email's actual date string (used as event timestamp instead of now).
    Returns True on success, False if transition is invalid.
    """
    order = get_order(order_id)
    if order is None:
        print(f"  [state_manager] Order {order_id} not found for transition.")
        return False

    current_state = order.get("state")
    allowed = VALID_TRANSITIONS.get(current_state, [])

    if new_state not in allowed:
        print(
            f"  [state_manager] Invalid transition: {current_state} → {new_state} "
            f"(allowed: {allowed})"
        )
        return False

    now = datetime.utcnow().isoformat()
    event_ts = event_date if event_date else now

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET state = ?, updated_at = ? WHERE order_id = ?",
            (new_state, now, order_id),
        )
        cursor.execute(
            """
            INSERT INTO order_events (order_id, from_state, to_state, trigger, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, current_state, new_state, trigger, event_ts),
        )
        conn.commit()

    print(f"  🔄 State transition: {current_state} → {new_state} (trigger: {trigger})")
    return True


def get_all_active_orders() -> list[dict]:
    """Returns all orders not in terminal states."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ", ".join(["?" for _ in TERMINAL_STATES])
        cursor.execute(
            f"SELECT * FROM orders WHERE state NOT IN ({placeholders})",
            TERMINAL_STATES,
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_all_orders() -> list[dict]:
    """Returns all orders."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def add_alert(order_id: str, alert_type: str, message: str) -> bool:
    """
    Inserts alert if the same alert_type is not already active (unresolved) for this order.
    Returns True if inserted, False if duplicate.
    """
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM alerts
            WHERE order_id = ? AND alert_type = ? AND resolved = 0
            """,
            (order_id, alert_type),
        )
        existing = cursor.fetchone()
        if existing:
            return False

        now = datetime.utcnow().isoformat()
        cursor.execute(
            """
            INSERT INTO alerts (order_id, alert_type, message, resolved, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (order_id, alert_type, message, now),
        )
        conn.commit()
        return True


def get_active_alerts() -> list[dict]:
    """Returns all unresolved alerts."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM alerts WHERE resolved = 0 ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def resolve_alert(alert_id: int) -> bool:
    """Marks an alert as resolved. Returns True on success."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE alerts SET resolved = 1 WHERE id = ?", (alert_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


def store_draft(order_id: str, draft_type: str, subject: str, body: str) -> bool:
    """
    Upserts a draft (insert or replace based on order_id + draft_type).
    Returns True on success.
    """
    now = datetime.utcnow().isoformat()
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM drafts WHERE order_id = ? AND draft_type = ?
            """,
            (order_id, draft_type),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE drafts SET subject = ?, body = ?, sent = 0, created_at = ?
                WHERE order_id = ? AND draft_type = ?
                """,
                (subject, body, now, order_id, draft_type),
            )
        else:
            cursor.execute(
                """
                INSERT INTO drafts (order_id, draft_type, subject, body, sent, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
                """,
                (order_id, draft_type, subject, body, now),
            )
        conn.commit()
        return True


def get_draft(order_id: str, draft_type: str) -> dict | None:
    """Returns a draft dict or None if not found."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM drafts WHERE order_id = ? AND draft_type = ?",
            (order_id, draft_type),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def mark_draft_sent(order_id: str, draft_type: str) -> bool:
    """Marks a draft as sent. Returns True on success."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE drafts SET sent = 1 WHERE order_id = ? AND draft_type = ?",
            (order_id, draft_type),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_order_events(order_id: str) -> list[dict]:
    """Returns all events for an order, ordered chronologically."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM order_events WHERE order_id = ? ORDER BY timestamp ASC",
            (order_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def log_check_event(order_id: str, trigger: str, event_date: str = None) -> None:
    """
    Logs a non-state-change overdue check event to order_events.
    Uses from_state == to_state (current state) to mark it as a check, not a transition.
    """
    now = datetime.utcnow().isoformat()
    event_ts = event_date if event_date else now
    order = get_order(order_id)
    current_state = order.get("state") if order else None
    with _get_connection() as conn:
        conn.execute(
            """INSERT INTO order_events (order_id, from_state, to_state, trigger, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (order_id, current_state, current_state, trigger, event_ts),
        )
        conn.commit()


def log_email(email_id: str, email_date: str, from_addr: str, subject: str,
              order_id: str, classified_type: str):
    """Records a processed email in the email_log table."""
    now = datetime.utcnow().isoformat()
    with _get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO email_log
               (email_id, email_date, from_addr, subject, order_id, classified_type, processed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (email_id, email_date, from_addr, subject, order_id, classified_type, now)
        )
        conn.commit()


def write_dashboard_state():
    """
    Writes current DB state to data/dashboard_state.json for the React frontend.
    Called after each email is processed.
    """
    import json as _json
    from datetime import date as _date

    data_dir = os.path.dirname(DB_PATH)
    output_path = os.path.join(data_dir, "dashboard_state.json")

    conn = _get_connection()

    with conn:
        orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()]
        alerts = [dict(r) for r in conn.execute("SELECT * FROM alerts WHERE resolved=0 ORDER BY created_at DESC").fetchall()]
        all_alerts = [dict(r) for r in conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()]
        drafts = [dict(r) for r in conn.execute("SELECT * FROM drafts").fetchall()]
        email_log_rows = [dict(r) for r in conn.execute("SELECT * FROM email_log ORDER BY email_date ASC").fetchall()]
        order_events_all = [dict(r) for r in conn.execute("SELECT * FROM order_events ORDER BY timestamp ASC").fetchall()]
        # Most recently processed email by wall-clock time (not email date)
        last_processed_row = conn.execute("SELECT email_date FROM email_log ORDER BY processed_at DESC LIMIT 1").fetchone()

    conn.close()

    # Simulation date: the email_date of the most recently clicked "Process Next"
    # Using processed_at (wall-clock) avoids the problem where an older scenario's
    # latest-dated email permanently dominates the "YOU ARE HERE" display.
    simulation_date = dict(last_processed_row)['email_date'] if last_processed_row else None

    # Parse simulation date for overdue calculations
    from datetime import datetime as _dt2
    if simulation_date:
        try:
            sim_date = _dt2.strptime(simulation_date[:10], "%Y-%m-%d").date()
        except Exception:
            sim_date = _date.today()
    else:
        sim_date = _date.today()

    # Build draft lookup: order_id -> draft dict
    draft_lookup = {}
    for d in drafts:
        draft_lookup[(d['order_id'], d['draft_type'])] = d

    # Build orders list with timeline
    TERMINAL_STATES = {"RESOLVED", "REFUND_REJECTED", "NON_REFUNDABLE", "AMOUNT_MISMATCH"}

    orders_out = []
    for o in orders:
        # Build timeline steps
        state = o.get("state", "")

        # Determine which steps are relevant based on state
        state_progress = {
            "ORDER_CONFIRMED": 0,
            "ORDER_SHIPPED": 1,
            "DELIVERY_EXPECTED": 1,
            "DELIVERY_DELAY_COMMUNICATED": 1,
            "DELIVERED": 2,
            "RETURN_REQUESTED": 3,
            "RETURN_PICKUP_PENDING": 3,
            "RETURN_PICKED_UP": 4,
            "REFUND_PENDING": 4,
            "REFUND_CLAIMED": 5,
            "RESOLVED": 6,
            "REFUND_REJECTED": 5,
            "AMOUNT_MISMATCH": 6,
            "NON_REFUNDABLE": 0,
            "AMBIGUOUS_VENDOR_RESPONSE": 1,
        }
        current_step = state_progress.get(state, 0)

        # Check overdue states
        is_overdue = any(a['order_id'] == o['order_id'] and
                        a['alert_type'] in {"DELIVERY_OVERDUE", "PICKUP_OVERDUE", "REFUND_OVERDUE"}
                        for a in all_alerts)

        step_names = ["Order Placed", "Shipped", "Delivered", "Return Requested", "Picked Up", "Refund Initiated", "Bank Credit"]
        step_date_fields = ["order_date", None, "actual_delivery_date", "return_requested_date", "actual_pickup_date", "refund_claim_date", "bank_credit_date"]

        # Build rich event log for this order from order_events + email_log
        order_id_val = o.get('order_id')
        this_order_events = [e for e in order_events_all if e['order_id'] == order_id_val]
        this_order_emails = {e['order_id']: e for e in email_log_rows if e['order_id'] == order_id_val}
        order_alerts_map = {a['alert_type']: a for a in all_alerts if a['order_id'] == order_id_val}

        # Determine if DELIVERY_DELAY was vendor-communicated
        INFO_STATES = {"DELIVERY_DELAY_COMMUNICATED"}

        event_log = []
        for ev in this_order_events:
            to_state = ev.get('to_state', '')
            trigger = ev.get('trigger', '')
            # Find matching email from log
            matched_email = next(
                (e for e in email_log_rows
                 if e['order_id'] == order_id_val and e['subject'] == trigger),
                None
            )
            # Classify event type
            from_st = ev.get('from_state')
            if from_st is not None and from_st == to_state:
                # Same state — this is an overdue check event, not a transition
                event_type = "check"
            elif to_state in INFO_STATES and o.get('has_delay_communication'):
                event_type = "info"
            else:
                event_type = "state_change"
            # Mark check events that fired an alert
            alert_fired = None
            if event_type == "check" and order_alerts_map:
                # Check if any alert was first created around this event's timestamp
                check_alert_map = {
                    "DELIVERY_EXPECTED": "DELIVERY_OVERDUE",
                    "RETURN_PICKUP_PENDING": "PICKUP_OVERDUE",
                    "REFUND_PENDING": "REFUND_OVERDUE",
                    "REFUND_CLAIMED": "REFUND_NO_BANK_CREDIT",
                }
                mapped_alert_type = check_alert_map.get(to_state)
                if mapped_alert_type and mapped_alert_type in order_alerts_map:
                    alert_fired = order_alerts_map[mapped_alert_type]['message']

            event_log.append({
                "timestamp": ev.get('timestamp', ''),
                "email_date": matched_email['email_date'] if matched_email else ev.get('timestamp', ''),
                "from_state": ev.get('from_state'),
                "to_state": to_state,
                "trigger": trigger,
                "email_from": matched_email['from_addr'] if matched_email else None,
                "classified_type": matched_email['classified_type'] if matched_email else None,
                "event_type": event_type,
                "alert_fired": alert_fired,
            })

        # Simple status timeline (for the stepper visual)
        timeline = []
        for i, (step_name, date_field) in enumerate(zip(step_names, step_date_fields)):
            date_val = o.get(date_field) if date_field else None
            if i < current_step:
                status = "done"
            elif i == current_step:
                if is_overdue and state not in {"RESOLVED", "REFUND_REJECTED"}:
                    status = "overdue"
                else:
                    status = "current"
            else:
                status = "pending"
            timeline.append({"step": step_name, "date": date_val, "status": status})

        # Check for draft emails
        has_draft = any(
            (o['order_id'], dt) in draft_lookup and not draft_lookup[(o['order_id'], dt)].get('sent')
            for dt in ['complaint', 'pickup_followup', 'escalation']
        )

        # Compute days overdue — only check the date relevant to current state
        days_overdue = None
        state_date_map = {
            "DELIVERY_EXPECTED": "expected_delivery_date",
            "DELIVERY_DELAY_COMMUNICATED": "expected_delivery_date",
            "RETURN_PICKUP_PENDING": "expected_pickup_date",
            "REFUND_PENDING": "expected_refund_date",
            "REFUND_CLAIMED": "expected_refund_date",
        }
        # Only show days_overdue if an active overdue alert actually fired for this order.
        # Without this guard, mixing scenarios with different date ranges causes false
        # "89d overdue" readings when the global simulation date jumps ahead.
        alert_type_for_state = {
            "DELIVERY_EXPECTED": "DELIVERY_OVERDUE",
            "DELIVERY_DELAY_COMMUNICATED": "DELIVERY_OVERDUE",
            "RETURN_PICKUP_PENDING": "PICKUP_OVERDUE",
            "REFUND_PENDING": "REFUND_OVERDUE",
        }
        has_active_overdue_alert = any(
            a['order_id'] == o['order_id'] and
            a['alert_type'] == alert_type_for_state.get(state) and
            a['resolved'] == 0
            for a in all_alerts
        )
        relevant_field = state_date_map.get(state)
        if relevant_field and has_active_overdue_alert:
            val = o.get(relevant_field)
            if val:
                try:
                    from datetime import datetime as _dt
                    exp = _dt.strptime(val[:10], "%Y-%m-%d").date()
                    diff = (sim_date - exp).days
                    if diff > 0:
                        days_overdue = diff
                except Exception:
                    pass

        # Compute refund window validity (delivery_date + policy_days)
        refund_window_until = None
        delivery_date = o.get("actual_delivery_date")
        policy_days = o.get("policy_days") or 7
        if delivery_date:
            try:
                from datetime import datetime as _dt, timedelta as _td
                d = _dt.strptime(delivery_date[:10], "%Y-%m-%d").date()
                refund_window_until = (d + _td(days=policy_days)).isoformat()
            except Exception:
                pass

        # Check if any email has already been sent for this order
        email_was_sent = any(
            draft_lookup.get((o['order_id'], dt), {}).get('sent')
            for dt in ['complaint', 'pickup_followup', 'escalation']
        )

        orders_out.append({
            "id": o.get("order_id"),
            "merchant": o.get("merchant"),
            "product": o.get("product"),
            "amount": o.get("amount"),
            "state": o.get("state"),
            "order_date": o.get("order_date"),
            "expected_delivery_date": o.get("expected_delivery_date"),
            "delivery_date": o.get("actual_delivery_date"),
            "return_requested_date": o.get("return_requested_date"),
            "expected_pickup_date": o.get("expected_pickup_date"),
            "return_pickup_date": o.get("actual_pickup_date"),
            "expected_refund_date": o.get("expected_refund_date"),
            "bank_credit_date": o.get("bank_credit_date"),
            "days_overdue": days_overdue,
            "has_draft_email": has_draft,
            "email_was_sent": email_was_sent,
            "policy_refundable": o.get("policy_refundable", 1),
            "policy_days": policy_days,
            "refund_window_until": refund_window_until,
            "timeline": timeline,
            "event_log": event_log,
        })

    # Build alerts list
    alerts_out = []
    for a in alerts:
        order_id = a['order_id']
        # Find matching order
        order = next((o for o in orders if o.get('order_id') == order_id), {})

        # Find draft
        draft_type_map = {
            "DELIVERY_OVERDUE": "complaint",
            "PICKUP_OVERDUE": "pickup_followup",
            "REFUND_OVERDUE": "escalation",
        }
        draft_type = draft_type_map.get(a['alert_type'])
        draft = draft_lookup.get((order_id, draft_type)) if draft_type else None

        severity = "high" if a['alert_type'] in {"REFUND_OVERDUE", "PICKUP_OVERDUE", "DELIVERY_OVERDUE", "REFUND_REJECTED", "AMOUNT_MISMATCH"} else "medium"

        # Build alert reasoning: expected_by, overdue_by, last_check
        expected_by_map = {
            "DELIVERY_OVERDUE": order.get('expected_delivery_date'),
            "PICKUP_OVERDUE": order.get('expected_pickup_date'),
            "REFUND_OVERDUE": order.get('expected_refund_date'),
        }
        expected_by = expected_by_map.get(a['alert_type'])
        overdue_by = None
        if expected_by:
            try:
                exp2 = _dt2.strptime(expected_by[:10], "%Y-%m-%d").date()
                overdue_by = (sim_date - exp2).days
            except Exception:
                pass

        alert_out = {
            "id": str(a['id']),
            "type": a['alert_type'].lower(),
            "severity": severity,
            "summary": a['message'],
            "merchant": order.get('merchant', ''),
            "order_id": order_id,
            "timestamp": a['created_at'],
            "has_draft_email": draft is not None and not draft.get('sent'),
            "draft_email": None,
            "reasoning": {
                "expected_by": expected_by,
                "overdue_by": overdue_by,
                "last_check": simulation_date,
            },
        }

        if draft and not draft.get('sent'):
            import os as _os
            alert_out["draft_email"] = {
                "to": _os.getenv("DEMO_EMAIL", "demo@example.com"),
                "subject": draft.get('subject', ''),
                "body": draft.get('body', ''),
                "order_id": order_id,
                "draft_type": draft_type,
            }

        alerts_out.append(alert_out)

    # Analytics
    merchant_orders = {}
    merchant_returns = {}
    merchant_alerts = {}

    for o in orders:
        m = o.get('merchant', 'Unknown')
        merchant_orders[m] = merchant_orders.get(m, 0) + 1
        if o.get('return_requested_date'):
            merchant_returns[m] = merchant_returns.get(m, 0) + 1

    for a in all_alerts:
        order = next((o for o in orders if o.get('order_id') == a['order_id']), {})
        m = order.get('merchant', 'Unknown')
        merchant_alerts[m] = merchant_alerts.get(m, 0) + 1

    return_rate_by_merchant = [
        {"merchant": m, "rate": round(merchant_returns.get(m, 0) / cnt, 2)}
        for m, cnt in merchant_orders.items()
        if cnt > 0
    ]
    return_rate_by_merchant.sort(key=lambda x: x['rate'], reverse=True)

    flagged_merchants = [
        {"merchant": m, "alert_count": cnt}
        for m, cnt in merchant_alerts.items()
    ]
    flagged_merchants.sort(key=lambda x: x['alert_count'], reverse=True)

    # Summary
    pending_refund_states = {"REFUND_PENDING", "REFUND_CLAIMED", "RETURN_PICKED_UP"}
    pending_refund_value = sum(
        o.get('amount', 0) or 0
        for o in orders
        if o.get('state') in pending_refund_states
    )
    resolved_count = sum(1 for o in orders if o.get('state') == 'RESOLVED')

    email_log_out = [
        {
            "email_id": e['email_id'],
            "date": e['email_date'],
            "from_addr": e['from_addr'],
            "subject": e['subject'],
            "order_id": e['order_id'],
            "classified_type": e['classified_type'],
        }
        for e in email_log_rows
    ]

    dashboard_state = {
        "lastUpdated": _date.today().isoformat() + "T" + __import__('datetime').datetime.now().strftime("%H:%M:%S"),
        "simulationDate": simulation_date,
        "summary": {
            "total_orders": len(orders),
            "active_alerts": len(alerts),
            "resolved": resolved_count,
            "pending_refund_value": pending_refund_value,
        },
        "orders": orders_out,
        "alerts": alerts_out,
        "email_log": email_log_out,
        "analytics": {
            "return_rate_by_merchant": return_rate_by_merchant,
            "flagged_merchants": flagged_merchants[:5],
        }
    }

    with open(output_path, 'w') as f:
        _json.dump(dashboard_state, f, indent=2, default=str)

    print(f"  📊 Dashboard state written to {output_path}")
