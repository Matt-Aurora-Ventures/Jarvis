# Local Claude Code with Ollama - Server Setup Guide

Run Claude Code entirely on your own machine using local open-source models. Zero API costs, complete privacy.

## Quick Start (Copy-Paste Ready)

### 1. Install Ollama

**Windows:**
```powershell
# Download and run: https://ollama.ai/download/windows
# Or use winget:
winget install Ollama.Ollama
```

**Linux (VPS):**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

### 2. Pull Recommended Models

For Jarvis (needs strong code + reasoning):
```bash
# Best for high-RAM servers (16GB+ VRAM)
ollama pull qwen2.5-coder:32b

# Good balance (8GB+ VRAM)
ollama pull qwen2.5-coder:14b

# Lightweight (4GB VRAM)
ollama pull qwen2.5-coder:7b

# Tiny fallback (2GB VRAM)
ollama pull gemma:2b
```

Verify models:
```bash
ollama list
```

### 3. Configure Claude Code for Local Mode

**Method A: Environment Variables (Temporary)**
```bash
# Linux/Mac
export ANTHROPIC_BASE_URL="http://localhost:11434"
export ANTHROPIC_AUTH_TOKEN="ollama"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Windows PowerShell
$env:ANTHROPIC_BASE_URL = "http://localhost:11434"
$env:ANTHROPIC_AUTH_TOKEN = "ollama"
$env:CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = "1"
```

**Method B: Persistent Config (.env)**
Add to `.env` in project root:
```bash
# Ollama Local Mode
ANTHROPIC_BASE_URL=http://localhost:11434
ANTHROPIC_AUTH_TOKEN=ollama
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Model selection (optional, default is your pulled model)
OLLAMA_MODEL=qwen2.5-coder:14b
```

### 4. Launch Claude Code Locally

```bash
# Navigate to your project
cd /path/to/jarvis

# Launch with specific model
claude --model qwen2.5-coder:14b

# Or let it use default
claude
```

## For Jarvis ai_supervisor Integration

The `ai_supervisor` component can now use your local Ollama!

Add to `.env`:
```bash
# Enable AI Supervisor with Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
AI_SUPERVISOR_ENABLED=true
```

Restart supervisor:
```bash
python bots/supervisor.py
```

Check status:
```bash
curl http://127.0.0.1:8080/health
# Should show: "ai_supervisor": {"status": "healthy"}
```

## Model Recommendations by Use Case

| Use Case | Model | VRAM | Speed | Accuracy |
|----------|-------|------|-------|----------|
| **Production VPS** | qwen2.5-coder:32b | 16GB+ | Slow | Excellent |
| **Development** | qwen2.5-coder:14b | 8GB+ | Medium | Very Good |
| **Local Testing** | qwen2.5-coder:7b | 4GB | Fast | Good |
| **Low-Resource** | gemma:2b | 2GB | Very Fast | Basic |

## Testing Your Setup

### Test 1: Verify Ollama is Running
```bash
curl http://localhost:11434/api/tags
# Should return JSON with your models
```

### Test 2: Chat Test
```bash
ollama run qwen2.5-coder:14b "Write a Python function to reverse a string"
```

### Test 3: Claude Code Test
```bash
cd /tmp
mkdir test-claude-local
cd test-claude-local
claude --model qwen2.5-coder:14b

# Try: "Create a hello world FastAPI app"
```

## Multi-Server Setup

### VPS (Production)
```bash
# .env on VPS
ANTHROPIC_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:32b
AI_SUPERVISOR_ENABLED=true
```

### Local Dev (Windows)
```bash
# .env on local machine
ANTHROPIC_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b
AI_SUPERVISOR_ENABLED=true

# Use different tokens to avoid conflicts
TREASURY_BOT_TOKEN=<local_token>
PUBLIC_BOT_TELEGRAM_TOKEN=<local_public_token>
```

## Troubleshooting

### Issue: Claude still tries to connect to Anthropic servers
**Fix:**
```bash
# Logout first
claude logout

# Set env vars
export ANTHROPIC_BASE_URL="http://localhost:11434"
export ANTHROPIC_AUTH_TOKEN="ollama"

# Then launch
claude --model qwen2.5-coder:14b
```

### Issue: Ollama not responding
**Fix:**
```bash
# Check if running
curl http://localhost:11434/api/tags

# Restart Ollama
# Windows: Restart Ollama service
# Linux: sudo systemctl restart ollama
# Mac: brew services restart ollama
```

### Issue: Model not found
**Fix:**
```bash
# List available models
ollama list

# Pull missing model
ollama pull qwen2.5-coder:14b
```

### Issue: Out of memory
**Fix:**
```bash
# Use smaller model
ollama pull qwen2.5-coder:7b
claude --model qwen2.5-coder:7b

# Or switch to CPU mode (slower but works)
OLLAMA_NUM_GPU=0 ollama serve
```

## Performance Comparison

| Setup | Cost | Privacy | Speed | Quality |
|-------|------|---------|-------|---------|
| **Claude API (Opus)** | $15-60/day | ❌ Cloud | Fast | Excellent |
| **Local Ollama (32B)** | $0 | ✅ Local | Medium | Very Good |
| **Local Ollama (7B)** | $0 | ✅ Local | Fast | Good |

## Benefits of Local Setup

✅ **Zero API costs** - No usage fees
✅ **Complete privacy** - Code never leaves your machine  
✅ **No rate limits** - Use as much as you want
✅ **Offline capable** - Works without internet
✅ **Custom models** - Fine-tune for your needs

## Next Steps

1. Install Ollama on all servers (VPS + local)
2. Pull appropriate model for each (32B for VPS, 7B for local)
3. Update `.env` with Ollama configuration
4. Enable `ai_supervisor` component
5. Test with simple prompts
6. Gradually shift workloads to local models

## Resources

- Ollama: https://ollama.ai
- Qwen2.5-Coder: https://ollama.ai/library/qwen2.5-coder
- Claude Code Docs: https://docs.anthropic.com/en/docs/agents-and-agentic-systems/claude-code
