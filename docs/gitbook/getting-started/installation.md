# Installation & Quick Start

Get Jarvis up and running on your local machine or VPS in minutes.

---

## Prerequisites

Before installing Jarvis, ensure you have:

- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Solana CLI** ([Installation Guide](https://docs.solana.com/cli/install-solana-cli-tools))
- **PostgreSQL 16+** ([Download](https://www.postgresql.org/download/))
- **Node.js 18+** (for frontend) ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/downloads))

### Optional (Recommended)

- **Ollama** for local LLM inference ([Download](https://ollama.ai))
- **Redis** for caching ([Download](https://redis.io/download))
- **Docker** for containerized deployment ([Download](https://docker.com))

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Matt-Aurora-Ventures/Jarvis.git
cd Jarvis
```

### 2. Install Python Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

**Required Variables**:
```env
# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
HELIUS_API_KEY=your_helius_key

# Trading
XAI_API_KEY=your_grok_api_key
TREASURY_LIVE_MODE=false  # Set to true for live trading

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_BUY_BOT_CHAT_ID=your_chat_id

# Twitter/X
TWITTER_BEARER_TOKEN=your_twitter_token
JARVIS_ACCESS_TOKEN=your_twitter_oauth

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/jarvis

# Optional
BITQUERY_API_KEY=your_bitquery_key  # For bags.fm monitoring
COINGECKO_API_KEY=your_coingecko_key
```

### 4. Initialize the Database

```bash
# Create database
createdb jarvis

# Run migrations
python scripts/init_db.py
```

### 5. Create Wallets

```bash
# Run wallet setup script
python scripts/setup_vps_wallets.py

# Follow prompts to create:
# - Treasury wallet
# - Active trading wallet
# - Profit wallet
```

The script will generate encrypted wallets in `wallets/.wallets/` and save the password to your `.env` file.

### 6. Run the Supervisor

The supervisor manages all bot components:

```bash
python bots/supervisor.py
```

You should see output like:
```
[INFO] Starting Jarvis Supervisor v4.6.5
[INFO] Components: telegram, treasury, twitter, sentiment
[INFO] Health check interval: 60 seconds
[INFO] All systems online
```

---

## Running Individual Components

You can also run components independently for development:

### Trading Bot Only

```bash
python bots/treasury/trading.py
```

### Telegram Bot Only

```bash
python tg_bot/bot.py
```

### Twitter/X Bot Only

```bash
python bots/twitter/autonomous_engine.py
```

### Sentiment Reporter Only

```bash
python bots/buy_tracker/sentiment_report.py
```

### Bags Intel Monitor Only

```bash
python bots/bags_intel/bags_intel_bot.py
```

---

## Optional: Install Ollama for Local LLM

For local, private LLM inference:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull models
ollama pull qwen3:8b
ollama pull llama3.1:8b

# Jarvis will auto-detect and use local models
```

---

## Docker Deployment

For a containerized setup:

```bash
# Build Docker image
docker build -t jarvis:latest .

# Run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f
```

---

## Systemd Service (Linux Production)

For production VPS deployment:

```bash
# Copy service file
sudo cp systemd/jarvis-supervisor.service /etc/systemd/system/

# Enable and start
sudo systemctl enable jarvis-supervisor
sudo systemctl start jarvis-supervisor

# Check status
sudo systemctl status jarvis-supervisor

# View logs
sudo journalctl -u jarvis-supervisor -f
```

---

## Verification

### Check System Health

```bash
# Via API
curl http://localhost:8080/health

# Via Telegram
# Send /status to @Jarviskr8tivbot
```

### Run Tests

```bash
# Run full test suite
pytest tests/ -v

# Expected: 1200+ tests passing
```

### View Dashboard

Open browser to:
```
http://localhost:8080
```

---

## Troubleshooting

### Common Issues

**1. Database Connection Error**

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify DATABASE_URL in .env
echo $DATABASE_URL
```

**2. Ollama Not Found**

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it:
ollama serve
```

**3. Wallet Password Error**

```bash
# Check .env has JARVIS_WALLET_PASSWORD
grep JARVIS_WALLET_PASSWORD .env

# If missing, re-run wallet setup:
python scripts/setup_vps_wallets.py
```

**4. Telegram Bot Not Responding**

```bash
# Check token is correct
grep TELEGRAM_BOT_TOKEN .env

# Verify bot is running
ps aux | grep "tg_bot/bot.py"
```

---

## Next Steps

✅ Installation complete! Now you can:

- **Fund your treasury wallet** to enable live trading
- **Configure trading strategies** in `bots/treasury/trading.py`
- **Customize risk parameters** in `.env`
- **Explore the dashboard** at http://localhost:8080
- **Join the community** on [Telegram](https://t.me/Jarviskr8tivbot)

**Ready to dive deeper?** → [Architecture Overview](../architecture/overview.md)

**Want to start trading?** → [Trading Guide](../trading/overview.md)

---

## Support

Need help?

- **Documentation**: [docs.jarvislife.io](#)
- **GitHub Issues**: [Report a bug](https://github.com/Matt-Aurora-Ventures/Jarvis/issues)
- **Telegram**: [@Jarviskr8tivbot](https://t.me/Jarviskr8tivbot)
- **Twitter**: [@Jarvis_lifeos](https://twitter.com/Jarvis_lifeos)
