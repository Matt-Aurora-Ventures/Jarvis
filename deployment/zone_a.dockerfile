# Zone A — Public-Facing Host (Untrusted)
#
# Runs: Dashboard, Telegram webhook, AI Macro Engine, Monitoring UI
# Does NOT have: signing keys, trading wallet, direct DB write access
# Does NOT run: execution service, signer process
#
# Network: inbound 443 (HTTPS), 8443 (Telegram webhook)
# Outbound: Telegram API, X API, OpenAI, Anthropic, monitoring stack
#
# Security:
#   - No PERPS_WALLET_ADDRESS environment variable
#   - No PERPS_DB_DSN pointing to execution tables
#   - Communicates with Zone B over mTLS authenticated channel only

FROM python:3.11-slim-bookworm AS base

LABEL zone="A" \
      description="Public-facing host: dashboard, Telegram, AI" \
      security.signing_keys="none" \
      security.can_submit_txs="false"

# Security hardening
RUN groupadd -r jarvis && useradd -r -g jarvis -s /sbin/nologin jarvis
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ONLY Zone A (AI + dashboard) dependencies
COPY requirements/ai.txt requirements/ai.txt
RUN pip install --no-cache-dir \
    --require-hashes \
    -r requirements/ai.txt

# Copy application code (no signer code needed)
COPY bots/telegram/ bots/telegram/
COPY bots/twitter/ bots/twitter/
COPY tg_bot/ tg_bot/
COPY web/ web/
COPY api/ api/
COPY core/context_loader.py core/context_loader.py
COPY lifeos/ lifeos/

# Remove any signer-related files if accidentally included
RUN find /app -name "wallet.py" -delete 2>/dev/null || true
RUN find /app -name "*.key" -delete 2>/dev/null || true
RUN find /app -name "*.pem" -delete 2>/dev/null || true

USER jarvis

# Telegram webhook
EXPOSE 8443

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8443/health || exit 1

# Entrypoint: Telegram webhook server
CMD ["python", "-m", "tg_bot.main", "--webhook"]
