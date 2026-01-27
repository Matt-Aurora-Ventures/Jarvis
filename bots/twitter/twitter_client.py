"""
X API Client
Handles authentication and posting via official xdk SDK
With tweepy fallback for media uploads (v1.1 API)
"""

import os
import json
import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from functools import wraps
import tempfile
import time

import aiohttp

from core.utils.circuit_breaker import APICircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

# Structured error logging integration
def _log_twitter_error(error: Exception, context: str, metadata: dict = None):
    """Log error with structured data and track in error rate system."""
    try:
        from core.logging.error_tracker import error_tracker
        error_tracker.track_error(
            error,
            context=context,
            component="twitter_client",
            metadata=metadata or {}
        )
    except Exception:
        pass

    try:
        from core.monitoring.supervisor_health_bus import log_component_error
        log_component_error(
            component="twitter_client",
            error=error,
            context={"operation": context, **(metadata or {})},
            severity="error"
        )
    except Exception:
        # Fallback to standard logging
        logger.error(f"[{context}] {error}", exc_info=True)


def _log_twitter_event(event_type: str, message: str, data: dict = None):
    """Log twitter bot event with structured data."""
    try:
        from core.monitoring.supervisor_health_bus import log_bot_event
        log_bot_event("twitter", event_type, message, data)
    except ImportError:
        logger.info(f"[{event_type}] {message}")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# OAuth2 token persistence file (same directory as .env)
OAUTH2_TOKEN_FILE = Path(__file__).parent / ".oauth2_tokens.json"


def _get_max_tweet_length() -> int:
    raw = os.getenv("X_MAX_TWEET_LENGTH") or os.getenv("TWITTER_MAX_TWEET_LENGTH")
    if raw:
        try:
            value = int(raw)
            if 1 <= value <= 4000:
                return value
        except ValueError:
            logger.warning("Invalid X_MAX_TWEET_LENGTH, falling back to 4000")
    return 4000


def _load_oauth2_tokens() -> Dict[str, str]:
    """Load OAuth2 tokens from persistent storage."""
    try:
        if OAUTH2_TOKEN_FILE.exists():
            with open(OAUTH2_TOKEN_FILE, 'r') as f:
                tokens = json.load(f)
                logger.debug("Loaded OAuth2 tokens from file")
                return tokens
    except Exception as e:
        logger.warning(f"Could not load OAuth2 tokens: {e}")
    return {}


def _save_oauth2_tokens(access_token: str, refresh_token: str) -> bool:
    """Save OAuth2 tokens atomically to persistent storage."""
    try:
        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "updated_at": datetime.utcnow().isoformat()
        }
        # Atomic write: temp file then rename
        dir_name = OAUTH2_TOKEN_FILE.parent
        fd, tmp_path = tempfile.mkstemp(dir=str(dir_name), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(tokens, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(OAUTH2_TOKEN_FILE))
            logger.info("OAuth2 tokens persisted to file")
            return True
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise
    except Exception as e:
        _log_twitter_error(e, "save_oauth2_tokens")
        return False

# Telegram sync (lazy import to avoid circular deps)
_telegram_sync = None

def _get_telegram_sync():
    """Lazy load telegram sync to avoid import issues."""
    global _telegram_sync
    if _telegram_sync is None:
        try:
            from bots.twitter.telegram_sync import get_telegram_sync
            _telegram_sync = get_telegram_sync()
        except Exception as e:
            logger.debug(f"Telegram sync not available: {e}")
            _telegram_sync = False  # Mark as unavailable
    return _telegram_sync if _telegram_sync else None

# Try to import official xdk first, fall back to tweepy
try:
    from xdk import Client as XClient
    HAS_XDK = True
    logger.info("Using official X SDK (xdk)")
except ImportError:
    HAS_XDK = False
    logger.warning("xdk not installed, falling back to tweepy")

try:
    import tweepy
    from tweepy.errors import TweepyException
    HAS_TWEEPY = True
except ImportError:
    HAS_TWEEPY = False
    logger.warning("tweepy not installed")


@dataclass
class TweetResult:
    """Result of a tweet operation"""
    success: bool
    tweet_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class RetryablePostError(Exception):
    """Retryable error raised when posting to X fails transiently."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _is_retryable_status(status_code: Optional[int]) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _is_retryable_exception(exc: Exception) -> bool:
    # Check aiohttp exceptions
    if isinstance(exc, (aiohttp.ClientError, aiohttp.ServerTimeoutError)):
        return True

    # Check requests exceptions (for sync fallback paths)
    try:
        import requests
        if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
            return True
        if isinstance(exc, requests.exceptions.RequestException):
            return True
    except Exception:
        pass

    return isinstance(exc, (asyncio.TimeoutError, TimeoutError, ConnectionError, OSError))


def with_retry(max_attempts: int = 3, base_delay: float = 2.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return await func(*args, **kwargs)
                except RetryablePostError as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        _log_twitter_error(
                            exc,
                            "post_tweet_retry_exhausted",
                            {"attempts": attempt}
                        )
                        return TweetResult(success=False, error=str(exc))

                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Retryable post error (attempt {attempt}/{max_attempts}): {exc}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


@dataclass
class TwitterCredentials:
    """X API credentials"""
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    access_token_secret: str = field(repr=False)
    bearer_token: Optional[str] = field(default=None, repr=False)
    # OAuth 2.0 for @Jarvis_lifeos
    oauth2_client_id: Optional[str] = field(default=None, repr=False)
    oauth2_client_secret: Optional[str] = field(default=None, repr=False)
    oauth2_access_token: Optional[str] = field(default=None, repr=False)
    oauth2_refresh_token: Optional[str] = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "TwitterCredentials":
        """Load credentials from environment variables and persisted token file"""
        try:
            from dotenv import load_dotenv
            # Load from root .env file (project root is 3 directories up)
            env_path = Path(__file__).parent.parent.parent / ".env"
            load_dotenv(env_path, override=False)
        except Exception:
            pass

        # Prefer JARVIS-specific tokens for @Jarvis_lifeos account
        # These are OAuth 1.0a tokens that work directly with the account
        jarvis_access = os.getenv("JARVIS_ACCESS_TOKEN")
        jarvis_secret = os.getenv("JARVIS_ACCESS_TOKEN_SECRET")

        # Use Jarvis tokens if available, otherwise fall back to X_ACCESS_TOKEN
        access_token = jarvis_access or os.getenv("X_ACCESS_TOKEN", "") or os.getenv("TWITTER_ACCESS_TOKEN", "")
        access_secret = jarvis_secret or os.getenv("X_ACCESS_TOKEN_SECRET", "") or os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

        # Load OAuth2 tokens - file takes precedence (contains refreshed tokens)
        persisted_tokens = _load_oauth2_tokens()
        oauth2_access = persisted_tokens.get("access_token") or os.getenv("X_OAUTH2_ACCESS_TOKEN")
        oauth2_refresh = persisted_tokens.get("refresh_token") or os.getenv("X_OAUTH2_REFRESH_TOKEN")

        return cls(
            api_key=os.getenv("X_API_KEY", "") or os.getenv("TWITTER_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", "") or os.getenv("TWITTER_API_SECRET", ""),
            access_token=access_token,
            access_token_secret=access_secret,
            bearer_token=os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN"),
            oauth2_client_id=os.getenv("X_OAUTH2_CLIENT_ID"),
            oauth2_client_secret=os.getenv("X_OAUTH2_CLIENT_SECRET"),
            oauth2_access_token=oauth2_access,
            oauth2_refresh_token=oauth2_refresh
        )

    def is_valid(self) -> bool:
        """Check if all required credentials are present"""
        has_oauth1 = all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret
        ])
        has_oauth2 = bool(self.oauth2_access_token)
        return has_oauth1 or has_oauth2

    def has_oauth2(self) -> bool:
        """Check if OAuth 2.0 credentials are available"""
        return bool(self.oauth2_access_token)


class TwitterClient:
    """
    X API client using OAuth 2.0 for @Jarvis_lifeos
    Falls back to tweepy for media uploads (v1.1 API still required)
    """

    def __init__(self, credentials: Optional[TwitterCredentials] = None):
        self.credentials = credentials or TwitterCredentials.from_env()
        self._xdk_client = None  # Official xdk client
        self._tweepy_api = None  # Tweepy for media uploads
        self._tweepy_client = None  # Tweepy v2 client (fallback)
        self._bearer_client = None  # Tweepy v2 client with bearer token (for reading)
        self._username: Optional[str] = None
        self._user_id: Optional[str] = None
        self._use_oauth2 = False  # Whether to use OAuth 2.0 for posting
        self._circuit_breaker = APICircuitBreaker("twitter_api")
        self._read_disabled_until: Optional[float] = None
        self._read_disabled_reason: Optional[str] = None
        self._load_read_state()

    def _load_read_state(self) -> None:
        try:
            from core.context_engine import context
            disabled_until, reason = context.get_x_read_disable()
            if disabled_until:
                self._read_disabled_until = float(disabled_until)
                self._read_disabled_reason = reason
        except Exception:
            pass

    def _read_allowed(self) -> bool:
        if not self._read_disabled_until:
            return True
        if time.time() >= self._read_disabled_until:
            self._read_disabled_until = None
            self._read_disabled_reason = None
            try:
                from core.context_engine import context
                context.clear_x_read_disable()
            except Exception:
                pass
            return True
        return False

    def _disable_reads(self, reason: str, cooldown_seconds: int = 900) -> None:
        new_until = time.time() + cooldown_seconds
        # Avoid log spam if already disabled with same reason
        if self._read_disabled_until and self._read_disabled_reason == reason:
            return
        self._read_disabled_until = new_until
        self._read_disabled_reason = reason
        logger.warning(f"Disabling X read endpoints for {cooldown_seconds}s: {reason}")
        try:
            from core.context_engine import context
            context.record_x_read_disable(self._read_disabled_until, reason)
        except Exception:
            pass

    def _get_expected_username(self) -> str:
        expected = (
            os.getenv("X_EXPECTED_USERNAME")
            or os.getenv("TWITTER_EXPECTED_USERNAME")
            or "jarvis_lifeos"
        )
        expected = expected.strip().lstrip("@").lower()
        if expected in ("", "any", "*"):
            return ""
        return expected

    @staticmethod
    def _username_matches(username: Optional[str], expected: str) -> bool:
        if not expected:
            return True
        if not username:
            return False
        return username.lower() == expected

    def connect(self) -> bool:
        """Initialize the X API connection - Use OAuth 1.0a (tweepy) as primary"""
        if not self.credentials.is_valid():
            _log_twitter_error(
                RuntimeError("Invalid X credentials - check environment variables"),
                "connect_invalid_credentials"
            )
            logger.error("Invalid X credentials - check environment variables")
            return False

        try:
            expected = self._get_expected_username()

            # PRIMARY: Use OAuth 1.0a (tweepy) - skip OAuth 2.0 which is expired
            tweepy_username = None
            tweepy_user_id = None
            if HAS_TWEEPY:
                try:
                    auth = tweepy.OAuth1UserHandler(
                        self.credentials.api_key,
                        self.credentials.api_secret,
                        self.credentials.access_token,
                        self.credentials.access_token_secret
                    )
                    self._tweepy_api = tweepy.API(auth, wait_on_rate_limit=True)

                    # Init v2 client (primary for posting)
                    self._tweepy_client = tweepy.Client(
                        consumer_key=self.credentials.api_key,
                        consumer_secret=self.credentials.api_secret,
                        access_token=self.credentials.access_token,
                        access_token_secret=self.credentials.access_token_secret,
                        wait_on_rate_limit=True
                    )

                    me = self._tweepy_client.get_me()
                    if me and me.data:
                        tweepy_username = me.data.username
                        tweepy_user_id = str(me.data.id)
                        self._username = tweepy_username
                        self._user_id = tweepy_user_id

                        # Init bearer token client for reading (mentions, etc.)
                        # OAuth 1.0a user tokens have limited read access on free tier
                        if self.credentials.bearer_token:
                            self._bearer_client = tweepy.Client(
                                bearer_token=self.credentials.bearer_token,
                                wait_on_rate_limit=True
                            )
                            logger.debug("Bearer token client initialized for reading")

                        if expected and not self._username_matches(self._username, expected):
                            logger.warning(
                                f"OAuth 1.0a authenticated as @{self._username}, "
                                f"but expected @{expected}. Attempting OAuth 2.0 fallback."
                            )
                        else:
                            logger.info(f"Connected to X as @{self._username} (OAuth 1.0a via tweepy)")
                            return True
                except Exception as e:
                    logger.warning(f"OAuth 1.0a connection failed: {e}")

            # FALLBACK: OAuth 2.0 user context (if available)
            if self.credentials.oauth2_access_token:
                try:
                    import requests

                    headers = {"Authorization": f"Bearer {self.credentials.oauth2_access_token}"}
                    resp = requests.get("https://api.twitter.com/2/users/me", headers=headers, timeout=10)
                    if resp.status_code == 200:
                        user = resp.json().get("data", {})
                        oauth2_username = user.get("username")
                        oauth2_user_id = user.get("id")
                        if expected and not self._username_matches(oauth2_username, expected):
                            logger.error(
                                f"OAuth 2.0 authenticated as @{oauth2_username}, "
                                f"but expected @{expected}."
                            )
                            return False
                        self._username = oauth2_username
                        self._user_id = str(oauth2_user_id) if oauth2_user_id else None
                        self._use_oauth2 = True
                        logger.info(f"Connected to X as @{self._username} (OAuth 2.0 user context)")
                        return True

                    if resp.status_code == 401 and self._refresh_oauth2_token():
                        return self.connect()

                    logger.error(f"OAuth 2.0 /users/me failed (status {resp.status_code})")
                except Exception as e:
                    logger.warning(f"OAuth 2.0 connection failed: {e}")

            # If OAuth 1.0a connected but mismatched expected user, keep it running to avoid downtime
            if tweepy_username and tweepy_user_id:
                logger.warning(
                    f"Continuing with OAuth 1.0a as @{tweepy_username} "
                    f"(expected @{expected}) until OAuth 2.0 tokens are provided."
                )
                self._username = tweepy_username
                self._user_id = tweepy_user_id
                return True

            logger.error("Failed to connect to X with available credentials")
            _log_twitter_error(
                RuntimeError("Failed to connect to X with available credentials"),
                "connect_failed"
            )
            return False

        except Exception as e:
            _log_twitter_error(e, "connect")
            return False

    def _refresh_oauth2_token(self) -> bool:
        """Refresh the OAuth 2.0 access token"""
        if not self.credentials.oauth2_refresh_token:
            return False

        try:
            import requests
            import base64

            token_url = "https://api.twitter.com/2/oauth2/token"
            credentials = base64.b64encode(
                f"{self.credentials.oauth2_client_id}:{self.credentials.oauth2_client_secret}".encode()
            ).decode()

            headers = {
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            }

            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.credentials.oauth2_refresh_token
            }

            resp = requests.post(token_url, headers=headers, data=data)
            if resp.status_code == 200:
                tokens = resp.json()
                new_access = tokens.get("access_token")
                new_refresh = tokens.get("refresh_token", self.credentials.oauth2_refresh_token)

                # Update in memory
                self.credentials.oauth2_access_token = new_access
                if "refresh_token" in tokens:
                    self.credentials.oauth2_refresh_token = new_refresh

                # Persist to file for next restart
                _save_oauth2_tokens(new_access, new_refresh)

                logger.info("OAuth 2.0 token refreshed and persisted successfully")
                return True

            _log_twitter_error(
                RuntimeError("Token refresh failed"),
                "refresh_oauth2_token_status",
                {"status_code": resp.status_code}
            )
            logger.error(f"Token refresh failed (status {resp.status_code})")
            return False

        except Exception as e:
            _log_twitter_error(e, "refresh_oauth2_token")
            return False

    @property
    def username(self) -> Optional[str]:
        """Get the authenticated username"""
        return self._username

    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._username is not None and (self._use_oauth2 or self._tweepy_client is not None)

    @with_retry(max_attempts=3, base_delay=2.0)
    async def post_tweet(
        self,
        text: str,
        media_ids: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        quote_tweet_id: Optional[str] = None,
        sync_to_telegram: bool = True
    ) -> TweetResult:
        """
        Post a tweet using OAuth 2.0 (for @Jarvis_lifeos)

        Args:
            text: Tweet content (max 280 chars)
            media_ids: List of media IDs to attach
            reply_to: Tweet ID to reply to
            quote_tweet_id: Tweet ID to quote
            sync_to_telegram: If True, push to Telegram (default True for main tweets)

        Returns:
            TweetResult with success status and tweet info
        """
        if not self.is_connected:
            return TweetResult(success=False, error="Not connected to X")

        # Validate text length (default 280 unless overridden via env)
        max_chars = _get_max_tweet_length()
        if len(text) > max_chars:
            logger.warning(f"Tweet too long ({len(text)} chars), truncating at word boundary to {max_chars} chars")
            # Find last space before max_chars to preserve word boundaries
            truncated = text[:max_chars - 3]
            last_space = truncated.rfind(' ')
            if last_space > max_chars - 500:  # Only use last space if it's not too early
                text = text[:last_space] + "..."
            else:
                # Fallback: just use max_chars - 3 (handles case with no spaces)
                text = truncated + "..."

        try:
            loop = asyncio.get_event_loop()

            # Build post data
            post_data = {"text": text}

            if media_ids:
                post_data["media"] = {"media_ids": media_ids}

            if reply_to:
                post_data["reply"] = {"in_reply_to_tweet_id": reply_to}

            if quote_tweet_id:
                post_data["quote_tweet_id"] = quote_tweet_id

            # Use OAuth 2.0 for @Jarvis_lifeos (primary method) - native aiohttp
            if self._use_oauth2:
                headers = {
                    "Authorization": f"Bearer {self.credentials.oauth2_access_token}",
                    "Content-Type": "application/json"
                }

                async def _request():
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://api.twitter.com/2/tweets",
                            headers=headers,
                            json=post_data,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            status = resp.status
                            resp_text = await resp.text()
                            try:
                                resp_json = await resp.json()
                            except Exception:
                                resp_json = {}

                            if _is_retryable_status(status):
                                raise RetryablePostError(
                                    f"OAuth 2.0 post failed ({status}): {resp_text}",
                                    status_code=status,
                                )
                            return status, resp_json, resp_text

                try:
                    status, resp_json, resp_text = await self._circuit_breaker.call(_request)
                except CircuitOpenError as exc:
                    return TweetResult(success=False, error=str(exc))
                except RetryablePostError:
                    raise
                except Exception as e:
                    if _is_retryable_exception(e):
                        raise RetryablePostError(f"OAuth 2.0 post failed due to network/timeout: {e}")
                    raise

                if status == 201:
                    data = resp_json.get("data", {})
                    tweet_id = data.get("id")
                    url = f"https://x.com/{self._username}/status/{tweet_id}"
                    logger.info(f"Tweet posted via OAuth 2.0: {url}")

                    # Sync to Telegram (only for main tweets, not replies)
                    if sync_to_telegram and not reply_to:
                        await self._sync_to_telegram(text, url)

                    return TweetResult(success=True, tweet_id=tweet_id, url=url)
                elif status == 401:
                    # Token expired, refresh and retry
                    logger.warning("OAuth 2.0 token expired during post, refreshing...")
                    if self._refresh_oauth2_token():
                        return await self.post_tweet(text, media_ids, reply_to, quote_tweet_id)
                    else:
                        _log_twitter_error(
                            RuntimeError("Token refresh failed during post"),
                            "post_tweet_refresh_failed"
                        )
                        logger.error("Token refresh failed - cannot post (will not fallback to wrong account)")
                        return TweetResult(success=False, error="OAuth 2.0 token refresh failed")
                else:
                    error_msg = f"OAuth 2.0 post failed ({status}): {resp_text}"
                    _log_twitter_error(
                        RuntimeError(f"OAuth 2.0 post failed ({status})"),
                        "post_tweet_oauth2_error",
                        {"status_code": status}
                    )
                    logger.error(error_msg)
                    # Do NOT fallback to tweepy - return error instead
                    return TweetResult(success=False, error=error_msg)

            # Use tweepy if OAuth 2.0 is not active (either not configured or failed to connect)
            if self._tweepy_client and not self._use_oauth2:
                async def _request():
                    return await loop.run_in_executor(
                        None,
                        lambda: self._tweepy_client.create_tweet(
                            text=text,
                            media_ids=media_ids,
                            in_reply_to_tweet_id=reply_to,
                            quote_tweet_id=quote_tweet_id
                        )
                    )

                try:
                    response = await self._circuit_breaker.call(_request)
                except CircuitOpenError as exc:
                    return TweetResult(success=False, error=str(exc))
                except Exception as e:
                    status_code = None
                    if HAS_TWEEPY and isinstance(e, TweepyException):
                        status_code = getattr(getattr(e, "response", None), "status_code", None)
                        if _is_retryable_status(status_code):
                            raise RetryablePostError(
                                f"Tweepy post failed ({status_code}): {e}",
                                status_code=status_code
                            )
                    if _is_retryable_exception(e):
                        raise RetryablePostError(f"Tweepy post failed due to network/timeout: {e}")
                    raise

                if response and response.data:
                    tweet_id = response.data["id"]
                    url = f"https://x.com/{self._username}/status/{tweet_id}"
                    logger.info(f"Tweet posted via tweepy: {url}")

                    # Sync to Telegram (only for main tweets, not replies)
                    if sync_to_telegram and not reply_to:
                        await self._sync_to_telegram(text, url)

                    return TweetResult(success=True, tweet_id=tweet_id, url=url)

            return TweetResult(success=False, error="No SDK available to post")

        except RetryablePostError:
            raise
        except Exception as e:
            _log_twitter_error(e, "post_tweet", {"text_length": len(text), "has_media": bool(media_ids)})
            return TweetResult(success=False, error=str(e))

    async def _sync_to_telegram(self, tweet_text: str, tweet_url: str) -> bool:
        """Sync tweet to Telegram channel."""
        try:
            tg_sync = _get_telegram_sync()
            if tg_sync and tg_sync.enabled:
                return await tg_sync.push_tweet(
                    tweet_text=tweet_text,
                    tweet_url=tweet_url,
                    username=self._username or "Jarvis_lifeos"
                )
        except Exception as e:
            logger.warning(f"Telegram sync failed (non-critical): {e}")
        return False

    async def upload_media(
        self,
        file_path: str,
        alt_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload media to X (uses tweepy v1.1 API - still required for media)

        Args:
            file_path: Path to the media file
            alt_text: Accessibility text for the media

        Returns:
            Media ID string or None on failure
        """
        if not self._tweepy_api:
            _log_twitter_error(
                RuntimeError("Tweepy API not initialized for media upload"),
                "upload_media_missing_client"
            )
            logger.error("Tweepy API not initialized for media upload")
            return None

        try:
            loop = asyncio.get_event_loop()

            ext = os.path.splitext(file_path)[1].lower()
            is_video = ext in {".mp4", ".mov", ".m4v", ".gif"}

            # Upload media via v1.1 API
            media = await loop.run_in_executor(
                None,
                lambda: self._tweepy_api.media_upload(
                    filename=file_path,
                    chunked=is_video,
                    media_category="tweet_video" if is_video else None,
                )
            )

            if alt_text and not is_video:
                await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_api.create_media_metadata(
                        media.media_id,
                        alt_text=alt_text
                    )
                )

            logger.info(f"Media uploaded: {media.media_id}")
            return str(media.media_id)

        except Exception as e:
            _log_twitter_error(e, "upload_media", {"file_path": file_path})
            return None

    async def upload_media_from_bytes(
        self,
        data: bytes,
        filename: str = "image.png",
        alt_text: Optional[str] = None
    ) -> Optional[str]:
        """
        Upload media from bytes data

        Args:
            data: Raw bytes of the media
            filename: Filename for the media
            alt_text: Accessibility text

        Returns:
            Media ID string or None on failure
        """
        import tempfile

        try:
            # Write to temp file
            suffix = os.path.splitext(filename)[1] or ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(data)
                temp_path = f.name

            # Upload the file
            media_id = await self.upload_media(temp_path, alt_text)

            # Clean up temp file
            os.unlink(temp_path)

            return media_id

        except Exception as e:
            _log_twitter_error(e, "upload_media_from_bytes", {"filename": filename})
            return None

    async def reply_to_tweet(
        self,
        tweet_id: str,
        text: str,
        media_ids: Optional[List[str]] = None
    ) -> TweetResult:
        """Reply to a specific tweet"""
        return await self.post_tweet(text, media_ids=media_ids, reply_to=tweet_id)

    async def quote_tweet(
        self,
        tweet_id: str,
        text: str,
        media_ids: Optional[List[str]] = None
    ) -> TweetResult:
        """Quote retweet with comment"""
        return await self.post_tweet(text, media_ids=media_ids, quote_tweet_id=tweet_id)

    async def get_mentions(
        self,
        since_id: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent mentions of the authenticated user

        Args:
            since_id: Only get mentions after this tweet ID
            max_results: Maximum number of mentions to retrieve

        Returns:
            List of mention tweet data
        """
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            # Try xdk first
            if self._xdk_client and self._user_id:
                try:
                    mentions = await loop.run_in_executor(
                        None,
                        lambda: self._xdk_client.posts.mentions(
                            user_id=self._user_id,
                            since_id=since_id,
                            max_results=max_results,
                            expansions=["author_id"],
                            user_fields=["username"]
                        )
                    )
                    if mentions and hasattr(mentions, 'data') and mentions.data:
                        # Build user lookup from includes
                        users = {}
                        if hasattr(mentions, 'includes') and mentions.includes:
                            for user in mentions.includes.get('users', []):
                                users[getattr(user, 'id', None)] = getattr(user, 'username', 'unknown')

                        return [
                            {
                                "id": tweet.id,
                                "text": tweet.text,
                                "author_id": tweet.author_id,
                                "author_username": users.get(tweet.author_id, "unknown"),
                                "created_at": getattr(tweet, 'created_at', None)
                            }
                            for tweet in mentions.data
                        ]
                except Exception as e:
                    logger.warning(f"xdk get_mentions failed: {e}, trying tweepy")

            # Use bearer token client for reading (OAuth 1.0a has limited access on free tier)
            read_client = self._bearer_client or self._tweepy_client
            if read_client and self._user_id:
                mentions = await loop.run_in_executor(
                    None,
                    lambda: read_client.get_users_mentions(
                        id=self._user_id,
                        since_id=since_id,
                        max_results=max_results,
                        tweet_fields=["created_at", "author_id", "conversation_id"],
                        expansions=["author_id"]
                    )
                )

                if not mentions or not mentions.data:
                    return []

                # Build user lookup
                users = {}
                if mentions.includes and "users" in mentions.includes:
                    for user in mentions.includes["users"]:
                        users[user.id] = user.username

                return [
                    {
                        "id": tweet.id,
                        "text": tweet.text,
                        "author_id": tweet.author_id,
                        "author_username": users.get(tweet.author_id, "unknown"),
                        "created_at": tweet.created_at,
                        "conversation_id": getattr(tweet, "conversation_id", None)
                    }
                    for tweet in mentions.data
                ]

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"mentions unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "get_mentions")
            return []

    async def like_tweet(self, tweet_id: str) -> bool:
        """Like a tweet"""
        if not self.is_connected:
            return False

        try:
            loop = asyncio.get_event_loop()

            # Try xdk first
            if self._xdk_client and self._user_id:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: self._xdk_client.posts.like(
                            user_id=self._user_id,
                            tweet_id=tweet_id
                        )
                    )
                    logger.info(f"Liked tweet via xdk: {tweet_id}")
                    return True
                except Exception as e:
                    logger.warning(f"xdk like failed: {e}, trying tweepy")

            # Fallback to tweepy
            if self._tweepy_client:
                await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.like(tweet_id)
                )
                logger.info(f"Liked tweet via tweepy: {tweet_id}")
                return True

            return False

        except Exception as e:
            _log_twitter_error(e, "like_tweet", {"tweet_id": tweet_id})
            return False

    async def retweet(self, tweet_id: str) -> bool:
        """Retweet a tweet"""
        if not self.is_connected:
            return False

        try:
            loop = asyncio.get_event_loop()

            # Try xdk first
            if self._xdk_client and self._user_id:
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: self._xdk_client.posts.retweet(
                            user_id=self._user_id,
                            tweet_id=tweet_id
                        )
                    )
                    logger.info(f"Retweeted via xdk: {tweet_id}")
                    return True
                except Exception as e:
                    logger.warning(f"xdk retweet failed: {e}, trying tweepy")

            # Fallback to tweepy
            if self._tweepy_client:
                await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.retweet(tweet_id)
                )
                logger.info(f"Retweeted via tweepy: {tweet_id}")
                return True

            return False

        except Exception as e:
            _log_twitter_error(e, "retweet", {"tweet_id": tweet_id})
            return False

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific tweet by ID"""
        if not self.is_connected:
            return None

        if not self._read_allowed():
            return None

        try:
            loop = asyncio.get_event_loop()

            # Try xdk first
            if self._xdk_client:
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda: self._xdk_client.posts.get(ids=[tweet_id])
                    )
                    if response and hasattr(response, 'data') and response.data:
                        tweet = response.data[0]
                        return {
                            "id": tweet.id,
                            "text": tweet.text,
                            "created_at": getattr(tweet, 'created_at', None),
                            "metrics": getattr(tweet, 'public_metrics', None)
                        }
                except Exception as e:
                    logger.warning(f"xdk get_tweet failed: {e}, trying tweepy")

            # Fallback to tweepy
            if self._tweepy_client:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.get_tweet(
                        tweet_id,
                        tweet_fields=["created_at", "public_metrics", "author_id"],
                        expansions=["author_id"]
                    )
                )

                if response and response.data:
                    return {
                        "id": response.data.id,
                        "text": response.data.text,
                        "created_at": response.data.created_at,
                        "metrics": response.data.public_metrics
                    }

            return None

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_tweet unauthorized ({status_code})")
                return None
            _log_twitter_error(e, "get_tweet")
            return None

    async def search_recent(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search recent tweets"""
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            # Try xdk first
            if self._xdk_client:
                try:
                    results = await loop.run_in_executor(
                        None,
                        lambda: self._xdk_client.posts.recent_search(
                            query=query,
                            max_results=max_results
                        )
                    )
                    if results and hasattr(results, 'data') and results.data:
                        return [
                            {"id": t.id, "text": t.text}
                            for t in results.data
                        ]
                except Exception as e:
                    logger.warning(f"xdk search failed: {e}, trying tweepy")

            # Fallback to tweepy
            if self._tweepy_client:
                results = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.search_recent_tweets(
                        query=query,
                        max_results=max_results
                    )
                )
                if results and results.data:
                    return [
                        {"id": t.id, "text": t.text}
                        for t in results.data
                    ]

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"search unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "search_recent", {"query": query})
            return []

    async def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user info by username."""
        if not self.is_connected:
            return None

        if not self._read_allowed():
            return None

        try:
            loop = asyncio.get_event_loop()

            # Try tweepy (more reliable for user lookups)
            if self._tweepy_client:
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda: self._tweepy_client.get_user(
                            username=username,
                            user_fields=["created_at", "public_metrics", "description", "verified"]
                        )
                    )
                    if response and response.data:
                        user = response.data
                        metrics = user.public_metrics or {}
                        return {
                            "id": str(user.id),
                            "username": user.username,
                            "name": user.name,
                            "followers_count": metrics.get("followers_count", 0),
                            "following_count": metrics.get("following_count", 0),
                            "tweet_count": metrics.get("tweet_count", 0),
                            "created_at": str(user.created_at) if user.created_at else None,
                            "description": user.description or "",
                            "verified": getattr(user, 'verified', False),
                        }
                except Exception as e:
                    logger.warning(f"tweepy get_user failed: {e}")

            return None

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_user unauthorized ({status_code})")
                return None
            _log_twitter_error(e, "get_user", {"username": username})
            return None

    async def get_quote_tweets(self, tweet_id: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Get quote tweets of a specific tweet."""
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            # Use tweepy for quote tweets
            if self._tweepy_client:
                try:
                    response = await loop.run_in_executor(
                        None,
                        lambda: self._tweepy_client.get_quote_tweets(
                            id=tweet_id,
                            max_results=min(max_results, 100),
                            tweet_fields=["author_id", "created_at", "text"],
                            expansions=["author_id"],
                            user_fields=["username", "public_metrics", "created_at", "description"]
                        )
                    )
                    if response and response.data:
                        # Build user lookup
                        users = {}
                        if response.includes and "users" in response.includes:
                            for user in response.includes["users"]:
                                metrics = user.public_metrics or {}
                                users[str(user.id)] = {
                                    "id": str(user.id),
                                    "username": user.username,
                                    "followers_count": metrics.get("followers_count", 0),
                                    "following_count": metrics.get("following_count", 0),
                                    "tweet_count": metrics.get("tweet_count", 0),
                                    "created_at": str(user.created_at) if user.created_at else None,
                                    "description": user.description or "",
                                }

                        return [
                            {
                                "id": str(tweet.id),
                                "text": tweet.text,
                                "author_id": str(tweet.author_id),
                                "author": users.get(str(tweet.author_id), {}),
                                "created_at": str(tweet.created_at) if tweet.created_at else None,
                            }
                            for tweet in response.data
                        ]
                except Exception as e:
                    logger.warning(f"tweepy get_quote_tweets failed: {e}")

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"quote_tweets unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "get_quote_tweets", {"tweet_id": tweet_id})
            return []

    async def get_liking_users(self, tweet_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get users who liked a specific tweet.
        Uses Twitter API v2 GET /2/tweets/:id/liking_users

        Args:
            tweet_id: The tweet ID to check
            max_results: Maximum users to retrieve (1-100)

        Returns:
            List of user dicts with id, username, name, verified
        """
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            if self._tweepy_client:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.get_liking_users(
                        id=tweet_id,
                        max_results=min(max_results, 100),
                        user_fields=["username", "verified", "public_metrics"]
                    )
                )

                if response and response.data:
                    return [
                        {
                            "id": str(user.id),
                            "username": user.username,
                            "name": getattr(user, "name", user.username),
                            "verified": getattr(user, "verified", False),
                        }
                        for user in response.data
                    ]

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_liking_users unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "get_liking_users", {"tweet_id": tweet_id})
            return []

    async def get_retweeters(self, tweet_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get users who retweeted a specific tweet.
        Uses Twitter API v2 GET /2/tweets/:id/retweeted_by

        Args:
            tweet_id: The tweet ID to check
            max_results: Maximum users to retrieve (1-100)

        Returns:
            List of user dicts with id, username, name, verified
        """
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            if self._tweepy_client:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.get_retweeters(
                        id=tweet_id,
                        max_results=min(max_results, 100),
                        user_fields=["username", "verified", "public_metrics"]
                    )
                )

                if response and response.data:
                    return [
                        {
                            "id": str(user.id),
                            "username": user.username,
                            "name": getattr(user, "name", user.username),
                            "verified": getattr(user, "verified", False),
                        }
                        for user in response.data
                    ]

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_retweeters unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "get_retweeters", {"tweet_id": tweet_id})
            return []

    async def get_tweet_replies(self, tweet_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Get replies to a specific tweet.
        Uses Twitter API v2 search with conversation_id filter.

        Args:
            tweet_id: The tweet ID to get replies for
            max_results: Maximum replies to retrieve

        Returns:
            List of reply dicts with id, text, author_username
        """
        if not self.is_connected:
            return []

        if not self._read_allowed():
            return []

        try:
            loop = asyncio.get_event_loop()

            # Search for replies using conversation_id
            query = f"conversation_id:{tweet_id} is:reply"

            if self._tweepy_client:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.search_recent_tweets(
                        query=query,
                        max_results=min(max_results, 100),
                        tweet_fields=["author_id", "conversation_id", "created_at"],
                        expansions=["author_id"],
                        user_fields=["username", "verified"]
                    )
                )

                if response and response.data:
                    # Build user lookup
                    users = {}
                    if response.includes and "users" in response.includes:
                        for user in response.includes["users"]:
                            users[str(user.id)] = {
                                "username": user.username,
                                "verified": getattr(user, "verified", False),
                            }

                    return [
                        {
                            "id": str(tweet.id),
                            "text": tweet.text,
                            "author_id": str(tweet.author_id),
                            "author_username": users.get(str(tweet.author_id), {}).get("username", ""),
                            "author_verified": users.get(str(tweet.author_id), {}).get("verified", False),
                        }
                        for tweet in response.data
                    ]

            return []

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_tweet_replies unauthorized ({status_code})")
                return []
            _log_twitter_error(e, "get_tweet_replies", {"tweet_id": tweet_id})
            return []

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single tweet by ID.

        Args:
            tweet_id: The tweet ID to fetch

        Returns:
            Tweet dict with id, text, author_id, author_username, or None
        """
        if not self.is_connected:
            return None

        if not self._read_allowed():
            return None

        try:
            loop = asyncio.get_event_loop()

            if self._tweepy_client:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.get_tweet(
                        id=tweet_id,
                        tweet_fields=["author_id", "created_at", "text", "public_metrics"],
                        expansions=["author_id"],
                        user_fields=["username", "verified"]
                    )
                )

                if response and response.data:
                    tweet = response.data
                    author_username = ""
                    author_verified = False

                    if response.includes and "users" in response.includes:
                        for user in response.includes["users"]:
                            if str(user.id) == str(tweet.author_id):
                                author_username = user.username
                                author_verified = getattr(user, "verified", False)
                                break

                    metrics = tweet.public_metrics or {}
                    return {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "author_id": str(tweet.author_id),
                        "author_username": author_username,
                        "author_verified": author_verified,
                        "created_at": str(tweet.created_at) if tweet.created_at else None,
                        "like_count": metrics.get("like_count", 0),
                        "retweet_count": metrics.get("retweet_count", 0),
                        "reply_count": metrics.get("reply_count", 0),
                    }

            return None

        except Exception as e:
            status_code = None
            if HAS_TWEEPY and isinstance(e, TweepyException):
                status_code = getattr(getattr(e, "response", None), "status_code", None)
            if status_code in (401, 403):
                self._disable_reads(f"get_tweet unauthorized ({status_code})")
                return None
            _log_twitter_error(e, "get_tweet_by_id", {"tweet_id": tweet_id})
            return None

    async def block_user(self, user_id: str) -> bool:
        """Block a user by ID."""
        if not self.is_connected or not self._user_id:
            return False

        try:
            loop = asyncio.get_event_loop()

            if self._tweepy_client:
                await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.block(target_user_id=user_id)
                )
                logger.info(f"Blocked user: {user_id}")
                return True

            return False

        except Exception as e:
            _log_twitter_error(e, "block_user", {"user_id": user_id})
            return False

    async def mute_user(self, user_id: str) -> bool:
        """Mute a user by ID."""
        if not self.is_connected or not self._user_id:
            return False

        try:
            loop = asyncio.get_event_loop()

            if self._tweepy_client:
                await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.mute(target_user_id=user_id)
                )
                logger.info(f"Muted user: {user_id}")
                return True

            return False

        except Exception as e:
            _log_twitter_error(e, "mute_user", {"user_id": user_id})
            return False

    def disconnect(self):
        """Clean up connections"""
        self._xdk_client = None
        self._tweepy_client = None
        self._tweepy_api = None
        self._username = None
        self._user_id = None
        logger.info("Disconnected from X")
