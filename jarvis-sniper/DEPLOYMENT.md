# Jarvis Sniper Deployment (V1)

This project is a **non-custodial** Solana sniping UI:

- **Buys and sells are executed via Bags** (server-side proxy routes under `/api/bags/*`).
- **Automated SL/TP requires Session Wallet mode** (a temporary burner key stored in the browser tab).
  - If the tab/browser closes, automation stops (by design; no server custody of user keys).

## Environment Variables

Start from `jarvis-sniper/.env.example` and create `jarvis-sniper/.env.local`.

Required:

- `SOLANA_RPC_URL` (server-side; can include provider API keys)
- `BAGS_API_KEY` (server-side; used by `/api/bags/quote` + `/api/bags/swap`)

Recommended:

- `NEXT_PUBLIC_SOLANA_RPC` (client-side; use a **public** endpoint)
- `ALLOWED_ORIGINS` (CORS allowlist for `/api/*` routes; comma-separated)
- `BAGS_REFERRAL_ACCOUNT` (optional referral account for Bags)

## Local Run

```bash
cd jarvis-sniper
npm install
npm run dev
```

Then open `http://localhost:3001`.

## Deploy: Docker (Hetzner/VPS)

```bash
cd jarvis-sniper
# create .env.local from .env.example first
docker compose up -d --build
```

Health check:

- `GET /api/health`

## Deploy: Vercel

1. Import the repo into Vercel.
2. Set environment variables (Project Settings → Environment Variables):
   - `SOLANA_RPC_URL`
   - `BAGS_API_KEY`
   - Optional: `BAGS_REFERRAL_ACCOUNT`, `ALLOWED_ORIGINS`
3. Deploy.

Notes:
- Vercel will run API routes as serverless functions. The Bags SDK stays server-side and is not exposed to users.
- Same-origin requests work without `ALLOWED_ORIGINS`; add it if you serve multiple origins.

## Operational Notes (V1)

- For a small beta (50–100 users), the built-in in-memory rate limiting is sufficient.
- For larger scale or multiple instances, move rate limiting + caching to a shared store (Redis/Upstash).

