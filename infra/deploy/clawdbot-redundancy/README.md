# ClawdBot Infrastructure Deployment

Complete deployment package for ClawdBot multi-agent system with extreme redundancy, self-healing, and autonomous evolution.

## Quick Start

```bash
# Deploy everything to VPS
./install-full.sh

# Or deploy manually step by step
./deploy-to-vps.sh
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         VPS (76.13.106.100)                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Friday    │  │    Matt     │  │   Jarvis    │             │
│  │  (CMO)      │  │   (COO)     │  │   (CTO)     │             │
│  │  :18789     │  │   :18800    │  │   :18801    │             │
│  │  Opus 4.5   │  │  Codex 5.2  │  │   Grok 4.1  │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│         └────────────────┴────────────────┘                     │
│                          │                                      │
│                    ┌─────┴─────┐                                │
│                    │ Health API │                               │
│                    │   :18888   │                               │
│                    └─────┬─────┘                                │
│                          │                                      │
│  ┌───────────────────────┴────────────────────────────────┐    │
│  │                  Shared Infrastructure                  │    │
│  │  • SuperMemory (SQLite)  • Tailscale Mesh              │    │
│  │  • Redis Context Cache   • Watchdog (1 min)            │    │
│  └────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
deploy/clawdbot-redundancy/
├── Dockerfile.clawdbot-full     # Full image with all packages
├── docker-compose.clawdbots.yml # 3-bot deployment
├── entrypoint.sh                # Container startup
├── tailscale-start.sh           # Mesh networking
├── firewall-rules.sh            # Security hardening
├── install-full.sh              # Master installer
├── deploy-to-vps.sh             # Simple deployment
│
├── scripts/
│   ├── nightly-backup.sh        # Soul/memory backup
│   ├── brain-export.sh          # Portable brain archive
│   ├── brain-import.sh          # Restore from archive
│   ├── self-evolution-reflect.sh# Daily/weekly/monthly reflection
│   ├── trust-ladder.sh          # Autonomy progression tracking
│   ├── circuit-breaker.sh       # Provider failure protection
│   ├── redis-hydration.sh       # Fast context loading
│   └── setup-cron.sh            # Automated task scheduler
│
├── monitoring/
│   ├── uptime-kuma-docker-compose.yml
│   ├── uptime-kuma-monitors.json
│   └── prometheus-config.yml
│
└── akash/
    ├── deploy.yaml              # Decentralized GPU deployment
    └── README.md
```

## Components

### 1. Pre-built Docker Image
All tools baked in for instant startup:
- **Essential**: git, curl, wget, openssh-client, jq, rsync
- **Infrastructure**: tailscale, iptables
- **Quality of Life**: vim, nano, htop, tree
- **Media**: ffmpeg

### 2. Multi-Layer Recovery
| Layer | Mechanism | Interval | Action |
|-------|-----------|----------|--------|
| 1 | Docker restart | Immediate | Container restart |
| 2 | VPS Watchdog | 1 minute | Health check + restart |
| 3 | Health API | On-demand | Remote recovery trigger |
| 4 | Circuit Breaker | Per-request | Provider fallback |

### 3. Persistent Memory
- **Soul Documents**: Personality, identity, agents, tools
- **Memory**: Learned patterns, conversation context
- **Skills**: Acquired capabilities
- **State**: Trust level, circuit breaker state

### 4. Self-Evolution System
- **Hourly**: Performance metrics
- **Daily**: Strategy effectiveness analysis
- **Weekly**: User satisfaction review
- **Monthly**: Architecture review

### 5. Trust Ladder
| Level | Name | Requirements |
|-------|------|--------------|
| 1 | Assisted | 0 successes |
| 2 | Monitored | 10 successes, <5 errors |
| 3 | Autonomous | 50 successes, <2 errors |
| 4 | Trusted | 200 successes, 0 errors |

## Configuration

### Environment Variables
```bash
# Required
TAILSCALE_AUTHKEY=tskey-auth-xxx  # Mesh authentication
XAI_API_KEY=xai-xxx               # For Jarvis (Grok)

# Optional
REDIS_HOST=localhost              # Context cache
TELEGRAM_BOT_TOKEN=xxx            # Alert notifications
TELEGRAM_CHAT_ID=xxx              # Alert destination
```

### Tailscale Setup
Containers join the mesh automatically with:
- `--cap-add=NET_ADMIN`
- `--device /dev/net/tun`
- `--tun=userspace-networking`

### Security
- Gateway ports (18789/18800/18801) restricted to Tailscale
- Health API (18888) public for external monitoring
- Credentials secured with `chmod 600`

## Management Commands

```bash
# Check status
./scripts/trust-ladder.sh status
./scripts/circuit-breaker.sh status

# Record events
./scripts/trust-ladder.sh record friday success "completed trade"
./scripts/circuit-breaker.sh record openai failure

# Backup/restore
./scripts/brain-export.sh friday /tmp/friday-brain.tar.gz
./scripts/brain-import.sh friday /tmp/friday-brain.tar.gz

# Manual reflection
./scripts/self-evolution-reflect.sh

# Redis operations
./scripts/redis-hydration.sh hydrate friday
./scripts/redis-hydration.sh status
```

## Monitoring

### Uptime Kuma
```bash
cd monitoring
docker-compose -f uptime-kuma-docker-compose.yml up -d
# Access: http://localhost:3001
```

### Prometheus + Grafana
```bash
docker run -d -p 9090:9090 \
  -v $(pwd)/monitoring/prometheus-config.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

## Akash Deployment (Decentralized)

For GPU workloads:
```bash
cd akash
akash tx deployment create deploy.yaml --from wallet
```

See [akash/README.md](akash/README.md) for details.

## Troubleshooting

### Container won't start
```bash
docker logs clawdbot-friday --tail 50
```

### Tailscale not connecting
```bash
docker exec clawdbot-friday tailscale status
# Check if authkey is valid and TUN device available
```

### High memory usage
```bash
docker stats --no-stream
# Check for "zombie mode" - restart if >90% memory
```

### Provider errors
```bash
./scripts/circuit-breaker.sh status
# If OPEN, wait for recovery or reset manually
./scripts/circuit-breaker.sh reset openai
```

## Cost Optimization

| Platform | Configuration | Cost |
|----------|--------------|------|
| VPS (current) | 4 CPU, 8GB RAM | ~$40/mo |
| Akash (CPU) | 4 CPU, 8GB RAM | ~$70/mo |
| Akash (GPU) | RTX 4090 | ~$580/mo |

## Contributing

1. Test changes locally with Docker
2. Deploy to staging VPS first
3. Run reflection analysis after changes
4. Document any new patterns in soul documents
