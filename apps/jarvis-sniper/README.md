# Jarvis Sniper (Web)

Non-custodial Solana sniping UI with Bags-powered execution, risk monitoring (SL/TP/Trail/Expiry), and an optional in-browser Session Wallet for auto-signing.

## Non-Negotiables (By Design)

- **Buys + sells execute via Bags** (server-side `/api/bags/*` proxy).
- **No user private keys ever touch our servers**.
- **Automation modes:**
  - **Phantom mode**: buys/sells require wallet approval popups. When SL/TP/Trail/Expiry hits, the UI shows **Exit pending** and you must click **Approve**.
  - **Session Wallet mode**: a temporary in-tab burner keypair that can **auto-sign** buys/sells. Exits can auto-execute **as long as the tab stays open**.

## Quickstart (Local)

```powershell
cd jarvis-sniper
npm i
npm run dev
```

Open `http://localhost:3000`.

## Environment Variables

Required (server):

- `BAGS_API_KEY` (Bags API key used by server routes `/api/bags/quote` + `/api/bags/swap`)
- `HELIUS_GATEKEEPER_RPC_URL` (server-only Helius Gatekeeper endpoint for production RPC)

Recommended:

- `SOLANA_RPC_URL` (legacy server RPC fallback; checked after `HELIUS_GATEKEEPER_RPC_URL`)
- `NEXT_PUBLIC_SOLANA_RPC` (client RPC for reads/price checks; used by UI + risk worker)
- `BAGS_REFERRAL_ACCOUNT` (optional referral account pubkey)
- `ALLOWED_ORIGINS` (comma-separated list of allowed Origins for API CORS)
- `XAI_API_KEY` (server-only restricted runtime key for batch autonomy)
- `AUTONOMY_JOB_TOKEN` (required for scheduler-triggered `/api/autonomy/hourly`)
- `AUTONOMY_AUDIT_BUCKET` (GCS bucket for hourly audit artifacts)

Notes:

- **Do not** prefix `BAGS_API_KEY` with `NEXT_PUBLIC_` (that would leak it to the browser bundle).
- Production is **fail-closed** for server RPC routes (`/api/rpc`, `/api/bags/*`) when no valid Helius RPC URL is configured.
- Hosting: set env vars in your hosting provider UI (Vercel/Railway/etc), not in git.

## Autonomy (Batch-Only Grok)

Sniper web includes a batch-only xAI autonomy control plane with strict fail-closed behavior:

- `POST /api/autonomy/hourly` (bearer token required)
- `GET /api/autonomy/audit/latest`
- `GET /api/autonomy/audit/[cycleId]`
- `GET /api/strategy-overrides`

Behavior:

- Batch-only model usage (no per-trade sync dependency).
- Frontier model policy (`grok-4-1-fast-reasoning` -> `grok-4-fast-reasoning` -> `grok-4`).
- Hard budget limits (`$10/day` default + hourly token caps).
- Hourly immutable decision matrix + rationale artifacts in GCS.
- Runtime overrides are constrained to allowlisted strategy fields and bounded deltas.

## Hosting Notes (50-100 Users)

- Bags SDK calls are proxied server-side, with in-memory caching + rate limiting:
  - `/api/bags/quote`: cached (3s TTL), 30 req/min per IP
  - `/api/bags/swap`: 20 req/min per IP
  - `/api/graduations`: cached (5s TTL), 60 req/min per IP
- Risk monitoring runs in a **Web Worker** to avoid background-tab throttling.
- SL/TP reliability on micro-caps depends on liquidity: some tokens will have **no sell route** even at high slippage.

## Safety

This project is early beta. Trades are real and you can lose 100% of funds used.
