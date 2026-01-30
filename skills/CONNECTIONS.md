# CONNECTIONS.md - All Available Connections & APIs

## Keys Location
All keys stored in: `/root/clawd/Jarvis/secrets/keys.json`

---

## 🔑 API Connections

### Anthropic (Claude)
- **Key**: `anthropic_api_key`
- **Use**: AI completions, Claude API calls
- **Docs**: https://docs.anthropic.com

### Groq
- **Key**: `groq_api_key`
- **Use**: Fast inference, Llama models
- **Docs**: https://console.groq.com/docs

### xAI (Grok)
- **Key**: `xai_api_key`
- **Use**: Grok API access
- **Docs**: https://docs.x.ai

---

## 🪙 Solana/Crypto APIs

### Bags.fm
- **API Key**: `bags_api_key`
- **Partner Key**: `bags_partner_key`
- **Use**: Token launches, bonding curves, trading
- **Base URL**: `https://api.bags.fm`
- **Endpoints**:
  - `GET /v1/tokens` - List tokens
  - `GET /v1/tokens/{mint}` - Token details
  - `POST /v1/swap` - Execute swap
  - `GET /v1/portfolio/{wallet}` - Wallet portfolio

### Birdeye
- **Key**: `birdeye_api_key`
- **Use**: Token prices, charts, OHLCV data
- **Base URL**: `https://public-api.birdeye.so`
- **Headers**: `X-API-KEY: {key}`
- **Endpoints**:
  - `GET /defi/price?address={mint}` - Current price
  - `GET /defi/ohlcv?address={mint}` - OHLCV data
  - `GET /defi/token_overview?address={mint}` - Token info

### Helius
- **Key**: `helius_api_key`
- **Use**: Solana RPC, webhooks, NFT APIs
- **RPC URL**: `https://mainnet.helius-rpc.com/?api-key={key}`
- **Enhanced RPC**: Transaction parsing, account data
- **Webhooks**: Real-time notifications

---

## 🐦 Twitter/X APIs

### Twitter API v2 (Aurora Account @aurora_ventures)
- **Keys**: `twitter.api_key`, `twitter.api_secret`
- **Tokens**: `twitter.access_token`, `twitter.access_secret`
- **Bearer**: `twitter.bearer_token`
- **Use**: Post tweets, read timeline, search

### Twitter OAuth2 (App-level)
- **Client ID**: `twitter_oauth2.client_id`
- **Client Secret**: `twitter_oauth2.client_secret`
- **Use**: OAuth2 flows, user authentication

### Jarvis X Account (@jarvis_lifeos) OAuth2
- **Access Token**: `twitter_jarvis_oauth2.access_token`
- **Refresh Token**: `twitter_jarvis_oauth2.refresh_token`
- **Use**: Post as Jarvis, engage with followers
- **Note**: Tokens may need refresh periodically

---

## 📱 Telegram Bots

### Main Bot Token
- **Token**: `telegram_bot_token`
- **Use**: Main Jarvis bot (current)

### ClawdJarvis Token
- **Token**: `telegram_clawdjarvis_token`
- **Bot**: @ClawdJarvis
- **Use**: Clawdbot-powered Jarvis instance

### ClawdFriday Token
- **Token**: `telegram_clawdfriday_token`
- **Bot**: @ClawdFriday
- **Use**: Friday assistant bot

---

## 🖥️ Infrastructure Connections

### Windows Desktop (SSH)
- **Host**: `100.102.41.120` (Tailscale)
- **User**: `lucid`
- **Use**: `ssh lucid@100.102.41.120`
- **Available**: Chrome CDP, local files, GPU

### Chrome CDP (Browser Control)
- **Port**: 9222 (via SSH tunnel)
- **Setup**: `ssh -L 9222:127.0.0.1:9222 lucid@100.102.41.120`
- **Check**: `curl http://127.0.0.1:9222/json/list`
- **Control Script**: `/root/clawd/scripts/chrome-control.mjs`
- **Commands**:
  ```bash
  node /root/clawd/scripts/chrome-control.mjs list      # List tabs
  node /root/clawd/scripts/chrome-control.mjs goto URL  # Navigate
  node /root/clawd/scripts/chrome-control.mjs screenshot # Capture
  node /root/clawd/scripts/chrome-control.mjs eval "JS" # Run JS
  ```

### VPS
- **Tailscale IP**: `100.66.17.93`
- **Location**: `/root/clawd/`

---

## 📁 Key File Locations

| What | Path |
|------|------|
| Jarvis Keys | `/root/clawd/Jarvis/secrets/keys.json` |
| ClawdMatt Keys | `/root/clawd/secrets/keys.json` |
| Windows Keys | `C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\secrets\keys.json` |
| Jarvis .env | `/root/clawd/Jarvis/tg_bot/.env` |

---

## 🛠️ Quick Usage Examples

### Bags.fm Token Lookup
```python
import requests
API_KEY = "bags_prod_..."
headers = {"Authorization": f"Bearer {API_KEY}"}
r = requests.get("https://api.bags.fm/v1/tokens", headers=headers)
```

### Birdeye Price Check
```python
import requests
API_KEY = "3922a536..."
headers = {"X-API-KEY": API_KEY}
r = requests.get(f"https://public-api.birdeye.so/defi/price?address={MINT}", headers=headers)
```

### Helius RPC Call
```python
import requests
API_KEY = "9b0285c5-..."
rpc_url = f"https://mainnet.helius-rpc.com/?api-key={API_KEY}"
payload = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [WALLET]}
r = requests.post(rpc_url, json=payload)
```

### Twitter Post (via tweepy)
```python
import tweepy
auth = tweepy.OAuthHandler(API_KEY, API_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)
api.update_status("Hello from Jarvis!")
```

---

## ⚠️ Security Notes

1. **Never expose keys in chat** - always use file paths
2. **Never commit keys to git** - use .gitignore
3. **Refresh OAuth tokens** - Twitter tokens expire
4. **Rate limits**: Birdeye (1000/day), Helius (varies), Twitter (varies)

---

## 🔄 Keeping Keys Updated

When keys change:
1. Update `/root/clawd/Jarvis/secrets/keys.json`
2. Update `.env` files if needed
3. Restart affected services

Matt stores master keys at:
`C:\Users\lucid\OneDrive\Desktop\Projects\Jarvis\secrets\keys.json`
