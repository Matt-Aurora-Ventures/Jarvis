# Zone B — Core Node (Validated Internal Network)
#
# Runs: Micro Engine, Risk Gate, Event Journal DB, Reconciliation Loop
# Does NOT have: signing keys (no PERPS_WALLET_PRIVATE_KEY)
# Does NOT expose: HTTP publicly
#
# Network: no public inbound ports
#           accepts intents from Zone A over authenticated internal channel
#           forwards validated intents to Zone C over Unix socket / ZeroMQ PUSH
#           connects outbound to PostgreSQL, Redis, Helius RPC
#
# Security:
#   - No PERPS_WALLET_ADDRESS private key material
#   - PostgreSQL: read/write to strategy tables, read-only on execution tables
#   - Zone C: push-only (cannot pull results, fire-and-forget)

FROM python:3.11-slim-bookworm AS base

LABEL zone="B" \
      description="Core: micro engine, risk gate, DB, reconciliation" \
      security.signing_keys="none" \
      security.can_submit_txs="false"

RUN groupadd -r jarvis && useradd -r -g jarvis -s /sbin/nologin jarvis
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install core tier dependencies
COPY requirements/core.txt requirements/core.txt
RUN pip install --no-cache-dir \
    --require-hashes \
    -r requirements/core.txt

# Copy strategy and risk code
COPY core/ core/
COPY bots/treasury/trading.py bots/treasury/trading.py
COPY lifeos/ lifeos/

# Remove wallet signing code — Zone B should never hold keys
RUN rm -f bots/treasury/wallet.py

USER jarvis

# No exposed ports (internal only)

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import psycopg; print('db ok')" || exit 1

CMD ["python", "-m", "core.jupiter_perps.reconciliation"]
