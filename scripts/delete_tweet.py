"""Delete a tweet from @Jarvis_lifeos."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "bots" / "twitter" / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

async def delete_tweet(tweet_id: str):
    """Delete a tweet."""
    from bots.twitter.twitter_client import TwitterClient
    
    client = TwitterClient()
    if not client.connect():
        print("Failed to connect to X")
        return False
    
    try:
        import tweepy
        
        # Use tweepy client to delete
        if client._tweepy_client:
            result = client._tweepy_client.delete_tweet(tweet_id)
            if result:
                print(f"Deleted tweet: {tweet_id}")
                return True
    except Exception as e:
        print(f"Error deleting tweet: {e}")
    
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/delete_tweet.py <tweet_id>")
        sys.exit(1)
    
    tweet_id = sys.argv[1]
    asyncio.run(delete_tweet(tweet_id))
