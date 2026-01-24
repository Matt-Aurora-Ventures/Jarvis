# Jarvis Technology Stack

**Generated**: 2026-01-24

---

## Languages & Runtimes

### Primary Languages
| Language | Version | Usage |
|----------|---------|-------|
| **Python** | 3.12.10 | Backend services, trading bots, AI integrations |
| **JavaScript/TypeScript** | ES2020+ | Frontend (React), Node.js tooling |
| **Shell/Bash** | - | Deployment scripts, automation |

### Python Runtime
- **Environment**: Virtual environment (`.venv/`)
- **Package Manager**: `pip` (standard), `uv` (alternative fast installer)
- **Path**: `PYTHONPATH=/app` in containerized environments

---

## Backend Frameworks & Libraries

### API Frameworks
| Framework | Version | Purpose | Entry Point |
|-----------|---------|---------|-------------|
| **FastAPI** | Latest | Main REST API server | `api/fastapi_app.py` |
| **Uvicorn** | Latest | ASGI server for FastAPI | Programmatic startup |
| **Flask** | Legacy | Legacy API (port 8765) | Mentioned in `env.example` |
| **python-telegram-bot** | Latest | Telegram bot framework | `tg_bot/bot.py` |

**FastAPI Configuration** (`api/fastapi_app.py`):
- Default port: `8766`
- CORS middleware with configurable origins
- WebSocket support for real-time updates
- Response compression (gzip/brotli)
- Security headers middleware
- Rate limiting with headers
- Request timeout handling
- Structured logging with request tracing

### Core Dependencies

**AI/LLM**:
- `anthropic` - Claude AI integration
- `openai` - OpenAI GPT models
- `xai` (via API) - Grok AI models
- `groq` - Groq inference

**Blockchain/Solana**:
- `solana` (via imports) - Solana blockchain client
- `solders` - Rust-based Solana SDK bindings
- Custom Jupiter aggregator client (`bots/treasury/jupiter.py`)

**HTTP/Networking**:
- `aiohttp>=3.9.0` - Async HTTP client (primary)
- `httpx` - Alternative async HTTP
- `requests` - Synchronous HTTP (legacy code)

**Data Processing**:
- `pandas` - Data analysis
- `numpy` - Numerical operations
- `pydantic` - Data validation (FastAPI models)

**Database**:
- `sqlalchemy` - ORM (found in `core/db/pool.py`)
- `psycopg2` or `psycopg3` - PostgreSQL adapter
- SQLite - Default storage (file-based)

**Caching**:
- `redis` - Distributed cache (optional, found in multiple files)

**Testing**:
- `pytest` - Test framework
- `pytest-asyncio` - Async test support

**Monitoring**:
- `psutil` - System metrics (CPU, memory, disk)
- `prometheus-client` - Metrics export
- OpenTelemetry - Distributed tracing (optional)

---

## Frontend Stack

**Location**: `frontend/`

### Framework & Build Tools
| Tool | Version | Purpose |
|------|---------|---------|
| **React** | 18.2.0 | UI framework |
| **Vite** | 5.0.4 | Build tool & dev server |
| **TailwindCSS** | 3.3.6 | CSS framework |
| **Electron** | 28.0.0 | Desktop app wrapper (optional) |

### Key Libraries
- `react-router-dom@6.20.0` - Client-side routing
- `zustand@4.4.7` - State management
- `axios@1.6.2` - HTTP client
- `socket.io-client@4.7.2` - WebSocket connections
- `lightweight-charts@5.1.0` - Trading charts
- `lucide-react@0.294.0` - Icon library

### Dev Tools
- `@vitejs/plugin-react` - React support in Vite
- `autoprefixer` - CSS post-processing
- `postcss` - CSS transformations
- `electron-builder` - Desktop app packaging

---

## Twitter/X Integration

**Dependencies** (`bots/twitter/requirements.txt`):
```
xdk>=0.1.0              # Official X SDK (primary)
tweepy>=4.14.0          # Tweepy for media uploads (v1.1 API)
aiohttp>=3.9.0          # Async HTTP
python-dotenv>=1.0.0    # Environment variables
```

**Key Files**:
- `bots/twitter/twitter_client.py` - Twitter API wrapper
- `bots/twitter/x_claude_cli_handler.py` - CLI command handler for X mentions
- `bots/twitter/autonomous_engine.py` - Autonomous posting engine
- `bots/twitter/jarvis_voice.py` - AI-generated content

---

## Configuration Files

### Environment Variables
**File**: `env.example` (template for `.env`)

**Key Config Sections**:
1. **General**: `NODE_ENV`, `DATA_DIR`, `LOG_LEVEL`
2. **API**: `API_HOST`, `API_PORT`, `CORS_ORIGINS`
3. **Solana**: `SOLANA_NETWORK`, `SOLANA_RPC_URL`, wallet paths
4. **External APIs**: AI providers, data sources, social platforms
5. **Database**: `DATABASE_URL`, `REDIS_URL`
6. **Security**: `JWT_SECRET`, rate limiting, IP allowlist

### Docker Configuration
| File | Purpose |
|------|---------|
| `docker-compose.bots.yml` | Main bot supervisor container |
| `docker-compose.web.yml` | Web interface deployment |
| `docker-compose.web-integrated.yml` | Integrated web + bots |
| `docker-compose-multi.yml` | Multi-service orchestration |
| `monitoring/docker-compose.monitoring.yml` | Observability stack |

**Container Orchestration**:
- Single-instance supervisor with `replicas: 1` enforcement
- Health checks on port `8080`
- Resource limits: 4GB RAM, 2 CPU cores
- Restart policy: on-failure, max 10 attempts

### Frontend Configuration
- `frontend/vite.config.js` - Vite build settings
- `frontend/tailwind.config.js` - TailwindCSS theme
- `frontend/postcss.config.js` - PostCSS plugins

---

## Database Configuration

### Default (SQLite)
```bash
DATABASE_URL=sqlite:///./data/jarvis.db
```

### Production (PostgreSQL)
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/jarvis
```

**Connection Pooling**: Implemented in `core/db/pool.py`

### State Files (JSON)
- `bots/treasury/.positions.json` - Active trading positions
- `~/.lifeos/trading/exit_intents.json` - Exit strategy tracking
- `bots/twitter/.grok_state.json` - Twitter bot state

---

## Runtime Architecture

### Process Supervision
**Main Supervisor**: `bots/supervisor.py`

**Managed Components**:
1. `buy_bot` - KR8TIV token tracking
2. `sentiment_reporter` - Hourly market reports
3. `twitter_poster` - Grok sentiment tweets
4. `telegram_bot` - Telegram interface
5. `autonomous_x` - Autonomous X posting
6. `bags_intel` - Bags.fm graduation monitoring
7. `public_trading_bot` - Mass-market trading (optional)
8. `treasury_bot` - Treasury management (optional)
9. `autonomous_manager` - AI moderation (optional)

### API Server
- **FastAPI** on port `8766` (configurable)
- **Health endpoint**: `/api/health`
- **Metrics endpoint**: `/api/metrics` (Prometheus format)
- **Docs**: `/api/docs` (Swagger UI)

### WebSocket Channels
- `/ws/trading` - Trade execution updates
- `/ws/staking` - Staking rewards
- `/ws/treasury` - Treasury activity
- `/ws/credits` - Credit usage
- `/ws/voice` - Voice command responses

---

## Security & Performance

### Middleware Stack (FastAPI)
1. **CORS** - Cross-origin requests
2. **Security Headers** - X-Frame-Options, CSP, etc.
3. **Rate Limiting** - Per-minute/hour/day limits with burst
4. **Request Tracing** - X-Request-ID injection
5. **Request Logging** - Comprehensive request/response logs
6. **Timeout Middleware** - Prevent hung requests
7. **Body Size Limit** - 10MB default
8. **Compression** - Gzip/Brotli for responses >1KB
9. **API Versioning** - Version negotiation middleware

### Authentication
- **JWT** - Token-based auth (`api/auth/jwt_auth.py`)
- **API Key** - X-API-Key header (`api/auth/key_auth.py`)

---

## Version Information

**Current Version**: 4.3.0 (per `api/fastapi_app.py`)

**Frontend Version**: 0.5.0 (per `frontend/package.json`)

**Python Requirement**: 3.12.10 (verified on system)

---

## Notes

- **Dependency Management**: No `requirements.txt` in root - dependencies tracked per-component
- **Virtual Environment**: `.venv/` for Python isolation
- **Node Modules**: `frontend/node_modules/` for JS dependencies
- **Data Directory**: `./data/` for logs, databases, caches
- **Kill Switches**: `LIFEOS_KILL_SWITCH`, `JARVIS_KILL_SWITCH` for emergency shutdown
