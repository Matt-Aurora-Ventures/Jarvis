"""Quick runner for investment service tests. Run: python run_inv_tests.py"""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "services/investments/tests/", "-v", "--tb=short"],
    cwd=r"c:\Users\lucid\Desktop\Jarvis",
    capture_output=True,
    text=True,
    timeout=120,
)
print(result.stdout)
if result.stderr:
    print(result.stderr)
sys.exit(result.returncode)
