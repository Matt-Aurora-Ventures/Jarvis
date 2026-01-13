"""
OAuth 2.0 Setup for @Jarvis_lifeos
Run this once to authorize the bot to post as @Jarvis_lifeos
"""

import os
import base64
import hashlib
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# OAuth 2.0 credentials
CLIENT_ID = os.getenv("X_OAUTH2_CLIENT_ID")
CLIENT_SECRET = os.getenv("X_OAUTH2_CLIENT_SECRET")
REDIRECT_URI = os.getenv("X_OAUTH2_REDIRECT_URI", "http://localhost:8888/callback")

# PKCE code verifier and challenge
code_verifier = secrets.token_urlsafe(32)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip("=")

# Store the authorization code
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code

        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            params = parse_qs(parsed.query)

            if "code" in params:
                auth_code = params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html><body style="font-family: Arial; text-align: center; padding-top: 50px;">
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """)
            else:
                error = params.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"<h1>Error: {error}</h1>".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging


def get_authorization_url():
    """Generate the OAuth 2.0 authorization URL"""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": secrets.token_urlsafe(16),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    return f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"


def exchange_code_for_tokens(code):
    """Exchange authorization code for access tokens"""
    token_url = "https://api.twitter.com/2/oauth2/token"

    # Basic auth header
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier
    }

    response = requests.post(token_url, headers=headers, data=data)
    return response.json()


def main():
    print("=" * 60)
    print("   JARVIS Twitter Bot - OAuth 2.0 Setup")
    print("=" * 60)
    print()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: OAuth 2.0 credentials not found in .env")
        print("Make sure X_OAUTH2_CLIENT_ID and X_OAUTH2_CLIENT_SECRET are set")
        return

    print("This will authorize your bot to post as @Jarvis_lifeos")
    print()
    print("Steps:")
    print("1. A browser window will open")
    print("2. Log in as @Jarvis_lifeos (NOT @aurora_ventures)")
    print("3. Click 'Authorize app'")
    print("4. The browser will redirect back here")
    print()

    # Generate auth URL
    auth_url = get_authorization_url()
    print(f"\nOpening browser...")
    print(f"If it doesn't open, visit: {auth_url}")
    webbrowser.open(auth_url)

    # Start local server to receive callback
    print("\nWaiting for authorization callback...")
    # Parse port from redirect URI
    from urllib.parse import urlparse
    parsed_uri = urlparse(REDIRECT_URI)
    port = parsed_uri.port or 8888
    server = HTTPServer(("127.0.0.1", port), CallbackHandler)

    while auth_code is None:
        server.handle_request()

    print(f"\nReceived authorization code!")
    print("Exchanging for access tokens...")

    # Exchange code for tokens
    tokens = exchange_code_for_tokens(auth_code)

    if "access_token" in tokens:
        print("\n" + "=" * 60)
        print("   SUCCESS! Add these to your .env file:")
        print("=" * 60)
        print()
        print(f"# OAuth 2.0 Tokens for @Jarvis_lifeos")
        print(f"X_OAUTH2_ACCESS_TOKEN={tokens['access_token']}")
        if "refresh_token" in tokens:
            print(f"X_OAUTH2_REFRESH_TOKEN={tokens['refresh_token']}")
        print()
        print(f"Token expires in: {tokens.get('expires_in', 'unknown')} seconds")
        print()

        # Verify the account
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        me = requests.get("https://api.twitter.com/2/users/me", headers=headers)
        if me.status_code == 200:
            user = me.json().get("data", {})
            print(f"Verified account: @{user.get('username', 'unknown')}")

    else:
        print("\nERROR: Failed to get tokens")
        print(tokens)


if __name__ == "__main__":
    main()
