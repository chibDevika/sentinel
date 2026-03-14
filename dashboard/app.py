import streamlit as st
import sqlite3
import json
import os
import sys
import subprocess
from datetime import datetime, date
import pandas as pd
import plotly.express as px

# --- Paths ---
DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(DASHBOARD_DIR, '..')
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'orders.db')
POINTER_PATH = os.path.join(PROJECT_ROOT, 'data', 'pointer.json')
ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
EMAILS_PATH = os.path.join(PROJECT_ROOT, 'data', 'mock_emails.json')
VENV_PYTHON = os.path.join(PROJECT_ROOT, '.venv', 'bin', 'python')
MAIN_PY = os.path.join(PROJECT_ROOT, 'main.py')

sys.path.insert(0, PROJECT_ROOT)

# --- State config ---
STATE_CONFIG = {
    "ORDER_CONFIRMED":              {"emoji": "🟡", "color": "#f0ad4e", "group": "pending"},
    "ORDER_SHIPPED":                {"emoji": "🔵", "color": "#5bc0de", "group": "active"},
    "DELIVERY_EXPECTED":            {"emoji": "🔵", "color": "#5bc0de", "group": "active"},
    "DELIVERED":                    {"emoji": "🟢", "color": "#5cb85c", "group": "good"},
    "RETURN_REQUESTED":             {"emoji": "🟡", "color": "#f0ad4e", "group": "pending"},
    "RETURN_PICKUP_PENDING":        {"emoji": "🟠", "color": "#f0a500", "group": "pending"},
    "RETURN_PICKED_UP":             {"emoji": "🔵", "color": "#5bc0de", "group": "active"},
    "REFUND_PENDING":               {"emoji": "🟠", "color": "#f0a500", "group": "pending"},
    "REFUND_CLAIMED":               {"emoji": "🔵", "color": "#5bc0de", "group": "active"},
    "RESOLVED":                     {"emoji": "✅", "color": "#5cb85c", "group": "good"},
    "DELIVERY_DELAY_COMMUNICATED":  {"emoji": "🟠", "color": "#f0a500", "group": "pending"},
    "REFUND_REJECTED":              {"emoji": "🔴", "color": "#d9534f", "group": "flagged"},
    "AMOUNT_MISMATCH":              {"emoji": "🔴", "color": "#d9534f", "group": "flagged"},
    "AMBIGUOUS_VENDOR_RESPONSE":    {"emoji": "🟠", "color": "#f0a500", "group": "pending"},
    "NON_REFUNDABLE":               {"emoji": "🔴", "color": "#d9534f", "group": "flagged"},
}

# --- Page config ---
st.set_page_config(
    page_title="Sentinel",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper functions ---

def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_orders():
    conn = get_db_connection()
    if not conn:
        return []
    with conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_active_alerts():
    conn = get_db_connection()
    if not conn:
        return []
    with conn:
        rows = conn.execute("SELECT * FROM alerts WHERE resolved=0 ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_order_events(order_id):
    conn = get_db_connection()
    if not conn:
        return []
    with conn:
        rows = conn.execute(
            "SELECT * FROM order_events WHERE order_id=? ORDER BY timestamp ASC", (order_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_draft(order_id, draft_type):
    conn = get_db_connection()
    if not conn:
        return None
    with conn:
        row = conn.execute(
            "SELECT * FROM drafts WHERE order_id=? AND draft_type=?", (order_id, draft_type)
        ).fetchone()
    return dict(row) if row else None


def mark_draft_sent(order_id, draft_type):
    conn = get_db_connection()
    if not conn:
        return
    with conn:
        conn.execute(
            "UPDATE drafts SET sent=1 WHERE order_id=? AND draft_type=?", (order_id, draft_type)
        )


def resolve_alert(alert_id):
    conn = get_db_connection()
    if not conn:
        return
    with conn:
        conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))


def get_pointer():
    if not os.path.exists(POINTER_PATH):
        return {"index": 0}
    with open(POINTER_PATH) as f:
        return json.load(f)


def get_total_emails():
    if not os.path.exists(EMAILS_PATH):
        return 0
    with open(EMAILS_PATH) as f:
        return len(json.load(f))


def get_next_expected_date(order):
    """Returns (label, date_str) for the most relevant upcoming date."""
    state = order.get('state', '')
    if state in ("ORDER_CONFIRMED", "ORDER_SHIPPED", "DELIVERY_EXPECTED", "DELIVERY_DELAY_COMMUNICATED"):
        d = order.get('expected_delivery_date') or order.get('updated_eta')
        return ("Expected delivery", d)
    elif state == "RETURN_PICKUP_PENDING":
        return ("Pickup by", order.get('expected_pickup_date'))
    elif state in ("REFUND_PENDING", "RETURN_PICKED_UP"):
        return ("Refund by", order.get('expected_refund_date'))
    elif state == "REFUND_CLAIMED":
        return ("Bank credit (est.)", order.get('refund_claim_date'))
    return ("—", None)


def days_remaining(date_str):
    """Returns int days remaining (negative = overdue). None if no date."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            d = datetime.strptime(date_str[:10], fmt).date()
            return (d - date.today()).days
        except ValueError:
            continue
    return None


def format_amount(amount):
    if amount is None:
        return "—"
    return f"₹{amount:,.2f}"


def run_pipeline_command(args):
    """Runs main.py with given args using venv python. Returns (stdout, stderr)."""
    python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    result = subprocess.run(
        [python, MAIN_PY] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr


def send_email_via_module(subject, body):
    """Send email using email_sender module."""
    try:
        from pipeline import email_sender
        return email_sender.send_email(subject, body)
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False


def get_env_value(key):
    if not os.path.exists(ENV_PATH):
        return None
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.strip().split('=', 1)[1]
    return None


def set_env_value(key, value):
    if not os.path.exists(ENV_PATH):
        return
    with open(ENV_PATH) as f:
        lines = f.readlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}\n")
    with open(ENV_PATH, 'w') as f:
        f.writelines(new_lines)


# --- Custom CSS ---
st.markdown("""
<style>
.alert-card { border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }
.alert-critical { background: #fff5f5; border-left: 4px solid #d9534f; }
.alert-warning  { background: #fffbf0; border-left: 4px solid #f0a500; }
.alert-info     { background: #f0f8ff; border-left: 4px solid #5bc0de; }
.metric-card    { background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }
.state-badge    { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.8em; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# --- Top bar ---
col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

with col1:
    st.markdown("## 🔍 Sentinel")

pointer = get_pointer()
total_emails = get_total_emails()
current_idx = pointer.get("index", 0)

with col2:
    if st.button("📧 Process Next Email", type="primary", disabled=(current_idx >= total_emails)):
        with st.spinner("Processing email..."):
            stdout, stderr = run_pipeline_command([])
        st.success(f"Processed email {current_idx + 1}")
        with st.expander("📋 Pipeline output", expanded=False):
            st.code(stdout or stderr or "No output")
        st.rerun()

with col3:
    if total_emails > 0:
        st.progress(current_idx / total_emails, text=f"Email {current_idx}/{total_emails}")

with col4:
    auto_send_val = get_env_value("AUTO_SEND_EMAILS") or "false"
    auto_send_on = auto_send_val.lower() == "true"
    new_auto = st.toggle("⚡ Auto-Send Emails", value=auto_send_on)
    if new_auto != auto_send_on:
        set_env_value("AUTO_SEND_EMAILS", "true" if new_auto else "false")
        if new_auto:
            st.warning("⚠️ Auto-send enabled — emails sent without confirmation")

# Pipeline controls
with st.expander("⚙️ Pipeline controls", expanded=False):
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("↺ Reset Pipeline", help="Resets email pointer and deletes database"):
            run_pipeline_command(["--reset"])
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
            st.success("Pipeline reset. Database cleared.")
            st.rerun()
    with col_r2:
        if st.button("⏩ Process All Remaining"):
            with st.spinner("Processing all emails..."):
                stdout, stderr = run_pipeline_command(["--all"])
            with st.expander("📋 Output"):
                st.code(stdout or stderr)
            st.rerun()

st.divider()

# --- Orders section ---
orders = get_all_orders()

st.markdown("### 📦 Orders")

if not orders:
    st.info("No orders yet. Click **📧 Process Next Email** to begin.")
else:
    for order in orders:
        state = order.get('state', 'UNKNOWN')
        cfg = STATE_CONFIG.get(state, {"emoji": "⚪", "color": "#999"})
        emoji = cfg["emoji"]

        date_label, next_date = get_next_expected_date(order)
        days_left = days_remaining(next_date)

        if days_left is not None and days_left < 0:
            date_display = f"🔴 {abs(days_left)}d overdue"
        elif days_left is not None:
            date_display = f"{days_left}d remaining"
        else:
            date_display = "—"

        header = (
            f"{emoji} **{order['merchant']}** — {order.get('product', '?')}  |  "
            f"{format_amount(order.get('amount'))}  |  `{state}`  |  "
            f"{date_label}: {date_display}"
        )

        with st.expander(header, expanded=(cfg.get('group') == 'flagged')):
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                st.markdown("**Order Details**")
                st.write(f"Order ID: `{order.get('order_id')}`")
                st.write(f"Merchant: {order.get('merchant')}")
                st.write(f"Product: {order.get('product')}")
                st.write(f"Amount: {format_amount(order.get('amount'))}")
                if order.get('policy_refundable') == 0:
                    st.error("Non-refundable item")
                elif order.get('policy_days'):
                    st.write(f"Refund policy: {order.get('policy_days')} business days")

            with col_b:
                st.markdown("**Key Dates**")
                date_fields = [
                    ("Ordered", "order_date"),
                    ("Expected delivery", "expected_delivery_date"),
                    ("Delivered", "actual_delivery_date"),
                    ("Return requested", "return_requested_date"),
                    ("Expected pickup", "expected_pickup_date"),
                    ("Picked up", "actual_pickup_date"),
                    ("Expected refund", "expected_refund_date"),
                    ("Refund claimed", "refund_claim_date"),
                    ("Bank credit", "bank_credit_date"),
                ]
                for label, field in date_fields:
                    val = order.get(field)
                    if val:
                        st.write(f"{label}: `{val[:10]}`")

            with col_c:
                st.markdown("**State Timeline**")
                events = get_order_events(order.get('order_id'))
                if events:
                    for ev in events:
                        ts = ev.get('timestamp', '')[:16]
                        st.write(f"`{ts}` {ev.get('from_state', '—')} → **{ev.get('to_state')}**")
                        if ev.get('trigger'):
                            st.caption(f"  ↳ {ev.get('trigger')[:60]}")
                else:
                    st.write("No events yet")

            # Draft emails
            for dtype, dlabel in [
                ("complaint", "Complaint Email"),
                ("pickup_followup", "Pickup Follow-up"),
                ("escalation", "Escalation Email"),
            ]:
                draft = get_draft(order.get('order_id'), dtype)
                if not draft:
                    continue
                st.markdown("---")
                st.markdown(f"**📧 {dlabel}**")
                if draft.get('sent'):
                    st.success(f"✅ {dlabel} already sent")
                else:
                    with st.expander(f"👁 Preview: {draft.get('subject', '')}"):
                        st.text_area(
                            "Body", draft.get('body', ''), height=180, disabled=True,
                            key=f"body_{order.get('order_id')}_{dtype}"
                        )
                    if st.button(f"✉️ Send {dlabel}", key=f"sendbtn_{order.get('order_id')}_{dtype}"):
                        if send_email_via_module(draft.get('subject', ''), draft.get('body', '')):
                            mark_draft_sent(order.get('order_id'), dtype)
                            st.success("✅ Email sent!")
                            st.rerun()

# --- Alerts section ---
st.divider()
st.markdown("### ⚠️ Active Alerts")

alerts = get_active_alerts()

ALERT_DRAFT_MAP = {
    "DELIVERY_OVERDUE": "complaint",
    "PICKUP_OVERDUE": "pickup_followup",
    "REFUND_OVERDUE": "escalation",
}

ALERT_CSS_MAP = {
    "DELIVERY_OVERDUE": "alert-critical",
    "PICKUP_OVERDUE": "alert-critical",
    "REFUND_OVERDUE": "alert-critical",
    "REFUND_REJECTED": "alert-critical",
    "AMOUNT_MISMATCH": "alert-critical",
    "REFUND_NO_BANK_CREDIT": "alert-warning",
    "NON_REFUNDABLE": "alert-warning",
    "DELIVERY_DELAY": "alert-info",
}

if not alerts:
    st.success("No active alerts ✅")
else:
    for alert in alerts:
        alert_type = alert.get('alert_type', '')
        css_class = ALERT_CSS_MAP.get(alert_type, "alert-info")

        st.markdown(f"""
        <div class="alert-card {css_class}">
            <strong>{alert_type.replace('_', ' ')}</strong> &nbsp;
            <span style="color:#666;font-size:0.85em">{alert.get('created_at', '')[:16]}</span><br>
            {alert.get('message', '')}
        </div>
        """, unsafe_allow_html=True)

        order_id = alert.get('order_id')
        draft_type = ALERT_DRAFT_MAP.get(alert_type)

        col1, col2 = st.columns([1, 5])
        with col1:
            if draft_type:
                draft = get_draft(order_id, draft_type)
                if draft and not draft.get('sent'):
                    with st.expander("📧 Preview email"):
                        st.write(f"**Subject:** {draft.get('subject')}")
                        st.text_area(
                            "Body", draft.get('body', ''), height=150, disabled=True,
                            key=f"alert_preview_{alert.get('id')}"
                        )
                    if st.button("✉️ Send Email", key=f"alert_send_{alert.get('id')}"):
                        if send_email_via_module(draft.get('subject', ''), draft.get('body', '')):
                            mark_draft_sent(order_id, draft_type)
                            resolve_alert(alert.get('id'))
                            st.success("Email sent!")
                            st.rerun()
                elif draft and draft.get('sent'):
                    st.success("✅ Email sent")
        with col2:
            if st.button("✓ Dismiss", key=f"dismiss_{alert.get('id')}"):
                resolve_alert(alert.get('id'))
                st.rerun()

# --- Analytics section ---
st.divider()
st.markdown("### 📊 Analytics")

m1, m2, m3, m4 = st.columns(4)

all_orders = get_all_orders()
all_alerts = get_active_alerts()

total_orders = len(all_orders)

pending_refund_states = {"REFUND_PENDING", "REFUND_CLAIMED", "RETURN_PICKED_UP"}
pending_refund_value = sum(
    o.get('amount', 0) or 0
    for o in all_orders
    if o.get('state') in pending_refund_states
)

active_alert_count = len(all_alerts)

resolved = [
    o for o in all_orders
    if o.get('state') == 'RESOLVED'
    and o.get('actual_pickup_date')
    and o.get('bank_credit_date')
]
if resolved:
    avg_days = 0
    for o in resolved:
        try:
            pickup = datetime.strptime(o['actual_pickup_date'][:10], "%Y-%m-%d").date()
            credit = datetime.strptime(o['bank_credit_date'][:10], "%Y-%m-%d").date()
            avg_days += (credit - pickup).days
        except (ValueError, KeyError):
            pass
    avg_days = avg_days / len(resolved)
    avg_display = f"{avg_days:.1f} days"
else:
    avg_display = "—"

with m1:
    st.metric("Total Orders", total_orders)
with m2:
    st.metric("Pending Refunds", f"₹{pending_refund_value:,.2f}")
with m3:
    st.metric("Active Alerts", active_alert_count)
with m4:
    st.metric("Avg Refund Time", avg_display)

# Bar chart
if all_orders:
    state_counts = {}
    for o in all_orders:
        s = o.get('state', 'UNKNOWN')
        state_counts[s] = state_counts.get(s, 0) + 1

    df = pd.DataFrame([
        {
            "State": k,
            "Count": v,
            "Color": STATE_CONFIG.get(k, {}).get("color", "#999"),
        }
        for k, v in state_counts.items()
    ])

    fig = px.bar(
        df, x="Count", y="State", orientation='h',
        color="State",
        color_discrete_map={row["State"]: row["Color"] for _, row in df.iterrows()},
        title="Orders by State",
    )
    fig.update_layout(showlegend=False, height=300, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🔍 Sentinel")
    st.markdown(
        "AI agent that monitors orders, returns & refunds — "
        "alerting you only when action is needed."
    )

    st.divider()
    st.markdown("### 📍 Pipeline Status")
    pointer = get_pointer()
    total_emails = get_total_emails()
    idx = pointer.get("index", 0)
    st.write(f"Emails processed: **{idx} / {total_emails}**")
    if idx < total_emails and os.path.exists(EMAILS_PATH):
        with open(EMAILS_PATH) as f:
            emails = json.load(f)
        if idx < len(emails):
            next_email = emails[idx]
            st.write(f"Next: `{next_email.get('email_type')}`")
            st.caption(next_email.get('subject', '')[:60])

    st.divider()
    st.markdown("### ⚙️ Settings")
    dry_run = get_env_value("DRY_RUN") or "true"
    auto_send = get_env_value("AUTO_SEND_EMAILS") or "false"
    st.write(f"DRY_RUN: `{dry_run}`")
    st.write(f"AUTO_SEND_EMAILS: `{auto_send}`")

    st.divider()
    if st.button("🔍 Run Overdue Check"):
        with st.spinner("Checking overdue orders..."):
            stdout, stderr = run_pipeline_command(["--check"])
        st.success("Overdue check complete")
        with st.expander("Output"):
            st.code(stdout or stderr)
        st.rerun()

    st.divider()
    st.caption("Built with Gemini · Tavily · Twilio · Streamlit")
