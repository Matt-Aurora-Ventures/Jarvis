#!/usr/bin/env python3
"""Wrapper to run emergency sellall with proper UTF-8 encoding on Windows"""
import sys
import subprocess

# Reconfigure stdout to use UTF-8
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Run the actual script
result = subprocess.run(
    [sys.executable, "scripts/emergency_sellall_and_transfer.py"],
    env={**dict(os.environ), "PYTHONIOENCODING": "utf-8"},
    capture_output=False
)

sys.exit(result.returncode)
