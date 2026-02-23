# Friday (CMO) — Heartbeat Checklist

## Run Every: 120 seconds

## Health Checks
- [ ] Am I responsive? (can I send a test message?)
- [ ] Is my Supermemory connection active?
- [ ] Am I within memory/CPU limits?
- [ ] Is the email queue processing? (check for stuck or failed sends)
- [ ] Are social media API connections live? (X/Twitter, Telegram)
- [ ] Are brand assets accessible? (logos, templates, style guide files)
- [ ] Is the content scheduler running on time?

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
2. Attempt self-recovery (reconnect API, flush queue, reload templates)
3. If self-recovery fails, alert Arsenal (or Jarvis if Arsenal is down)
4. Send brief status to group: "Friday experiencing issues with [service]. Working on recovery."
