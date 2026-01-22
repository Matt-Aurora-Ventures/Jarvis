# JARVIS Web Demo - Architecture Document

## Project Overview
Secure, standalone web application extracted from JARVIS Telegram bot demo features.
Designed to run on jarvislife.io with premium UI/UX matching the main site.

## Security Architecture (Burak Eregar Principles)

### Rule #1: Treat Every Client as Hostile
**Implementation:**
- All prices, balances, and trade amounts are calculated server-side
- User roles and permissions stored in server session only
- Token addresses validated against on-chain data
- Never trust client-provided amounts or rates

### Rule #2: Enforce Everything Server-Side
**Implementation:**
- Authentication via JWT with refresh tokens
- Rate limiting per user (10 req/min for reads, 5 req/min for writes)
- All trade calculations verified on-chain before execution
- Position ownership verified before any action
- Request replay protection via nonce/timestamp validation
- Input sanitization and validation on all endpoints

### Rule #3: UI Restrictions Are Not Security
**Implementation:**
- All backend endpoints assume they can be called directly
- Disabled buttons in UI don't prevent API calls
- Hidden features still have full authorization checks
- Admin features require server-side role verification
- No security logic in frontend JavaScript

## Core Features (Extracted from demo.py)

### 1. Wallet Management
- **Create Wallet**: Generate new Solana wallet with AES-256 encryption
- **Import Wallet**: Support private key and seed phrase import
- **Balance Display**: Real-time SOL balance and USD value
- **Token Holdings**: View all token balances with USD values
- **Send/Receive**: Transfer SOL and SPL tokens
- **Export Keys**: Secure private key export with warnings

### 2. Trading Features
- **Quick Buy**: Preset amounts (0.1, 0.5, 1, 5 SOL)
- **Quick Sell**: Sell tokens by percentage (25%, 50%, 75%, 100%)
- **Token Search**: Search and analyze any Solana token
- **Position Management**: View, edit, close positions
- **P&L Tracking**: Real-time profit/loss calculations
- **Trade History**: Complete transaction history with charts

### 3. AI & Sentiment Analysis
- **Market Regime Detection**: Bull/Bear/Neutral classification
- **Risk Level Assessment**: Low/Normal/High/Extreme risk scoring
- **AI Picks**: Grok-powered token recommendations with conviction scores
- **Sentiment Hub**: Multi-source sentiment aggregation
  - Social sentiment (Twitter/X)
  - On-chain metrics
  - Traditional market indicators
  - News sentiment
- **Trending Tokens**: Real-time trending with AI analysis
- **Bags.fm Integration**: Top volume tokens with sentiment scores

### 4. Advanced Trading Tools
- **Insta Snipe**: One-click trading on trending tokens
- **DCA (Dollar Cost Average)**: Automated recurring buys
- **Price Alerts**: Set price target notifications
- **Watchlist**: Track favorite tokens
- **Auto-trade**: AI-powered automated trading (admin only)

### 5. Learning & Intelligence
- **Trade Intelligence**: Self-improving trade outcome learning
- **Performance Dashboard**: Win rate, P&L history, strategy performance
- **Learning Dashboard**: View AI model improvements over time
- **Success Fee Tracking**: 0.5% fee on winning trades

### 6. Portfolio Analytics
- **Position Health Indicators**: Visual health bars based on P&L
- **Price Charts**: Matplotlib-generated price/P&L charts
- **P&L Reports**: Detailed profit/loss breakdowns
- **Fee Statistics**: Trading fees, success fees, total costs

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Authentication**: JWT with httpOnly cookies
- **Database**: PostgreSQL for user data, Redis for sessions/cache
- **Blockchain**: Solana web3.py, Jupiter API for swaps
- **AI/ML**: OpenAI Grok API, local sentiment models
- **Security**:
  - bcrypt for password hashing
  - cryptography for wallet encryption
  - rate limiting via slowapi
  - CORS with strict origins
  - CSP headers
  - Request validation via Pydantic

### Frontend
- **Framework**: React 18 with TypeScript
- **Styling**: Tailwind CSS + Custom jarvislife.io theme
- **State Management**: Zustand or Redux Toolkit
- **Charts**: Chart.js or Recharts for price/P&L visualizations
- **Animations**: GSAP for jarvislife.io-style animations
- **Icons**: Lucide React (modern icon set)

### Design System (jarvislife.io Match)

#### Colors
```css
--bg-dark: #0B0C0D;
--text-primary: #FFFFFF;
--accent-green: #39FF14;
--grey-light: #a0a0a0;
--grey-dark: #666666;
```

#### Typography
- **Headlines**: Clash Display (weights 500-600)
- **Body**: DM Sans (regular, medium)

#### Effects
- **Glassmorphism**: backdrop-filter: blur(24px) on cards
- **Glow**: 0 0 20px rgba(57, 255, 20, 0.3) on accent elements
- **Animations**: GSAP ScrollTrigger, staggered entrances

#### Components
- Path Cards: Gradient borders with 24px border-radius
- Data Visualization: Animated grid overlays with scanning lines
- Status Indicators: Pulsing dots (green=active, grey=inactive)
- Hover States: Scale + glow intensification

## File Structure

```
web_demo/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # Configuration management
│   │   ├── security.py             # Auth, JWT, rate limiting
│   │   ├── middleware.py           # Request validation, CORS
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # Login, register, refresh
│   │   │   ├── wallet.py           # Wallet management endpoints
│   │   │   ├── trading.py          # Trading endpoints
│   │   │   ├── positions.py        # Position management
│   │   │   ├── sentiment.py        # AI sentiment endpoints
│   │   │   ├── portfolio.py        # Portfolio analytics
│   │   │   └── admin.py            # Admin-only endpoints
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User model
│   │   │   ├── wallet.py           # Wallet model
│   │   │   ├── position.py         # Position model
│   │   │   └── trade.py            # Trade history model
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── wallet_service.py   # Core wallet logic
│   │   │   ├── trading_service.py  # Core trading logic
│   │   │   ├── sentiment_service.py # AI sentiment engine
│   │   │   ├── jupiter_service.py  # Jupiter DEX integration
│   │   │   ├── bags_service.py     # Bags.fm API integration
│   │   │   └── intelligence_service.py # Trade intelligence
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── encryption.py       # Wallet encryption
│   │       ├── validation.py       # Input validation
│   │       └── charts.py           # Chart generation
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_wallet.py
│   │   ├── test_trading.py
│   │   └── test_security.py
│   ├── alembic/                    # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── assets/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── Auth/
│   │   │   │   ├── LoginForm.tsx
│   │   │   │   └── RegisterForm.tsx
│   │   │   ├── Wallet/
│   │   │   │   ├── WalletOverview.tsx
│   │   │   │   ├── WalletCreate.tsx
│   │   │   │   ├── WalletImport.tsx
│   │   │   │   └── TokenHoldings.tsx
│   │   │   ├── Trading/
│   │   │   │   ├── QuickTrade.tsx
│   │   │   │   ├── TokenSearch.tsx
│   │   │   │   ├── BuyPanel.tsx
│   │   │   │   └── SellPanel.tsx
│   │   │   ├── Positions/
│   │   │   │   ├── PositionsList.tsx
│   │   │   │   ├── PositionCard.tsx
│   │   │   │   └── PositionDetails.tsx
│   │   │   ├── Sentiment/
│   │   │   │   ├── SentimentHub.tsx
│   │   │   │   ├── MarketRegime.tsx
│   │   │   │   ├── AIPicksList.tsx
│   │   │   │   └── TrendingTokens.tsx
│   │   │   ├── Portfolio/
│   │   │   │   ├── PortfolioOverview.tsx
│   │   │   │   ├── PnLChart.tsx
│   │   │   │   └── PnLReport.tsx
│   │   │   ├── Learning/
│   │   │   │   ├── LearningDashboard.tsx
│   │   │   │   └── PerformanceMetrics.tsx
│   │   │   └── UI/
│   │   │       ├── Button.tsx
│   │   │       ├── Card.tsx
│   │   │       ├── Input.tsx
│   │   │       ├── Modal.tsx
│   │   │       └── GlassCard.tsx
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   ├── useWallet.ts
│   │   │   ├── usePositions.ts
│   │   │   └── useSentiment.ts
│   │   ├── services/
│   │   │   ├── api.ts              # Axios instance with auth
│   │   │   ├── authService.ts
│   │   │   ├── walletService.ts
│   │   │   ├── tradingService.ts
│   │   │   └── sentimentService.ts
│   │   ├── store/
│   │   │   ├── authStore.ts
│   │   │   ├── walletStore.ts
│   │   │   └── positionsStore.ts
│   │   ├── styles/
│   │   │   ├── globals.css
│   │   │   └── jarvis-theme.css
│   │   ├── types/
│   │   │   ├── auth.ts
│   │   │   ├── wallet.ts
│   │   │   ├── trading.ts
│   │   │   └── sentiment.ts
│   │   └── utils/
│   │       ├── formatting.ts
│   │       └── validation.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```

## Security Implementation Details

### Authentication Flow
1. User registers with email/password
2. Password hashed with bcrypt (12 rounds)
3. JWT access token (15 min) + refresh token (7 days)
4. Tokens stored in httpOnly cookies
5. CSRF token in header for state-changing requests

### Authorization
- Role-based: `user`, `admin`
- Middleware checks JWT validity on every request
- Admin endpoints require `admin` role server-side
- Wallet operations require ownership verification

### Rate Limiting
```python
# Per-user limits
READ_ENDPOINTS: 10 requests/minute
WRITE_ENDPOINTS: 5 requests/minute
TRADE_ENDPOINTS: 3 requests/minute
AUTH_ENDPOINTS: 5 requests/hour (login/register)
```

### Input Validation
All inputs validated server-side:
- Token addresses: Must be valid Solana base58 addresses
- Amounts: Positive decimals, max precision check
- Percentages: 0-100 range
- Strings: Max length, sanitized for XSS
- Timestamps: Within reasonable range (prevent replay)

### Wallet Security
- Master password never stored
- Private keys encrypted with AES-256-GCM
- Encryption key derived from user password via Argon2
- Keys only decrypted in memory for signing
- Optional 2FA for wallet operations

### Trade Execution Security
1. Client requests trade with token address and amount
2. Server validates token address on-chain
3. Server recalculates swap route via Jupiter API
4. Server verifies user has sufficient balance
5. Server checks rate limits and position limits
6. Server signs and submits transaction
7. Server confirms transaction on-chain
8. Server updates position records

### API Security Headers
```
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'
```

## Deployment Architecture

### Production Stack
- **Web Server**: Nginx as reverse proxy
- **App Server**: Gunicorn with Uvicorn workers (4-8 workers)
- **Database**: PostgreSQL 15 with connection pooling
- **Cache**: Redis 7 for sessions and rate limiting
- **Storage**: S3-compatible for chart images
- **Monitoring**: Prometheus + Grafana
- **Logging**: ELK stack (Elasticsearch, Logstash, Kibana)

### Docker Compose Services
```yaml
services:
  - postgres (database)
  - redis (cache/sessions)
  - backend (FastAPI app)
  - frontend (Nginx serving React build)
  - nginx (reverse proxy)
```

### Environment Variables
```
# App
APP_ENV=production
SECRET_KEY=<random-256-bit>
CORS_ORIGINS=https://jarvislife.io

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/jarvis_demo
REDIS_URL=redis://redis:6379/0

# Solana
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
JUPITER_API_URL=https://quote-api.jup.ag/v6

# AI
XAI_API_KEY=<grok-api-key>
BAGS_API_KEY=<bags-api-key>

# Security
JWT_SECRET=<random-256-bit>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

## API Endpoints Summary

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/refresh` - Refresh access token
- `POST /api/auth/logout` - Invalidate tokens

### Wallet
- `POST /api/wallet/create` - Create new wallet
- `POST /api/wallet/import` - Import existing wallet
- `GET /api/wallet/balance` - Get SOL balance
- `GET /api/wallet/holdings` - Get token holdings
- `POST /api/wallet/send` - Send SOL/tokens
- `GET /api/wallet/address` - Get receive address
- `GET /api/wallet/transactions` - Transaction history

### Trading
- `POST /api/trading/buy` - Execute buy order
- `POST /api/trading/sell` - Execute sell order
- `POST /api/trading/quick-buy` - Quick buy with preset
- `GET /api/trading/quote` - Get swap quote
- `POST /api/trading/search` - Search tokens

### Positions
- `GET /api/positions` - List all positions
- `GET /api/positions/{id}` - Get position details
- `POST /api/positions/{id}/close` - Close position
- `POST /api/positions/{id}/edit` - Edit TP/SL

### Sentiment
- `GET /api/sentiment/market-regime` - Current market regime
- `GET /api/sentiment/ai-picks` - AI-recommended tokens
- `GET /api/sentiment/trending` - Trending tokens
- `GET /api/sentiment/bags-top` - Bags.fm top tokens
- `POST /api/sentiment/analyze/{token}` - Analyze specific token

### Portfolio
- `GET /api/portfolio/overview` - Portfolio summary
- `GET /api/portfolio/pnl` - P&L history
- `GET /api/portfolio/performance` - Performance metrics
- `GET /api/portfolio/chart` - P&L chart image

### Learning (Admin)
- `GET /api/learning/dashboard` - Learning metrics
- `GET /api/learning/outcomes` - Trade outcomes
- `POST /api/learning/retrain` - Trigger model retrain

## UI/UX Design Specifications

### Main Dashboard Layout
```
┌─────────────────────────────────────────────────┐
│  JARVIS Logo          Market Regime    [User]   │
├─────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  Wallet      │  │  Portfolio Overview      │ │
│  │  Balance     │  │  - Open Positions: 5     │ │
│  │  SOL: 2.45   │  │  - Total P&L: +$125.43   │ │
│  │  USD: $423   │  │  - Win Rate: 67%         │ │
│  └──────────────┘  └──────────────────────────┘ │
├─────────────────────────────────────────────────┤
│  ┌─ Sentiment Hub ──────────────────────────┐  │
│  │  Market: 🟢 BULLISH   Risk: 🟡 NORMAL    │  │
│  │  BTC: +5.2%           SOL: +8.1%         │  │
│  └───────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│  [⚡ Insta Snipe]  [📊 AI Picks]  [🔥 Trending] │
├─────────────────────────────────────────────────┤
│  ┌─ AI Picks (Top 5) ──────────────────────┐   │
│  │  1. TOKEN1  🎯 HIGH    +45% (24h)       │   │
│  │  2. TOKEN2  📊 MED     +23% (24h)       │   │
│  │  3. TOKEN3  📊 MED     +18% (24h)       │   │
│  └───────────────────────────────────────────┘  │
├─────────────────────────────────────────────────┤
│  ┌─ Open Positions ─────────────────────────┐  │
│  │  TOKEN1  🟢 +15.2%  $45.23              │  │
│  │  TOKEN2  🔴 -3.5%   -$12.10             │  │
│  │  [View All Positions]                    │  │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Design Tokens
```typescript
export const theme = {
  colors: {
    background: '#0B0C0D',
    surface: 'rgba(255, 255, 255, 0.05)',
    surfaceHover: 'rgba(255, 255, 255, 0.08)',
    text: {
      primary: '#FFFFFF',
      secondary: '#A0A0A0',
      tertiary: '#666666',
    },
    accent: {
      green: '#39FF14',
      greenGlow: 'rgba(57, 255, 20, 0.3)',
    },
    status: {
      success: '#39FF14',
      error: '#FF3939',
      warning: '#FFA500',
      info: '#3B82F6',
    },
  },
  fonts: {
    display: '"Clash Display", sans-serif',
    body: '"DM Sans", sans-serif',
  },
  effects: {
    glass: {
      background: 'rgba(255, 255, 255, 0.05)',
      backdropFilter: 'blur(24px)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
    },
    glow: {
      boxShadow: '0 0 20px rgba(57, 255, 20, 0.3)',
    },
  },
  animation: {
    duration: {
      fast: '0.2s',
      normal: '0.3s',
      slow: '0.5s',
    },
    easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
  },
};
```

## Performance Optimization

### Backend
- Connection pooling (PostgreSQL, Redis)
- Query optimization with indexes
- Caching frequently accessed data (market regime, trending tokens)
- Async request handling
- Background tasks for non-critical operations

### Frontend
- Code splitting by route
- Lazy loading components
- Image optimization (WebP)
- Virtual scrolling for long lists
- Debounced search inputs
- Optimistic UI updates

## Testing Strategy

### Backend Tests
- Unit tests: Services, utilities (80%+ coverage)
- Integration tests: API endpoints
- Security tests: Auth, rate limiting, input validation
- Load tests: Handle 100 concurrent users

### Frontend Tests
- Unit tests: Components, hooks, utilities
- Integration tests: User flows
- E2E tests: Critical paths (Playwright)

## Monitoring & Alerts

### Metrics
- Request rate, latency, error rate
- Authentication success/failure rate
- Trade execution success rate
- Wallet operation success rate
- AI service response times

### Alerts
- High error rate (>5%)
- High latency (>2s p95)
- Failed trades (>10% failure rate)
- Database connection issues
- Redis connection issues
- Solana RPC issues

## Future Enhancements (V2)

1. Mobile app (React Native)
2. Advanced charting (TradingView integration)
3. Social features (copy trading, leaderboards)
4. Advanced order types (limit, stop-loss)
5. Multi-wallet support
6. Hardware wallet integration (Ledger)
7. WebSocket real-time updates
8. Voice commands (for accessibility)
9. Dark/Light theme toggle
10. Multi-language support
