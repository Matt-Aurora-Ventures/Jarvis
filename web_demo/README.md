# JARVIS Web Demo

**Secure, Standalone AI-Powered Solana Trading Interface**

Extracted from the JARVIS Telegram bot and rebuilt as a secure web application with premium jarvislife.io design. Implements Burak Eregar's security principles for production-grade protection.

---

## 🎯 Features

### Trading
- ✅ Quick Buy/Sell with preset amounts
- ✅ Token search and analysis
- ✅ Position management with real-time P&L
- ✅ Trade history with charts
- ✅ DCA (Dollar Cost Average)
- ✅ Price alerts

### AI & Sentiment
- 🤖 Market regime detection (Bull/Bear/Neutral)
- 🎯 AI-powered token recommendations
- 📊 Multi-source sentiment aggregation
- 🔥 Trending tokens with analysis
- 🎒 Bags.fm integration

### Wallet
- 🔐 AES-256 encrypted wallet management
- 💼 Create or import wallets
- 💰 Real-time balance tracking
- 📈 Token holdings overview
- 🔄 Send/Receive SOL and SPL tokens

### Intelligence
- 🧠 Self-improving trade intelligence
- 📊 Performance analytics
- 💎 Success fee tracking (0.5% on wins)
- 📈 Win rate and P&L reporting

---

## 🛡️ Security Architecture

### Implementing Burak Eregar's Principles

#### Rule #1: Treat Every Client as Hostile
- ✅ All prices, balances, and amounts calculated server-side
- ✅ User roles stored in server session only
- ✅ Token addresses validated against blockchain
- ✅ Never trust client-provided values

#### Rule #2: Enforce Everything Server-Side
- ✅ JWT authentication with httpOnly cookies
- ✅ Rate limiting per user (10 req/min reads, 5 req/min writes)
- ✅ All trades verified on-chain before execution
- ✅ Ownership verification on every request
- ✅ Replay attack protection via nonce/timestamp
- ✅ Input sanitization on all endpoints

#### Rule #3: UI Restrictions Are Not Security
- ✅ All endpoints assume direct API calls
- ✅ Disabled buttons don't prevent execution
- ✅ Hidden features still have full auth checks
- ✅ Admin features require server-side role verification

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### 1. Clone and Setup

```bash
cd web_demo

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

### 2. Configure Environment

#### Backend (.env)
```bash
cp .env.example .env
# Edit .env with your values
```

Required variables:
```env
# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
JWT_SECRET=<generate-with-openssl-rand-hex-32>

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/jarvis_demo
REDIS_URL=redis://localhost:6379/0

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# AI Provider (choose one)
# Option 1: Grok (Cloud - requires API key)
XAI_API_KEY=your-grok-api-key
XAI_ENABLED=true

# Option 2: Ollama (Local - zero cost)
OLLAMA_ENABLED=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder

# Optional
BAGS_API_KEY=your-bags-api-key
```

#### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
```

### 3. Database Setup

```bash
# Initialize database
cd backend
alembic upgrade head
```

### 4. Run Development Servers

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Access at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (development only)

---

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services:
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Production Deployment

```bash
# Build for production
docker-compose -f docker-compose.prod.yml up -d

# With Nginx reverse proxy
docker-compose -f docker-compose.prod.yml --profile nginx up -d
```

---

## 🤖 AI Provider Setup

### Option 1: Grok (Cloud - Premium AI)

1. Get API key from [x.ai](https://x.ai)
2. Set environment variables:
```env
XAI_API_KEY=your-key-here
XAI_ENABLED=true
OLLAMA_ENABLED=false
```

**Pros**: Most powerful, cloud-based, no local resources
**Cons**: Costs money, requires internet

### Option 2: Ollama (Local - Zero Cost)

1. Install Ollama:
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# Download from https://ollama.com/download
```

2. Pull a model:
```bash
# Recommended for coding/analysis
ollama pull qwen3-coder

# Alternatives
ollama pull llama3
ollama pull mistral
```

3. Start Ollama server:
```bash
ollama serve
```

4. Configure environment:
```env
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3-coder
XAI_ENABLED=false
```

**Pros**: Zero cost, privacy-first, runs locally
**Cons**: Requires local resources (8GB+ RAM), slower inference

### VPS Deployment for Ollama

If running on a VPS for better performance:

```bash
# On VPS
ollama serve --host 0.0.0.0:11434

# On app server
OLLAMA_BASE_URL=http://your-vps-ip:11434
```

**Security Note**: Use SSL/TLS and firewall rules for production.

---

## 📁 Project Structure

```
web_demo/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Configuration
│   │   ├── security.py          # Auth & security
│   │   ├── api/                 # API endpoints
│   │   ├── models/              # Database models
│   │   ├── services/            # Business logic
│   │   └── utils/               # Utilities
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── services/            # API services
│   │   ├── store/               # State management
│   │   ├── styles/              # CSS & theme
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🎨 Design System

### Colors
- **Background**: #0B0C0D (deep dark)
- **Accent**: #39FF14 (electric green with glow)
- **Text**: #FFFFFF (primary), #A0A0A0 (secondary)

### Typography
- **Display**: Clash Display (headlines)
- **Body**: DM Sans (text)

### Effects
- **Glassmorphism**: backdrop-filter: blur(24px)
- **Glow**: 0 0 20px rgba(57, 255, 20, 0.3)
- **Animations**: GSAP for smooth transitions

### Components
- Glass cards with gradient borders
- Pulsing status indicators
- Animated hover states
- Visual health bars for positions

---

## 🔒 Security Features

### Authentication
- JWT access tokens (15 min lifetime)
- Refresh tokens (7 day lifetime)
- httpOnly cookies (no XSS exposure)
- CSRF protection on state-changing requests

### Rate Limiting
```
READ_ENDPOINTS:  10 requests/minute
WRITE_ENDPOINTS: 5 requests/minute
TRADE_ENDPOINTS: 3 requests/minute
AUTH_ENDPOINTS:  5 requests/hour
```

### Wallet Security
- AES-256-GCM encryption
- Argon2 key derivation
- Master password never stored
- Keys only decrypted in memory

### API Security
- HTTPS required in production
- CORS with strict origin whitelist
- Security headers (HSTS, CSP, etc.)
- Input validation on all endpoints
- SQL injection prevention via ORM

---

## 📊 API Endpoints

### Authentication
- `POST /api/auth/register` - Register user
- `POST /api/auth/login` - Login
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/logout` - Logout

### Wallet
- `POST /api/wallet/create` - Create wallet
- `POST /api/wallet/import` - Import wallet
- `GET /api/wallet/balance` - Get balance
- `GET /api/wallet/holdings` - Get token holdings

### Trading
- `POST /api/trading/buy` - Execute buy
- `POST /api/trading/sell` - Execute sell
- `GET /api/trading/quote` - Get swap quote
- `POST /api/trading/search` - Search tokens

### Sentiment
- `GET /api/sentiment/market-regime` - Market analysis
- `GET /api/sentiment/ai-picks` - AI recommendations
- `GET /api/sentiment/trending` - Trending tokens
- `POST /api/sentiment/analyze/{token}` - Analyze token

### Positions
- `GET /api/positions` - List positions
- `GET /api/positions/{id}` - Get position details
- `POST /api/positions/{id}/close` - Close position

Full API documentation available at `/docs` (development only).

---

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest
pytest --cov=app tests/  # With coverage
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

### E2E Tests
```bash
npm run test:e2e
```

---

## 📈 Monitoring

### Metrics Endpoint
```
GET /metrics  # Prometheus format
```

### Health Checks
```
GET /health         # Basic health
GET /health/ready   # Readiness (K8s)
```

### Logging
- Structured JSON logs
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request/response logging
- Security event logging

---

## 🚢 Production Deployment

### Environment Checklist
- [ ] Set strong `SECRET_KEY` and `JWT_SECRET`
- [ ] Use production database (PostgreSQL)
- [ ] Enable HTTPS (SSL certificate)
- [ ] Configure CORS for production domain
- [ ] Set `APP_ENV=production`
- [ ] Disable debug mode (`DEBUG=False`)
- [ ] Configure firewall rules
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure backups (database, wallet keys)
- [ ] Enable rate limiting
- [ ] Review security headers

### Nginx Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name jarvislife.io;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 🐛 Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.10+

# Check database connection
psql $DATABASE_URL -c "SELECT 1"

# Check Redis connection
redis-cli ping
```

### Frontend build fails
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 18+
```

### Ollama connection issues
```bash
# Check if Ollama is running
curl http://localhost:11434/api/version

# Start Ollama server
ollama serve

# Test model
ollama run qwen3-coder "Hello"
```

### Database migrations
```bash
# Check current version
alembic current

# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 📚 Documentation

- [Architecture](./ARCHITECTURE.md) - Full system architecture
- [API Reference](http://localhost:8000/docs) - OpenAPI docs (dev only)
- [Security](./docs/SECURITY.md) - Security implementation details
- [Deployment](./docs/DEPLOYMENT.md) - Production deployment guide

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Standards
- Backend: Black formatting, Ruff linting, type hints
- Frontend: Prettier formatting, ESLint
- Tests: 80%+ coverage required

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🙏 Credits

- **JARVIS AI** - Original Telegram bot
- **jarvislife.io** - Design system inspiration
- **Burak Eregar** - Security principles
- **Jupiter** - Solana DEX aggregation
- **Grok** - AI sentiment analysis
- **Ollama** - Local AI inference

---

## 📬 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/jarvis-web-demo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/jarvis-web-demo/discussions)
- **Security**: security@jarvislife.io

---

## 🗺️ Roadmap

### V1.0 (Current)
- ✅ Core trading features
- ✅ AI sentiment analysis
- ✅ Wallet management
- ✅ Security implementation

### V1.1 (Next)
- [ ] WebSocket real-time updates
- [ ] Advanced charting (TradingView)
- [ ] Hardware wallet support (Ledger)
- [ ] Mobile responsive design

### V2.0 (Future)
- [ ] Mobile app (React Native)
- [ ] Social features (copy trading)
- [ ] Advanced order types
- [ ] Multi-wallet support

---

**Built with ❤️ for the Solana community**
