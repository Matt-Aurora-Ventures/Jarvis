# This is /home/ubuntu/copri_app/src/integrations/x_integration.py
import requests
import json

# Placeholder for X API (formerly Twitter API)
# Actual implementation would use the official X API client or make direct HTTP requests
# with proper authentication (e.g., OAuth 2.0 Bearer Token or OAuth 1.0a for user context)

X_API_BASE_URL_V2 = "https://api.twitter.com/2" # Example for v2 API

class XIntegration:
    def __init__(self, bearer_token=None, api_key=None, api_secret_key=None, access_token=None, access_token_secret=None):
        """Initializes the X client.
        bearer_token: For App-only authentication (v2).
        api_key, api_secret_key, access_token, access_token_secret: For User context authentication (v1.1 or v2 with OAuth 2.0 PKCE).
        """
        self.bearer_token = bearer_token
        self.api_key = api_key
        self.api_secret_key = api_secret_key
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.headers = {}

        if self.bearer_token:
            self.headers["Authorization"] = f"Bearer {self.bearer_token}"
        
        # For OAuth 1.0a, requests would need to be signed, typically using a library like requests-oauthlib
        print("[XIntegration] Initialized. Authentication method depends on provided tokens.")

    def search_recent_tweets(self, query, max_results=10):
        """Searches for recent tweets matching the query (v2 API)."""
        if not self.bearer_token:
            print("[XIntegration] Bearer token required for v2 search. Cannot search tweets.")
            return []
        
        url = f"{X_API_BASE_URL_V2}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,public_metrics,entities,source",
            "expansions": "author_id",
            "user.fields": "username,name,profile_image_url,verified"
        }
        try:
            # response = requests.get(url, headers=self.headers, params=params)
            # response.raise_for_status()
            # print(f"[XIntegration] Fetched tweets for query: {query}")
            # return response.json()
            print(f"[XIntegration] Simulating fetching tweets for query: {query}")
            return {
                "data": [
                    {"id": "sim_tweet_1", "text": f"Simulated tweet about {query}", "author_id": "sim_author_1"},
                    {"id": "sim_tweet_2", "text": f"Another simulated tweet on {query}", "author_id": "sim_author_2"}
                ],
                "includes": {
                    "users": [
                        {"id": "sim_author_1", "username": "simuser1", "name": "Sim User One"},
                        {"id": "sim_author_2", "username": "simuser2", "name": "Sim User Two"}
                    ]
                }
            }
        except requests.exceptions.RequestException as e:
            print(f"Error searching X/Twitter for tweets: {e}")
            return []

    def get_user_profile(self, username):
        """Gets public profile information for a given username (v2 API)."""
        if not self.bearer_token:
            print("[XIntegration] Bearer token required for v2 user lookup. Cannot get profile.")
            return None
        
        url = f"{X_API_BASE_URL_V2}/users/by/username/{username}"
        params = {
            "user.fields": "created_at,description,entities,id,location,name,pinned_tweet_id,profile_image_url,protected,public_metrics,url,username,verified"
        }
        try:
            # response = requests.get(url, headers=self.headers, params=params)
            # response.raise_for_status()
            # print(f"[XIntegration] Fetched profile for username: {username}")
            # return response.json()
            print(f"[XIntegration] Simulating fetching profile for username: {username}")
            return {
                "data": {
                    "id": "sim_user_id_123",
                    "name": username.capitalize(),
                    "username": username,
                    "description": "Simulated user description.",
                    "public_metrics": {"followers_count": 100, "following_count": 50, "tweet_count": 200}
                }
            }
        except requests.exceptions.RequestException as e:
            print(f"Error getting X/Twitter user profile for {username}: {e}")
            return None

# Example usage (for testing)
# if __name__ == "__main__":
#     # This would require setting up an X Developer App and getting a Bearer Token
#     TEST_BEARER_TOKEN = None # "YOUR_X_BEARER_TOKEN"

#     if not TEST_BEARER_TOKEN:
#         print("X Bearer Token not set. Cannot run live tests.")
#         x_client = XIntegration()
#         # Simulate calls even without token for structure check
#         x_client.search_recent_tweets(query="#AI")
#         x_client.get_user_profile(username="TwitterDev")
#     else:
#         x_client = XIntegration(bearer_token=TEST_BEARER_TOKEN)
#         tweets = x_client.search_recent_tweets(query="#AI OR #ArtificialIntelligence lang:en -is:retweet", max_results=5)
#         if tweets and tweets.get("data"):
#             print(f"Recent AI tweets: {json.dumps(tweets, indent=2)}")
        
#         profile = x_client.get_user_profile(username="TwitterDev")
#         if profile and profile.get("data"):
#             print(f"TwitterDev profile: {json.dumps(profile, indent=2)}")

