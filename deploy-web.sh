#!/bin/bash
# Jarvis Web Demo - Quick Deployment Script
# Run on VPS to deploy web demo and bags monitor

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Jarvis Web Demo - Deployment Script"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if running on VPS
if [[ ! -f "/etc/os-release" ]]; then
    echo "❌ Error: This script must run on a Linux VPS"
    exit 1
fi

# Check Docker installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker not installed. Install Docker first:"
    echo "   curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "   sudo sh get-docker.sh"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose not installed"
    exit 1
fi

echo "✅ Docker installed: $(docker --version)"
echo "✅ Docker Compose installed: $(docker-compose --version)"
echo ""

# Check if .env.web exists
if [[ ! -f ".env.web" ]]; then
    echo "❌ Error: .env.web not found"
    echo ""
    echo "Please create .env.web with your configuration:"
    echo "  cp .env.web.example .env.web"
    echo "  nano .env.web"
    echo ""
    echo "Required variables:"
    echo "  - DEMO_SECRET_KEY (generate with: openssl rand -hex 32)"
    echo "  - DEMO_JWT_SECRET (generate with: openssl rand -hex 32)"
    echo "  - DEMO_DB_PASSWORD (strong password)"
    echo "  - SOLANA_RPC_URL, API keys, etc."
    exit 1
fi

echo "✅ Environment file found: .env.web"
echo ""

# Check SSL certificates
if [[ ! -f "nginx/ssl/jarvislife.io/fullchain.pem" ]] || [[ ! -f "nginx/ssl/jarvislife.io/privkey.pem" ]]; then
    echo "⚠️  Warning: SSL certificates not found in nginx/ssl/jarvislife.io/"
    echo ""
    echo "Options:"
    echo "  1. Generate Let's Encrypt cert (recommended):"
    echo "     certbot certonly --standalone -d jarvislife.io -d demo.jarvislife.io"
    echo "     mkdir -p nginx/ssl/jarvislife.io"
    echo "     cp /etc/letsencrypt/live/jarvislife.io/fullchain.pem nginx/ssl/jarvislife.io/"
    echo "     cp /etc/letsencrypt/live/jarvislife.io/privkey.pem nginx/ssl/jarvislife.io/"
    echo ""
    echo "  2. Generate self-signed cert (testing only):"
    echo "     mkdir -p nginx/ssl/jarvislife.io"
    echo "     openssl req -x509 -nodes -days 365 -newkey rsa:2048 \\"
    echo "       -keyout nginx/ssl/jarvislife.io/privkey.pem \\"
    echo "       -out nginx/ssl/jarvislife.io/fullchain.pem \\"
    echo "       -subj \"/CN=jarvislife.io\""
    echo ""
    read -p "Continue without SSL? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Deployment cancelled. Set up SSL certificates and try again."
        exit 1
    fi
    echo "⚠️  Proceeding without SSL (HTTP only - not recommended for production)"
fi

# Load environment
export $(cat .env.web | grep -v '^#' | xargs)

# Ask for confirmation
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Deployment Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Domain: ${PRIMARY_DOMAIN:-jarvislife.io}"
echo "Backend: FastAPI (Python)"
echo "Frontend: React (Vite)"
echo "Database: PostgreSQL 15"
echo "Cache: Redis 7"
echo "Services: demo-backend, demo-frontend, bags-monitor, postgres, redis, nginx"
echo ""
echo "This will:"
echo "  1. Build Docker images (5-10 minutes)"
echo "  2. Start all services"
echo "  3. Initialize database"
echo "  4. Configure nginx reverse proxy"
echo ""
read -p "Proceed with deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Deployment cancelled"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Building Docker Images..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

docker-compose -f docker-compose.web.yml build

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting Services..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

docker-compose -f docker-compose.web.yml up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to be ready (max 60 seconds)..."
echo ""

TIMEOUT=60
ELAPSED=0

while [[ $ELAPSED -lt $TIMEOUT ]]; do
    HEALTHY=$(docker-compose -f docker-compose.web.yml ps | grep "healthy" | wc -l)
    TOTAL=$(docker-compose -f docker-compose.web.yml ps | grep -E "(demo|bags|postgres|redis)" | wc -l)

    echo -ne "   Services ready: $HEALTHY/$TOTAL\r"

    if [[ $HEALTHY -eq $TOTAL ]]; then
        echo ""
        echo "✅ All services are healthy!"
        break
    fi

    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [[ $ELAPSED -ge $TIMEOUT ]]; then
    echo ""
    echo "⚠️  Warning: Some services may not be ready yet"
    echo "   Check logs: docker-compose -f docker-compose.web.yml logs -f"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗄️  Initializing Database..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Wait a bit for postgres to fully start
sleep 5

# Run migrations
if docker exec jarvis-demo-backend alembic upgrade head 2>/dev/null; then
    echo "✅ Database migrations applied"
else
    echo "ℹ️  Migrations not available or already applied"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get VPS IP
VPS_IP=$(hostname -I | awk '{print $1}')

echo "🌐 Access your web demo at:"
echo ""
if [[ -f "nginx/ssl/jarvislife.io/fullchain.pem" ]]; then
    echo "   🔒 https://jarvislife.io/demo"
    echo "   🔒 https://demo.jarvislife.io"
else
    echo "   🔓 http://$VPS_IP/demo (HTTP only - set up SSL!)"
fi
echo ""

echo "📊 API Endpoints:"
echo "   Backend: https://jarvislife.io/api"
echo "   Bags Monitor: https://jarvislife.io/api/bags"
echo "   Health Check: https://jarvislife.io/api/health"
echo ""

echo "📋 Service Status:"
docker-compose -f docker-compose.web.yml ps

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📚 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Test the deployment:"
echo "   curl https://jarvislife.io/api/health"
echo ""
echo "2. View logs:"
echo "   docker-compose -f docker-compose.web.yml logs -f"
echo ""
echo "3. Monitor resources:"
echo "   docker stats"
echo ""
echo "4. Set up backups (see DEPLOYMENT_WEB_GUIDE.md)"
echo ""
echo "5. Configure DNS (if using subdomain)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📖 Full Documentation: DEPLOYMENT_WEB_GUIDE.md"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check health
echo "🔍 Testing health endpoints..."
echo ""

sleep 3

# Test backend health
if curl -sf https://jarvislife.io/api/health > /dev/null 2>&1; then
    echo "✅ Backend health check: PASSED"
elif curl -sf http://$VPS_IP:8000/health > /dev/null 2>&1; then
    echo "✅ Backend health check: PASSED (HTTP)"
else
    echo "⚠️  Backend health check: FAILED (may still be starting up)"
    echo "   Check logs: docker-compose -f docker-compose.web.yml logs demo-backend"
fi

echo ""
echo "🎉 Deployment successful!"
echo ""
