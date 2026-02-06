import time
import subprocess
from datetime import datetime

LOGS = [
    '/root/clawdbots/logs/friday.log',
    '/root/clawdbots/logs/matt.log',
    '/root/clawdbots/logs/jarvis.log'
]

def tail_log(path, lines=20):
    try:
        out = subprocess.check_output(['tail', f'-n', str(lines), path], stderr=subprocess.STDOUT)
        return out.decode('utf-8', errors='replace')
    except Exception as e:
        return f"ERROR reading {path}: {e}"

if __name__ == '__main__':
    while True:
        ts = datetime.utcnow().isoformat()
        report = [f"\n=== LOG WATCH {ts}Z ===\n"]
        for p in LOGS:
            report.append(f"--- {p} ---\n{tail_log(p, 15)}")
        print('\n'.join(report), flush=True)
        time.sleep(300)
