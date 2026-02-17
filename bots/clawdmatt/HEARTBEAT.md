# Arsenal (COO) — Heartbeat Checklist

## Run Every: 60 seconds

## Health Checks
- [ ] Am I responsive? (can I send a test message?)
- [ ] Is my Supermemory connection active?
- [ ] Am I within memory/CPU limits?
- [ ] Are all team members reporting status? (check last heartbeat from each bot)
- [ ] Is the moderation queue clear or being processed?
- [ ] Are assigned tasks progressing? (flag any stale tasks older than 15 minutes)
- [ ] Is the group management connection active?

## Team Checks
- [ ] Have I received heartbeat pings from peers in the last 5 minutes?
- [ ] Is Jarvis (fallback coordinator) responsive?
- [ ] Any unacknowledged tasks in the group?
- [ ] Are any bots unresponsive? (escalate to Jarvis if peer is down >2 heartbeats)

## Response Length Guard
- Maximum single message: 4000 characters
- If response exceeds limit: split into multiple messages
- Never let a response cause a timeout
- If processing takes >30 seconds, send a "working on it..." interim message

## If Something Fails
1. Log the failure with timestamp and affected bot/service
2. Attempt self-recovery (reconnect, re-poll team status)
3. If self-recovery fails, alert Jarvis directly
4. Send brief status to group: "Arsenal experiencing issues with [service]. Working on recovery."
