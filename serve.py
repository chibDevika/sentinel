#!/usr/bin/env python3
"""
serve.py — Serves the project for the React dashboard demo.

Usage:
    python serve.py          # serves on http://localhost:8080

Then open: http://localhost:8080/dashboard/index.html
"""
import http.server
import socketserver
import os
import json
import subprocess
import sys
import threading
import time
import requests as _requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", 8080))
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, '.venv', 'bin', 'python')
MAIN_PY = os.path.join(PROJECT_ROOT, 'main.py')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def do_GET(self):
        if self.path == '/' or self.path == '':
            self.send_response(302)
            self.send_header('Location', '/dashboard/index.html')
            self.end_headers()
            return

        if self.path.startswith('/api/scenarios'):
            import json as _json
            from collections import OrderedDict

            emails_path = os.path.join(PROJECT_ROOT, 'data', 'mock_emails.json')
            pointer_path = os.path.join(PROJECT_ROOT, 'data', 'pointer.json')

            with open(emails_path) as f:
                all_emails = _json.load(f)

            pointer = {}
            if os.path.exists(pointer_path):
                with open(pointer_path) as f:
                    pointer = _json.load(f)

            # Collect scenarios in order of first appearance
            seen = OrderedDict()
            for e in all_emails:
                s = e.get('scenario')
                if s and s not in seen:
                    seen[s] = []
                if s:
                    seen[s].append(e)

            scenarios = []
            for scenario_id, s_emails in seen.items():
                processed = pointer.get(scenario_id, 0)
                scenarios.append({
                    "id": scenario_id,
                    "total": len(s_emails),
                    "processed": min(processed, len(s_emails)),
                    "complete": processed >= len(s_emails),
                })

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(_json.dumps(scenarios).encode())
            return

        # API endpoint to mark a draft as sent
        if self.path.startswith('/api/mark-sent'):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            order_id = params.get('order_id', [''])[0]
            draft_type = params.get('draft_type', [''])[0]

            print(f"\n[mark-sent] hit — order_id={repr(order_id)} draft_type={repr(draft_type)}", flush=True)

            if order_id and draft_type:
                sys.path.insert(0, PROJECT_ROOT)
                from pipeline import state_manager, email_sender
                draft = state_manager.get_draft(order_id, draft_type)
                if draft and not draft.get('sent'):
                    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
                    print(f"[mark-sent] DRY_RUN={dry_run} | Subject: {draft.get('subject', '(none)')}", flush=True)
                    email_sender.send_email(draft['subject'], draft['body'])
                elif draft and draft.get('sent'):
                    print(f"[mark-sent] Draft already marked sent — skipping send", flush=True)
                else:
                    print(f"[mark-sent] No draft found for order_id={order_id} draft_type={draft_type}", flush=True)
                state_manager.mark_draft_sent(order_id, draft_type)
                state_manager.write_dashboard_state()
            else:
                print(f"[mark-sent] Missing params — skipping", flush=True)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            return

        # API endpoint for pipeline control from DevControls
        if self.path.startswith('/api/pipeline'):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            args_str = params.get('args', [''])[0].strip()
            args = args_str.split() if args_str else []

            python = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
            result = subprocess.run(
                [python, MAIN_PY] + args,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout + result.stderr

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(output.encode())
            return

        # Serve everything else normally
        super().do_GET()

    def log_message(self, format, *args):
        # Suppress noisy request logs, only show errors
        if args[1] not in ('200', '304'):
            super().log_message(format, *args)


def _telegram_callback_poller():
    """
    Background thread: polls Telegram for callback_query updates (button taps).
    When the user taps '✅ Approve & Send Email' on a Telegram notification,
    this handler looks up the draft, sends the email, and marks it sent.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return

    sys.path.insert(0, PROJECT_ROOT)
    from pipeline import state_manager, email_sender
    from pipeline.notifier import answer_callback, edit_message_text

    offset = None
    base_url = f"https://api.telegram.org/bot{bot_token}"

    print("[Telegram] Callback poller started — button taps will trigger email sends.", flush=True)

    while True:
        try:
            params = {"timeout": 20, "allowed_updates": ["callback_query"]}
            if offset is not None:
                params["offset"] = offset

            resp = _requests.get(f"{base_url}/getUpdates", params=params, timeout=30)
            updates = resp.json().get("result", [])

            for update in updates:
                offset = update["update_id"] + 1
                cq = update.get("callback_query")
                if not cq:
                    continue

                data = cq.get("data", "")
                if not data.startswith("send|"):
                    answer_callback(cq["id"])
                    continue

                _, order_id, draft_type = data.split("|", 2)
                chat_id = str(cq["message"]["chat"]["id"])
                message_id = cq["message"]["message_id"]

                print(f"\n[Telegram] Button tapped — order_id={order_id} draft_type={draft_type}", flush=True)

                draft = state_manager.get_draft(order_id, draft_type)
                if not draft:
                    answer_callback(cq["id"], "⚠️ Draft not found.")
                    continue

                if draft.get("sent"):
                    answer_callback(cq["id"], "Email was already sent.")
                    edit_message_text(chat_id, message_id, cq["message"]["text"] + "\n\n✅ Already sent.")
                    continue

                print(f"[Telegram] Sending email: {draft.get('subject')}", flush=True)
                ok = email_sender.send_email(draft["subject"], draft["body"])
                state_manager.mark_draft_sent(order_id, draft_type)
                state_manager.write_dashboard_state()

                if ok:
                    answer_callback(cq["id"], "✅ Email sent!")
                    edit_message_text(
                        chat_id,
                        message_id,
                        cq["message"]["text"] + "\n\n✅ Email approved & sent from Telegram.",
                    )
                    print(f"[Telegram] ✅ Email sent and draft marked as sent.", flush=True)
                else:
                    answer_callback(cq["id"], "❌ Failed to send. Check server logs.")

        except Exception as e:
            print(f"[Telegram] Poller error: {e}", flush=True)
            time.sleep(5)


if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)

    # Start Telegram callback poller in background
    t = threading.Thread(target=_telegram_callback_poller, daemon=True)
    t.start()

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\nRefundTracker dashboard running at:")
        print(f"   http://localhost:{PORT}/dashboard/index.html\n")
        print(f"   Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
