# JARVIS Code Review Checklist

A comprehensive checklist for reviewing pull requests in the JARVIS project.

---

## Quick Reference

Use this checklist when reviewing PRs. Not all items apply to every PR.

```
Copy this into your PR review:

## Code Review Checklist
- [ ] Code quality
- [ ] Security
- [ ] Testing
- [ ] Documentation
- [ ] Performance
```

---

## 1. Code Quality

### Readability
- [ ] Code is self-explanatory or well-commented
- [ ] Variable/function names are descriptive and consistent
- [ ] No magic numbers (use named constants)
- [ ] Complex logic has explanatory comments
- [ ] No unnecessary comments or commented-out code

### Structure
- [ ] Functions are small and focused (single responsibility)
- [ ] No deep nesting (max 3-4 levels)
- [ ] DRY - no duplicated code
- [ ] Proper error handling with specific exceptions
- [ ] Consistent code style (follows CODE_STYLE.md)

### Python-Specific
- [ ] Type hints on function signatures
- [ ] Proper use of async/await
- [ ] No blocking calls in async functions
- [ ] Context managers for resources (files, connections)
- [ ] No mutable default arguments

---

## 2. Security

### Critical Checks
- [ ] No hardcoded secrets, API keys, or passwords
- [ ] No sensitive data in logs
- [ ] Input validation on all external data
- [ ] SQL injection prevention (parameterized queries)
- [ ] No command injection vulnerabilities

### Authentication & Authorization
- [ ] API endpoints check authentication
- [ ] Proper authorization for sensitive operations
- [ ] No privilege escalation paths
- [ ] Session handling is secure

### Data Handling
- [ ] PII is properly protected
- [ ] Encryption used for sensitive data at rest
- [ ] HTTPS for external communications
- [ ] No data leakage in error messages

### Dependencies
- [ ] New dependencies are vetted
- [ ] No known vulnerabilities in dependencies
- [ ] Dependencies are pinned to versions

---

## 3. Testing

### Coverage
- [ ] New code has unit tests
- [ ] Edge cases are tested
- [ ] Error conditions are tested
- [ ] Tests cover the happy path

### Quality
- [ ] Tests are readable and maintainable
- [ ] Tests use appropriate assertions
- [ ] No test interdependencies
- [ ] Mocks are used appropriately
- [ ] Tests actually test the code (not just pass)

### Integration
- [ ] Integration tests for new features
- [ ] API changes have endpoint tests
- [ ] Database changes have migration tests

---

## 4. Documentation

### Code Documentation
- [ ] Public functions have docstrings
- [ ] Complex algorithms are explained
- [ ] API changes documented in API_DOCUMENTATION.md
- [ ] Breaking changes noted

### External Documentation
- [ ] README updated if needed
- [ ] CHANGELOG entry added
- [ ] Configuration changes documented
- [ ] New environment variables documented

---

## 5. Performance

### Efficiency
- [ ] No N+1 query problems
- [ ] Appropriate use of caching
- [ ] No unnecessary database calls
- [ ] Batch operations where appropriate

### Scalability
- [ ] No memory leaks
- [ ] Connection pooling used
- [ ] Timeouts on external calls
- [ ] Rate limiting considered

### Async
- [ ] Proper use of asyncio
- [ ] No blocking in async code
- [ ] Concurrent operations use gather/wait
- [ ] Resource cleanup in all paths

---

## 6. Architecture

### Design
- [ ] Follows existing patterns in codebase
- [ ] No circular dependencies
- [ ] Proper separation of concerns
- [ ] Dependency injection used appropriately

### Compatibility
- [ ] Backward compatible (or migration provided)
- [ ] No breaking changes to public APIs
- [ ] Database migrations are reversible
- [ ] Feature flags for risky changes

---

## 7. Operations

### Logging & Monitoring
- [ ] Appropriate log levels used
- [ ] Structured logging format
- [ ] Metrics added for new features
- [ ] Alerts configured for critical paths

### Error Handling
- [ ] Errors are logged with context
- [ ] User-facing errors are friendly
- [ ] Retry logic for transient failures
- [ ] Circuit breakers for external services

### Deployment
- [ ] No deployment blockers
- [ ] Database migrations tested
- [ ] Environment variables documented
- [ ] Rollback plan considered

---

## Review Severity Levels

Use these labels to categorize feedback:

| Level | Meaning | Action |
|-------|---------|--------|
| 🔴 **Blocker** | Critical issue, must fix | Cannot merge |
| 🟠 **Major** | Significant problem | Should fix before merge |
| 🟡 **Minor** | Improvement suggested | Nice to fix |
| 🟢 **Nitpick** | Style/preference | Optional |
| 💡 **Suggestion** | Alternative approach | For consideration |
| ❓ **Question** | Need clarification | Please explain |

---

## PR Size Guidelines

| Size | Files | Lines Changed | Review Time |
|------|-------|---------------|-------------|
| XS | 1-2 | < 50 | 15 min |
| S | 3-5 | 50-150 | 30 min |
| M | 6-10 | 150-400 | 1 hour |
| L | 11-20 | 400-800 | 2 hours |
| XL | 20+ | 800+ | Split PR |

**Prefer smaller PRs.** Large PRs should be split when possible.

---

## Common Issues to Watch For

### JARVIS-Specific

1. **Treasury Operations**
   - Check transaction limits
   - Verify wallet security
   - Confirm slippage settings
   - Emergency shutdown path exists

2. **Bot Commands**
   - Rate limiting applied
   - Input validation present
   - Error responses user-friendly
   - Admin-only commands protected

3. **LLM Integration**
   - Token limits checked
   - Cost tracking implemented
   - Fallback providers configured
   - Response validation present

4. **API Endpoints**
   - Authentication required
   - Request validation
   - Response format consistent
   - Rate limiting applied

---

## Review Workflow

### Before Review
1. Read the PR description
2. Check linked issues
3. Understand the context
4. Pull and run locally (if needed)

### During Review
1. Start with architecture/design
2. Then security concerns
3. Then code quality
4. Then testing
5. Finally documentation

### After Review
1. Summarize findings
2. Prioritize feedback
3. Be constructive
4. Suggest alternatives

---

## Constructive Feedback Tips

### Do
- "Consider using X because..."
- "What if we...?"
- "Nice approach! We could also..."
- Explain the 'why'

### Don't
- "This is wrong"
- "Don't do it this way"
- "Why would you...?"
- Criticize without alternatives

---

## Approval Guidelines

### Approve When
- All blockers resolved
- Tests pass
- Documentation complete
- Security concerns addressed

### Request Changes When
- Critical security issues
- Missing tests for new features
- Breaking changes undocumented
- Major performance concerns

### Comment When
- Minor improvements suggested
- Questions need answering
- Alternatives to consider

---

## Templates

### Review Comment Template
```markdown
**[Level]** Category: Brief description

Current code:
\`\`\`python
# problematic code
\`\`\`

Suggestion:
\`\`\`python
# improved code
\`\`\`

Reason: Explanation of why this is better.
```

### Approval Template
```markdown
## Review Summary

✅ Approved

### What I Reviewed
- [x] Code quality
- [x] Security
- [x] Testing
- [x] Documentation

### Notes
- Nice implementation of X
- Consider Y for future improvement (not blocking)

LGTM! 🚀
```

### Request Changes Template
```markdown
## Review Summary

🔴 Changes Requested

### Blockers
1. Security: Missing input validation on X
2. Testing: No tests for error cases

### Suggestions
- Consider caching for performance

Please address blockers before merging.
```

---

## Related Documents

- [Code Style Guide](CODE_STYLE.md)
- [Contributing Guidelines](CONTRIBUTING.md)
- [Security Guidelines](SECURITY_GUIDELINES.md)
- [API Documentation](API_DOCUMENTATION.md)
