# Jarvis Sniper Deployment (V1)

This project is a **non-custodial** Solana sniping UI:

- **Buys and sells are executed via Bags** (server-side proxy routes under `/api/bags/*`).
- **Automated SL/TP requires Session Wallet mode** (a temporary burner key stored in the browser tab).
  - If the tab/browser closes, automation stops (by design; no server custody of user keys).
  - After exits, the app auto-sweeps excess SOL back to the user’s main wallet (banks profit, reduces blast radius).

## Environment Variables

Start from `jarvis-sniper/.env.example` and create `jarvis-sniper/.env.local`.

Required:

- `HELIUS_GATEKEEPER_RPC_URL` (server-side Helius Gatekeeper URL; production routes fail closed without this)
- `BAGS_API_KEY` (server-side; used by `/api/bags/quote` + `/api/bags/swap`)
- `AUTONOMY_JOB_TOKEN` (bearer token required by `POST /api/autonomy/hourly`)
- `AUTONOMY_AUDIT_BUCKET` (GCS bucket for hourly autonomy decision artifacts)
- `XAI_API_KEY` (restricted runtime key for batch-only autonomy jobs)

Recommended:

- `SOLANA_RPC_URL` (legacy server fallback checked after `HELIUS_GATEKEEPER_RPC_URL`)
- `NEXT_PUBLIC_SOLANA_RPC` (client-side; use a **public** endpoint)
- `ALLOWED_ORIGINS` (CORS allowlist for `/api/*` routes; comma-separated)
- `BAGS_REFERRAL_ACCOUNT` (optional referral account for Bags)
- `XAI_FRONTIER_MODEL=grok-4-1-fast-reasoning`
- `XAI_FRONTIER_FALLBACK_MODELS=grok-4-fast-reasoning,grok-4`
- `XAI_BATCH_ENABLED=true`
- `XAI_DAILY_BUDGET_USD=10`
- `XAI_HOURLY_MAX_INPUT_TOKENS=150000`
- `XAI_HOURLY_MAX_OUTPUT_TOKENS=30000`
- `AUTONOMY_ENABLED=true`
- `AUTONOMY_MAX_ADJUSTMENTS_PER_CYCLE=1`

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
   - `HELIUS_GATEKEEPER_RPC_URL`
   - `SOLANA_RPC_URL`
   - `BAGS_API_KEY`
   - Optional: `BAGS_REFERRAL_ACCOUNT`, `ALLOWED_ORIGINS`
3. Deploy.

Notes:
- Vercel will run API routes as serverless functions. The Bags SDK stays server-side and is not exposed to users.
- Same-origin requests work without `ALLOWED_ORIGINS`; add it if you serve multiple origins.
- Production RPC endpoints are fail-closed: if Helius RPC config is missing/invalid, `/api/rpc` and `/api/bags/*` return `503` instead of falling back to public RPC.

## WWW Hostname Note (Firebase Hosting)

The default Firebase Hosting domain is `https://<project>.web.app` (for this app: `https://kr8tiv.web.app`).

`https://www.kr8tiv.web.app` is a different hostname and will fail TLS with a certificate name mismatch (DNS resolves, but the cert does not include `www.*`). This cannot be fixed with an app-level redirect, because the TLS handshake fails before any HTTP request reaches the app.

Recommended options:

1. Use the canonical non-`www` URL: `https://kr8tiv.web.app`
2. Add a custom domain in Firebase Hosting (ex: `sniper.jarvislife.io`) and configure both apex + `www` if you want `www` support with a valid certificate.

Quick verification (Windows curl):

```bash
curl.exe -I --ssl-no-revoke https://kr8tiv.web.app
curl.exe -I --ssl-no-revoke https://www.kr8tiv.web.app
```

Expected:
- `kr8tiv.web.app` returns `HTTP/1.1 200 OK`
- `www.kr8tiv.web.app` fails with `SEC_E_WRONG_PRINCIPAL` / certificate name mismatch

## Operational Notes (V1)

- For a small beta (50–100 users), the built-in in-memory rate limiting is sufficient.
- For larger scale or multiple instances, move rate limiting + caching to a shared store (Redis/Upstash).

## Firebase / Cloud Run Env Example

For `kr8tiv` (`ssrkr8tiv`, `us-central1`), set Gatekeeper URL before deploy:

```bash
gcloud run services update ssrkr8tiv \
  --project kr8tiv \
  --region us-central1 \
  --set-env-vars HELIUS_GATEKEEPER_RPC_URL="https://beta.helius-rpc.com/?api-key=REPLACE_ME"
```

Then deploy with the hardened flow:

```bash
npm run deploy:hardened
```

## Autonomy Scheduler + Audit Trail

1. Create bucket + lifecycle (180 days):

```bash
gcloud storage buckets create gs://kr8tiv-sniper-autonomy-audit --project kr8tiv --location us-central1
gcloud storage buckets update gs://kr8tiv-sniper-autonomy-audit --lifecycle-file=- <<'JSON'
{
  "rule": [
    { "action": { "type": "Delete" }, "condition": { "age": 180 } }
  ]
}
JSON
```

2. Configure scheduler:

```bash
npm run autonomy:scheduler
```

3. Optional: provision restricted xAI runtime key:

```bash
npm run xai:provision-key
```

4. Smoke checks:

```bash
curl -i https://kr8tiv.web.app/api/health
curl -i https://kr8tiv.web.app/api/autonomy/audit/latest
curl -i -X POST https://kr8tiv.web.app/api/autonomy/hourly -H "Authorization: Bearer <AUTONOMY_JOB_TOKEN>" -H "Content-Type: application/json" -d "{}"
```

## Rollback

To disable runtime autonomy without removing artifacts/history:

```bash
gcloud run services update ssrkr8tiv --project kr8tiv --region us-central1 --set-env-vars AUTONOMY_ENABLED=false
```
