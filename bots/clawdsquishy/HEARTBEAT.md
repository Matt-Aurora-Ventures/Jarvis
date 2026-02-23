# Squishy (CRO) — Heartbeat Checklist

## Run Every: 120 seconds

## Health Checks
- [ ] Am I responsive? (can I send a test message?)
- [ ] Is my Supermemory connection active?
- [ ] Am I within memory/CPU limits?
- [ ] Are data feed connections alive? (market data, news APIs, research sources)
- [ ] Is the research archive intact and accessible? (verify index, check last write)
- [ ] Is the Gemini API connection active and responding within latency threshold?
- [ ] Are web scraping targets reachable? (check for rate limits or blocks)

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
1. Log the failure with timestamp and data source name
2. Attempt self-recovery (reconnect feed, rotate API key, switch to backup source)
3. If self-recovery fails, alert Arsenal (or Jarvis if Arsenal is down)
4. Send brief status to group: "Squishy experiencing issues with [data source]. Working on recovery."
