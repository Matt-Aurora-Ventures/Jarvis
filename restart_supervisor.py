"""Restart the JARVIS supervisor to apply code changes."""
import psutil
import subprocess
import sys
import time
from pathlib import Path

def find_supervisor():
    """Find the supervisor.py process."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info.get('cmdline', [])
            if cmdline and 'supervisor.py' in ' '.join(cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def main():
    print("Restarting JARVIS supervisor...")
    print()

    # Find supervisor process
    supervisor = find_supervisor()

    if supervisor:
        print(f"[OK] Found supervisor process (PID: {supervisor.pid})")
        print("[*] Stopping supervisor...")

        try:
            supervisor.terminate()
            supervisor.wait(timeout=10)
            print("[OK] Supervisor stopped gracefully")
        except psutil.TimeoutExpired:
            print("[!] Graceful stop timed out, forcing...")
            supervisor.kill()
            print("[OK] Supervisor forcefully stopped")
        except Exception as e:
            print(f"[ERR] Error stopping supervisor: {e}")
            return 1

        # Wait a moment for cleanup
        time.sleep(2)
    else:
        print("[i] No supervisor process found (may already be stopped)")

    # Start supervisor
    print()
    print("[*] Starting supervisor...")

    supervisor_path = Path(__file__).parent / "bots" / "supervisor.py"

    # Start in background
    subprocess.Popen(
        [sys.executable, str(supervisor_path)],
        cwd=Path(__file__).parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    )

    print("[OK] Supervisor started")
    print()
    print("Brand guide changes now active:")
    print("  [OK] Twitter bot using full JARVIS_VOICE_BIBLE")
    print("  [OK] Telegram bot using full JARVIS_VOICE_BIBLE")
    print()
    print("Monitor supervisor.log for startup confirmation.")

    return 0

if __name__ == "__main__":
    sys.exit(main())
