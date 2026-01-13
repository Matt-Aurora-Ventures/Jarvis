#!/usr/bin/env python3
"""
Persistent bot runner - auto-restarts bots if they crash.
"""
import subprocess
import sys
import time
import os

# Change to Jarvis directory
JARVIS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(JARVIS_DIR)

BOTS = [
    {"name": "TG Bot", "cmd": [sys.executable, "tg_bot/bot.py"]},
    {"name": "Buy Tracker", "cmd": [sys.executable, "bots/buy_tracker/bot.py"]},
]

def run_bot(bot):
    """Run a bot and return the process."""
    print(f"[RUNNER] Starting {bot['name']}...")
    env = os.environ.copy()
    env["PYTHONPATH"] = JARVIS_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.Popen(
        bot["cmd"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

def main():
    print("=" * 50)
    print("JARVIS BOT RUNNER - Auto-restart enabled")
    print("=" * 50)

    processes = {}

    # Start all bots
    for bot in BOTS:
        processes[bot["name"]] = {"bot": bot, "proc": run_bot(bot), "restarts": 0}

    print(f"Started {len(processes)} bots. Monitoring...")

    try:
        while True:
            for name, data in processes.items():
                proc = data["proc"]

                # Check if process died
                if proc.poll() is not None:
                    data["restarts"] += 1
                    print(f"[RUNNER] {name} died (exit={proc.returncode}). Restart #{data['restarts']}")

                    # Wait a bit before restart
                    time.sleep(2)

                    # Restart
                    data["proc"] = run_bot(data["bot"])

                # Print any output
                try:
                    line = proc.stdout.readline()
                    if line:
                        print(f"[{name}] {line.rstrip()}")
                except:
                    pass

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n[RUNNER] Shutting down...")
        for name, data in processes.items():
            if data["proc"].poll() is None:
                data["proc"].terminate()
        print("[RUNNER] Done.")

if __name__ == "__main__":
    main()
