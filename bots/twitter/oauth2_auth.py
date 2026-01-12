"""
OAuth 2.0 Authentication Helper for @Jarvis_lifeos

Run this script to get new OAuth 2.0 tokens.
"""
import os
import sys
import webbrowser
import winreg
import hashlib
import base64
import secrets
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
import requests

# Load env
for env_path in [Path(__file__).parent / '.env', Path(__file__).parent.parent.parent / 'tg_bot' / '.env']:
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

CLIENT_ID = os.environ.get('X_OAUTH2_CLIENT_ID')
CLIENT_SECRET = os.environ.get('X_OAUTH2_CLIENT_SECRET')
REDIRECT_URI = "http://localhost:8888/callback"

# PKCE
code_verifier = secrets.token_urlsafe(32)
code_challenge = base64.urlsafe_b64encode(
    hashlib.sha256(code_verifier.encode()).digest()
).decode().rstrip('=')

class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback"""

    def do_GET(self):
        if '/callback' in self.path:
            # Parse the authorization code
            query = parse_qs(urlparse(self.path).query)
            code = query.get('code', [None])[0]

            if code:
                # Exchange code for tokens
                print(f"\n✅ Got authorization code!")
                tokens = exchange_code(code)

                if tokens:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b"""
                    <html><body style="font-family: monospace; padding: 40px;">
                    <h1>Success!</h1>
                    <p>OAuth 2.0 tokens received. Check your terminal for the tokens.</p>
                    <p>You can close this window.</p>
                    </body></html>
                    """)

                    # Store in class for access
                    self.server.tokens = tokens
                else:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"Failed to exchange code for tokens")
            else:
                error = query.get('error', ['unknown'])[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Error: {error}".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress logging


def exchange_code(code: str) -> dict:
    """Exchange authorization code for tokens"""
    credentials = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()

    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': code_verifier
    }

    resp = requests.post('https://api.twitter.com/2/oauth2/token', headers=headers, data=data)

    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"❌ Token exchange failed: {resp.text}")
        return None


def _find_firefox_path() -> str:
    """Return a Firefox executable path if available (avoid Nightly)."""
    env_path = os.environ.get("FIREFOX_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    candidates = [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        r"C:\Program Files\Firefox Developer Edition\firefox.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe"
        ) as key:
            path = winreg.QueryValue(key, None)
            if path and Path(path).exists():
                return path
    except OSError:
        pass

    return ""


def main():
    print("=" * 50)
    print("X OAuth 2.0 Authentication for @Jarvis_lifeos")
    print("=" * 50)
    print()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Missing X_OAUTH2_CLIENT_ID or X_OAUTH2_CLIENT_SECRET in .env")
        return

    # Build authorization URL
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'scope': 'tweet.read tweet.write users.read offline.access',
        'state': secrets.token_urlsafe(16),
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }

    auth_url = f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"

    print("Opening browser for authorization...")
    print()
    print("If browser doesn't open, visit this URL:")
    print(auth_url)
    print()

    # Open Firefox explicitly (avoid Nightly)
    firefox_path = _find_firefox_path()
    if firefox_path:
        browser = webbrowser.BackgroundBrowser(firefox_path)
        browser.open(auth_url, new=1)
        print(f"Using Firefox at: {firefox_path}")
    else:
        print("Firefox not found. Set FIREFOX_PATH to firefox.exe if needed.")
        webbrowser.open(auth_url, new=1)

    # Start local server to receive callback
    print("Waiting for callback on http://localhost:8888/callback ...")
    print()

    server = HTTPServer(('localhost', 8888), CallbackHandler)
    server.tokens = None
    server.handle_request()  # Handle one request

    if server.tokens:
        print()
        print("=" * 50)
        print("✅ NEW TOKENS (update your .env file)")
        print("=" * 50)
        print()
        print(f"X_OAUTH2_ACCESS_TOKEN={server.tokens.get('access_token')}")
        print(f"X_OAUTH2_REFRESH_TOKEN={server.tokens.get('refresh_token')}")
        print()
        print(f"Token type: {server.tokens.get('token_type')}")
        print(f"Expires in: {server.tokens.get('expires_in')} seconds")
        print(f"Scope: {server.tokens.get('scope')}")
        print()

        # Verify the token works
        headers = {'Authorization': f"Bearer {server.tokens.get('access_token')}"}
        resp = requests.get('https://api.twitter.com/2/users/me', headers=headers)
        if resp.status_code == 200:
            user = resp.json().get('data', {})
            print(f"✅ Authenticated as: @{user.get('username')}")

        # Ask to update .env
        print()
        update = input("Update .env file automatically? (y/n): ").strip().lower()
        if update == 'y':
            env_path = Path(__file__).parent / '.env'
            if env_path.exists():
                with open(env_path, 'r') as f:
                    content = f.read()

                # Replace tokens
                import re
                content = re.sub(
                    r'X_OAUTH2_ACCESS_TOKEN=.*',
                    f"X_OAUTH2_ACCESS_TOKEN={server.tokens.get('access_token')}",
                    content
                )
                content = re.sub(
                    r'X_OAUTH2_REFRESH_TOKEN=.*',
                    f"X_OAUTH2_REFRESH_TOKEN={server.tokens.get('refresh_token')}",
                    content
                )

                with open(env_path, 'w') as f:
                    f.write(content)

                print(f"✅ Updated {env_path}")
            else:
                print(f"❌ {env_path} not found")
    else:
        print("❌ No tokens received")


if __name__ == "__main__":
    main()
