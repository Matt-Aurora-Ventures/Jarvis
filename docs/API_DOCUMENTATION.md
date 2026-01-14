# JARVIS API Documentation

## Overview

JARVIS provides a RESTful API for managing AI-assisted trading operations, bot interactions, and system monitoring.

**Base URL:** `http://localhost:8000/api`

**API Version:** `v1`

---

## Authentication

All protected endpoints require authentication via API key.

### Headers

```http
X-API-Key: your_api_key_here
Authorization: Bearer your_jwt_token
```

### Authentication Endpoints

#### POST /api/auth/login
Authenticate and receive JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## Health & Status

### GET /api/health
System health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-13T12:00:00Z",
  "services": {
    "database": "operational",
    "redis": "operational",
    "llm_providers": "operational"
  },
  "uptime_seconds": 86400
}
```

### GET /api/health/detailed
Detailed health information including component metrics.

**Response:**
```json
{
  "status": "healthy",
  "components": {
    "database": {
      "status": "operational",
      "latency_ms": 5,
      "pool_size": 10,
      "active_connections": 3
    },
    "llm": {
      "status": "operational",
      "providers": {
        "groq": "available",
        "ollama": "available",
        "openrouter": "degraded"
      }
    },
    "bots": {
      "telegram": "running",
      "twitter": "running",
      "treasury": "running"
    }
  }
}
```

### GET /api/status
Public status page data.

**Response:**
```json
{
  "overall_status": "operational",
  "services": [
    {
      "name": "API",
      "status": "operational",
      "uptime_percent": 99.95
    }
  ],
  "active_incidents": [],
  "incidents_24h": 0
}
```

---

## Chat & Conversation

### POST /api/chat
Send a message to JARVIS.

**Request:**
```json
{
  "message": "What's the current SOL price?",
  "context": {
    "user_id": "user_123",
    "conversation_id": "conv_456"
  }
}
```

**Response:**
```json
{
  "response": "SOL is currently trading at $105.50, up 2.3% in the last 24 hours.",
  "metadata": {
    "model": "llama-3.3-70b-versatile",
    "tokens_used": 150,
    "latency_ms": 450
  }
}
```

### POST /api/chat/stream
Stream a response from JARVIS (Server-Sent Events).

**Request:** Same as `/api/chat`

**Response:** SSE stream with events:
```
event: token
data: {"content": "SOL"}

event: token
data: {"content": " is"}

event: done
data: {"total_tokens": 150}
```

---

## Trading Operations

### GET /api/trading/portfolio
Get current portfolio holdings.

**Response:**
```json
{
  "total_value_usd": 10000.00,
  "holdings": [
    {
      "symbol": "SOL",
      "amount": 50.0,
      "value_usd": 5275.00,
      "pnl_percent": 12.5
    },
    {
      "symbol": "USDC",
      "amount": 4725.00,
      "value_usd": 4725.00,
      "pnl_percent": 0
    }
  ],
  "last_updated": "2026-01-13T12:00:00Z"
}
```

### GET /api/trading/history
Get trade history.

**Query Parameters:**
- `limit` (int): Max results (default: 50)
- `offset` (int): Pagination offset
- `symbol` (string): Filter by symbol
- `side` (string): "buy" or "sell"
- `start_date` (ISO datetime): Filter from date
- `end_date` (ISO datetime): Filter to date

**Response:**
```json
{
  "trades": [
    {
      "id": "trade_001",
      "symbol": "SOL/USDC",
      "side": "buy",
      "amount": 10.0,
      "price": 100.00,
      "total_usd": 1000.00,
      "timestamp": "2026-01-13T10:00:00Z",
      "status": "filled"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

### POST /api/trading/quote
Get a trade quote.

**Request:**
```json
{
  "symbol": "SOL/USDC",
  "side": "buy",
  "amount": 10.0
}
```

**Response:**
```json
{
  "quote_id": "quote_789",
  "symbol": "SOL/USDC",
  "side": "buy",
  "amount": 10.0,
  "price": 105.50,
  "total_usd": 1055.00,
  "slippage_estimate": 0.1,
  "expires_at": "2026-01-13T12:01:00Z"
}
```

### POST /api/trading/execute
Execute a trade (requires approval).

**Request:**
```json
{
  "quote_id": "quote_789"
}
```

**Response:**
```json
{
  "trade_id": "trade_002",
  "status": "pending_approval",
  "approval_required": true,
  "approval_reason": "Trade exceeds $500 threshold"
}
```

---

## LLM Operations

### GET /api/llm/providers
List available LLM providers.

**Response:**
```json
{
  "providers": [
    {
      "name": "groq",
      "status": "available",
      "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
    },
    {
      "name": "ollama",
      "status": "available",
      "models": ["llama3.3", "mistral"]
    }
  ]
}
```

### GET /api/llm/usage
Get LLM usage statistics.

**Query Parameters:**
- `period` (string): "day", "week", "month" (default: "day")

**Response:**
```json
{
  "period": "day",
  "total_requests": 1500,
  "total_tokens": 2500000,
  "total_cost_usd": 2.50,
  "by_provider": {
    "groq": {
      "requests": 1000,
      "tokens": 2000000,
      "cost_usd": 1.00
    }
  },
  "by_model": {
    "llama-3.3-70b-versatile": {
      "requests": 800,
      "tokens": 1600000,
      "cost_usd": 0.80
    }
  }
}
```

### POST /api/llm/analyze
Analyze text using LLM.

**Request:**
```json
{
  "text": "BTC showing strong bullish divergence on 4H",
  "analysis_type": "sentiment",
  "options": {
    "include_trading_signal": true
  }
}
```

**Response:**
```json
{
  "sentiment": {
    "label": "positive",
    "score": 0.85,
    "keywords": ["bullish", "divergence"]
  },
  "trading_signal": {
    "action": "buy",
    "confidence": 0.75,
    "reasoning": "Bullish divergence suggests potential upward movement"
  }
}
```

---

## Bot Management

### GET /api/bots
List all bots and their status.

**Response:**
```json
{
  "bots": [
    {
      "name": "telegram",
      "status": "running",
      "uptime_seconds": 86400,
      "messages_processed": 1500,
      "errors_count": 2
    },
    {
      "name": "twitter",
      "status": "running",
      "uptime_seconds": 86400,
      "posts_made": 25,
      "engagement_score": 0.85
    }
  ]
}
```

### POST /api/bots/{bot_name}/command
Execute a bot command.

**Request:**
```json
{
  "command": "status",
  "args": {}
}
```

**Response:**
```json
{
  "success": true,
  "output": "Bot is running normally"
}
```

---

## Monitoring

### GET /api/metrics
Get Prometheus-formatted metrics.

**Response:**
```text
# HELP jarvis_http_requests_total Total HTTP requests
# TYPE jarvis_http_requests_total counter
jarvis_http_requests_total{method="GET",endpoint="/api/health"} 1500

# HELP jarvis_http_latency_seconds HTTP request latency
# TYPE jarvis_http_latency_seconds histogram
jarvis_http_latency_seconds_bucket{le="0.1"} 1400
jarvis_http_latency_seconds_bucket{le="0.5"} 1490
```

### GET /api/logs
Query aggregated logs.

**Query Parameters:**
- `level` (string): "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
- `source` (string): Filter by source
- `message` (string): Search pattern
- `trace_id` (string): Filter by trace
- `limit` (int): Max results (default: 100)

**Response:**
```json
{
  "logs": [
    {
      "timestamp": "2026-01-13T12:00:00Z",
      "level": "ERROR",
      "message": "Connection timeout",
      "source": "database",
      "trace_id": "trace_123"
    }
  ],
  "total": 5,
  "stats": {
    "error_rate_per_minute": 0.5
  }
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "amount",
      "reason": "Must be greater than 0"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2026-01-13T12:00:00Z"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMITED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

---

## Rate Limiting

Rate limits are applied per API key:

| Tier | Requests/Minute | Requests/Hour | Requests/Day |
|------|-----------------|---------------|--------------|
| Free | 60 | 1,000 | 10,000 |
| Pro | 300 | 10,000 | 100,000 |
| Enterprise | Unlimited | Unlimited | Unlimited |

Rate limit headers are included in all responses:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1673611200
```

---

## Webhooks

Configure webhooks to receive real-time notifications.

### POST /api/webhooks
Create a webhook.

**Request:**
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["trade.executed", "alert.triggered"],
  "secret": "your_webhook_secret"
}
```

### Webhook Events

| Event | Description |
|-------|-------------|
| `trade.executed` | Trade completed |
| `trade.failed` | Trade failed |
| `alert.triggered` | Alert condition met |
| `bot.error` | Bot encountered error |
| `system.degraded` | Service degradation |

### Webhook Payload

```json
{
  "event": "trade.executed",
  "timestamp": "2026-01-13T12:00:00Z",
  "data": {
    "trade_id": "trade_002",
    "symbol": "SOL/USDC",
    "side": "buy",
    "amount": 10.0,
    "price": 105.50
  },
  "signature": "sha256=..."
}
```

---

## SDK Examples

### Python
```python
from jarvis import JarvisClient

client = JarvisClient(api_key="your_key")

# Chat with JARVIS
response = client.chat("What's the SOL price?")
print(response.message)

# Get portfolio
portfolio = client.trading.get_portfolio()
for holding in portfolio.holdings:
    print(f"{holding.symbol}: ${holding.value_usd}")
```

### JavaScript/TypeScript
```typescript
import { JarvisClient } from '@jarvis/sdk';

const client = new JarvisClient({ apiKey: 'your_key' });

// Chat with JARVIS
const response = await client.chat('What\'s the SOL price?');
console.log(response.message);

// Stream response
for await (const chunk of client.chatStream('Analyze BTC')) {
  process.stdout.write(chunk.content);
}
```

---

## OpenAPI/Swagger

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

---

## Changelog

See [API Changelog](/api/changelog) for version history and breaking changes.

### v1.2.0 (2026-01-13)
- Added log aggregation endpoint
- Added uptime monitoring endpoints
- Added memory usage metrics

### v1.1.0 (2026-01-10)
- Added LLM cost tracking
- Added bot health monitoring
- Improved error responses

### v1.0.0 (2026-01-01)
- Initial API release
