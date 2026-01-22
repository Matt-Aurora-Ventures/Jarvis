# JARVIS Runbook

## Local Setup (Windows/macOS/Linux)

1) Create/activate a virtualenv and install dependencies.

```bash
python -m venv .venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
pip install -r tg_bot/requirements.txt
```

2) Create a `.env` file (copy from `env.example`) and set required keys.

3) Optional: enable local LLM (Ollama) for Anthropic-compatible calls.

```bash
# Install Ollama (https://ollama.com)
# Pull a model (example)
ollama pull qwen3-coder

# .env
ANTHROPIC_API_KEY=ollama
ANTHROPIC_BASE_URL=http://localhost:11434/v1
OLLAMA_ANTHROPIC_BASE_URL=http://localhost:11434/v1
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder
CLAUDE_USE_API_MODE=true
AI_RUNTIME_ENABLED=true
AI_RUNTIME_MODEL=qwen3-coder
```

Notes:
- `ANTHROPIC_BASE_URL` routes Anthropic SDK calls to your local Ollama.
- `OLLAMA_ANTHROPIC_BASE_URL` is preferred when set (same endpoint).
- `CLAUDE_USE_API_MODE=true` makes `/code` and `/dev` use the API path (no CLI required).
- `AI_RUNTIME_ENABLED=true` enables optional per-component AI sidecars (fail-open).
- If you prefer CLI, install Claude Code and set `CLAUDE_CLI_PATH`.

### Claude Code + Ollama (local or VPS)

- Claude Code used to cost $3-$15 per million tokens; now it can run locally with open-source models.
- January 16, 2026: Ollama 0.14.0 became compatible with Anthropic's Messages API.
- Claude Code can run against any local Ollama model (zero ongoing costs; code stays local).
- Suggested models: qwen3-coder (everyday tasks), gpt-oss-20b (complex).

Quick setup:

```bash
ollama pull qwen3-coder
# Install Claude Code (see your installer)
```

Windows (PowerShell):

```bash
$env:ANTHROPIC_BASE_URL="http://localhost:11434/v1"
$env:OLLAMA_ANTHROPIC_BASE_URL="http://localhost:11434/v1"
$env:ANTHROPIC_API_KEY="ollama"
$env:CLAUDE_USE_API_MODE="true"
$env:AI_RUNTIME_ENABLED="true"
$env:AI_RUNTIME_MODEL="qwen3-coder"
claude --model qwen3-coder
```

Linux/macOS:

```bash
export ANTHROPIC_BASE_URL="http://localhost:11434/v1"
export OLLAMA_ANTHROPIC_BASE_URL="http://localhost:11434/v1"
export ANTHROPIC_API_KEY="ollama"
export CLAUDE_USE_API_MODE="true"
export AI_RUNTIME_ENABLED="true"
export AI_RUNTIME_MODEL="qwen3-coder"
claude --model qwen3-coder
```

4) Start components.

```bash
python tg_bot/cli.py start
python bots/twitter/run_autonomous.py
```

---

## VPS Setup (Ubuntu)

1) Install system deps and Python venv.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git curl
```

2) Install Ollama and pull a model.

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull qwen3-coder
```

3) Configure environment (systemd example).

Edit `/etc/default/jarvis-supervisor` (or your unit file `Environment=` block):

```bash
ANTHROPIC_API_KEY=ollama
ANTHROPIC_BASE_URL=http://localhost:11434/v1
OLLAMA_ANTHROPIC_BASE_URL=http://localhost:11434/v1
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder
CLAUDE_USE_API_MODE=true
AI_RUNTIME_ENABLED=true
AI_RUNTIME_MODEL=qwen3-coder
```

4) Restart services.

```bash
sudo systemctl daemon-reload
sudo systemctl restart jarvis-supervisor
sudo systemctl status jarvis-supervisor
```

5) Verify local LLM routing.

```bash
curl http://localhost:11434/api/tags
grep -i "ANTHROPIC_BASE_URL" /etc/default/jarvis-supervisor
```

---

## Local LLM Health Checks

```bash
python - <<'PY'
import os
print("ANTHROPIC_BASE_URL:", os.getenv("ANTHROPIC_BASE_URL"))
print("ANTHROPIC_API_KEY set:", bool(os.getenv("ANTHROPIC_API_KEY")))
PY
```

If `/code` or `/dev` reports API not configured, verify:
- `ANTHROPIC_API_KEY` is set (any non-empty string is fine for local)
- `ANTHROPIC_BASE_URL` points to your local endpoint
*** End Patch"}}锟 remains, adjust: since apply_patch freeform; must supply correct syntax. We'll re-run properly. Let's craft apply_patch with correct patch content. We'll include ASCII; avoid Unicode. Use simple text. We'll re-run. 
