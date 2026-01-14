# JARVIS Import Organization Standards

Guidelines for organizing imports in Python files.

---

## Import Order

Imports should be organized in the following groups, separated by blank lines:

1. **Standard Library** - Built-in Python modules
2. **Third-Party** - Installed packages (pip)
3. **Local Application** - JARVIS modules

```python
# 1. Standard library
import os
import sys
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

# 2. Third-party packages
import httpx
from fastapi import FastAPI, Depends
from pydantic import BaseModel

# 3. Local application
from core.config import settings
from core.security import verify_token
from core.llm import get_provider
```

---

## Import Style

### Use Absolute Imports

Prefer absolute imports over relative imports:

```python
# GOOD: Absolute imports
from core.security.auth import verify_token
from core.llm.providers import get_default_provider

# AVOID: Relative imports (except in __init__.py)
from .auth import verify_token
from ..llm.providers import get_default_provider
```

### Import Specific Names

Import specific names rather than entire modules when practical:

```python
# GOOD: Import specific classes/functions
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from fastapi import FastAPI, HTTPException, Depends

# ACCEPTABLE: Import module for namespacing
import logging
import json

# AVOID: Star imports
from typing import *  # Never do this
from core.utils import *  # Never do this
```

### Group Related Imports

```python
# GOOD: Related items on one line
from typing import Dict, List, Optional, Any, Union

# GOOD: Split when too long (88 char limit)
from typing import (
    Dict, List, Optional, Any, Union,
    Callable, Awaitable, TypeVar, Generic
)
```

---

## Type Imports

Use `TYPE_CHECKING` for imports only needed for type hints:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import User
    from core.services import TradingService

class OrderHandler:
    def __init__(self, service: "TradingService"):
        self.service = service
```

---

## Module Aliases

Use standard aliases for common packages:

```python
import numpy as np
import pandas as pd
import tensorflow as tf
import matplotlib.pyplot as plt

# Avoid non-standard aliases
import numpy as numpy_lib  # Don't do this
```

---

## Avoiding Circular Imports

### Strategy 1: Move imports inside functions

```python
def get_user_service():
    # Import inside function to avoid circular import
    from core.services.user import UserService
    return UserService()
```

### Strategy 2: Use TYPE_CHECKING

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import User  # Only imported for type checking

def process_user(user: "User") -> None:
    pass
```

### Strategy 3: Restructure modules

If you frequently have circular imports, consider:
- Moving shared code to a common module
- Using dependency injection
- Creating interface/protocol classes

---

## Import Tools

### isort Configuration

Add to `pyproject.toml`:

```toml
[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
known_first_party = ["core", "api", "bots", "integrations", "tg_bot"]
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
```

### Running isort

```bash
# Check imports
isort --check-only .

# Fix imports
isort .

# Show diff
isort --diff .
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
```

---

## Common Import Patterns

### Logging

```python
import logging

logger = logging.getLogger(__name__)
```

### Configuration

```python
from core.config import settings

# Or for specific settings
from core.config.settings import DATABASE_URL, API_KEY
```

### FastAPI Dependencies

```python
from fastapi import Depends, HTTPException, status
from core.security import get_current_user, verify_api_key
from core.db import get_db
```

### Async Utilities

```python
import asyncio
from typing import Awaitable, Callable
from functools import wraps
```

### Data Classes

```python
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
```

### Pydantic Models

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List
```

---

## Anti-Patterns

### Don't import from __init__ chains

```python
# AVOID: Deep __init__ chains
from core.services.user.handlers.registration import RegistrationHandler

# PREFER: Export from package level
from core.services import RegistrationHandler
```

### Don't shadow builtins

```python
# AVOID
from typing import List
list = []  # Shadows builtin

# PREFER
from typing import List
items: List[str] = []
```

### Don't import unused

```python
# AVOID: Unused imports
import os  # Never used
from typing import Dict, List  # Dict never used

# Use tools like autoflake to remove unused imports
```

---

## Checking Imports

Run these tools before committing:

```bash
# Sort imports
isort .

# Remove unused imports
autoflake --in-place --remove-all-unused-imports -r .

# Check circular dependencies
python scripts/check_circular_deps.py core/

# Verify import order
ruff check --select I .
```

---

## Quick Reference

| Pattern | Example |
|---------|---------|
| Standard lib | `import os` |
| Specific import | `from typing import Dict` |
| Third-party | `from fastapi import FastAPI` |
| Local module | `from core.config import settings` |
| Type checking | `if TYPE_CHECKING: from ... import ...` |
| Lazy import | `def fn(): from x import y; return y()` |
| Alias | `import numpy as np` |
