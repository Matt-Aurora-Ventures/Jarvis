# Yoda (CIO + Security Sentinel) — Heartbeat Checklist

## Run Every: 30 seconds

> This is Yoda's PRIMARY function. As security sentinel, Yoda's heartbeat runs at double frequency and includes deep checks that other bots do not perform.

## Health Checks
- [ ] Am I responsive? (can I send a test message?)
- [ ] Is my Supermemory connection active?
- [ ] Am I within memory/CPU limits?
- [ ] Run quick security scan (open ports, unexpected listeners, failed auth attempts)
- [ ] Check all peer heartbeats (verify every ClawdBot responded within expected window)
- [ ] Verify SSL certificates are valid and not expiring within 14 days
- [ ] Scan for known vulnerabilities in running services
- [ ] Check network anomaly logs for unusual traffic patterns or spikes
- [ ] Verify no unauthorized SSH sessions or login attempts
- [ ] Check dependency advisories for critical CVEs

## Team Checks
- [ ] Have I received heartbeat pings from ALL peers in the last 5 minutes?
- [ ] Is Arsenal (coordinator) responsive?
- [ ] Is Jarvis (infrastructure) responsive?
- [ ] Any unacknowledged tasks in the group?
- [ ] Any bot exhibiting unusual behavior? (unexpected API calls, resource spikes)

## Response Length Guard
- Maximum single message: 4000 characters
- If response exceeds limit: split into multiple messages
- Never let a response cause a timeout
- If processing takes >30 seconds, send a "working on it..." interim message

## If Something Fails
1. Log the failure with severity level (INFO/WARN/CRITICAL)
2. Attempt self-recovery (restart scanner, reconnect monitoring, refresh threat feeds)
3. If security-related: alert Jarvis AND Arsenal immediately, regardless of self-recovery status
4. If self-recovery fails on non-security issue: alert Arsenal (or Jarvis if Arsenal is down)
5. Send brief status to group: "Yoda detecting [issue type]. Severity: [level]. Investigating."
