# Zone → Requirements Mapping

## Zone A — Public Host (Untrusted)

**File:** `requirements/ai.txt`
**Install command:**
```bash
pip install --require-hashes -r requirements/ai.txt
```
**Contains:** langgraph, openai, anthropic, python-telegram-bot, aiohttp
**Explicitly excluded:** anchorpy, solders, wallet.py, xgboost, psycopg execution tables

---

## Zone B — Core Node (Internal)

**File:** `requirements/core.txt`
**Install command:**
```bash
pip install --require-hashes -r requirements/core.txt
```
**Contains:** numpy, pandas, xgboost, scikit-learn, ccxt, psycopg, redis, freqtrade, solders (read-only)
**Explicitly excluded:** wallet.py private key, signing capability

---

## Zone C — Signer Host (Hardened)

**File:** `requirements/signer.txt`
**Install command:**
```bash
pip install --require-hashes -r requirements/signer.txt
```
**Contains:** anchorpy, solders, solana, base58, psycopg, prometheus-client, cryptography
**Target:** ≤10 packages total (including transitive deps)
**Explicitly excluded:** everything in ai.txt and core.txt

### Signer Host Startup Sequence
1. `python -m core.jupiter_perps.integrity` → verify IDL hash (exit 1 if mismatch)
2. Load `bots/treasury/wallet.py:SecureWallet` → decrypt keys
3. `python -m core.jupiter_perps.execution_service` → start intent loop
4. Background: `core.jupiter_perps.reconciliation.reconciliation_loop()` every 10s

---

## Dev / CI

**File:** `requirements/dev.txt`
**Install command:**
```bash
pip install -r requirements/dev.txt
```
**Contains:** pytest, mypy, ruff, pip-tools, pre-commit
**NOT installed in any production zone**

---

## Lockfile Management

```bash
# After modifying any .in file:
./scripts/freeze_deps.sh

# Before deploying, verify lockfiles are up-to-date:
./scripts/verify_deps.sh

# CI automatically runs verify_deps.sh on every push
```

## Environment Variables per Zone

| Variable | Zone A | Zone B | Zone C |
|----------|--------|--------|--------|
| `TELEGRAM_BOT_TOKEN` | ✅ | ❌ | ❌ |
| `XAI_API_KEY` | ✅ | ❌ | ❌ |
| `ANTHROPIC_API_KEY` | ✅ | ❌ | ❌ |
| `PERPS_DB_DSN` | ❌ | ✅ (strategy) | ✅ (execution) |
| `PERPS_WALLET_ADDRESS` | ❌ | ❌ | ✅ |
| `JARVIS_WALLET_PASSWORD` | ❌ | ❌ | ✅ |
| `HELIUS_RPC_URL` | ❌ | ✅ (read) | ✅ (submit) |
| `PERPS_LIVE_MODE` | ❌ | ❌ | ✅ |
| `LIFEOS_KILL_SWITCH` | ✅ | ✅ | ✅ |
