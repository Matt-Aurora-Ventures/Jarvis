"""Morning Brief Generator for ClawdMatt."""
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BOTS = ["clawdmatt", "clawdjarvis", "clawdfriday"]
HANDOFFS_DIR = Path("/root/clawdbots/handoffs")
LOG_DIR = Path("/var/log/clawdbot")
TASKS_FILE = Path("/root/clawdbots/active_tasks.json")
BRIEF_MARKER = HANDOFFS_DIR / ".brief_sent"


class MorningBrief:

    async def generate_brief(self):
        return self._generate()

    def generate_brief_sync(self):
        return self._generate()

    def _generate(self):
        sections = []
        now = datetime.utcnow()
        header = "MORNING BRIEF -- " + now.strftime("%A, %B %d, %Y %H:%M UTC")
        sections.append(header + "\n")

        sections.append("SYSTEM HEALTH")
        try:
            for bot in BOTS:
                result = subprocess.run(
                    ["systemctl", "is-active", bot],
                    capture_output=True, text=True, timeout=5
                )
                status = "OK" if result.stdout.strip() == "active" else "DOWN"
                sections.append("  [" + status + "] " + bot)

            disk = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
            dl = disk.stdout.strip().split("\n")[-1].split()
            sections.append("  Disk: " + dl[2] + " used / " + dl[1] + " total (" + dl[4] + ")")

            mem = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
            ml = mem.stdout.strip().split("\n")[1].split()
            sections.append("  RAM: " + ml[2] + " used / " + ml[1] + " total")

            uptime = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
            sections.append("  Uptime: " + uptime.stdout.strip())
        except Exception as e:
            sections.append("  Health check error: " + str(e))

        sections.append("\nPENDING HANDOFFS")
        try:
            pf = HANDOFFS_DIR / "pending.json"
            if pf.exists():
                pending = json.loads(pf.read_text())
                pt = [h for h in pending if h.get("status") == "pending"]
                if pt:
                    for h in pt:
                        sections.append("  -> " + h["to"] + ": " + h["task"][:60])
                else:
                    sections.append("  No pending handoffs")
            else:
                sections.append("  No pending handoffs")
        except Exception as e:
            sections.append("  Handoff check error: " + str(e))

        sections.append("\nERRORS (Last 24h)")
        try:
            ec = 0
            for bot in BOTS:
                result = subprocess.run(
                    ["journalctl", "-u", bot, "--since", "24 hours ago", "--no-pager", "-q"],
                    capture_output=True, text=True, timeout=10
                )
                err_lines = [l for l in result.stdout.split("\n") if "ERROR" in l]
                if err_lines:
                    sections.append("  " + bot + " journal: " + str(len(err_lines)) + " errors")
                    ec += len(err_lines)
            if ec == 0:
                sections.append("  No errors found")
        except Exception as e:
            sections.append("  Log check error: " + str(e))

        sections.append("\nACTIVE TASKS")
        try:
            if TASKS_FILE.exists():
                tasks = json.loads(TASKS_FILE.read_text())
                active = [t for t in tasks if t.get("status") == "active"]
                if active:
                    for t in active[:5]:
                        sections.append("  - " + t.get("description", "Unknown"))
                else:
                    sections.append("  No active tasks")
            else:
                sections.append("  No task file found")
        except Exception:
            sections.append("  No active tasks")

        sections.append("\nRECOMMENDATIONS")
        sections.append("  - Review pending handoffs")
        sections.append("  - Check error logs if count > 0")
        sections.append("  - Verify all bots responsive")

        return "\n".join(sections)

    @staticmethod
    def should_send():
        now = datetime.utcnow()
        if now.hour != 8 or now.minute > 10:
            return False
        if BRIEF_MARKER.exists():
            sent_date = BRIEF_MARKER.read_text().strip()
            if sent_date == now.strftime("%Y-%m-%d"):
                return False
        return True

    @staticmethod
    def mark_sent():
        BRIEF_MARKER.parent.mkdir(parents=True, exist_ok=True)
        BRIEF_MARKER.write_text(datetime.utcnow().strftime("%Y-%m-%d"))
