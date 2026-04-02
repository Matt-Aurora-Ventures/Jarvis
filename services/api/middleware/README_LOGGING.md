# API Request Logging

Comprehensive request/response logging with sensitive data masking and log rotation.

## Features

- Request/response logging with timing
- Correlation IDs (X-Request-ID)
- Sensitive data masking (passwords, API keys, tokens)
- Slow request detection
- Error logging with stack traces
- Log rotation and compression
- Cleanup of old logs

## Configuration

### Environment Variables

```bash
# Enable/disable logging
REQUEST_LOGGING_ENABLED=true           # Enable request logging middleware
LOG_REQUEST_BODY=false                 # Log request bodies
LOG_RESPONSE_BODY=false                # Log response bodies
SLOW_REQUEST_THRESHOLD=1.0             # Seconds to warn on slow requests

# Log storage
API_LOG_DIR=/var/log/jarvis            # Log directory
LOG_LEVEL=INFO                         # Logging level
```

## What Gets Logged

### Request
- Method, path, query parameters
- Client IP, User-Agent
- Headers (sensitive ones masked)
- Body (if enabled, with masking)
- Request ID

### Response
- Status code
- Response time
- Content length
- Headers
- Errors (with stack traces)

### Sensitive Data Masking

Automatically masks:
- **Headers**: Authorization, X-API-Key, Cookie, X-CSRF-Token
- **Body**: password, secret, token, api_key, private_key, credit_card, ssn

## API Endpoints

### View Statistics
```bash
GET /api/logs/stats
```

### Cleanup Old Logs
```bash
POST /api/logs/cleanup
{
  "max_age_days": 30,
  "compress_age_days": 7,
  "dry_run": false
}
```

### List Log Files
```bash
GET /api/logs/files?limit=10&compressed_only=false
```

### Get Recent Logs
```bash
GET /api/logs/recent?lines=100&level=ERROR
```

## Log Rotation

Logs automatically rotate when they reach 50MB (configurable). Old logs are compressed and deleted after 30 days.

### Manual Rotation Setup

```python
from api.log_rotation import setup_log_rotation

handler = setup_log_rotation(
    log_file="/var/log/jarvis/api.log",
    max_bytes=50 * 1024 * 1024,  # 50MB
    backup_count=10
)
```

## Testing

```bash
pytest tests/unit/api/test_request_logging.py -v
pytest tests/unit/api/test_log_rotation.py -v
```

## Example Log Output

```
2026-01-19 10:30:45 - jarvis.api - INFO - Request: GET /api/health
2026-01-19 10:30:45 - jarvis.api - INFO - Response: GET /api/health 200 (45ms)
```

With extra data:
```json
{
  "request": {
    "request_id": "abc123",
    "method": "POST",
    "path": "/api/users",
    "query": {},
    "client_ip": "192.168.1.1",
    "user_agent": "curl/7.68.0",
    "headers": {
      "authorization": "Bear...ken",
      "content-type": "application/json"
    },
    "body": {
      "username": "user1",
      "password": "****"
    }
  },
  "response": {
    "request_id": "abc123",
    "status_code": 201,
    "duration_ms": 123.45,
    "content_length": 456
  }
}
```
