#!/usr/bin/env python3
"""
Development Server Runner.

Starts all necessary services for local development:
- FastAPI backend (port 8766)
- Flask legacy API (port 8765)
- Frontend dev server (port 3000/5173)
"""

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent


def run_command(name: str, cmd: list, cwd: Path = ROOT, env: dict = None):
    """Run a command in a subprocess."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    print(f"[{name}] Starting: {' '.join(cmd)}")
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def stream_output(procs: dict):
    """Stream output from all processes."""
    import select

    while any(p.poll() is None for p in procs.values()):
        for name, proc in procs.items():
            if proc.stdout and proc.poll() is None:
                line = proc.stdout.readline()
                if line:
                    print(f"[{name}] {line.decode().rstrip()}")
        time.sleep(0.01)


def main():
    procs = {}

    def cleanup(sig=None, frame=None):
        print("\nShutting down all services...")
        for name, proc in procs.items():
            if proc.poll() is None:
                print(f"[{name}] Stopping...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    print("=" * 60)
    print("JARVIS Development Server")
    print("=" * 60)

    # Load .env if exists
    env_file = ROOT / ".env"
    if env_file.exists():
        print(f"Loading environment from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

    # Start FastAPI
    procs["api"] = run_command(
        "api",
        [sys.executable, "-m", "uvicorn", "api.fastapi_app:app",
         "--host", "0.0.0.0", "--port", "8766", "--reload"],
        env={"PYTHONPATH": str(ROOT)},
    )

    # Start Flask (legacy)
    if os.getenv("ENABLE_FLASK", "false").lower() == "true":
        procs["flask"] = run_command(
            "flask",
            [sys.executable, "api/server.py"],
            env={"PYTHONPATH": str(ROOT)},
        )

    # Start frontend
    frontend_dir = ROOT / "frontend"
    if frontend_dir.exists() and (frontend_dir / "package.json").exists():
        procs["frontend"] = run_command(
            "frontend",
            ["npm", "run", "dev"],
            cwd=frontend_dir,
        )

    print("\nServices started:")
    print("  - FastAPI: http://localhost:8766")
    print("  - API Docs: http://localhost:8766/api/docs")
    if "flask" in procs:
        print("  - Flask: http://localhost:8765")
    if "frontend" in procs:
        print("  - Frontend: http://localhost:5173")
    print("\nPress Ctrl+C to stop all services\n")

    try:
        stream_output(procs)
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
