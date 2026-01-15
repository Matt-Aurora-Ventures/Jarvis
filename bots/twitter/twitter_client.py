"""
X API Client
Handles authentication and posting via official xdk SDK
With tweepy fallback for media uploads (v1.1 API)
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

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


@dataclass
class TwitterCredentials:
    """X API credentials"""
    api_key: str
    api_secret: str
    access_token: str
    access_token_secret: str
    bearer_token: Optional[str] = None
    # OAuth 2.0 for @Jarvis_lifeos
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    oauth2_access_token: Optional[str] = None
    oauth2_refresh_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TwitterCredentials":
        """Load credentials from environment variables"""
        try:
            from dotenv import load_dotenv
            env_path = Path(__file__).parent / ".env"
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
        
        return cls(
            api_key=os.getenv("X_API_KEY", "") or os.getenv("TWITTER_API_KEY", ""),
            api_secret=os.getenv("X_API_SECRET", "") or os.getenv("TWITTER_API_SECRET", ""),
            access_token=access_token,
            access_token_secret=access_secret,
            bearer_token=os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN"),
            oauth2_client_id=os.getenv("X_OAUTH2_CLIENT_ID"),
            oauth2_client_secret=os.getenv("X_OAUTH2_CLIENT_SECRET"),
            oauth2_access_token=os.getenv("X_OAUTH2_ACCESS_TOKEN"),
            oauth2_refresh_token=os.getenv("X_OAUTH2_REFRESH_TOKEN")
        )

    def is_valid(self) -> bool:
        """Check if all required credentials are present"""
        return all([
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_token_secret
        ])

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
        self._username: Optional[str] = None
        self._user_id: Optional[str] = None
        self._use_oauth2 = False  # Whether to use OAuth 2.0 for posting

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
        """Initialize the X API connection"""
        if not (self.credentials.is_valid() or self.credentials.has_oauth2()):
            logger.error("Invalid X credentials - check environment variables")
            return False

        try:
            expected = self._get_expected_username()

            # Check if we have OAuth 2.0 for @Jarvis_lifeos
            if self.credentials.has_oauth2():
                # Verify OAuth 2.0 token
                import requests
                headers = {"Authorization": f"Bearer {self.credentials.oauth2_access_token}"}
                resp = requests.get("https://api.twitter.com/2/users/me", headers=headers)
                if resp.status_code == 200:
                    user = resp.json().get("data", {})
                    self._username = user.get("username")
                    self._user_id = user.get("id")
                    if not self._username_matches(self._username, expected):
                        logger.error(
                            "OAuth 2.0 account mismatch: expected @%s, got @%s",
                            expected or "any",
                            self._username or "unknown",
                        )
                        self._use_oauth2 = False
                        self._username = None
                        self._user_id = None
                        return False
                    self._use_oauth2 = True
                    logger.info(f"Connected to X as @{self._username} (via OAuth 2.0)")
                elif resp.status_code == 401:
                    # Token expired, try to refresh
                    logger.warning("OAuth 2.0 token expired, attempting refresh...")
                    if self._refresh_oauth2_token():
                        return self.connect()  # Retry with new token
                    else:
                        logger.error("Failed to refresh OAuth 2.0 token")
                        self._use_oauth2 = False

            # Also init tweepy for media uploads (v1.1 API)
            tweepy_username = None
            tweepy_user_id = None
            if HAS_TWEEPY and self.credentials.is_valid():
                auth = tweepy.OAuth1UserHandler(
                    self.credentials.api_key,
                    self.credentials.api_secret,
                    self.credentials.access_token,
                    self.credentials.access_token_secret
                )
                self._tweepy_api = tweepy.API(auth, wait_on_rate_limit=True)

                # Also init v2 client as fallback (for @aurora_ventures)
                self._tweepy_client = tweepy.Client(
                    bearer_token=self.credentials.bearer_token,
                    consumer_key=self.credentials.api_key,
                    consumer_secret=self.credentials.api_secret,
                    access_token=self.credentials.access_token,
                    access_token_secret=self.credentials.access_token_secret,
                    wait_on_rate_limit=True
                )

                try:
                    me = self._tweepy_client.get_me()
                    if me and me.data:
                        tweepy_username = me.data.username
                        tweepy_user_id = str(me.data.id)
                except Exception as e:
                    logger.warning(f"Failed to verify tweepy account: {e}")

                if tweepy_username and not self._username_matches(tweepy_username, expected):
                    logger.error(
                        "Tweepy account mismatch: expected @%s, got @%s",
                        expected or "any",
                        tweepy_username,
                    )
                    self._tweepy_api = None
                    self._tweepy_client = None
                    if not self._use_oauth2:
                        return False

                if self._use_oauth2 and self._username and tweepy_username:
                    if tweepy_username.lower() != self._username.lower():
                        logger.error(
                            "Tweepy account does not match OAuth 2.0 account (@%s vs @%s). "
                            "Disabling tweepy to prevent cross-account posting.",
                            tweepy_username,
                            self._username,
                        )
                        self._tweepy_api = None
                        self._tweepy_client = None

            # If OAuth 2.0 worked, we're done
            if self._use_oauth2 and self._username:
                return True

            # If tweepy connected to the expected account, allow it even if OAuth 2.0 failed
            # This handles the case where OAuth 2.0 tokens expired but JARVIS_ACCESS_TOKEN works
            if self._tweepy_client and tweepy_username:
                if self._username_matches(tweepy_username, expected):
                    self._username = tweepy_username
                    self._user_id = tweepy_user_id
                    logger.info(f"Connected to X as @{self._username} (via tweepy with Jarvis tokens)")
                    return True
                else:
                    logger.error(f"Tweepy connected to wrong account: @{tweepy_username}, expected @{expected}")
                    return False

            logger.error("Failed to verify X credentials")
            return False

        except Exception as e:
            logger.error(f"X connection error: {e}")
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
                self.credentials.oauth2_access_token = tokens.get("access_token")
                if "refresh_token" in tokens:
                    self.credentials.oauth2_refresh_token = tokens["refresh_token"]
                logger.info("OAuth 2.0 token refreshed successfully")
                return True

            logger.error(f"Token refresh failed: {resp.text}")
            return False

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False

    @property
    def username(self) -> Optional[str]:
        """Get the authenticated username"""
        return self._username

    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._username is not None and (self._use_oauth2 or self._tweepy_client is not None)

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

        # Validate text length
        if len(text) > 280:
            logger.warning(f"Tweet too long ({len(text)} chars), truncating")
            text = text[:277] + "..."

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

            # Use OAuth 2.0 for @Jarvis_lifeos (primary method)
            if self._use_oauth2:
                import requests

                headers = {
                    "Authorization": f"Bearer {self.credentials.oauth2_access_token}",
                    "Content-Type": "application/json"
                }

                response = await loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        "https://api.twitter.com/2/tweets",
                        headers=headers,
                        json=post_data
                    )
                )

                if response.status_code == 201:
                    data = response.json().get("data", {})
                    tweet_id = data.get("id")
                    url = f"https://x.com/{self._username}/status/{tweet_id}"
                    logger.info(f"Tweet posted via OAuth 2.0: {url}")

                    # Sync to Telegram (only for main tweets, not replies)
                    if sync_to_telegram and not reply_to:
                        await self._sync_to_telegram(text, url)

                    return TweetResult(success=True, tweet_id=tweet_id, url=url)
                elif response.status_code == 401:
                    # Token expired, refresh and retry
                    logger.warning("OAuth 2.0 token expired during post, refreshing...")
                    if self._refresh_oauth2_token():
                        return await self.post_tweet(text, media_ids, reply_to, quote_tweet_id)
                    else:
                        logger.error("Token refresh failed - cannot post (will not fallback to wrong account)")
                        return TweetResult(success=False, error="OAuth 2.0 token refresh failed")
                else:
                    error_msg = f"OAuth 2.0 post failed ({response.status_code}): {response.text}"
                    logger.error(error_msg)
                    # Do NOT fallback to tweepy - return error instead
                    return TweetResult(success=False, error=error_msg)

            # Use tweepy if OAuth 2.0 is not active (either not configured or failed to connect)
            if self._tweepy_client and not self._use_oauth2:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.create_tweet(
                        text=text,
                        media_ids=media_ids,
                        in_reply_to_tweet_id=reply_to,
                        quote_tweet_id=quote_tweet_id
                    )
                )

                if response and response.data:
                    tweet_id = response.data["id"]
                    url = f"https://x.com/{self._username}/status/{tweet_id}"
                    logger.info(f"Tweet posted via tweepy: {url}")

                    # Sync to Telegram (only for main tweets, not replies)
                    if sync_to_telegram and not reply_to:
                        await self._sync_to_telegram(text, url)

                    return TweetResult(success=True, tweet_id=tweet_id, url=url)

            return TweetResult(success=False, error="No SDK available to post")

        except Exception as e:
            logger.error(f"Failed to post tweet: {e}")
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
            logger.error(f"Failed to upload media: {e}")
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
            logger.error(f"Failed to upload media from bytes: {e}")
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

            # Fallback to tweepy
            if self._tweepy_client and self._user_id:
                mentions = await loop.run_in_executor(
                    None,
                    lambda: self._tweepy_client.get_users_mentions(
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
                        "conversation_id": tweet.conversation_id
                    }
                    for tweet in mentions.data
                ]

            return []

        except Exception as e:
            logger.error(f"Failed to get mentions: {e}")
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
            logger.error(f"Failed to like tweet: {e}")
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
            logger.error(f"Failed to retweet: {e}")
            return False

    async def get_tweet(self, tweet_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific tweet by ID"""
        if not self.is_connected:
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
            logger.error(f"Failed to get tweet: {e}")
            return None

    async def search_recent(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """Search recent tweets"""
        if not self.is_connected:
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
            logger.error(f"Failed to search: {e}")
            return []

    def disconnect(self):
        """Clean up connections"""
        self._xdk_client = None
        self._tweepy_client = None
        self._tweepy_api = None
        self._username = None
        self._user_id = None
        logger.info("Disconnected from X")
