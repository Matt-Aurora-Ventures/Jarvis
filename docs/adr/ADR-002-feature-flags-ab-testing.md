# ADR-002: Feature Flags for A/B Testing and Gradual Rollout

## Status

Accepted

## Date

2026-01-15

## Context

JARVIS is an autonomous trading platform where incorrect behavior can result in financial losses. We need a mechanism to:

1. **Gradual Rollout**: Deploy new features to a subset of users first
2. **A/B Testing**: Compare algorithm performance between variants
3. **Quick Rollback**: Disable features without deployment
4. **Environment Control**: Different behavior in dev/staging/production

### Current Pain Points

- Deploying new algorithms requires full restart
- No way to test with a subset of users
- Rollback requires code revert and redeploy
- Feature testing requires environment variable changes

## Decision

Implement a **comprehensive feature flag system** with:

1. **In-memory Flag Store**: Fast access for hot paths
2. **Persistent Configuration**: File-based for durability
3. **User Targeting**: Enable features for specific users/groups
4. **Percentage Rollout**: Enable for X% of requests
5. **Override Hierarchy**: User > Group > Percentage > Default

### Architecture

```
core/feature_flags.py      - Core flag system
core/feature_manager.py    - High-level API
lifeos/config/feature_flags.json - Persistent storage
```

## Consequences

### Positive

1. **Safe Deployments**: Test with 1% of users before full rollout
2. **Quick Rollback**: Disable feature in seconds, not minutes
3. **A/B Testing**: Compare algorithm variants statistically
4. **Kill Switches**: Emergency disable without deployment
5. **User Targeting**: Beta features for specific users

### Negative

1. **Code Complexity**: Additional conditionals in code paths
2. **Testing Burden**: Must test both flag states
3. **Flag Debt**: Old flags need cleanup
4. **Consistency Risk**: Users may see different behavior

### Mitigations

1. **Flag Hygiene**: Remove flags older than 90 days
2. **Testing Standards**: All flag paths must have tests
3. **Documentation**: Document all active flags
4. **Monitoring**: Alert on unexpected flag states

## Implementation

### Flag Definition

```python
# core/feature_flags.py

class FeatureFlag:
    """Defines a feature flag with targeting rules."""

    name: str
    enabled: bool = False
    percentage: float = 0.0  # 0-100
    user_ids: List[int] = []
    description: str = ""
    created_at: datetime
```

### Usage Pattern

```python
from core.feature_flags import is_feature_enabled

async def analyze_token(token: str, user_id: int):
    # Check if new algorithm is enabled for this user
    if is_feature_enabled("new_sentiment_algo", user_id=user_id):
        return await new_sentiment_analysis(token)
    else:
        return await legacy_sentiment_analysis(token)
```

### A/B Testing Example

```python
# Deploy new algorithm to 10% of users
feature_manager.set_flag("new_algo_v2", enabled=True, percentage=10)

# After validation, increase to 50%
feature_manager.set_flag("new_algo_v2", percentage=50)

# Full rollout
feature_manager.set_flag("new_algo_v2", percentage=100)

# If issues detected, immediate disable
feature_manager.disable("new_algo_v2")
```

### Current Flags

| Flag Name | Description | Status |
|-----------|-------------|--------|
| `dexter_react_agent` | New ReAct reasoning loop | 100% rolled out |
| `enhanced_risk_scoring` | Multi-factor risk model | 25% testing |
| `whale_tracking_v2` | Improved whale detection | Beta users only |
| `autonomous_x_posting` | Autonomous X posts | Enabled with limits |

## Configuration

```json
// lifeos/config/feature_flags.json
{
  "flags": {
    "dexter_react_agent": {
      "enabled": true,
      "percentage": 100,
      "description": "ReAct reasoning for trading decisions"
    },
    "enhanced_risk_scoring": {
      "enabled": true,
      "percentage": 25,
      "user_ids": [8527130908],
      "description": "Multi-factor risk assessment"
    }
  }
}
```

## Alternatives Considered

### Alternative 1: Environment Variables Only

- **Pros**: Simple, no code changes
- **Cons**: Requires restart, no user targeting
- **Decision**: Rejected - insufficient for gradual rollout

### Alternative 2: Third-Party Service (LaunchDarkly, Flagsmith)

- **Pros**: Rich UI, analytics, audit trail
- **Cons**: External dependency, cost, latency
- **Decision**: Rejected - unnecessary complexity for current scale

### Alternative 3: Database-Backed Flags

- **Pros**: Persistent, queryable
- **Cons**: Database dependency in hot path
- **Decision**: Partially adopted - use file persistence with in-memory cache

## Metrics

Track for each flag:
- Exposure count (how many times checked)
- Enabled/disabled counts
- Error rates per variant
- Performance metrics per variant

## References

- [Feature Flag Implementation](../core/feature_flags.py)
- [Feature Manager API](../core/feature_manager.py)
- [Configuration File](../lifeos/config/feature_flags.json)

## Review

- **Author**: JARVIS Development Team
- **Reviewed By**: Architecture Council
- **Last Updated**: 2026-01-15
