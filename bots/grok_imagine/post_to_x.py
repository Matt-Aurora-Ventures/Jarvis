"""
Post tweet with video to @jarvis_lifeos using Twitter API v2.

Uses OAuth 2.0 for posting and tweepy v1.1 API for media uploads.
Playwright is only used for Grok Imagine video generation.
"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.twitter.twitter_client import TwitterClient

# Load Twitter credentials from twitter bot's .env
TWITTER_ENV_PATH = Path(__file__).parent.parent / "twitter" / ".env"
load_dotenv(TWITTER_ENV_PATH)

# Default paths - can be overridden when calling post_tweet_with_video()
DEFAULT_VIDEO_PATH = Path(__file__).parent / "generated" / "jarvis_btc_video_20260112_094950.mp4"

DEFAULT_TWEET_TEXT = """BTC consolidating at $90K while the charts whisper "accumulation zone."

My algorithms are patient. Your emotions shouldn't be."""


async def post_tweet_with_video(
    tweet_text: str = None,
    video_path: str = None,
    alt_text: str = "JARVIS AI-generated video"
) -> bool:
    """
    Post tweet with video to @jarvis_lifeos via Twitter API v2.

    Args:
        tweet_text: The tweet content (max 280 chars)
        video_path: Path to the video file
        alt_text: Accessibility text for the video

    Returns:
        True if successful, False otherwise
    """
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    tweet_text = tweet_text or DEFAULT_TWEET_TEXT
    video_path = Path(video_path) if video_path else DEFAULT_VIDEO_PATH

    print("\n" + "="*60)
    print("POSTING TO @jarvis_lifeos (via API v2)")
    print("="*60)

    if not video_path.exists():
        print(f"ERROR: Video not found: {video_path}")
        return False

    print(f"Video: {video_path}")
    print(f"Tweet: {tweet_text[:50]}...")

    # Initialize Twitter client
    client = TwitterClient()

    print("\nConnecting to Twitter API...")
    if not client.connect():
        print("ERROR: Failed to connect to Twitter API")
        print("Make sure OAuth 2.0 credentials are set in bots/twitter/.env")
        return False

    print(f"Connected as @{client.username}")

    # Check we're posting to the right account
    if client.username and client.username.lower() != "jarvis_lifeos":
        print(f"WARNING: Connected as @{client.username}, expected @jarvis_lifeos")
        print("Aborting to prevent posting to wrong account.")
        return False

    try:
        # Upload video
        print("\nUploading video...")
        media_id = await client.upload_media(
            file_path=str(video_path),
            alt_text=alt_text
        )

        if not media_id:
            print("ERROR: Failed to upload video")
            return False

        print(f"Video uploaded, media_id: {media_id}")

        # Post the tweet
        print("\nPosting tweet...")
        result = await client.post_tweet(
            text=tweet_text,
            media_ids=[media_id]
        )

        if result.success:
            print("\n" + "="*60)
            print("*** TWEET POSTED SUCCESSFULLY! ***")
            print(f"URL: {result.url}")
            print("="*60)
            return True
        else:
            print(f"ERROR: Failed to post tweet: {result.error}")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        client.disconnect()


async def post_text_only(tweet_text: str) -> bool:
    """
    Post a text-only tweet to @jarvis_lifeos.

    Args:
        tweet_text: The tweet content (max 280 chars)

    Returns:
        True if successful, False otherwise
    """
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    print("\n" + "="*60)
    print("POSTING TO @jarvis_lifeos (via API v2)")
    print("="*60)
    print(f"Tweet: {tweet_text[:50]}...")

    client = TwitterClient()

    if not client.connect():
        print("ERROR: Failed to connect to Twitter API")
        return False

    print(f"Connected as @{client.username}")

    if client.username and client.username.lower() != "jarvis_lifeos":
        print(f"WARNING: Connected as @{client.username}, expected @jarvis_lifeos")
        return False

    try:
        result = await client.post_tweet(text=tweet_text)

        if result.success:
            print(f"\n*** TWEET POSTED: {result.url} ***")
            return True
        else:
            print(f"ERROR: {result.error}")
            return False
    finally:
        client.disconnect()


if __name__ == "__main__":
    result = asyncio.run(post_tweet_with_video())
    if result:
        print("\nDone!")
    else:
        print("\nFailed to post tweet")
