import os
from datetime import datetime


class Logger:
    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "agent_logs",
            )
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self._timestamp()

    def _timestamp(self):
        return datetime.now().strftime("[%Y-%m-%d %H:%M]")

    def _write(self, filename, message):
        path = os.path.join(self.log_dir, filename)
        with open(path, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    def log_prompt(self, content):
        ts = self._timestamp()
        msg = f"{ts} USER_PROMPT: {content}"
        self._write("prompts.log", msg)

    def log_decision(self, content):
        ts = self._timestamp()
        msg = f"{ts} DECISION: {content}"
        self._write("decisions.log", msg)

    def log_command(self, command, output=""):
        ts = self._timestamp()
        self._write("commands.log", f"{ts} COMMAND: {command}")
        if output:
            self._write("commands.log", f"{ts} OUTPUT: {output[:2000]}")

    def log_test_run(self, score_str):
        ts = self._timestamp()
        msg = f"{ts} TEST_RUN: {score_str}"
        self._write("test_runs.log", msg)

    def log_error(self, content):
        ts = self._timestamp()
        msg = f"{ts} ERROR: {content}"
        self._write("errors.log", msg)

    def log_human_intervention(self, content="None recorded"):
        ts = self._timestamp()
        msg = f"{ts} HUMAN_INTERVENTION: {content}"
        self._write("human_interventions.log", msg)


logger = Logger()
