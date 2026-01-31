# Next Steps After Code Reconciliation

**Status:** Local and GitHub are synchronized at commit 93a6ff5
**Date:** 2026-01-31 13:25

---

## Option 1: Commit Unstaged Security Improvements (RECOMMENDED)

These are security hardening changes that should be committed:

```bash
# Add security improvements
git add core/data/query_optimizer.py
git add tests/security/test_sql_injection.py
git add scripts/check_telegram_tokens.py
git add docs/CODE_RECONCILIATION_JAN_31.md

# Commit with descriptive message
git commit -m "$(cat <<'COMMIT_MSG'
security: query optimizer SELECT-only enforcement + test improvements

**Query Optimizer Security:**
- Restrict analyze() to SELECT queries only
- Prevent execution of INSERT/UPDATE/DELETE in analysis
- Add clear warnings for non-SELECT queries

**Test Infrastructure:**
- Fix Windows file locking issues in SQL injection tests
- Proper cleanup of temp files with try/finally
- Handle PermissionError on Windows

**Diagnostic Tools:**
- Add check_telegram_tokens.py for token config analysis
- Helps diagnose polling lock conflicts

Defense-in-depth: Query analyzer should never modify data.

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
COMMIT_MSG
)"

# Push to GitHub
git push origin main
```

---

## Option 2: Review Changes First

If you want to review the changes before committing:

```bash
# See what will be committed
git diff core/data/query_optimizer.py
git diff tests/security/test_sql_injection.py
cat scripts/check_telegram_tokens.py

# Review specific sections
git diff --stat
```

---

## Option 3: Deploy to VPS (After Committing)

Once the security improvements are committed and pushed:

```bash
# SSH to VPS
ssh user@vps-hostname

# Navigate to project
cd /path/to/jarvis

# Backup current state
git log -1 > /tmp/pre-update-commit.txt

# Pull latest changes
git fetch origin main
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Restart services
systemctl restart jarvis-supervisor
systemctl restart jarvis-telegram

# Verify services are running
systemctl status jarvis-supervisor
systemctl status jarvis-telegram

# Check logs for errors
journalctl -u jarvis-supervisor -n 50
journalctl -u jarvis-telegram -n 50
```

### VPS Rollback (If Needed)

```bash
# If issues occur, rollback to previous version
git reset --hard 0b595a7
pip install -r requirements.txt
systemctl restart jarvis-supervisor
systemctl restart jarvis-telegram
```

---

## Option 4: Skip Unstaged Changes (Not Recommended)

If you want to skip the security improvements for now:

```bash
# Discard unstaged changes (NOT RECOMMENDED - loses security hardening)
git restore core/data/query_optimizer.py
git restore tests/security/test_sql_injection.py
rm scripts/check_telegram_tokens.py
rm docs/CODE_RECONCILIATION_JAN_31.md

# This will lose the SELECT-only enforcement and Windows test fixes
```

---

## Recommended Workflow

**Step 1:** Commit security improvements (Option 1)
```bash
git add core/data/query_optimizer.py tests/security/test_sql_injection.py scripts/check_telegram_tokens.py docs/CODE_RECONCILIATION_JAN_31.md
git commit -m "security: query optimizer SELECT-only + test improvements"
git push origin main
```

**Step 2:** Coordinate VPS deployment
- Notify user that changes are ready
- Schedule deployment window
- Have rollback plan ready

**Step 3:** Deploy to VPS (Option 3)
- Pull latest changes
- Restart services
- Verify logs

**Step 4:** Monitor
- Watch for errors in first 30 minutes
- Check Telegram bot responsiveness
- Verify supervisor stability

---

## Summary of Changes to Deploy

### Already on GitHub (from earlier commits)
- Supervisor single-instance lock
- SQL injection fixes (38 points)
- Telegram polling coordinator
- WebSocket cleanup
- Dependency updates

### Pending (unstaged)
- Query optimizer SELECT-only security
- Test infrastructure improvements
- Token diagnostic tool

### Total Impact
- 2,000+ lines improved
- Zero conflicts
- Low risk deployment

---

## Questions?

Review the full reconciliation report at:
`C:/Users/lucid/OneDrive/Desktop/Projects/Jarvis/docs/CODE_RECONCILIATION_JAN_31.md`

