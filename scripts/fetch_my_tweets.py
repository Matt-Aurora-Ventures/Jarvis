#!/usr/bin/env python3
"""
Fetch the last 1000 tweets from your X timeline and save to a document.
Uses the existing TwitterClient infrastructure.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bots.twitter.twitter_client import TwitterClient


async def fetch_my_tweets(max_tweets: int = 1000) -> list:
    """Fetch user's own tweets using Twitter API."""

    # Initialize Twitter client
    client = TwitterClient()

    # Connect to Twitter
    if not client.connect():
        print("Failed to connect to Twitter API")
        return []

    print(f"Connected as @{client.username}")
    print(f"Fetching last {max_tweets} tweets...")

    # Get user ID
    if not client._user_id:
        print("Could not get user ID")
        return []

    all_tweets = []
    pagination_token = None

    # Fetch tweets in batches (max 100 per request)
    while len(all_tweets) < max_tweets:
        remaining = max_tweets - len(all_tweets)
        batch_size = min(100, remaining)  # API max is 100

        try:
            # Use bearer token client for reading (better for timeline access)
            read_client = client._bearer_client or client._tweepy_client
            if read_client:
                loop = asyncio.get_event_loop()

                kwargs = {
                    "id": client._user_id,
                    "max_results": batch_size,
                    "tweet_fields": ["created_at", "public_metrics", "referenced_tweets"],
                    "exclude": ["retweets"],  # Optional: exclude retweets to get more original content
                }

                if pagination_token:
                    kwargs["pagination_token"] = pagination_token

                print(f"  Attempting to fetch batch with {batch_size} tweets...")

                response = await loop.run_in_executor(
                    None,
                    lambda: read_client.get_users_tweets(**kwargs)
                )

                if not response or not response.data:
                    print(f"No more tweets found. Retrieved {len(all_tweets)} total.")
                    break

                # Add tweets to collection
                for tweet in response.data:
                    metrics = tweet.public_metrics or {}

                    # Check if it's a retweet or reply
                    is_retweet = False
                    is_reply = False
                    if hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets:
                        for ref in tweet.referenced_tweets:
                            if ref.type == "retweeted":
                                is_retweet = True
                            elif ref.type == "replied_to":
                                is_reply = True

                    tweet_data = {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "created_at": str(tweet.created_at) if tweet.created_at else None,
                        "like_count": metrics.get("like_count", 0),
                        "retweet_count": metrics.get("retweet_count", 0),
                        "reply_count": metrics.get("reply_count", 0),
                        "is_retweet": is_retweet,
                        "is_reply": is_reply,
                        "url": f"https://x.com/{client.username}/status/{tweet.id}"
                    }
                    all_tweets.append(tweet_data)

                print(f"Fetched {len(all_tweets)} tweets so far...")

                # Check for next page
                if hasattr(response, 'meta') and response.meta:
                    pagination_token = response.meta.get('next_token')
                    if not pagination_token:
                        print("No more pages available.")
                        break
                else:
                    break

                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)
            else:
                print("Tweepy client not available")
                break

        except Exception as e:
            print(f"Error fetching tweets: {e}")
            break

    return all_tweets


async def main():
    """Main function to fetch and save tweets."""

    print("=" * 80)
    print("JARVIS Twitter Archive Generator")
    print("=" * 80)
    print()

    # Fetch tweets
    tweets = await fetch_my_tweets(max_tweets=1000)

    if not tweets:
        print("No tweets retrieved.")
        return

    print(f"\n[OK] Retrieved {len(tweets)} tweets")

    # Create output directory if needed
    output_dir = project_root / "docs"
    output_dir.mkdir(exist_ok=True)

    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save as JSON
    json_file = output_dir / f"twitter_archive_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved JSON: {json_file}")

    # Save as formatted markdown
    md_file = output_dir / f"twitter_archive_{timestamp}.md"
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write(f"# Twitter Archive - @{tweets[0]['url'].split('/')[3] if tweets else 'unknown'}\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"Total tweets: {len(tweets)}\n\n")
        f.write("---\n\n")

        # Stats
        original_tweets = [t for t in tweets if not t['is_retweet'] and not t['is_reply']]
        retweets = [t for t in tweets if t['is_retweet']]
        replies = [t for t in tweets if t['is_reply']]

        f.write("## Stats\n\n")
        f.write(f"- Original tweets: {len(original_tweets)}\n")
        f.write(f"- Retweets: {len(retweets)}\n")
        f.write(f"- Replies: {len(replies)}\n")
        f.write(f"- Total engagement: {sum(t['like_count'] + t['retweet_count'] for t in tweets):,} (likes + retweets)\n")
        f.write("\n---\n\n")

        # Write each tweet
        f.write("## Tweets\n\n")
        for i, tweet in enumerate(tweets, 1):
            tweet_type = ""
            if tweet['is_retweet']:
                tweet_type = " [RETWEET]"
            elif tweet['is_reply']:
                tweet_type = " [REPLY]"

            f.write(f"### Tweet {i}{tweet_type}\n\n")
            f.write(f"**Date:** {tweet['created_at']}\n\n")
            f.write(f"**URL:** [{tweet['url']}]({tweet['url']})\n\n")
            f.write(f"**Engagement:** Likes: {tweet['like_count']} | Retweets: {tweet['retweet_count']} | Replies: {tweet['reply_count']}\n\n")
            f.write(f"**Text:**\n\n")
            f.write(f"> {tweet['text']}\n\n")
            f.write("---\n\n")

    print(f"[OK] Saved Markdown: {md_file}")

    print("\n" + "=" * 80)
    print("[OK] Archive complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
