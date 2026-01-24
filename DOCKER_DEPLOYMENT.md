# Jarvis Docker Deployment Guide

**Last Updated**: 2026-01-24

Complete guide for deploying Jarvis bot system using Docker multi-container architecture.

---

## Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- 8GB+ RAM on host machine
- Secrets configured in `secrets/keys.json`

---

## Architecture Overview

### Multi-Container Design

Each service runs in its own isolated container:

| Service | Container | Purpose | Resources |
|---------|-----------|---------|-----------|
| `supervisor` | jarvis-supervisor | Health monitoring & orchestration | 1 CPU / 2GB RAM |
| `telegram-bot` | jarvis-telegram-bot | Main Telegram interface | 1 CPU / 2GB RAM |
| `buy-tracker` | jarvis-buy-tracker | KR8TIV token tracking | 1 CPU / 2GB RAM |
| `twitter-bot` | jarvis-twitter-bot | Autonomous X posting | 0.5 CPU / 1GB RAM |
| `treasury` | jarvis-treasury | Trading engine | 1 CPU / 3GB RAM |
| `sentiment-reporter` | jarvis-sentiment-reporter | Market sentiment analysis | 0.5 CPU / 1GB RAM |
| `bags-intel` | jarvis-bags-intel | Bags.fm monitoring (optional) | 0.5 CPU / 1GB RAM |
| `redis` | jarvis-redis | Shared cache & state | 0.5 CPU / 256MB RAM |

**Total Resources Required**: ~6 CPUs, ~12GB RAM for full deployment

---

## Quick Start

### 1. Configure Environment

```bash
# Copy environment template
cp .env.multi.example .env

# Edit .env with your actual credentials
nano .env
```

**Required Variables**:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_ADMIN_IDS` - Comma-separated admin user IDs
- `TELEGRAM_BUY_BOT_CHAT_ID` - Chat ID for buy alerts
- `XAI_API_KEY` - Grok AI API key
- `ANTHROPIC_API_KEY` - Claude AI API key
- `HELIUS_API_KEY` - Solana RPC API key

### 2. Start Core Services

```bash
# Start all core services (telegram, buy-tracker, twitter, treasury, sentiment)
docker-compose -f docker-compose-multi.yml up -d

# View logs
docker-compose -f docker-compose-multi.yml logs -f

# View specific service logs
docker-compose -f docker-compose-multi.yml logs -f telegram-bot
```

### 3. Verify Services

```bash
# Check running containers
docker ps | grep jarvis

# Check health
curl http://localhost:8080/health

# View service status
docker-compose -f docker-compose-multi.yml ps
```

---

## Deployment Options

### Core Deployment (Default)

```bash
docker-compose -f docker-compose-multi.yml up -d
```

**Starts**:
- supervisor
- telegram-bot
- buy-tracker
- twitter-bot
- treasury
- sentiment-reporter
- redis

### Full Deployment (with Bags Intel)

```bash
docker-compose -f docker-compose-multi.yml --profile full up -d
```

**Adds**:
- bags-intel (bags.fm graduation monitoring)

### Monitoring Deployment

```bash
docker-compose -f docker-compose-multi.yml --profile monitoring up -d
```

**Adds**:
- prometheus (metrics collection)
- grafana (dashboards at http://localhost:3001)

### Combined Deployment

```bash
docker-compose -f docker-compose-multi.yml --profile full --profile monitoring up -d
```

**Starts all services** including bags-intel, prometheus, and grafana.

---

## VPS Deployment

### Step 1: Transfer Files

```bash
# From local machine
rsync -avz --progress \
  Dockerfile.* \
  docker-compose-multi.yml \
  .env.multi.example \
  requirements.txt \
  jarvis-vps:/home/jarvis/Jarvis/
```

### Step 2: Transfer Secrets

```bash
# Secure transfer of secrets
scp -r secrets/ jarvis-vps:/home/jarvis/Jarvis/
```

### Step 3: Configure Environment on VPS

```bash
# SSH to VPS
ssh jarvis-vps

# Navigate to project
cd /home/jarvis/Jarvis

# Create .env from example
cp .env.multi.example .env

# Edit with actual credentials
nano .env
```

### Step 4: Build and Start

```bash
# Build all images
docker-compose -f docker-compose-multi.yml build

# Start services
docker-compose -f docker-compose-multi.yml up -d

# Watch logs
docker-compose -f docker-compose-multi.yml logs -f
```

---

## Container Management

### Start/Stop Services

```bash
# Start all services
docker-compose -f docker-compose-multi.yml up -d

# Stop all services
docker-compose -f docker-compose-multi.yml down

# Stop specific service
docker-compose -f docker-compose-multi.yml stop telegram-bot

# Start specific service
docker-compose -f docker-compose-multi.yml start telegram-bot

# Restart specific service
docker-compose -f docker-compose-multi.yml restart twitter-bot
```

### View Logs

```bash
# All services (tail mode)
docker-compose -f docker-compose-multi.yml logs -f

# Specific service
docker-compose -f docker-compose-multi.yml logs -f buy-tracker

# Last 100 lines
docker-compose -f docker-compose-multi.yml logs --tail=100

# Since timestamp
docker-compose -f docker-compose-multi.yml logs --since=2h
```

### Update Services

```bash
# Pull latest code
git pull

# Rebuild specific service
docker-compose -f docker-compose-multi.yml build telegram-bot

# Restart with new image
docker-compose -f docker-compose-multi.yml up -d telegram-bot

# Or rebuild all and restart
docker-compose -f docker-compose-multi.yml build
docker-compose -f docker-compose-multi.yml up -d
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose-multi.yml logs <service-name>

# Check container status
docker-compose -f docker-compose-multi.yml ps

# Inspect container
docker inspect jarvis-<service-name>

# Execute shell in container
docker exec -it jarvis-telegram-bot /bin/bash
```

### Telegram Polling Conflicts

If you see "Conflict: terminated by other getUpdates request":

```bash
# 1. Stop all containers
docker-compose -f docker-compose-multi.yml down

# 2. Clear webhook on Telegram
curl -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook?drop_pending_updates=true"

# 3. Remove lock files
docker volume ls | grep jarvis
docker volume rm <lock-volume-if-exists>

# 4. Start containers
docker-compose -f docker-compose-multi.yml up -d
```

### Port Already in Use

```bash
# Check what's using the port
sudo lsof -i :8080

# Change port in .env
HEALTH_PORT=8081

# Restart
docker-compose -f docker-compose-multi.yml down
docker-compose -f docker-compose-multi.yml up -d
```

### Out of Memory

```bash
# Check container memory usage
docker stats

# Increase limits in docker-compose-multi.yml
# Edit resources.limits.memory for each service

# Restart
docker-compose -f docker-compose-multi.yml down
docker-compose -f docker-compose-multi.yml up -d
```

---

## Resource Monitoring

### View Resource Usage

```bash
# Real-time stats for all containers
docker stats

# Specific container
docker stats jarvis-telegram-bot

# Summary
docker-compose -f docker-compose-multi.yml top
```

### Disk Usage

```bash
# Check Docker disk usage
docker system df

# Check volumes
docker volume ls
du -sh /var/lib/docker/volumes/jarvis-*

# Clean up old images/containers
docker system prune -a
```

---

## Backup & Recovery

### Backup Persistent Data

```bash
# Backup all volumes
docker run --rm \
  -v jarvis-data:/data \
  -v jarvis-logs:/logs \
  -v jarvis-state:/state \
  -v $(pwd):/backup \
  alpine tar czf /backup/jarvis-backup-$(date +%Y%m%d).tar.gz /data /logs /state

# Backup to remote
scp jarvis-backup-*.tar.gz user@backup-server:/backups/
```

### Restore from Backup

```bash
# Extract backup
docker run --rm \
  -v jarvis-data:/data \
  -v jarvis-logs:/logs \
  -v jarvis-state:/state \
  -v $(pwd):/backup \
  alpine tar xzf /backup/jarvis-backup-20260124.tar.gz -C /
```

---

## Security Best Practices

1. **Never commit .env** - Keep credentials in `.env` file, not in version control
2. **Use read-only mounts** - Secrets are mounted `:ro` (read-only)
3. **Network isolation** - All services communicate over private `jarvis-network`
4. **Resource limits** - Each container has CPU and memory limits
5. **Health checks** - Services auto-restart on failure
6. **Logging limits** - Log rotation prevents disk fill

---

## Migration from Non-Docker Setup

### 1. Export Current State

```bash
# On VPS (non-Docker)
# Copy state files
cp -r ~/.lifeos /tmp/lifeos-backup
cp -r bots/buy_tracker/.positions.json /tmp/
cp -r bots/twitter/.grok_state.json /tmp/
```

### 2. Stop Non-Docker Services

```bash
# Kill supervisor
pkill -f supervisor.py

# Verify stopped
ps aux | grep python
```

### 3. Start Docker Services

```bash
# Start Docker deployment
docker-compose -f docker-compose-multi.yml up -d

# Verify
docker ps
```

### 4. Restore State (if needed)

```bash
# Copy state into Docker volumes
docker cp /tmp/lifeos-backup jarvis-telegram-bot:/root/.lifeos
docker cp /tmp/.positions.json jarvis-buy-tracker:/app/bots/buy_tracker/
docker cp /tmp/.grok_state.json jarvis-twitter-bot:/app/bots/twitter/

# Restart containers
docker-compose -f docker-compose-multi.yml restart
```

---

## Performance Tuning

### Optimize Redis

```bash
# Edit docker-compose-multi.yml
# Increase maxmemory for Redis if needed:
command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

### Scale Resources

```bash
# Increase resources for specific service
# Edit docker-compose-multi.yml
deploy:
  resources:
    limits:
      cpus: '2.0'       # Increase from 1.0
      memory: 4G        # Increase from 2G
```

---

## Monitoring with Grafana

### Access Grafana

1. Start monitoring stack: `docker-compose -f docker-compose-multi.yml --profile monitoring up -d`
2. Open browser: http://localhost:3001 (or http://your-vps-ip:3001)
3. Login: admin / admin (change password immediately)

### Import Dashboards

1. Click "+" → "Import"
2. Use dashboard ID `1860` (Node Exporter Full)
3. Select Prometheus data source
4. Click "Import"

---

## Next Steps

After successful deployment:

1. ✅ Verify all services are running: `docker ps`
2. ✅ Check logs for errors: `docker-compose -f docker-compose-multi.yml logs -f`
3. ✅ Test Telegram bot: Send `/start` command
4. ✅ Verify X bot: Check @Jarvis_lifeos timeline
5. ✅ Monitor resource usage: `docker stats`
6. ✅ Set up backups: Configure automated backup script
7. ✅ Configure monitoring: Set up Grafana dashboards

---

## Support

- Documentation: `/docs` directory
- Error Knowledge Base: `docs/ERROR_KNOWLEDGE_BASE.md`
- Logs: `docker-compose -f docker-compose-multi.yml logs <service>`

