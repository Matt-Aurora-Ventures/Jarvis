# ============================================================================
# Jarvis LifeOS - Production Dockerfile
# ============================================================================
# Multi-stage build for optimized image size
# Base: Python 3.11 slim + Debian bookworm
# ============================================================================

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Minimal production image
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="Jarvis LifeOS <jarvis@lifeos.ai>"
LABEL version="4.6.6"
LABEL description="Jarvis LifeOS - Autonomous Trading & AI Assistant"

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    redis-tools \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash jarvis

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create directory structure
WORKDIR /home/jarvis/Jarvis
RUN mkdir -p \
    logs \
    data \
    backups \
    bots/treasury \
    bots/twitter \
    bots/data \
    && chown -R jarvis:jarvis /home/jarvis

# Copy application code
COPY --chown=jarvis:jarvis . .

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; r = requests.get('http://localhost:8080/health', timeout=5); exit(0 if r.status_code == 200 else 1)" || exit 1

# Switch to non-root user
USER jarvis

# Default environment variables
ENV JARVIS_HOME=/home/jarvis/Jarvis
ENV LOG_LEVEL=INFO
ENV PYTHONPATH=/home/jarvis/Jarvis

# Expose ports
# 8080: Health check API
# 5000: System Control Deck
# 5001: Trading Web UI
EXPOSE 8080 5000 5001

# Default command
CMD ["python", "bots/supervisor.py"]
