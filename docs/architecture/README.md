# Jarvis Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │Dashboard │  │ Trading  │  │   Chat   │  │ Voice Control    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
└───────┼─────────────┼─────────────┼──────────────────┼──────────┘
        │             │             │                  │
        └─────────────┴─────────────┴──────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Nginx Proxy     │
                    └─────────┬─────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌─────────▼─────────┐  ┌───────▼───────┐
│  FastAPI App  │   │  WebSocket Hub    │  │  Legacy Flask │
│  (REST API)   │   │  (Real-time)      │  │  (Migration)  │
└───────┬───────┘   └─────────┬─────────┘  └───────────────┘
        │                     │
        └──────────┬──────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
┌───▼───┐    ┌─────▼─────┐   ┌────▼────┐
│ Redis │    │  SQLite   │   │  Vault  │
│ Cache │    │  Database │   │ Secrets │
└───────┘    └───────────┘   └─────────┘
```

## Core Components

### API Layer (`api/`)
- **fastapi_app.py** - Main FastAPI application
- **middleware/** - Request processing (rate limiting, auth, security headers)
- **auth/** - Authentication (JWT, API keys)
- **routes/** - API endpoints
- **schemas/** - Request/response validation

### Core Layer (`core/`)
- **providers.py** - AI provider integration (OpenAI, Gemini, etc.)
- **trading_pipeline.py** - Trading strategy execution
- **memory.py** - Conversation memory management
- **encryption.py** - Secure storage and encryption

### Security Layer (`core/security/`)
- **sanitizer.py** - Input sanitization
- **session_manager.py** - Session management
- **two_factor.py** - 2FA implementation
- **audit_trail.py** - Security event logging

### Resilience Layer (`core/resilience/`)
- **circuit_breaker.py** - Fault tolerance
- **retry.py** - Retry with backoff
- **fallback.py** - Graceful degradation

## Data Flow

### API Request Flow
```
Request → Middleware Chain → Route Handler → Service → Response
           │
           ├─ Rate Limiting
           ├─ Authentication
           ├─ Request Tracing
           └─ Body Validation
```

### Trading Flow
```
Signal → Validation → Risk Check → Order → Execution → Settlement
           │              │           │         │
           └──────────────┴───────────┴─────────┘
                          Audit Trail
```

## Security Architecture

### Authentication Methods
1. **JWT Tokens** - Short-lived access tokens
2. **API Keys** - Service-to-service auth
3. **2FA** - TOTP-based second factor

### Security Layers
1. **Network** - TLS, rate limiting, IP allowlist
2. **Application** - Input validation, CSRF, XSS prevention
3. **Data** - Encryption at rest, secure vault

## Deployment

### Docker Compose Services
- `jarvis-api` - FastAPI backend
- `jarvis-frontend` - React development server
- `redis` - Caching layer
- `nginx` - Reverse proxy
- `prometheus` - Metrics collection
- `grafana` - Dashboards

### Kubernetes
- Deployment with HPA
- ConfigMaps and Secrets
- PersistentVolumeClaims

## Monitoring

### Metrics
- HTTP request rate and latency
- Provider API calls
- Trade executions
- Cache hit/miss rates

### Alerting
- High error rate
- Provider failures
- High latency
- Memory leaks
