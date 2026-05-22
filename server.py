import http.server
import json
import os
import sys
import subprocess
import threading
import re
import urllib.parse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
AGENT_SCRIPT = os.path.join(PROJECT_ROOT, "agent", "agent.py")
PROMPT_FILE = os.path.join(PROJECT_ROOT, "agent_logs", "user_prompt.txt")

_agent_process = None
_agent_lock = threading.Lock()


class AgentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PROJECT_ROOT, **kwargs)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            global _agent_process
            running = (
                _agent_process is not None
                and _agent_process.poll() is None
            )
            prompt_pending = os.path.exists(PROMPT_FILE)
            self._send_json({
                "agent_running": running,
                "prompt_pending": prompt_pending,
                "prompt": (
                    open(PROMPT_FILE, "r", encoding="utf-8").read()
                    if prompt_pending
                    else None
                ),
            })
            return

        if path.startswith("/agent_logs/") or path == "/knit.py":
            return super().do_GET()

        if path == "/" or path == "":
            return super().do_GET()

        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/prompt":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            prompt_text = data.get("prompt", "").strip()

            if not prompt_text:
                self._send_json({"error": "Prompt cannot be empty"}, 400)
                return

            os.makedirs(os.path.dirname(PROMPT_FILE), exist_ok=True)
            with open(PROMPT_FILE, "w", encoding="utf-8") as f:
                f.write(prompt_text)

            thread = threading.Thread(target=self._launch_agent, daemon=True)
            thread.start()

            self._send_json({
                "status": "launched",
                "message": "Agent started with your prompt",
            })
            return

        if self.path == "/api/archive":
            errors = self._archive_and_clear()
            self._send_json({
                "status": "archived" if not errors else "partial",
                "errors": errors,
                "message": "Logs archived and cleared" if not errors else f"Archive completed with issues: {errors}",
            })
            return

        self._send_json({"error": "Not found"}, 404)

    def _archive_and_clear(self):
        logs_dir = os.path.join(PROJECT_ROOT, "agent_logs")
        archive_dir = os.path.join(
            logs_dir, "archives", datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        )
        os.makedirs(archive_dir, exist_ok=True)
        errors = []

        log_files = [
            "prompts.log",
            "decisions.log",
            "commands.log",
            "test_runs.log",
            "errors.log",
            "human_interventions.log",
            "final_report.md",
        ]
        for fname in log_files:
            src = os.path.join(logs_dir, fname)
            if os.path.exists(src) and os.path.getsize(src) > 0:
                try:
                    with open(src, "r", encoding="utf-8") as f:
                        content = f.read()
                    dst = os.path.join(archive_dir, fname)
                    with open(dst, "w", encoding="utf-8") as f:
                        f.write(content)
                    open(src, "w").close()
                except Exception as e:
                    errors.append(f"{fname}: {e}")

        sol = os.path.join(PROJECT_ROOT, "knit.py")
        if os.path.exists(sol):
            try:
                with open(sol, "r", encoding="utf-8") as f:
                    content = f.read()
                dst = os.path.join(archive_dir, "knit.py")
                with open(dst, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                errors.append(f"knit.py: {e}")

        marker = os.path.join(archive_dir, ".archive")
        with open(marker, "w") as f:
            f.write(f"Archived at {datetime.now().isoformat()}")

        last_archive = os.path.join(logs_dir, ".last_archive")
        with open(last_archive, "w", encoding="utf-8") as f:
            f.write(archive_dir)

        return errors

    def _launch_agent(self):
        global _agent_process
        with _agent_lock:
            if _agent_process is not None and _agent_process.poll() is None:
                return
            _agent_process = subprocess.Popen(
                [sys.executable, AGENT_SCRIPT],
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )


def main():
    port = int(os.environ.get("PORT", 8000))
    server = http.server.HTTPServer(("0.0.0.0", port), AgentHandler)
    print(f"SPRK Server running at http://localhost:{port}")
    print(f"Open your browser and type what you want the agent to build.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
