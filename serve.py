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
from urllib.parse import urlparse, parse_qs

PORT = 8080
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.join(PROJECT_ROOT, '.venv', 'bin', 'python')
MAIN_PY = os.path.join(PROJECT_ROOT, 'main.py')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def do_GET(self):
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

            if order_id and draft_type:
                sys.path.insert(0, PROJECT_ROOT)
                from pipeline import state_manager
                state_manager.mark_draft_sent(order_id, draft_type)
                state_manager.write_dashboard_state()

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


if __name__ == '__main__':
    os.chdir(PROJECT_ROOT)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\nRefundTracker dashboard running at:")
        print(f"   http://localhost:{PORT}/dashboard/index.html\n")
        print(f"   Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
