# API Versioning Guide

JARVIS API supports versioning to allow smooth evolution without breaking existing clients.

## Quick Start

### Enable Versioning

Set environment variable (enabled by default):
```bash
API_VERSIONING_ENABLED=true
```

### Access Versioned Endpoints

**Option 1: URL Path (Recommended)**
```bash
# V1 endpoint
curl http://localhost:8766/api/v1/staking/pool

# Original endpoint (still works)
curl http://localhost:8766/api/staking/pool
```

**Option 2: Accept-Version Header**
```bash
curl -H "Accept-Version: v1" http://localhost:8766/api/staking/pool
```

Response includes version header:
```
X-API-Version: v1
```

## Version Discovery

### List All Versions
```bash
GET /api/versions
```

Response:
```json
{
  "current_version": "v1",
  "versions": [
    {
      "version": "v1",
      "current": true,
      "deprecated": false
    }
  ]
}
```

### Get Current Request Version
```bash
GET /api/version
```

Response:
```json
{
  "version": "v1",
  "current": true,
  "deprecated": false
}
```

## Version Priority

When multiple version indicators exist:

1. **URL Path** - Takes highest priority
2. **Accept-Version Header** - Fallback if no path version
3. **Default** - Uses current version (v1)

Example:
```bash
# Path wins: Uses v1
curl -H "Accept-Version: v2" http://localhost:8766/api/v1/staking/pool
```

## Available Versions

### V1 (Current)

All existing endpoints have v1 equivalents:

| Original | V1 Equivalent |
|----------|---------------|
| `/api/staking/*` | `/api/v1/staking/*` |
| `/api/credits/*` | `/api/v1/credits/*` |
| `/api/rewards/*` | `/api/v1/rewards/*` |
| `/api/treasury/reports/*` | `/api/v1/treasury/reports/*` |
| `/api/health/*` | `/api/v1/health/*` |

Both paths work identically - use v1 prefix for explicit versioning.

## Deprecation Warnings

When a version or endpoint is deprecated, responses include headers:

```http
Deprecation: true
Sunset: 2026-06-01
Warning: 299 - "API version v0 is deprecated. Will be removed after 2026-06-01. Please migrate to v1."
```

Example:
```bash
curl -I http://localhost:8766/api/v0/staking/pool

HTTP/1.1 200 OK
X-API-Version: v0
Deprecation: true
Sunset: 2026-06-01
Warning: 299 - "API version v0 is deprecated..."
```

## Creating New Versions

### Step 1: Define Version Routes

Create `api/routes/v2/__init__.py`:
```python
from api.versioning import create_versioned_router

def create_v2_routers() -> list[APIRouter]:
    routers = []

    # Create v2 staking router
    staking_v2 = create_versioned_router(
        version="v2",
        prefix="/staking",
        tags=["Staking"],
    )

    @staking_v2.get("/pool")
    async def get_pool_v2():
        # New v2 implementation
        return {"version": "v2", "data": "..."}

    routers.append(staking_v2)
    return routers
```

### Step 2: Register in versioning.py

Update `SUPPORTED_VERSIONS`:
```python
SUPPORTED_VERSIONS = ["v1", "v2"]
CURRENT_VERSION = "v2"
```

### Step 3: Include in App

Update `api/fastapi_app.py`:
```python
from api.routes.v2 import create_v2_routers

# In _include_routers()
v2_routers = create_v2_routers()
for router in v2_routers:
    app.include_router(router)
```

### Step 4: Deprecate Old Version (Optional)

```python
DEPRECATED_VERSIONS = {
    "v1": "2026-12-31"  # Sunset date
}
```

## Marking Endpoints as Deprecated

Use the `@deprecated` decorator:

```python
from api.versioning import deprecated

@router.get("/old-endpoint")
@deprecated("v2", "2026-06-01", "Use /new-endpoint instead")
async def old_handler():
    return {"data": "..."}
```

Response will include deprecation headers automatically.

## Best Practices

### 1. Always Use Explicit Versions for New Features

```python
# Good - Explicit v2 feature
@staking_v2.get("/new-feature")
async def new_feature():
    ...

# Bad - Adding to v1 after release
@staking_v1.get("/new-feature")  # Don't modify released versions
```

### 2. Maintain Backward Compatibility in Same Version

Within v1, don't break existing contracts:
- Add optional fields, don't change required ones
- Add new endpoints, don't change existing ones
- Extend enums, don't remove values

### 3. Provide Migration Guides

When deprecating, document migration path:
```python
ENDPOINT_DEPRECATIONS = {
    ("v1", "/api/v1/staking/stake"): ("v2", "2026-06-01")
}
```

### 4. Test Both Versions

```python
def test_v1_endpoint(client):
    response = client.get("/api/v1/staking/pool")
    assert response.status_code == 200

def test_v2_endpoint(client):
    response = client.get("/api/v2/staking/pool")
    assert response.status_code == 200
```

### 5. Monitor Version Usage

Check logs for version distribution:
```bash
# Count requests by version
grep "X-API-Version" api.log | sort | uniq -c
```

## Client Examples

### Python

```python
import requests

# Option 1: Path
response = requests.get("http://localhost:8766/api/v1/staking/pool")

# Option 2: Header
response = requests.get(
    "http://localhost:8766/api/staking/pool",
    headers={"Accept-Version": "v1"}
)

# Check version used
print(response.headers["X-API-Version"])  # v1

# Check if deprecated
if response.headers.get("Deprecation") == "true":
    sunset = response.headers.get("Sunset")
    print(f"Warning: API deprecated, sunset {sunset}")
```

### JavaScript

```javascript
// Option 1: Path
const response = await fetch("http://localhost:8766/api/v1/staking/pool");

// Option 2: Header
const response = await fetch("http://localhost:8766/api/staking/pool", {
  headers: {
    "Accept-Version": "v1"
  }
});

// Check version
const version = response.headers.get("X-API-Version");
console.log(`Using version: ${version}`);

// Check deprecation
if (response.headers.get("Deprecation") === "true") {
  const sunset = response.headers.get("Sunset");
  console.warn(`API deprecated, sunset ${sunset}`);
}
```

### cURL

```bash
# Path-based
curl http://localhost:8766/api/v1/staking/pool

# Header-based
curl -H "Accept-Version: v1" http://localhost:8766/api/staking/pool

# Check headers
curl -I http://localhost:8766/api/v1/staking/pool | grep -E "X-API-Version|Deprecation|Sunset"
```

## Troubleshooting

### Version Not Recognized

**Problem:** Getting default version instead of requested
```bash
curl http://localhost:8766/api/v99/staking/pool
# Returns v1, not v99
```

**Solution:** Check `SUPPORTED_VERSIONS` in `api/versioning.py`

### Both Versions Show Same Data

**Problem:** v1 and v2 return identical responses

**Solution:** V2 router is copying v1 routes. Create new handlers:
```python
# Don't do this
for route in staking_v1.routes:
    staking_v2.routes.append(route)

# Do this
@staking_v2.get("/pool")
async def get_pool_v2():
    # New v2 implementation
    ...
```

### Deprecation Headers Not Showing

**Problem:** Old version doesn't show deprecation

**Solution:** Add to `DEPRECATED_VERSIONS`:
```python
DEPRECATED_VERSIONS = {
    "v1": "2026-06-01"
}
```

### Middleware Not Running

**Problem:** No `X-API-Version` header in responses

**Solution:** Check middleware is enabled:
```bash
API_VERSIONING_ENABLED=true
```

And verify middleware order in `fastapi_app.py`:
```python
app.add_middleware(APIVersionMiddleware)
```

## Migration Checklist

When releasing a new version:

- [ ] Create new version router (`api/routes/vX/`)
- [ ] Add to `SUPPORTED_VERSIONS`
- [ ] Update `CURRENT_VERSION`
- [ ] Include in `_include_routers()`
- [ ] Add deprecation date for old version
- [ ] Write migration guide
- [ ] Update API docs
- [ ] Add tests for new version
- [ ] Announce deprecation timeline
- [ ] Monitor usage of old version
- [ ] Remove old version after sunset date

## FAQ

**Q: Do I need to version everything?**
A: No. Only version public-facing API endpoints. Internal endpoints can evolve freely.

**Q: How long should deprecation period be?**
A: Minimum 6 months for major versions, 3 months for minor changes.

**Q: Can I support multiple versions simultaneously?**
A: Yes. All registered versions in `SUPPORTED_VERSIONS` work concurrently.

**Q: What happens if I don't specify a version?**
A: You get `CURRENT_VERSION` by default (currently v1).

**Q: Should I duplicate code between versions?**
A: No. Share business logic, only version the API contract:
```python
# Shared logic
from core.staking import get_pool_stats

# V1 endpoint
@staking_v1.get("/pool")
async def pool_v1():
    stats = get_pool_stats()
    return {"data": stats}  # V1 format

# V2 endpoint
@staking_v2.get("/pool")
async def pool_v2():
    stats = get_pool_stats()
    return {"pool": stats, "version": "v2"}  # V2 format
```

## References

- [Semantic Versioning](https://semver.org/)
- [API Versioning Best Practices](https://www.troyhunt.com/your-api-versioning-is-wrong-which-is/)
- [RFC 7231 - HTTP Semantics](https://tools.ietf.org/html/rfc7231)
