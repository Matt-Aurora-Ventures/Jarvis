# API Reference

Jarvis provides a RESTful API for programmatic access to all features.

---

## Base URL

```
Production: https://api.jarvislife.io/v1
Development: http://localhost:8080/v1
```

---

## Authentication

All API requests require authentication via API key.

### Getting an API Key

1. **Via Telegram**: Send `/api_key` to [@Jarviskr8tivbot](https://t.me/Jarviskr8tivbot)
2. **Via Web Dashboard**: Visit [jarvislife.io](https://jarvislife.io) → Settings → API Keys

### Authentication Header

```http
Authorization: Bearer YOUR_API_KEY
```

### Example

```bash
curl -H "Authorization: Bearer sk_live_abc123..." \
     https://api.jarvislife.io/v1/portfolio
```

---

## Rate Limits

| Tier | Limit | Cost |
|------|-------|------|
| **Free** | 60 requests/min | Free |
| **Pro** | 600 requests/min | 1,000 KR8TIV/month or $10/month |
| **Enterprise** | Unlimited | Custom pricing |

**Rate Limit Headers**:
```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1642694400
```

---

## Endpoints

### 1. System Status

**GET** `/status`

Check system health and uptime.

**Response**:
```json
{
  "status": "ok",
  "version": "4.6.5",
  "uptime_seconds": 86400,
  "components": {
    "trading_engine": "healthy",
    "telegram_bot": "healthy",
    "twitter_bot": "healthy",
    "database": "healthy"
  }
}
```

---

### 2. Portfolio

**GET** `/portfolio`

Get current portfolio with open positions.

**Response**:
```json
{
  "total_value_sol": 125.5,
  "total_value_usd": 12550.0,
  "available_balance_sol": 25.5,
  "open_positions": [
    {
      "token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
      "symbol": "USDC",
      "amount": 100.0,
      "entry_price": 1.0001,
      "current_price": 1.0002,
      "pnl_pct": 0.01,
      "pnl_usd": 0.10,
      "risk_tier": "ESTABLISHED"
    }
  ],
  "positions_count": 15,
  "max_positions": 50
}
```

---

### 3. Execute Trade

**POST** `/trade`

Execute a buy or sell trade.

**Request Body**:
```json
{
  "action": "BUY",  // or "SELL"
  "token": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "amount_sol": 2.0,
  "slippage_bps": 100,  // 1%
  "stop_loss_pct": 10,  // Optional
  "take_profit_pct": 20  // Optional
}
```

**Response**:
```json
{
  "status": "success",
  "transaction_signature": "5vJ...",
  "entry_price": 1.0001,
  "amount_tokens": 1999.8,
  "fee_sol": 0.005,
  "slippage_actual_bps": 50
}
```

**Error Response**:
```json
{
  "status": "error",
  "error_code": "INSUFFICIENT_BALANCE",
  "message": "Not enough SOL for trade + fees",
  "details": {
    "required_sol": 2.005,
    "available_sol": 1.5
  }
}
```

---

### 4. Sentiment

**GET** `/sentiment/current`

Get latest market sentiment analysis.

**Response**:
```json
{
  "timestamp": "2026-01-23T14:30:00Z",
  "market_regime": "bullish",
  "btc_change_24h": 3.2,
  "sol_change_24h": 5.1,
  "trending_tokens": [
    {
      "symbol": "BONK",
      "sentiment_score": 78,
      "confidence": "high",
      "reason": "Strong social volume + whale accumulation"
    }
  ],
  "macro_analysis": {
    "DXY": "down",
    "STOCKS": "up",
    "CRYPTO_IMPACT": "positive"
  }
}
```

---

### 5. Trade History

**GET** `/history?limit=20&offset=0`

Get recent trade history.

**Query Parameters**:
- `limit`: Number of trades (default: 20, max: 100)
- `offset`: Pagination offset (default: 0)
- `status`: Filter by status (`open`, `closed`, `all`)

**Response**:
```json
{
  "trades": [
    {
      "id": "trade_123",
      "action": "BUY",
      "token": "USDC",
      "amount_sol": 2.0,
      "entry_price": 1.0001,
      "exit_price": 1.02,
      "pnl_pct": 1.99,
      "pnl_usd": 39.8,
      "status": "closed",
      "entry_time": "2026-01-23T10:00:00Z",
      "exit_time": "2026-01-23T14:30:00Z",
      "hold_duration_hours": 4.5
    }
  ],
  "total_count": 150,
  "has_more": true
}
```

---

### 6. Staking

**POST** `/staking/stake`

Stake KR8TIV tokens to earn SOL rewards.

**Request Body**:
```json
{
  "amount_kr8tiv": 1000
}
```

**Response**:
```json
{
  "status": "success",
  "staked_amount": 1000,
  "total_staked": 5000,
  "current_tier": "Silver",
  "estimated_apy": 15.2
}
```

---

**POST** `/staking/claim`

Claim accumulated staking rewards.

**Response**:
```json
{
  "status": "success",
  "claimed_sol": 2.5,
  "claimed_usd": 250.0,
  "remaining_rewards_sol": 0.0
}
```

---

**GET** `/staking/status`

Get current staking status.

**Response**:
```json
{
  "staked_kr8tiv": 5000,
  "current_tier": "Silver",
  "pending_rewards_sol": 2.5,
  "pending_rewards_usd": 250.0,
  "apy": 15.2,
  "next_distribution": "2026-01-26T00:00:00Z"
}
```

---

### 7. Positions

**GET** `/positions`

Get all open positions.

**Response**:
```json
{
  "positions": [
    {
      "id": "pos_123",
      "token": "USDC",
      "amount": 100.0,
      "entry_price": 1.0001,
      "current_price": 1.0002,
      "pnl_pct": 0.01,
      "stop_loss": 0.9001,
      "take_profit": 1.2001,
      "risk_tier": "ESTABLISHED",
      "entry_time": "2026-01-23T10:00:00Z"
    }
  ],
  "count": 15,
  "max_allowed": 50
}
```

---

**POST** `/positions/{id}/close`

Close a specific position.

**Response**:
```json
{
  "status": "success",
  "exit_price": 1.02,
  "pnl_pct": 1.99,
  "pnl_usd": 39.8,
  "transaction_signature": "5vJ..."
}
```

---

### 8. Alerts

**GET** `/alerts?limit=20`

Get recent alerts and notifications.

**Response**:
```json
{
  "alerts": [
    {
      "id": "alert_123",
      "type": "stop_loss_triggered",
      "severity": "warning",
      "message": "Stop loss triggered for BONK",
      "details": {
        "token": "BONK",
        "exit_price": 0.000015,
        "pnl_pct": -8.5
      },
      "timestamp": "2026-01-23T14:30:00Z"
    }
  ]
}
```

---

## Websocket API (Coming Soon)

For real-time updates, Jarvis will support WebSocket connections:

```javascript
const ws = new WebSocket('wss://api.jarvislife.io/v1/ws');

ws.on('message', (data) => {
  const event = JSON.parse(data);
  if (event.type === 'position_update') {
    console.log('Position updated:', event.data);
  }
});

// Subscribe to events
ws.send(JSON.stringify({
  action: 'subscribe',
  channels: ['positions', 'trades', 'sentiment']
}));
```

---

## SDKs

Official SDKs are planned for:

- **Python** (Q2 2026)
- **JavaScript/TypeScript** (Q2 2026)
- **Rust** (Q3 2026)

Until then, use the REST API directly with your preferred HTTP client.

---

## Error Codes

| Code | Description |
|------|-------------|
| `400` | Bad Request - Invalid parameters |
| `401` | Unauthorized - Invalid API key |
| `403` | Forbidden - Insufficient permissions |
| `404` | Not Found - Resource doesn't exist |
| `429` | Too Many Requests - Rate limit exceeded |
| `500` | Internal Server Error - System error |
| `503` | Service Unavailable - Maintenance mode |

---

## Support

Need help with the API?

- **Documentation**: [docs.jarvislife.io](#)
- **GitHub Issues**: [Report API bugs](https://github.com/Matt-Aurora-Ventures/Jarvis/issues)
- **Telegram**: [@Jarviskr8tivbot](https://t.me/Jarviskr8tivbot)
- **Twitter**: [@Jarvis_lifeos](https://twitter.com/Jarvis_lifeos)
