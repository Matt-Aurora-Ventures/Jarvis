# JARVIS Commit Message Conventions

## Overview

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification
for commit messages. This enables automatic changelog generation and semantic versioning.

---

## Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### Example

```
feat(trading): add limit order support

Implement limit order functionality with the following features:
- Price validation against current market
- Order book integration
- Automatic cancellation after timeout

Closes #123
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(api): add user preferences endpoint` |
| `fix` | Bug fix | `fix(bot): handle empty message gracefully` |
| `docs` | Documentation only | `docs: update API documentation` |
| `style` | Formatting, no code change | `style: format with black` |
| `refactor` | Code restructuring | `refactor(cache): simplify invalidation logic` |
| `perf` | Performance improvement | `perf(db): add index for user queries` |
| `test` | Adding/updating tests | `test(trading): add integration tests` |
| `build` | Build system changes | `build: update docker configuration` |
| `ci` | CI configuration | `ci: add security scanning step` |
| `chore` | Maintenance tasks | `chore: update dependencies` |
| `revert` | Revert previous commit | `revert: feat(api): add user preferences` |
| `security` | Security improvements | `security: rotate api keys` |

---

## Scopes

Scopes indicate which part of the codebase is affected:

| Scope | Description |
|-------|-------------|
| `api` | FastAPI application and routes |
| `core` | Core business logic |
| `trading` | Trading functionality |
| `bot` | Telegram/Twitter bots |
| `db` | Database and migrations |
| `cache` | Caching layer |
| `auth` | Authentication/authorization |
| `monitoring` | Metrics and observability |
| `llm` | LLM provider integration |
| `config` | Configuration |
| `security` | Security features |
| `deps` | Dependencies |

---

## Subject Line

- Use imperative mood ("add" not "added" or "adds")
- Don't capitalize the first letter
- No period at the end
- Maximum 50 characters (soft limit)
- Maximum 72 characters (hard limit)

### Good Examples

```
feat(api): add rate limiting to public endpoints
fix(bot): prevent duplicate message processing
docs: add contributing guidelines
```

### Bad Examples

```
Added rate limiting           # Past tense
Add Rate Limiting.           # Capitalized, has period
feat(api): Add a really long description that explains everything in detail  # Too long
```

---

## Body

- Separate from subject with a blank line
- Explain **what** and **why**, not **how**
- Wrap at 72 characters
- Use bullet points for lists

### Example

```
fix(trading): handle slippage in large orders

Large orders were failing due to price movement between
quote and execution. This fix:

- Adds configurable slippage tolerance
- Implements price checks before execution
- Retries with updated quotes on failure

This resolves issues reported by multiple users during
high volatility periods.
```

---

## Footer

### Issue References

```
Closes #123
Fixes #456
Resolves #789
```

### Breaking Changes

```
BREAKING CHANGE: API response format changed

The /api/v1/trades endpoint now returns an array
instead of an object. Update client code accordingly.
```

### Co-Authors

```
Co-Authored-By: Name <email@example.com>
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Special Cases

### Reverting Commits

```
revert: feat(api): add user preferences

This reverts commit abc123def456.

Reason: Feature caused performance regression in production.
```

### Work in Progress

Use `[WIP]` prefix for work in progress (will be squashed):

```
[WIP] feat(trading): implement stop-loss orders
```

### Multiple Changes

If a commit affects multiple areas, use comma-separated scopes:

```
fix(api,bot): handle rate limit errors consistently
```

---

## Commit Lint

We use commitlint to enforce these conventions. Configuration is in `.commitlintrc.json`.

### Setup

```bash
# Install commitlint
npm install -g @commitlint/cli @commitlint/config-conventional

# Test a commit message
echo "feat(api): add new endpoint" | commitlint
```

### Pre-commit Hook

The pre-commit hook validates commit messages automatically.

---

## Quick Reference

```
feat:     New feature
fix:      Bug fix
docs:     Documentation
style:    Formatting
refactor: Code restructuring
perf:     Performance
test:     Tests
build:    Build system
ci:       CI/CD
chore:    Maintenance
revert:   Revert commit
security: Security fix
```

---

## Examples by Category

### Features

```
feat(api): add WebSocket support for real-time prices
feat(bot): implement inline keyboard for trade confirmation
feat(trading): add DCA order type
```

### Bug Fixes

```
fix(auth): validate JWT expiration correctly
fix(db): handle connection timeout gracefully
fix(cache): prevent race condition in invalidation
```

### Documentation

```
docs: add API authentication guide
docs(readme): update installation instructions
docs(api): document rate limiting headers
```

### Performance

```
perf(db): add composite index for trade queries
perf(api): implement response caching
perf(llm): batch token counting
```

### Security

```
security(auth): implement CSRF protection
security(api): add rate limiting
security: rotate compromised API keys
```
