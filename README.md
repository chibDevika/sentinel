# Sentinel — AI Refund & Order Tracker

An agentic AI pipeline that monitors your inbox for order, delivery, return, and refund emails — and automatically tracks state, raises alerts, and drafts escalation emails when things go wrong.

**Live demo:** https://web-production-ad940.up.railway.app/dashboard/index.html

> **Note:** The live demo is wired to the author's personal Telegram and Gmail accounts. Telegram alerts and escalation emails are delivered to the configured accounts only — reviewers can observe all pipeline activity and draft emails directly in the dashboard.

---

## What it does

- **Classifies** incoming emails (order confirmed, shipped, delivered, return, refund, bank credit, etc.) using Gemini
- **Extracts** structured fields (order ID, amounts, dates, merchants) from email bodies
- **Tracks order state** through a full lifecycle state machine (ORDER_CONFIRMED → DELIVERY_EXPECTED → DELIVERED → RETURN_PICKUP_PENDING → REFUND_PENDING → RESOLVED)
- **Checks merchant refund policies** via Tavily web search
- **Raises alerts** when deliveries, pickups, or refunds are overdue
- **Drafts escalation emails** (complaint, pickup follow-up, refund escalation) using Gemini — approve and send from the dashboard or directly from your phone
- **Sends Telegram notifications** with actionable inline buttons — tap "✅ Approve & Send Email" on your phone to trigger the send without opening the dashboard
- **Visualises everything** in a React dashboard with event timelines, alert cards, and email drafts

---

## Scenarios covered

| Scenario                               | Merchant     | What it demonstrates                                        |
| -------------------------------------- | ------------ | ----------------------------------------------------------- |
| Happy path                             | Nykaa        | Full order → return → refund → bank credit journey          |
| Refund overdue                         | TATA CLiQ    | Refund not received after pickup — escalation email drafted |
| Return pickup overdue                  | Myntra       | Pickup slot missed — follow-up email drafted                |
| Delivery overdue (no comms)            | Amazon India | No delivery, no vendor update — complaint email drafted     |
| Delivery delayed (vendor communicated) | H&M          | Vendor sends delay email — logged silently, no alert        |
| Fraudulent refund claim                | Flipkart     | Vendor claims refund sent, no bank credit after 7 days      |
| QC fail / refund rejected              | AJIO         | Return rejected after quality inspection                    |
| Non-refundable item                    | Meesho       | Policy check flags item as non-returnable at order stage    |
| No refund policy found                 | ShopKart     | Unknown merchant, policy lookup fails — alert raised        |

---

## Project structure

```
sentinel/
├── main.py                  # Pipeline entry point
├── serve.py                 # Dev server (serves dashboard + API endpoints)
├── requirements.txt
├── .env.example
├── pipeline/
│   ├── classifier.py        # Gemini email classifier
│   ├── extractor.py         # Gemini field extractor
│   ├── state_manager.py     # SQLite state machine + dashboard state writer
│   ├── decision_engine.py   # Overdue detection + alert logic
│   ├── policy_checker.py    # Tavily merchant policy lookup
│   ├── email_sender.py      # Gmail SMTP sender + Gemini email drafter
│   └── notifier.py          # WhatsApp/Telegram notifications
├── dashboard/
│   ├── index.html
│   ├── Dashboard.jsx        # React dashboard (vanilla, no build step)
│   └── app.py               # Optional Streamlit view
└── data/
    ├── mock_emails.json     # 40 simulated emails across 9 scenarios
    └── dashboard_state.json # Live state written after each email processed
```

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/chibDevika/sentinel.git
cd sentinel
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in `.env`:

```
GEMINI_API_KEY=...
TAVILY_API_KEY=...

# Gmail SMTP (for sending emails)
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=...
DEMO_EMAIL=recipient@example.com

# Telegram bot (for WhatsApp-style notifications)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Set to true to auto-send emails without dashboard approval
AUTO_SEND_EMAILS=false

# Set to false to send real emails (default: dry run)
DRY_RUN=true
```

### 3. Run the dashboard server

```bash
python serve.py
# Opens at http://localhost:8080/dashboard/index.html
```

---

## Usage

### Process emails by scenario (recommended)

```bash
python main.py --scenario refund_overdue     # process next email in this scenario
python main.py --scenario happy_path
python main.py --scenario delivery_delayed
# ... etc
```

### Or process everything at once

```bash
python main.py --all
```

### Other commands

```bash
python main.py --reset    # clear database and all pointers
python main.py --check    # run overdue check on all active orders
python main.py            # list all scenarios and their progress
```

The **Pipeline Controls** panel in the dashboard gives you the same controls with a UI — select a scenario, click "Process Next Email", and watch the order timeline build in real time.

---

## How alerts work

| Alert type              | Trigger                                                             |
| ----------------------- | ------------------------------------------------------------------- |
| `DELIVERY_OVERDUE`      | Past expected delivery date, no delivery confirmed, no vendor comms |
| `PICKUP_OVERDUE`        | Past expected pickup date, no pickup confirmed                      |
| `REFUND_OVERDUE`        | Past expected refund date, no bank credit                           |
| `REFUND_NO_BANK_CREDIT` | Vendor claims refund sent, >5 days with no bank credit              |
| `REFUND_REJECTED`       | Merchant explicitly rejects refund                                  |
| `AMOUNT_MISMATCH`       | Bank credit amount differs from expected refund amount              |
| `NON_REFUNDABLE`        | Merchant policy flags item as non-returnable                        |
| `POLICY_UNKNOWN`        | No refund policy found for merchant                                 |

Overdue checks run as synthetic pipeline entries — they evaluate all active orders at a specific simulation date and only log an event if a **new** alert fires (no duplicate events).
