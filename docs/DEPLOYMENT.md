# JARVIS - Deployment Guide

**Last Updated:** 2026-01-26
**Version:** V1.0 Production
**Target Environment:** Ubuntu 22.04 LTS

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [System Requirements](#system-requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Database Setup](#database-setup)
6. [Process Management](#process-management)
7. [Monitoring & Logging](#monitoring--logging)
8. [Security Hardening](#security-hardening)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services

- Ubuntu 22.04 LTS
- Python 3.11+
- PostgreSQL 15+ with TimescaleDB 2.13+
- Redis 7.2+
- Supervisor (process manager)
- Nginx (optional, for reverse proxy)

### API Keys Required

```bash
# Solana RPC Providers
HELIUS_API_KEY=...
QUICKNODE_API_KEY=...
ALCHEMY_API_KEY=...

# Trading Platforms
BAGS_API_KEY=...
BITQUERY_API_KEY=...

# AI/ML
XAI_API_KEY=...          # Grok AI

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_BUY_BOT_CHAT_ID=...

# Twitter/X (Optional)
TWITTER_BEARER_TOKEN=...
JARVIS_ACCESS_TOKEN=...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/jarvis_core
REDIS_URL=redis://localhost:6379
```

---

## System Requirements

### Minimum Specifications

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Storage | 20 GB SSD | 50 GB SSD |
| Network | 10 Mbps | 100 Mbps |

### Estimated Resource Usage

```
Memory Usage:
  - Python processes: 500 MB - 1 GB
  - PostgreSQL: 1-2 GB
  - Redis: 200-500 MB
  Total: ~2-4 GB

Storage Usage:
  - Application code: 500 MB
  - Database: 1-5 GB (grows over time)
  - Logs: 100 MB/day (with rotation)
  - Backups: 2x database size

Network Usage:
  - WebSocket (Geyser): 100-500 KB/s
  - RPC calls: 10-50 KB/s
  - API calls: 5-20 KB/s
  Total: ~200 KB/s average
```

---

## Installation

### 1. System Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    postgresql-15 \
    redis-server \
    supervisor \
    nginx \
    build-essential \
    libpq-dev

# Install TimescaleDB
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt update
sudo apt install -y timescaledb-2-postgresql-15
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 2. Clone Repository

```bash
# Create jarvis user
sudo useradd -m -s /bin/bash jarvis
sudo su - jarvis

# Clone repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis
```

### 3. Python Environment

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

### 4. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Check PostgreSQL
psql --version    # Should be 15+

# Check Redis
redis-cli --version

# Check TimescaleDB
psql -U postgres -c "SELECT extversion FROM pg_extension WHERE extname='timescaledb';"
```

---

## Configuration

### 1. Environment Variables

**Create `.env` file:**

```bash
cd ~/jarvis
cp .env.example .env
nano .env
```

**Required Variables:**

```bash
# ============================================
# CORE CONFIGURATION
# ============================================
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# ============================================
# DATABASE CONFIGURATION
# ============================================
DATABASE_URL=postgresql://jarvis:CHANGE_ME@localhost:5432/jarvis_core
REDIS_URL=redis://localhost:6379/0

# ============================================
# SOLANA RPC PROVIDERS
# ============================================
HELIUS_API_KEY=your_helius_api_key_here
QUICKNODE_API_KEY=your_quicknode_api_key_here
ALCHEMY_API_KEY=your_alchemy_api_key_here

# ============================================
# TRADING PLATFORMS
# ============================================
BAGS_API_KEY=your_bags_api_key_here
BITQUERY_API_KEY=your_bitquery_api_key_here

# ============================================
# AI/ML SERVICES
# ============================================
XAI_API_KEY=your_xai_api_key_here
GROK_DAILY_COST_LIMIT=10.0  # $10/day

# ============================================
# TELEGRAM BOT
# ============================================
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_BUY_BOT_CHAT_ID=your_chat_id_here

# ============================================
# TWITTER/X (OPTIONAL)
# ============================================
TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
JARVIS_ACCESS_TOKEN=your_jarvis_access_token_here
X_BOT_ENABLED=true

# ============================================
# TRADING CONFIGURATION
# ============================================
TREASURY_LIVE_MODE=true
MAX_POSITION_SIZE_USD=500
MAX_DAILY_LOSS_USD=1000
MAX_OPEN_POSITIONS=50
DEFAULT_STOP_LOSS_PCT=10.0
DEFAULT_TAKE_PROFIT_PCT=20.0

# ============================================
# SECURITY
# ============================================
SECRET_KEY=CHANGE_ME_TO_RANDOM_STRING
JWT_SECRET=CHANGE_ME_TO_RANDOM_STRING
```

**Generate secure keys:**

```bash
# Generate random secret keys
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Use output for SECRET_KEY and JWT_SECRET
```

### 2. Wallet Configuration

**IMPORTANT: Never commit wallet private keys to git!**

```bash
# Create wallet directory (outside git repo)
mkdir -p ~/.lifeos/wallets

# Generate new wallet (or import existing)
# Use Solana CLI: solana-keygen new -o ~/.lifeos/wallets/treasury.json

# Set permissions (owner read-only)
chmod 400 ~/.lifeos/wallets/treasury.json

# Configure wallet path in .env
echo "WALLET_PATH=/home/jarvis/.lifeos/wallets/treasury.json" >> .env
```

---

## Database Setup

### 1. PostgreSQL Database Creation

```bash
# Switch to postgres user
sudo su - postgres

# Create jarvis user
createuser jarvis --pwprompt
# Enter password when prompted

# Create databases
createdb -O jarvis jarvis_core
createdb -O jarvis jarvis_analytics

# Enable TimescaleDB extension
psql -d jarvis_analytics -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Exit postgres user
exit
```

### 2. Initialize Schema

```bash
# Activate virtual environment
cd ~/jarvis
source .venv/bin/activate

# Run migrations
python scripts/migrate_databases.py --verify
python scripts/migrate_databases.py --execute

# Verify tables created
psql -U jarvis -d jarvis_core -c "\dt"
psql -U jarvis -d jarvis_analytics -c "\dt"
```

### 3. Create Hypertables (TimescaleDB)

```bash
# Create hypertables for time-series data
psql -U jarvis -d jarvis_analytics <<EOF
-- Performance metrics (1-day chunks)
SELECT create_hypertable('performance_metrics', 'time', chunk_time_interval => INTERVAL '1 day');

-- Token prices (1-hour chunks)
SELECT create_hypertable('token_prices', 'time', chunk_time_interval => INTERVAL '1 hour');

-- Sentiment scores (1-hour chunks)
SELECT create_hypertable('sentiment_scores', 'time', chunk_time_interval => INTERVAL '1 hour');

-- Enable compression (data older than 7 days)
SELECT add_compression_policy('performance_metrics', INTERVAL '7 days');
SELECT add_compression_policy('token_prices', INTERVAL '7 days');
SELECT add_compression_policy('sentiment_scores', INTERVAL '7 days');

-- Verify hypertables
SELECT * FROM timescaledb_information.hypertables;
EOF
```

### 4. Redis Configuration

```bash
# Edit Redis config
sudo nano /etc/redis/redis.conf

# Recommended settings:
# maxmemory 512mb
# maxmemory-policy allkeys-lru
# save 900 1
# save 300 10
# save 60 10000

# Restart Redis
sudo systemctl restart redis-server
```

---

## Process Management

### 1. Supervisor Configuration

**Install Supervisor:**

```bash
sudo apt install -y supervisor
```

**Create supervisor config:**

```bash
sudo nano /etc/supervisor/conf.d/jarvis.conf
```

**Configuration:**

```ini
[group:jarvis]
programs=jarvis-telegram,jarvis-twitter,jarvis-bags-intel,jarvis-api

[program:jarvis-telegram]
command=/home/jarvis/jarvis/.venv/bin/python bots/supervisor.py
directory=/home/jarvis/jarvis
user=jarvis
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stopasgroup=true
killasgroup=true
stdout_logfile=/var/log/jarvis/telegram.log
stderr_logfile=/var/log/jarvis/telegram.err
environment=PYTHONUNBUFFERED="1"

[program:jarvis-twitter]
command=/home/jarvis/jarvis/.venv/bin/python bots/twitter/autonomous_engine.py
directory=/home/jarvis/jarvis
user=jarvis
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stdout_logfile=/var/log/jarvis/twitter.log
stderr_logfile=/var/log/jarvis/twitter.err
environment=PYTHONUNBUFFERED="1"

[program:jarvis-bags-intel]
command=/home/jarvis/jarvis/.venv/bin/python bots/bags_intel/monitor.py
directory=/home/jarvis/jarvis
user=jarvis
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stdout_logfile=/var/log/jarvis/bags-intel.log
stderr_logfile=/var/log/jarvis/bags-intel.err
environment=PYTHONUNBUFFERED="1"

[program:jarvis-api]
command=/home/jarvis/jarvis/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
directory=/home/jarvis/jarvis
user=jarvis
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stdout_logfile=/var/log/jarvis/api.log
stderr_logfile=/var/log/jarvis/api.err
environment=PYTHONUNBUFFERED="1"
```

### 2. Create Log Directory

```bash
# Create log directory
sudo mkdir -p /var/log/jarvis
sudo chown jarvis:jarvis /var/log/jarvis
```

### 3. Start Services

```bash
# Reload supervisor config
sudo supervisorctl reread
sudo supervisorctl update

# Start all services
sudo supervisorctl start jarvis:*

# Check status
sudo supervisorctl status
```

**Expected Output:**
```
jarvis-api                       RUNNING   pid 12345, uptime 0:00:10
jarvis-bags-intel                RUNNING   pid 12346, uptime 0:00:10
jarvis-telegram                  RUNNING   pid 12347, uptime 0:00:10
jarvis-twitter                   RUNNING   pid 12348, uptime 0:00:10
```

### 4. Service Management Commands

```bash
# Stop all services
sudo supervisorctl stop jarvis:*

# Restart specific service
sudo supervisorctl restart jarvis-telegram

# View logs
sudo supervisorctl tail -f jarvis-telegram

# Restart all after code update
sudo supervisorctl restart jarvis:*
```

---

## Monitoring & Logging

### 1. Log Rotation

**Create logrotate config:**

```bash
sudo nano /etc/logrotate.d/jarvis
```

**Configuration:**

```
/var/log/jarvis/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 jarvis jarvis
    sharedscripts
    postrotate
        /usr/bin/supervisorctl restart jarvis:* > /dev/null 2>&1 || true
    endscript
}
```

### 2. Health Check Endpoint

**Test health endpoint:**

```bash
curl http://localhost:8000/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": true,
    "redis": true,
    "rpc": true,
    "geyser": true
  },
  "timestamp": "2026-01-26T12:34:56Z"
}
```

### 3. Automated Health Monitoring

**Create health check script:**

```bash
nano ~/jarvis/scripts/health_check.sh
```

```bash
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
TELEGRAM_ALERT_CHAT_ID="your_admin_chat_id"

response=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$response" != "200" ]; then
    echo "JARVIS health check failed! Status: $response"
    # Send Telegram alert
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_ALERT_CHAT_ID" \
        -d "text=🚨 JARVIS health check failed! Status: $response"
fi
```

**Schedule health checks (cron):**

```bash
crontab -e

# Add health check every 5 minutes
*/5 * * * * /home/jarvis/jarvis/scripts/health_check.sh
```

### 4. Prometheus Metrics (Optional)

**Expose metrics endpoint:**

```python
# Already implemented in api/main.py
from prometheus_client import make_asgi_app

# Mount Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())
```

**Scrape metrics:**

```bash
curl http://localhost:8000/metrics
```

---

## Security Hardening

### 1. Firewall Configuration

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH (if remote)
sudo ufw allow ssh

# Allow API (if needed externally)
# sudo ufw allow 8000/tcp

# Allow PostgreSQL (only from localhost)
sudo ufw deny 5432/tcp

# Allow Redis (only from localhost)
sudo ufw deny 6379/tcp

# Check status
sudo ufw status
```

### 2. PostgreSQL Security

```bash
# Edit pg_hba.conf
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Ensure local connections only:
# local   all   jarvis   scram-sha-256
# host    all   jarvis   127.0.0.1/32   scram-sha-256

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### 3. File Permissions

```bash
# Secure wallet files
chmod 400 ~/.lifeos/wallets/*.json

# Secure .env file
chmod 600 ~/jarvis/.env

# Secure log files
sudo chown -R jarvis:jarvis /var/log/jarvis
chmod 640 /var/log/jarvis/*.log
```

### 4. SSL/TLS (Optional - API)

**Using Nginx reverse proxy:**

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com

# Nginx config
sudo nano /etc/nginx/sites-available/jarvis
```

```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /metrics {
        deny all;  # Block public access to metrics
    }
}
```

---

## Backup & Recovery

### 1. Database Backups

**Automated backup script:**

```bash
nano ~/jarvis/scripts/backup_db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/jarvis/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
pg_dump -U jarvis jarvis_core | gzip > "$BACKUP_DIR/jarvis_core_$DATE.sql.gz"
pg_dump -U jarvis jarvis_analytics | gzip > "$BACKUP_DIR/jarvis_analytics_$DATE.sql.gz"

# Backup Redis
redis-cli --rdb "$BACKUP_DIR/redis_$DATE.rdb"

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +30 -delete

echo "Backup completed: $DATE"
```

**Schedule backups (cron):**

```bash
crontab -e

# Daily backup at 2 AM
0 2 * * * /home/jarvis/jarvis/scripts/backup_db.sh
```

### 2. Recovery Process

**Restore PostgreSQL:**

```bash
# Stop services
sudo supervisorctl stop jarvis:*

# Restore database
gunzip -c /home/jarvis/backups/jarvis_core_20260126_020000.sql.gz | psql -U jarvis jarvis_core
gunzip -c /home/jarvis/backups/jarvis_analytics_20260126_020000.sql.gz | psql -U jarvis jarvis_analytics

# Start services
sudo supervisorctl start jarvis:*
```

**Restore Redis:**

```bash
# Stop Redis
sudo systemctl stop redis-server

# Copy RDB file
sudo cp /home/jarvis/backups/redis_20260126_020000.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# Start Redis
sudo systemctl start redis-server
```

---

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

**Check logs:**
```bash
sudo supervisorctl tail jarvis-telegram stderr
```

**Common causes:**
- Missing environment variables
- Database connection failure
- Port already in use
- Python dependency issues

**Solution:**
```bash
# Verify .env file
cat ~/jarvis/.env | grep -v "^#" | grep -v "^$"

# Test database connection
psql -U jarvis -d jarvis_core -c "SELECT 1;"

# Check port availability
sudo netstat -tlnp | grep 8000
```

#### 2. Database Connection Errors

**Error:** `psycopg2.OperationalError: FATAL: password authentication failed`

**Solution:**
```bash
# Reset PostgreSQL password
sudo -u postgres psql
ALTER USER jarvis WITH PASSWORD 'new_password';
\q

# Update .env
nano ~/jarvis/.env
# DATABASE_URL=postgresql://jarvis:new_password@localhost:5432/jarvis_core
```

#### 3. Redis Connection Errors

**Error:** `redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379`

**Solution:**
```bash
# Check Redis status
sudo systemctl status redis-server

# Start Redis if stopped
sudo systemctl start redis-server

# Test connection
redis-cli ping
# Should return: PONG
```

#### 4. RPC Provider Failures

**Error:** `All RPC providers unhealthy`

**Solution:**
```bash
# Check API keys
env | grep API_KEY

# Test RPC endpoints
curl -X POST https://mainnet.helius-rpc.com/?api-key=YOUR_KEY \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"getSlot"}'
```

#### 5. High Memory Usage

**Symptoms:** Process killed by OOM

**Solution:**
```bash
# Check memory usage
free -h

# Reduce PostgreSQL shared_buffers
sudo nano /etc/postgresql/15/main/postgresql.conf
# shared_buffers = 128MB

# Restart PostgreSQL
sudo systemctl restart postgresql

# Limit Python workers
# In supervisor config:
# environment=WORKERS="2"
```

### Debug Mode

**Enable debug logging:**

```bash
# Edit .env
nano ~/jarvis/.env
LOG_LEVEL=DEBUG

# Restart services
sudo supervisorctl restart jarvis:*

# Monitor logs
sudo supervisorctl tail -f jarvis-telegram
```

---

## Upgrade Process

### 1. Pull Latest Code

```bash
cd ~/jarvis
git pull origin main
```

### 2. Update Dependencies

```bash
source .venv/bin/activate
pip install -r requirements.txt --upgrade
```

### 3. Run Migrations

```bash
python scripts/migrate_databases.py --verify
python scripts/migrate_databases.py --execute
```

### 4. Restart Services

```bash
sudo supervisorctl restart jarvis:*
```

### 5. Verify

```bash
# Check health
curl http://localhost:8000/health

# Check logs
sudo supervisorctl tail jarvis-telegram
```

---

## Production Checklist

**Before going live:**

- [ ] All environment variables configured
- [ ] Wallet file secured (chmod 400)
- [ ] Database backups scheduled (cron)
- [ ] Log rotation configured
- [ ] Firewall rules applied
- [ ] SSL/TLS configured (if public API)
- [ ] Health monitoring active
- [ ] Test trade executed successfully
- [ ] Alert system configured (Telegram)
- [ ] Documentation reviewed
- [ ] Recovery plan tested

---

**Related Documentation:**
- [Features Overview](./FEATURES.md)
- [Architecture](./ARCHITECTURE.md)
- [API Improvements](./API_IMPROVEMENTS.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
