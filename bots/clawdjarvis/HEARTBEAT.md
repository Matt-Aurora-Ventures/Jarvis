# Jarvis (CTO) — Heartbeat Checklist

## Run Every: 60 seconds

## Health Checks
- [ ] Am I responsive? (can I send a test message?)
- [ ] Is my Supermemory connection active?
- [ ] Am I within memory/CPU limits?
- [ ] Are all Docker containers healthy? (check `docker ps` for restarts or exited containers)
- [ ] Are trading positions within risk parameters?
- [ ] Are infrastructure metrics nominal? (disk, CPU, memory, network)
- [ ] Is Tailscale mesh connected with all expected peers?
- [ ] Are database connections alive and query latency acceptable?

## Team Checks
- [ ] Have I received heartbeat pings from peers in the last 5 minutes?
- [ ] Is Arsenal (coordinator) responsive?
- [ ] Any unacknowledged tasks in the group?

## Response Length Guard
- Maximum single message: 4000 characters
- If response exceeds limit: split into multiple messages
- Never let a response cause a timeout
- If processing takes >30 seconds, send a "working on it..." interim message

## If Something Fails
1. Log the failure with timestamp and service name
2. Attempt self-recovery (restart container, reconnect database, refresh API token)
3. If self-recovery fails, alert Arsenal with failure details
4. Send brief status to group: "Jarvis experiencing issues with [service]. Working on recovery."
