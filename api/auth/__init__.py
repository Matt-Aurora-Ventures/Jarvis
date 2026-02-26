"""Authentication modules."""
from api.auth.key_auth import validate_api_key, APIKeyAuth, api_key_header

try:
    from api.auth.jwt_auth import JWTAuth, create_access_token, create_refresh_token, verify_token
except RuntimeError as exc:
    # JWT support is optional at import time to keep API key auth usable
    # in environments that have not set JWT_SECRET_KEY.
    _jwt_error = str(exc)
    JWTAuth = None  # type: ignore[assignment]

    def _jwt_unavailable(*_args, **_kwargs):
        raise RuntimeError(f"JWT authentication unavailable: {_jwt_error}")

    create_access_token = _jwt_unavailable  # type: ignore[assignment]
    create_refresh_token = _jwt_unavailable  # type: ignore[assignment]
    verify_token = _jwt_unavailable  # type: ignore[assignment]

__all__ = [
    "validate_api_key",
    "APIKeyAuth",
    "api_key_header",
    "JWTAuth",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
]
