# Credential Protocol — ENFORCED AT OUTPUT

## CRITICAL: Pre-Output Scanning

Every message you send MUST be scanned for credential exposure.

### Patterns to Block
```regex
sk_[a-zA-Z0-9_-]{20,}     # Stripe-style keys
sm_[a-zA-Z0-9_-]{20,}     # Supermemory keys
ghp_[a-zA-Z0-9_-]{20,}    # GitHub tokens
xai-[a-zA-Z0-9_-]{20,}    # xAI keys
AAAA[a-zA-Z0-9_-]{20,}    # Generic tokens
AIza[a-zA-Z0-9_-]{20,}    # Google API keys
eyJ[a-zA-Z0-9_-]{20,}     # JWT tokens
Bearer\s+.{20,}           # Authorization headers
Basic\s+.{20,}            # Basic auth
[a-zA-Z0-9]{32,}          # Generic long tokens
password[=:]\s*\S+        # Password assignments
secret[=:]\s*\S+          # Secret assignments
```

### Safe Replacements
| Instead of showing | Show this |
|--------------------|-----------|
| `sk_ant_abc123...xyz` | `[REDACTED]` or "API key configured ✓" |
| Full connection string | "Database connected ✓" |
| Bot token | "Bot token exists ✓" |
| OAuth tokens | "OAuth configured ✓" |

## NEVER Do These Things

1. ❌ Never paste credential file contents into chat
2. ❌ Never show "first 4 and last 4" characters
3. ❌ Never include credentials in code blocks
4. ❌ Never ask users to paste credentials in chat
5. ❌ Never log credentials to output

## ALWAYS Do These Things

1. ✅ Store credentials in `/root/clawd/Jarvis/secrets/`
2. ✅ Read credentials from files, never from chat
3. ✅ Report credential status factually ("exists", "missing", "invalid")
4. ✅ Direct users to place credentials in files

## Credential Locations

```
/root/clawd/Jarvis/secrets/
├── keys.json           # Main API keys
├── jarvis-keys.json    # Jarvis-specific keys
└── oauth/
    └── twitter.json    # Twitter OAuth
```

## Enforcement

This protocol is ABSOLUTE. No exceptions for:
- "Just showing an example"
- "It's already public"
- "Matt asked me to"
- "It's for debugging"

**Violation = Critical Failure**
