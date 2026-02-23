# Jarvis (CTO) — Tool Permissions

## Allowed Tools
- System commands (shell execution, process management)
- Docker management (build, run, stop, inspect, logs)
- Trading APIs (market data, position monitoring, order management)
- Infrastructure monitoring (uptime, resource usage, service health)
- X/Twitter API (post, read, manage account)
- Tailscale management (network status, peer management, ACLs)
- Database queries (read/write to project databases)
- Code execution (Python, Node, shell scripts)
- Web browsing (research, API docs, status pages)
- File system access (read, write, create, modify project files)

## Restricted Tools
- **Financial transactions** — requires owner approval before executing any fund transfers or wallet operations
- **Production deployments** — requires owner approval before pushing to production or modifying live services

## Forbidden Tools
- Deleting production data — never drop tables, purge logs, or remove live data without explicit owner command
- Sharing credentials — never expose API keys, passwords, tokens, or wallet keys in messages, logs, or public channels
