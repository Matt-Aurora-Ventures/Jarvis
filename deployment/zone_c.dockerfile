# Zone C — Signer Host (Hardened, Isolated)
#
# Runs: ONLY the execution service + PDA reconciliation loop
# Has: signing keys (encrypted, via JARVIS_WALLET_PASSWORD + PERPS_WALLET_ADDRESS)
# Does NOT run: Telegram, dashboard, AI, HTTP server, SSH (key-only via separate port)
#
# Network:
#   inbound:  NOTHING (default deny all)
#   outbound: Helius RPC (443), optional Jito (443), PostgreSQL (5432)
#
# Security:
#   - Minimal OS (slim-bookworm = ~50MB base)
#   - Signer-only dependencies (<10 packages)
#   - Private key material in encrypted env or hardware wallet
#   - IDL hash enforced at startup — process exits if IDL tampered
#   - No interactive shell access in production
#
# CRITICAL: This Dockerfile must NEVER install:
#   flask, fastapi, uvicorn, gunicorn, django
#   langgraph, openai, anthropic
#   pandas, numpy, xgboost, scikit-learn
#   redis, ccxt, freqtrade
#   telegram, twitter, playwright
#
# Signer host dep count target: ≤ 10 packages

FROM python:3.11-slim-bookworm AS base

LABEL zone="C" \
      description="Signer host: execution service only" \
      security.signing_keys="encrypted" \
      security.can_submit_txs="true" \
      security.inbound_ports="none"

# Absolute minimum OS setup
RUN groupadd -r signer && useradd -r -g signer -s /sbin/nologin signer
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ONLY signer tier dependencies
# --require-hashes ensures no dependency drift
COPY requirements/signer.txt requirements/signer.txt
RUN pip install --no-cache-dir \
    --require-hashes \
    -r requirements/signer.txt

# Copy ONLY the execution stack — no web, no AI, no strategy
COPY core/jupiter_perps/ core/jupiter_perps/
COPY core/solana_execution.py core/solana_execution.py
COPY core/security/tx_confirmation.py core/security/tx_confirmation.py
COPY bots/treasury/wallet.py bots/treasury/wallet.py

# IDL must be baked in — not fetched at runtime
# The fetch_idl.py script populates this before building the image
COPY core/jupiter_perps/idl/jupiter_perps.json core/jupiter_perps/idl/jupiter_perps.json
COPY core/jupiter_perps/idl/jupiter_perps.json.sha256 core/jupiter_perps/idl/jupiter_perps.json.sha256

# Verify IDL hash is valid at IMAGE BUILD TIME
RUN python -c "
import hashlib
from pathlib import Path
idl = Path('core/jupiter_perps/idl/jupiter_perps.json').read_bytes()
expected = Path('core/jupiter_perps/idl/jupiter_perps.json.sha256').read_text().strip()
actual = hashlib.sha256(idl).hexdigest()
assert actual == expected, f'IDL hash mismatch at build time: {actual} != {expected}'
print('IDL hash verified at build time:', actual[:16])
"

# Drop to non-root
USER signer

# NO EXPOSED PORTS

# Startup: verify IDL again at runtime, then run execution service
CMD ["python", "-m", "core.jupiter_perps.execution_service"]
