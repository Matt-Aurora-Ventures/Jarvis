import subprocess
import os
import sys

urls = [
    "https://notebooklm.google.com/notebook/cfd9d32c-4d31-432c-a5dd-807805467705",
    "https://notebooklm.google.com/notebook/33098fc6-903a-4ed9-9c1d-394310d98cbb",
    "https://notebooklm.google.com/notebook/a48dd50e-d59b-470a-a5d3-290199cbc53a",
    "https://notebooklm.google.com/notebook/8f416fa8-3633-4347-9361-56d5d6dd39c9",
    "https://notebooklm.google.com/notebook/f63346c4-0a4d-45c6-9796-226568e6e23d"
]

script_path = r"c:\Users\lucid\.gemini\antigravity\skills\notebooklm\scripts\run.py"
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

with open("notebook_insights_phase3.txt", "w", encoding="utf-8") as f:
    for i, url in enumerate(urls, 1):
        question = "What does this notebook contain regarding Phase 3: Specialized Snipers? Specifically looking for technical details, python code samples, API endpoints, logic flows, dependencies and structural requirements for the Alvara Protocol (ERC-7621) Grok-managed basket integration, and the Solana 'TradFi Options' data triggers strategy execution."
        cmd = [sys.executable, script_path, "ask_question.py", "--question", question, "--notebook-url", url]
        print(f"Querying Notebook {i}/5 for Phase 3...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
            f.write(f"\n\n=== Notebook {i}: {url} ===\n")
            f.write(result.stdout)
            if result.stderr:
                f.write("\n-- STDERR --\n" + result.stderr)
        except Exception as e:
            f.write(f"\n\n=== ERROR on {url} ===\n{str(e)}\n\n")

print("Finished querying all notebooks for Phase 3. Results written to notebook_insights_phase3.txt")
