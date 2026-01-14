# JARVIS Release Checklist

## Pre-Release Checklist

### Code Quality
- [ ] All tests passing on main branch
- [ ] No critical security vulnerabilities
- [ ] Code coverage meets threshold (>60%)
- [ ] Static analysis passes (Ruff, MyPy)
- [ ] No TODO/FIXME items for this release

### Documentation
- [ ] CHANGELOG.md updated
- [ ] API documentation current
- [ ] README updated if needed
- [ ] Migration guide written (if breaking changes)

### Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Load tests performed
- [ ] Manual testing completed
- [ ] Staging deployment verified

### Dependencies
- [ ] Dependencies updated and compatible
- [ ] Security audit of dependencies
- [ ] requirements.txt up to date

---

## Release Process

### 1. Version Bump

```bash
# Update version in files
# - pyproject.toml
# - core/__init__.py
# - api/fastapi_app.py (if hardcoded)

# Create version commit
git checkout main
git pull origin main
git checkout -b release/vX.Y.Z
```

### 2. Update Changelog

Add release notes to CHANGELOG.md:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Deprecated
- Features to be removed

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
```

### 3. Create Release Commit

```bash
git add .
git commit -m "chore: release vX.Y.Z"
git push origin release/vX.Y.Z
```

### 4. Create Pull Request

- Create PR from release branch to main
- Title: "Release vX.Y.Z"
- Request review from team

### 5. Merge and Tag

After approval:

```bash
# Merge PR
git checkout main
git pull origin main

# Create tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### 6. Create GitHub Release

1. Go to Releases on GitHub
2. Click "Draft a new release"
3. Select the tag
4. Add release notes from CHANGELOG
5. Publish release

### 7. Deploy

Follow [Deployment Runbook](runbooks/DEPLOYMENT.md)

---

## Post-Release Checklist

### Immediate (0-1 hour)
- [ ] Verify production deployment
- [ ] Health checks passing
- [ ] No error spikes in monitoring
- [ ] Basic functionality verified

### Short-term (1-24 hours)
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Review user feedback
- [ ] Update status page

### Announcement
- [ ] Team notification
- [ ] User-facing changelog (if public)
- [ ] Social media update (if applicable)

---

## Rollback Procedure

If issues are found:

1. **Assess severity**
   - Critical: Immediate rollback
   - High: Rollback within 1 hour
   - Medium: Fix forward if possible

2. **Execute rollback**
   ```bash
   # See deployment runbook for details
   docker tag jarvis-api:previous jarvis-api:latest
   docker-compose up -d
   ```

3. **Post-mortem**
   - Document what went wrong
   - Create issues for fixes
   - Schedule post-mortem meeting

---

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

Examples:
- 1.0.0 → 2.0.0: Breaking API change
- 1.0.0 → 1.1.0: New feature added
- 1.0.0 → 1.0.1: Bug fix

---

## Release Types

### Regular Release
- Scheduled (e.g., bi-weekly)
- Full testing cycle
- Complete documentation

### Hotfix Release
- Emergency fixes only
- Abbreviated testing
- Quick deployment

### Pre-Release
- Alpha/Beta versions
- Limited distribution
- Feedback collection

---

## Automation

### CI/CD Pipeline

The CI/CD pipeline automatically:
1. Runs tests on every push
2. Builds Docker images on tag
3. Deploys to staging on main merge
4. Deploys to production on release tag

### Required Checks

Before merge, all of these must pass:
- [ ] pytest
- [ ] ruff
- [ ] mypy
- [ ] black --check
- [ ] security scan

---

## Contact

For release questions:
- Primary: Tech Lead
- Secondary: Engineering Manager
