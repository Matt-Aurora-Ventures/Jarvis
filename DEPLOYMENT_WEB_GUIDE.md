# Jarvis Web Demo - Production Deployment Guide

Complete guide for deploying the web demo app and bags monitor to your Hostinger VPS without interfering with existing bot services.

**Last Updated**: 2026-01-24

---

## Architecture Overview

### Deployed Services

| Service | URL | Container | Purpose |
|---------|-----|-----------|---------|
| **Web Demo UI** | `https://jarvislife.io/demo` | demo-frontend | Trading interface |
| **Backend API** | `https://jarvislife.io/api` | demo-backend | FastAPI server |
| **Bags Monitor** | `https://jarvislife.io/api/bags` | bags-monitor | Bags.fm tracking |
| **PostgreSQL** | Internal only | demo-postgres | Demo database |
| **Redis** | Internal only | demo-redis | Sessions & cache |

### Alternative URLs

- `https://demo.jarvislife.io` → Full app at subdomain
- `https://jarvislife.cloud/demo` → Redirect to main domain

### Network Isolation

```
┌─ Existing Bot Services ─────────────┐
│ jarvis-supervisor                   │
│ jarvis-telegram-bot                 │
│ jarvis-buy-tracker                  │
│ jarvis-twitter-bot                  │
│ jarvis-treasury                     │
│ Network: jarvis-network             │
└─────────────────────────────────────┘

┌─ Web Demo Services (NEW) ───────────┐
│ demo-frontend                       │
│ demo-backend                        │
│ bags-monitor                        │
│ demo-postgres                       │
│ demo-redis                          │
│ nginx                               │
│ Network: jarvis-web-network         │
└─────────────────────────────────────┘

No conflicts - separate networks!
```

---

## Prerequisites

### On Your Local Machine

1. ✅ SSH access to VPS
2. ✅ Git access to repository
3. ✅ SSH key from gitignore (`.env` or `secrets/`)

### On VPS

Already setup (from screenshot):
- ✅ Ubuntu 24.04 LTS
- ✅ Docker installed
- ✅ Root access
- ✅ SSH key added

Verify Docker:
```bash
ssh root@72.617.126  # Your VPS IP from screenshot
docker --version
docker-compose --version
```

Expected output:
```
Docker version 20.10+
Docker Compose version 2.0+
```

---

## Step 1: DNS Configuration

### Option A: Path-Based (Recommended - No DNS Changes)

Deploy at `jarvislife.io/demo` - works immediately, no DNS setup needed.

### Option B: Subdomain (Better UX)

1. Login to Hostinger DNS panel
2. Add A record:
   ```
   Type: A
   Name: demo
   Value: 72.617.126  # Your VPS IP
   TTL: 3600
   ```
3. Wait 5-60 minutes for propagation
4. Test: `ping demo.jarvislife.io`

---

## Step 2: Clone/Pull Latest Code on VPS

```bash
# SSH to VPS
ssh root@72.617.126

# Navigate to project (or clone if first time)
cd /root/Jarvis || git clone https://github.com/yourusername/Jarvis.git /root/Jarvis

# Pull latest changes
cd /root/Jarvis
git pull

# Verify files exist
ls -la docker-compose.web.yml nginx/web.conf
```

---

## Step 3: Configure Environment

### Copy and Edit Environment File

```bash
# Copy template
cp .env.web.example .env.web

# Edit with your values
nano .env.web
```

### Generate Strong Secrets

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate JWT_SECRET
openssl rand -hex 32

# Generate DB password
openssl rand -base64 32
```

### Minimal .env.web Configuration

**IMPORTANT**: You can reuse API keys from your existing `.env` file!

```bash
# Security (generate new)
DEMO_SECRET_KEY=<output-from-openssl-rand>
DEMO_JWT_SECRET=<output-from-openssl-rand>
DEMO_DB_PASSWORD=<output-from-openssl-rand>

# Reuse from existing .env
SOLANA_RPC_URL=<copy-from-.env>
HELIUS_API_KEY=<copy-from-.env>
ANTHROPIC_API_KEY=<copy-from-.env>
XAI_API_KEY=<copy-from-.env>
BAGS_API_KEY=<copy-from-.env>
BITQUERY_API_KEY=<copy-from-.env>

# Optional (for bags monitor notifications)
TELEGRAM_BOT_TOKEN=<copy-from-.env>
TELEGRAM_BUY_BOT_CHAT_ID=<copy-from-.env>

# Domain
PRIMARY_DOMAIN=jarvislife.io
```

**Quick Copy Script**:
```bash
# Extract values from existing .env and populate .env.web
grep "SOLANA_RPC_URL" .env >> .env.web
grep "HELIUS_API_KEY" .env >> .env.web
grep "ANTHROPIC_API_KEY" .env >> .env.web
grep "XAI_API_KEY" .env >> .env.web
grep "BAGS_API_KEY" .env >> .env.web
grep "BITQUERY_API_KEY" .env >> .env.web
grep "TELEGRAM_BOT_TOKEN" .env >> .env.web
grep "TELEGRAM_BUY_BOT_CHAT_ID" .env >> .env.web
```

---

## Step 4: SSL Certificate Setup

### Option A: Let's Encrypt (Recommended - Free & Auto-Renew)

```bash
# Install Certbot
apt update
apt install -y certbot

# Stop nginx temporarily (if running)
docker-compose -f docker-compose.web.yml down nginx

# Generate certificate
certbot certonly --standalone -d jarvislife.io -d demo.jarvislife.io

# Certificates will be at:
# /etc/letsencrypt/live/jarvislife.io/fullchain.pem
# /etc/letsencrypt/live/jarvislife.io/privkey.pem

# Create SSL directory for Docker
mkdir -p nginx/ssl/jarvislife.io
cp /etc/letsencrypt/live/jarvislife.io/fullchain.pem nginx/ssl/jarvislife.io/
cp /etc/letsencrypt/live/jarvislife.io/privkey.pem nginx/ssl/jarvislife.io/

# Set permissions
chmod 644 nginx/ssl/jarvislife.io/fullchain.pem
chmod 600 nginx/ssl/jarvislife.io/privkey.pem

# Auto-renewal (certbot already sets this up)
# Verify: certbot renew --dry-run
```

### Option B: Self-Signed (Development Only)

```bash
mkdir -p nginx/ssl/jarvislife.io

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/jarvislife.io/privkey.pem \
  -out nginx/ssl/jarvislife.io/fullchain.pem \
  -subj "/CN=jarvislife.io"
```

**Warning**: Browsers will show "Not Secure" warning. Only use for testing.

### Option C: Existing Hostinger SSL

If you already have SSL from Hostinger for your static site:

```bash
# Ask Hostinger support for SSL cert files OR
# Export from Hostinger panel and upload to VPS

scp /path/to/cert.pem root@72.617.126:/root/Jarvis/nginx/ssl/jarvislife.io/fullchain.pem
scp /path/to/key.pem root@72.617.126:/root/Jarvis/nginx/ssl/jarvislife.io/privkey.pem
```

---

## Step 5: Deploy Services

### Build and Start

```bash
# Load environment
export $(cat .env.web | xargs)

# Build images (first time - takes 5-10 minutes)
docker-compose -f docker-compose.web.yml build

# Start services
docker-compose -f docker-compose.web.yml up -d

# Watch logs
docker-compose -f docker-compose.web.yml logs -f
```

### Verify Services

```bash
# Check all containers running
docker ps | grep jarvis

# Expected output:
# jarvis-web-nginx          Up      0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
# jarvis-demo-frontend      Up      (internal)
# jarvis-demo-backend       Up      (internal)
# jarvis-bags-monitor       Up      (internal)
# jarvis-demo-postgres      Up      (internal)
# jarvis-demo-redis         Up      (internal)

# Check health
docker-compose -f docker-compose.web.yml ps
```

All services should show "healthy" status.

### Initialize Database

```bash
# Run migrations (first time only)
docker exec jarvis-demo-backend alembic upgrade head

# Verify
docker exec jarvis-demo-backend alembic current
```

---

## Step 6: Test Deployment

### Health Checks

```bash
# Backend health
curl https://jarvislife.io/api/health

# Expected: {"status":"healthy","timestamp":"2026-01-24T..."}

# Bags monitor health
curl https://jarvislife.io/api/bags/health

# Expected: {"status":"ok"}
```

### Access Web Demo

Open in browser:
- **Main site**: `https://jarvislife.io/demo`
- **Subdomain** (if configured): `https://demo.jarvislife.io`

You should see the trading interface.

### Create Test Account

1. Click "Register" or "Sign Up"
2. Enter email and password
3. Create demo wallet
4. Fund with demo SOL (backend provides 10 SOL for demo accounts)

---

## Step 7: Configure Existing Site (Optional)

If you have static HTML at `jarvislife.io`, you'll need to serve it alongside the demo app.

### Copy Static Files to Nginx

```bash
# Create directory for static site
mkdir -p nginx/www

# Upload your HTML files to VPS
scp -r /path/to/your/html/* root@72.617.126:/root/Jarvis/nginx/www/

# Update docker-compose.web.yml nginx section:
# Add volume mount:
volumes:
  - ./nginx/web.conf:/etc/nginx/conf.d/web.conf:ro
  - ./nginx/ssl:/etc/nginx/ssl:ro
  - ./nginx/www:/var/www/html:ro  # <-- ADD THIS
  - nginx_logs:/var/log/nginx

# Restart nginx
docker-compose -f docker-compose.web.yml restart nginx
```

Now:
- `https://jarvislife.io/` → Your static HTML site
- `https://jarvislife.io/demo` → Web demo app
- `https://jarvislife.io/api` → Backend API

---

## Management Commands

### View Logs

```bash
# All services
docker-compose -f docker-compose.web.yml logs -f

# Specific service
docker-compose -f docker-compose.web.yml logs -f demo-backend

# Last 100 lines
docker-compose -f docker-compose.web.yml logs --tail=100
```

### Restart Services

```bash
# All services
docker-compose -f docker-compose.web.yml restart

# Specific service
docker-compose -f docker-compose.web.yml restart demo-backend

# Rebuild and restart after code changes
docker-compose -f docker-compose.web.yml build demo-backend
docker-compose -f docker-compose.web.yml up -d demo-backend
```

### Stop Services

```bash
# Stop all
docker-compose -f docker-compose.web.yml down

# Stop but keep data
docker-compose -f docker-compose.web.yml stop
```

### Resource Usage

```bash
# Real-time stats
docker stats

# Disk usage
docker system df

# Clean up old images
docker system prune -a
```

---

## Updating the App

### Pull Latest Code and Redeploy

```bash
# SSH to VPS
ssh root@72.617.126
cd /root/Jarvis

# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.web.yml build
docker-compose -f docker-compose.web.yml up -d

# Watch for errors
docker-compose -f docker-compose.web.yml logs -f
```

### Zero-Downtime Update

```bash
# Build new images
docker-compose -f docker-compose.web.yml build

# Rolling restart (one service at a time)
docker-compose -f docker-compose.web.yml up -d --no-deps demo-frontend
docker-compose -f docker-compose.web.yml up -d --no-deps demo-backend
docker-compose -f docker-compose.web.yml up -d --no-deps bags-monitor
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose -f docker-compose.web.yml logs <service-name>

# Common issues:
# 1. Missing environment variables
grep "DEMO_SECRET_KEY" .env.web  # Should not be empty

# 2. Port conflicts
sudo lsof -i :80   # Check if port 80 is in use
sudo lsof -i :443  # Check if port 443 is in use

# 3. SSL cert not found
ls -la nginx/ssl/jarvislife.io/
```

### Database Connection Failed

```bash
# Check postgres running
docker-compose -f docker-compose.web.yml ps demo-postgres

# Check logs
docker-compose -f docker-compose.web.yml logs demo-postgres

# Test connection
docker exec jarvis-demo-postgres psql -U jarvis_demo -c "SELECT 1"
```

### Frontend Shows 502 Bad Gateway

```bash
# Check backend is running
docker-compose -f docker-compose.web.yml ps demo-backend

# Check backend logs
docker-compose -f docker-compose.web.yml logs demo-backend

# Restart backend
docker-compose -f docker-compose.web.yml restart demo-backend
```

### SSL Certificate Errors

```bash
# Verify cert files exist
ls -la /etc/letsencrypt/live/jarvislife.io/

# Re-copy to nginx directory
cp /etc/letsencrypt/live/jarvislife.io/fullchain.pem nginx/ssl/jarvislife.io/
cp /etc/letsencrypt/live/jarvislife.io/privkey.pem nginx/ssl/jarvislife.io/

# Restart nginx
docker-compose -f docker-compose.web.yml restart nginx
```

### Check if Conflicting with Existing Bots

```bash
# Check all running containers
docker ps

# Web services should be in jarvis-web-network
# Bot services should be in jarvis-network

# Verify networks
docker network ls | grep jarvis
```

---

## Security Checklist

Before going live:

- [ ] **Strong secrets**: Generated with `openssl rand -hex 32`
- [ ] **HTTPS enabled**: Let's Encrypt or valid SSL certificate
- [ ] **Firewall configured**: Only ports 80, 443, and SSH (22) open
- [ ] **Database secured**: No external access (internal network only)
- [ ] **CORS configured**: Only allow your domains in `.env.web`
- [ ] **Rate limiting active**: Nginx config includes rate limits
- [ ] **Debug mode off**: `DEBUG=false` in `.env.web`
- [ ] **Backups enabled**: Database backups scheduled (see below)

---

## Backup & Recovery

### Manual Backup

```bash
# Backup database
docker exec jarvis-demo-postgres pg_dump -U jarvis_demo jarvis_demo > backup-$(date +%Y%m%d).sql

# Backup wallet data
docker run --rm -v jarvis_demo_wallets:/data -v $(pwd):/backup alpine tar czf /backup/wallets-$(date +%Y%m%d).tar.gz /data

# Upload to secure location
scp backup-*.sql wallets-*.tar.gz user@backup-server:/backups/
```

### Automated Backups (Cron)

```bash
# Create backup script
cat > /root/backup-jarvis-web.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=/root/backups/jarvis-web
mkdir -p $BACKUP_DIR
DATE=$(date +%Y%m%d-%H%M)

# Database backup
docker exec jarvis-demo-postgres pg_dump -U jarvis_demo jarvis_demo > $BACKUP_DIR/db-$DATE.sql

# Compress and keep last 7 days
gzip $BACKUP_DIR/db-$DATE.sql
find $BACKUP_DIR -name "db-*.sql.gz" -mtime +7 -delete
EOF

chmod +x /root/backup-jarvis-web.sh

# Add to cron (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /root/backup-jarvis-web.sh") | crontab -
```

### Restore from Backup

```bash
# Restore database
gunzip backup-20260124.sql.gz
docker exec -i jarvis-demo-postgres psql -U jarvis_demo jarvis_demo < backup-20260124.sql

# Restore wallets
docker run --rm -v jarvis_demo_wallets:/data -v $(pwd):/backup alpine tar xzf /backup/wallets-20260124.tar.gz -C /
```

---

## Monitoring

### Check Service Health

```bash
# Health check endpoint
curl https://jarvislife.io/api/health

# Metrics (if enabled)
curl https://jarvislife.io/api/metrics
```

### Resource Monitoring

```bash
# Real-time stats
docker stats --no-stream

# Disk usage
df -h

# Memory usage
free -h
```

### Log Monitoring

```bash
# Watch all logs
docker-compose -f docker-compose.web.yml logs -f

# Watch for errors
docker-compose -f docker-compose.web.yml logs -f | grep -i error

# Nginx access logs
docker exec jarvis-web-nginx tail -f /var/log/nginx/jarvislife-access.log
```

---

## Performance Tuning

### Increase Backend Workers

Edit `docker-compose.web.yml`:

```yaml
demo-backend:
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Increase Database Resources

```yaml
demo-postgres:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 4G
```

### Enable Response Caching

Add to nginx config:

```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=100m;

location /api/sentiment {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    # ... rest of config
}
```

---

## Next Steps

After successful deployment:

1. ✅ **Test thoroughly**: Create demo account, execute trades, check UI
2. ✅ **Monitor logs**: Watch for errors in first 24 hours
3. ✅ **Set up backups**: Enable automated daily backups
4. ✅ **Configure monitoring**: Add health check alerts
5. ✅ **Document credentials**: Store API keys securely
6. ✅ **Update main site**: Add link to `/demo` from your homepage
7. ✅ **Share with users**: Announce availability

---

## Support

- **Logs**: `docker-compose -f docker-compose.web.yml logs <service>`
- **Health**: `curl https://jarvislife.io/api/health`
- **Documentation**: See `web_demo/README.md`
- **Issues**: Check service logs first

---

**Deployment Complete! 🎉**

Your web demo is now live at:
- `https://jarvislife.io/demo` (or `https://demo.jarvislife.io`)
- Backend API: `https://jarvislife.io/api`
- Bags Monitor: `https://jarvislife.io/api/bags`
