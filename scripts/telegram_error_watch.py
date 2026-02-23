import json
import subprocess
import time
from pathlib import Path
import sys

CHAT_ID = "-5003286623"
LIMIT = 120
INTERVAL = 300  # 5 minutes
STATE_FILE = Path(".tmp/telegram_error_watch_state.json")
LOG_FILE = Path(".tmp/telegram_error_watch.log")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def log_line(line: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_messages():
    cmd = [sys.executable, "scripts/telegram_fetch.py", "recent", "--chat-id", CHAT_ID, "--limit", str(LIMIT)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))
    if proc.returncode != 0:
        log_line(f"fetch error: {proc.stderr}")
        return None
    return json.loads(proc.stdout)


def extract_errors(messages, last_id):
    new_errors = []
    for m in messages:
        mid = m.get("id")
        if last_id and mid <= last_id:
            continue
        text = m.get("text")
        if isinstance(text, str) and "Error" in text:
            new_errors.append(m)
    return new_errors


def send_notification(errors):
    if not errors:
        return
    summary = "\n".join([f"{e.get('date')} | {e.get('text')[:200]}" for e in errors[:5]])
    note = f"ClawdBots error sweep detected {len(errors)} new errors:\n{summary}"
    cmd = [sys.executable, "scripts/telegram_fetch.py", "send", "--chat-id", CHAT_ID, "--text", note]
    subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path.cwd()))


def main():
    state = load_state()
    last_id = state.get("last_id", 0)
    while True:
        messages = fetch_messages()
        if messages:
            latest_id = max(m.get("id", 0) for m in messages)
            errors = extract_errors(messages, last_id)
            if errors:
                send_notification(errors)
            last_id = max(last_id, latest_id)
            save_state({"last_id": last_id})
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
