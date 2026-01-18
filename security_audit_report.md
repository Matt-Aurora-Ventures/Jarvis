# Security Audit Report

**Generated:** 2026-01-18 15:55:55

## Summary

- **Critical Issues:** 27
- **High Issues:** 15
- **Medium Issues:** 1
- **Low Issues:** 0
- **Vulnerable Dependencies:** 0
- **Git Secrets:** 0

## Findings

### Secrets

#### [!] Potential hardcoded_secret found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\encryption.py`:75
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_secret found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\encryption.py`:193
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\secret_hygiene.py`:349
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\secret_hygiene.py`:374
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\security_hardening.py`:21
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\security_hardening.py`:24
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\security_hardening.py`:711
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_password found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `core\security_hardening.py`:739
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_secret found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `scripts\create_deployment_with_keys.py`:124
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential hardcoded_secret found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `scripts\create_deployment_with_keys.py`:130
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential solana_private_key found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `scripts\sell_and_report.py`:30
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential solana_private_key found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `scripts\verify_tx.py`:11
- **Recommendation:** Move secret to environment variable or secure vault.

#### [!] Potential solana_private_key found
*Severity: CRITICAL*

Found what appears to be a hardcoded secret.
- File: `scripts\verify_tx.py`:12
- **Recommendation:** Move secret to environment variable or secure vault.

### Vulnerabilities

#### [H] Unsafe pickle.load()
*Severity: HIGH*

Pickle deserialization can execute arbitrary code
- File: `core\google_integration.py`:249
- **Recommendation:** Use json or a safer serialization format

#### [H] Unsafe pickle.load()
*Severity: HIGH*

Pickle deserialization can execute arbitrary code
- File: `core\ml_regime_detector.py`:634
- **Recommendation:** Use json or a safer serialization format

#### [H] Unsafe pickle.load()
*Severity: HIGH*

Pickle deserialization can execute arbitrary code
- File: `scripts\security_audit.py`:263
- **Recommendation:** Use json or a safer serialization format

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `core\iterative_improver.py`:151
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `core\secret_hygiene.py`:351
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `core\secret_hygiene.py`:376
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `scripts\security_audit.py`:272
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `scripts\security_audit.py`:273
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `scripts\security_audit.py`:275
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of eval()
*Severity: HIGH*

eval() can execute arbitrary code
- File: `scripts\security_scan.py`:152
- **Recommendation:** Avoid eval(). Use ast.literal_eval() for safe parsing

#### [H] Use of exec()
*Severity: HIGH*

exec() can execute arbitrary code
- File: `core\iterative_improver.py`:151
- **Recommendation:** Avoid exec() if possible

#### [H] Use of exec()
*Severity: HIGH*

exec() can execute arbitrary code
- File: `scripts\security_audit.py`:280
- **Recommendation:** Avoid exec() if possible

#### [H] Use of exec()
*Severity: HIGH*

exec() can execute arbitrary code
- File: `scripts\security_audit.py`:281
- **Recommendation:** Avoid exec() if possible

#### [H] Use of exec()
*Severity: HIGH*

exec() can execute arbitrary code
- File: `scripts\security_audit.py`:283
- **Recommendation:** Avoid exec() if possible

#### [H] Use of exec()
*Severity: HIGH*

exec() can execute arbitrary code
- File: `scripts\security_scan.py`:153
- **Recommendation:** Avoid exec() if possible

#### [M] subprocess with shell=True
*Severity: MEDIUM*

shell=True can be vulnerable to shell injection
- File: `core\self_healing.py`:259
- **Recommendation:** Avoid shell=True. Pass command as list.

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:220
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:240
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:283
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:302
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:327
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\data_retention.py`:338
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\memory_driven_behavior.py`:224
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\pnl_tracker.py`:494
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\pnl_tracker.py`:524
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\public_user_manager.py`:381
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\self_improvement_engine.py`:214
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `core\watchlist.py`:244
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `scripts\optimize_queries.py`:214
- **Recommendation:** Use parameterized queries

#### [!] SQL with f-string
*Severity: CRITICAL*

Potential SQL injection vulnerability
- File: `scripts\optimize_queries.py`:218
- **Recommendation:** Use parameterized queries

### Git

#### [i] Git history check
*Severity: INFO*

Reviewed 100 recent commits.
- **Recommendation:** Consider running trufflehog for comprehensive git secret scanning


## Recommendations

1. Address all Critical and High severity issues immediately
2. Update vulnerable dependencies to fixed versions
3. Rotate any secrets found in git history
4. Review Medium severity issues within 30 days
