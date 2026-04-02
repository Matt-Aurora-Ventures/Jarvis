"""
Example: Adding API v2

This file demonstrates how to add a new API version (v2) with breaking changes
while maintaining backward compatibility with v1.

DO NOT RUN - This is a reference example showing the pattern.
"""

# =============================================================================
# Step 1: Create api/routes/v2/__init__.py
# =============================================================================

"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.versioning import create_versioned_router


# =============================================================================
# V2 Models (Breaking Changes from V1)
# =============================================================================

class StakingPoolV2(BaseModel):
    '''V2 uses different field names and adds new fields.'''
    pool_address: str  # V1 used 'address'
    total_staked_tokens: int  # V1 used 'total_staked'
    current_apy: float  # V1 used 'apy'
    active_stakers: int  # NEW in V2
    pool_status: str  # NEW in V2: 'active', 'paused', 'deprecated'


class UserStakeV2(BaseModel):
    '''V2 adds more detailed staking info.'''
    wallet_address: str
    staked_amount: int
    rewards_earned: int
    stake_timestamp: int
    estimated_rewards: int  # NEW in V2
    multiplier: float  # NEW in V2: Based on stake duration


# =============================================================================
# V2 Routers
# =============================================================================

def create_v2_routers() -> list[APIRouter]:
    '''Create all v2 API routers.'''
    routers = []

    # Staking V2
    staking_v2 = create_versioned_router(
        version='v2',
        prefix='/staking',
        tags=['Staking'],
    )

    @staking_v2.get('/pool', response_model=StakingPoolV2)
    async def get_pool_v2():
        '''Get staking pool info (V2 format).'''
        # V2 uses different field names
        from core.staking import get_pool_info

        pool = get_pool_info()

        return StakingPoolV2(
            pool_address=pool['address'],
            total_staked_tokens=pool['total_staked'],
            current_apy=pool['apy'],
            active_stakers=pool.get('staker_count', 0),  # New field
            pool_status='active',  # New field
        )

    @staking_v2.get('/user/{wallet}', response_model=UserStakeV2)
    async def get_user_stake_v2(wallet: str):
        '''Get user staking info (V2 format with additional fields).'''
        from core.staking import get_user_stake, calculate_rewards

        stake = get_user_stake(wallet)
        if not stake:
            raise HTTPException(status_code=404, detail='Stake not found')

        # V2 adds estimated rewards and multiplier
        estimated = calculate_rewards(
            stake['amount'],
            stake['duration_days']
        )

        return UserStakeV2(
            wallet_address=wallet,
            staked_amount=stake['amount'],
            rewards_earned=stake['rewards'],
            stake_timestamp=stake['timestamp'],
            estimated_rewards=estimated,  # New in V2
            multiplier=stake.get('multiplier', 1.0),  # New in V2
        )

    routers.append(staking_v2)

    # Credits V2 (example of different endpoint structure)
    credits_v2 = create_versioned_router(
        version='v2',
        prefix='/credits',
        tags=['Credits'],
    )

    @credits_v2.get('/balance/{user_id}')
    async def get_balance_v2(user_id: str):
        '''
        V2 changes response structure.

        V1 returned: {'balance': 100, 'tier': 'pro'}
        V2 returns: {'user': {...}, 'credits': {...}, 'subscription': {...}}
        '''
        from core.credits import get_user_credits

        credits = get_user_credits(user_id)

        # V2 has nested structure
        return {
            'user': {
                'id': user_id,
                'email': credits.get('email'),
            },
            'credits': {
                'available': credits['balance'],
                'reserved': credits.get('reserved', 0),  # New in V2
                'total_spent': credits.get('spent', 0),  # New in V2
            },
            'subscription': {
                'tier': credits['tier'],
                'renewal_date': credits.get('renewal'),  # New in V2
            }
        }

    routers.append(credits_v2)

    return routers
"""


# =============================================================================
# Step 2: Update api/versioning.py
# =============================================================================

"""
# In api/versioning.py

CURRENT_VERSION = 'v2'  # Update to v2
SUPPORTED_VERSIONS = ['v1', 'v2']  # Add v2

# Mark v1 as deprecated (optional, with sunset date)
DEPRECATED_VERSIONS = {
    'v1': '2026-12-31'  # Give users 6-12 months to migrate
}
"""


# =============================================================================
# Step 3: Update api/fastapi_app.py
# =============================================================================

"""
# In api/fastapi_app.py, in _include_routers() function

def _include_routers(app: FastAPI):
    '''Include all API routers.'''

    # ... existing code ...

    # V2 versioned routes
    if os.getenv('API_VERSIONING_ENABLED', 'true').lower() == 'true':
        try:
            from api.routes.v2 import create_v2_routers
            v2_routers = create_v2_routers()
            for router in v2_routers:
                app.include_router(router)
            logger.info(f'Included {len(v2_routers)} v2 versioned routes')
        except Exception as e:
            logger.warning(f'V2 versioned routes not available: {e}')

    # ... rest of existing code ...
"""


# =============================================================================
# Step 4: Add Migration Guide
# =============================================================================

"""
Create docs/API_V1_TO_V2_MIGRATION.md:

# Migrating from API v1 to v2

## Breaking Changes

### Staking Endpoints

#### GET /api/v1/staking/pool vs /api/v2/staking/pool

**V1 Response:**
```json
{
  "address": "ABC123...",
  "total_staked": 1000000,
  "apy": 12.5
}
```

**V2 Response:**
```json
{
  "pool_address": "ABC123...",
  "total_staked_tokens": 1000000,
  "current_apy": 12.5,
  "active_stakers": 42,
  "pool_status": "active"
}
```

**Migration:**
- Rename `address` → `pool_address`
- Rename `total_staked` → `total_staked_tokens`
- Rename `apy` → `current_apy`
- Handle new fields: `active_stakers`, `pool_status`

### Credits Endpoints

#### GET /api/v1/credits/balance/{user_id} vs /api/v2/credits/balance/{user_id}

**V1 Response:**
```json
{
  "balance": 100,
  "tier": "pro"
}
```

**V2 Response:**
```json
{
  "user": {
    "id": "user123",
    "email": "user@example.com"
  },
  "credits": {
    "available": 100,
    "reserved": 20,
    "total_spent": 500
  },
  "subscription": {
    "tier": "pro",
    "renewal_date": "2026-02-01"
  }
}
```

**Migration:**
- Access `balance` as `credits.available`
- Access `tier` as `subscription.tier`
- Handle nested structure

## Timeline

- **2026-01-19:** V2 released, V1 deprecated
- **2026-06-30:** V1 deprecation warnings intensify
- **2026-12-31:** V1 removed (sunset date)

## How to Migrate

### Option 1: Update to V2 Format (Recommended)

```python
# Before (V1)
response = requests.get('http://api.example.com/api/v1/staking/pool')
pool_address = response.json()['address']
apy = response.json()['apy']

# After (V2)
response = requests.get('http://api.example.com/api/v2/staking/pool')
pool_address = response.json()['pool_address']
apy = response.json()['current_apy']
```

### Option 2: Gradual Migration

```python
# Support both versions during transition
def get_pool_info(api_version='v2'):
    response = requests.get(f'http://api.example.com/api/{api_version}/staking/pool')

    if api_version == 'v1':
        data = response.json()
        return {
            'pool_address': data['address'],
            'apy': data['apy'],
            # ... map v1 to common format
        }
    else:
        return response.json()
```
"""


# =============================================================================
# Step 5: Add Tests
# =============================================================================

"""
# In tests/unit/test_api_v2.py

import pytest
from fastapi.testclient import TestClient

def test_v2_staking_pool(client):
    '''Test V2 staking pool endpoint.'''
    response = client.get('/api/v2/staking/pool')
    assert response.status_code == 200

    data = response.json()
    # V2 field names
    assert 'pool_address' in data
    assert 'total_staked_tokens' in data
    assert 'current_apy' in data
    # V2 new fields
    assert 'active_stakers' in data
    assert 'pool_status' in data

def test_v1_still_works(client):
    '''Ensure V1 continues working during deprecation period.'''
    response = client.get('/api/v1/staking/pool')
    assert response.status_code == 200

    data = response.json()
    # V1 field names
    assert 'address' in data
    assert 'total_staked' in data
    assert 'apy' in data

def test_v1_deprecation_headers(client):
    '''Ensure V1 returns deprecation headers.'''
    response = client.get('/api/v1/staking/pool')
    assert response.headers.get('Deprecation') == 'true'
    assert response.headers.get('Sunset') == '2026-12-31'

def test_v2_no_deprecation(client):
    '''Ensure V2 does not have deprecation headers.'''
    response = client.get('/api/v2/staking/pool')
    assert response.headers.get('Deprecation') is None
"""


# =============================================================================
# Summary
# =============================================================================

if __name__ == '__main__':
    print(__doc__)
    print('''
Key Points:

1. V2 can have breaking changes (different field names, response structure)
2. V1 continues working during deprecation period
3. Clients get deprecation warnings automatically
4. Clear migration guide helps users transition
5. Both versions tested to ensure correctness
6. Sunset date gives users time to migrate

This pattern allows API evolution while maintaining backward compatibility.
    ''')
