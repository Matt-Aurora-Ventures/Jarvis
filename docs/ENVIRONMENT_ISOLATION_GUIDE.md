# Environment Variable Isolation Guide

**Purpose:** Prevent credential leakage between components via environment variable bleed
**Last Updated:** 2026-01-31
**Priority:** HIGH SECURITY

---

## Problem: Environment Variable Bleed

### What is it?

When multiple components load different `.env` files, variables can leak across component boundaries:

```python
# Component A loads twitter/.env
load_dotenv("bots/twitter/.env")  # Sets XAI_API_KEY

# Component B loads telegram/.env
load_dotenv("tg_bot/.env")  # XAI_API_KEY still visible!

# Component B can now access Component A's credentials
print(os.getenv("XAI_API_KEY"))  # SECURITY RISK
```

### Why is it dangerous?

1. **Credential Misuse**: Components access credentials they shouldn't have
2. **Audit Confusion**: Hard to track which component uses which credentials
3. **Token Conflicts**: Multiple bots using same TELEGRAM_BOT_TOKEN (actual issue we had!)
4. **Data Leakage**: Sensitive keys logged by wrong component

---

## Solution: Component Isolation

### Principle

**Each component should ONLY load its own .env file and ONLY access its own credentials.**

### Implementation Rules

1. **Use `override=False`** - Never overwrite existing env vars
2. **Scope Loading** - Load .env as late as possible (component init)
3. **Validate Ownership** - Check that required vars exist before use
4. **Prefix Keys** - Use component prefixes for shared systems
5. **Explicit Loading** - No global .env loading at import time

---

## Current Architecture

### Component .env Files

| Component | .env Location | Purpose |
|-----------|---------------|---------|
| Main System | `lifeos/config/.env` | System-wide settings |
| Telegram Bot | `tg_bot/.env` | Telegram bot config |
| Twitter Bot | `bots/twitter/.env` | X/Twitter credentials |
| Treasury | `lifeos/config/.env` | Trading credentials (shared) |
| Buy Tracker | `bots/buy_tracker/.env` | Buy tracker config |
| Bags Intel | `bots/bags_intel/.env` | Bags.fm credentials |

### Credential Ownership Matrix

| Credential | Owner | Used By |
|------------|-------|---------|
| TELEGRAM_BOT_TOKEN | tg_bot | Main Telegram bot |
| TREASURY_BOT_TOKEN | treasury | Treasury trading bot |
| X_BOT_TELEGRAM_TOKEN | twitter | X sync to Telegram |
| XAI_API_KEY | twitter | Grok API (sentiment, content) |
| ANTHROPIC_API_KEY | system | Claude AI (all components) |
| HELIUS_API_KEY | system | Solana RPC (all components) |
| BIRDEYE_API_KEY | system | Token data (all components) |
| BAGS_API_KEY | bags_intel | Bags.fm graduation monitoring |

---

## Best Practices

### 1. Isolated Loading

**GOOD:**
```python
# Component loads only its own .env
class TwitterBot:
    def __init__(self):
        # Load .env scoped to this component
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)

        # Validate ownership
        self.api_key = os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("XAI_API_KEY not found (required by Twitter bot)")
```

**BAD:**
```python
# Global import-time loading
from dotenv import load_dotenv
load_dotenv("all_secrets.env")  # Leaks everywhere!

# Module-level access
API_KEY = os.getenv("XAI_API_KEY")  # Visible to all imports
```

### 2. Component Prefixes

For shared systems (supervisor, database), use prefixes:

```bash
# lifeos/config/.env
SYSTEM_DATABASE_URL=postgresql://...
SYSTEM_REDIS_URL=redis://...
SYSTEM_LOG_LEVEL=INFO

# Component-specific
TG_BOT_ADMIN_IDS=123456789
TWITTER_BOT_ENABLED=true
TREASURY_LIVE_MODE=false
```

### 3. Explicit Validation

```python
def load_component_config(component_name: str, required_vars: List[str]):
    """Load .env with validation"""
    env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)

    # Validate all required vars exist
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(
            f"{component_name} missing required environment variables: {missing}"
        )
```

### 4. Scoped Access

**Use dataclasses to scope credentials:**

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class TwitterConfig:
    """Twitter bot configuration - scoped credentials"""

    api_key: str
    api_secret: str
    bearer_token: str
    access_token: str
    access_token_secret: str
    xai_api_key: str

    @classmethod
    def from_env(cls):
        """Load from environment variables"""
        # Load .env only when needed
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)

        # Explicit field mapping
        return cls(
            api_key=os.getenv("X_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", ""),
            bearer_token=os.getenv("X_BEARER_TOKEN", ""),
            access_token=os.getenv("X_ACCESS_TOKEN", ""),
            access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET", ""),
            xai_api_key=os.getenv("XAI_API_KEY", ""),
        )

    def validate(self) -> List[str]:
        """Return list of missing required fields"""
        missing = []
        if not self.api_key:
            missing.append("X_API_KEY")
        if not self.xai_api_key:
            missing.append("XAI_API_KEY")
        return missing

# Usage
config = TwitterConfig.from_env()
if missing := config.validate():
    raise ValueError(f"Missing Twitter config: {missing}")
```

---

## Anti-Patterns to Avoid

### 1. Global .env Loading

```python
# ❌ BAD: Top-level import loading
from dotenv import load_dotenv
load_dotenv()  # Loads .env from CWD - could be ANY file!

# ✅ GOOD: Explicit path, scoped to function
def init_component():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
```

### 2. Shared .env Files

```python
# ❌ BAD: Multiple components loading same file
# bots/twitter/bot.py
load_dotenv("lifeos/config/.env")

# tg_bot/bot.py
load_dotenv("lifeos/config/.env")  # Same file!

# ✅ GOOD: Each component has its own .env
# bots/twitter/bot.py
load_dotenv("bots/twitter/.env")

# tg_bot/bot.py
load_dotenv("tg_bot/.env")
```

### 3. Override=True

```python
# ❌ BAD: Overwrites existing vars
load_dotenv(".env", override=True)  # Can clobber system vars!

# ✅ GOOD: Respect existing values
load_dotenv(".env", override=False)  # Never overwrites
```

### 4. No Validation

```python
# ❌ BAD: Assumes vars exist
api_key = os.getenv("API_KEY")
client = Client(api_key)  # Crashes if None!

# ✅ GOOD: Validate before use
api_key = os.getenv("API_KEY")
if not api_key:
    raise ValueError("API_KEY environment variable required")
client = Client(api_key)
```

---

## Audit Checklist

### Component Isolation Audit

Run this audit for each component:

```bash
# Check .env loading
grep -r "load_dotenv" bots/twitter/

# Verify override=False
grep -r "load_dotenv.*override" bots/twitter/

# Find global loads (danger!)
grep -r "^from dotenv import load_dotenv" bots/twitter/

# Check for shared .env files
find . -name ".env" -exec echo {} \;
```

### Expected Findings

Each component should:
- [ ] Load ONLY its own .env file
- [ ] Use `override=False` always
- [ ] Not load .env at module import time
- [ ] Validate required credentials exist
- [ ] Not access credentials from other components

---

## Current Status (2026-01-31)

### Compliant Components

✅ **tg_bot/config.py** - Uses manual parsing with setdefault (good!)
✅ **bots/twitter/telegram_sync.py** - Loads both .env with override=False
✅ **bots/treasury/run_treasury.py** - Loads with override=False

### Needs Review

⏳ **bots/twitter/autonomous_engine.py** - Manual parsing (lines 74-82)
⏳ **bots/twitter/config.py** - Uses load_dotenv (check override)
⏳ **bots/bags_intel/config.py** - Uses load_dotenv (check override)

### Action Items

1. Audit all components using grep findings above
2. Add `override=False` where missing
3. Move module-level loads to function/class init
4. Add validation for required vars
5. Document credential ownership in README

---

## Testing Isolation

### Test 1: Component Independence

```python
# test_env_isolation.py
import os
import sys
from pathlib import Path

def test_twitter_isolation():
    """Twitter bot should only see its own credentials"""

    # Clear environment
    for key in list(os.environ.keys()):
        if key.startswith(("XAI", "X_", "TWITTER")):
            del os.environ[key]

    # Load Twitter config
    sys.path.insert(0, str(Path(__file__).parent.parent / "bots" / "twitter"))
    from config import TwitterConfig

    config = TwitterConfig.from_env()

    # Should have Twitter creds
    assert config.api_key
    assert config.xai_api_key

    # Should NOT have Telegram creds
    assert not os.getenv("TELEGRAM_BOT_TOKEN")
    assert not os.getenv("TREASURY_BOT_TOKEN")

def test_telegram_isolation():
    """Telegram bot should only see its own credentials"""

    # Clear environment
    for key in list(os.environ.keys()):
        if key.startswith(("TELEGRAM", "XAI", "ANTHROPIC")):
            del os.environ[key]

    # Load Telegram config
    sys.path.insert(0, str(Path(__file__).parent.parent / "tg_bot"))
    from config import get_config

    config = get_config()

    # Should have Telegram creds
    assert config.telegram_token

    # Should NOT have Twitter OAuth
    assert not os.getenv("X_API_KEY")
    assert not os.getenv("X_ACCESS_TOKEN")
```

### Test 2: No Override

```python
def test_no_override():
    """Components should not overwrite existing env vars"""

    # Set a var before loading
    os.environ["XAI_API_KEY"] = "original_value"

    # Load .env (should not overwrite)
    from dotenv import load_dotenv
    load_dotenv("bots/twitter/.env", override=False)

    # Should still be original
    assert os.getenv("XAI_API_KEY") == "original_value"
```

---

## Migration Guide

### For Existing Components

1. **Locate .env loading code**
   ```bash
   grep -n "load_dotenv" bots/mycomponent/*.py
   ```

2. **Add override=False**
   ```python
   # Before
   load_dotenv(".env")

   # After
   load_dotenv(".env", override=False)
   ```

3. **Move to function scope**
   ```python
   # Before (module-level)
   from dotenv import load_dotenv
   load_dotenv()
   API_KEY = os.getenv("API_KEY")

   # After (scoped)
   class MyComponent:
       def __init__(self):
           from dotenv import load_dotenv
           env_path = Path(__file__).parent / ".env"
           load_dotenv(env_path, override=False)
           self.api_key = os.getenv("API_KEY")
   ```

4. **Add validation**
   ```python
   if not self.api_key:
       raise ValueError("API_KEY required by MyComponent")
   ```

---

## Centralized Loader Utility

**File:** `core/config/env_loader.py` (NEW)

```python
"""
Centralized environment loading utility with isolation guarantees
"""

import os
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass


@dataclass
class EnvLoadResult:
    """Result of loading environment variables"""
    loaded_vars: List[str]
    missing_vars: List[str]
    path: Path


def load_component_env(
    component_path: Path,
    required_vars: Optional[List[str]] = None,
    optional_vars: Optional[List[str]] = None,
    validate: bool = True
) -> EnvLoadResult:
    """
    Load .env file for a component with isolation guarantees

    Args:
        component_path: Path to component directory (e.g., Path(__file__).parent)
        required_vars: List of required environment variable names
        optional_vars: List of optional environment variable names
        validate: Whether to raise error on missing required vars

    Returns:
        EnvLoadResult with loaded/missing vars

    Raises:
        ValueError: If validation enabled and required vars missing
    """
    env_path = component_path / ".env"

    if not env_path.exists():
        if validate and required_vars:
            raise FileNotFoundError(f"Component .env not found: {env_path}")
        return EnvLoadResult([], required_vars or [], env_path)

    # Load with override=False (never overwrite existing vars)
    from dotenv import load_dotenv
    load_dotenv(env_path, override=False)

    # Track what was loaded
    loaded = []
    missing = []

    # Check required vars
    for var in (required_vars or []):
        if os.getenv(var):
            loaded.append(var)
        else:
            missing.append(var)

    # Check optional vars
    for var in (optional_vars or []):
        if os.getenv(var):
            loaded.append(var)

    # Validate
    if validate and missing:
        raise ValueError(
            f"Component at {component_path} missing required environment variables: {missing}\n"
            f"Please add them to {env_path}"
        )

    return EnvLoadResult(loaded, missing, env_path)


# Usage example
if __name__ == "__main__":
    # Twitter bot
    result = load_component_env(
        component_path=Path(__file__).parent.parent / "bots" / "twitter",
        required_vars=["XAI_API_KEY", "X_API_KEY"],
        optional_vars=["X_BEARER_TOKEN"],
        validate=True
    )
    print(f"Loaded: {result.loaded_vars}")
    print(f"Missing: {result.missing_vars}")
```

---

## References

- Python dotenv Documentation: https://saurabh-kumar.com/python-dotenv/
- 12-Factor App: https://12factor.net/config
- Security Best Practices: `docs/VPS_HARDENING_GUIDE.md`

---

**Maintained By:** Jarvis Security Team
**Last Audit:** 2026-01-31
**Next Review:** 2026-02-28
