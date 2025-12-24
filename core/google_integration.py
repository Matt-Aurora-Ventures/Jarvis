"""
Google API Integration for Jarvis.
Autonomous integration with Google services using OAuth 2.0.
"""

import json
import os
import pickle
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
GOOGLE_CREDENTIALS_PATH = ROOT / "secrets" / "google_credentials.json"
GOOGLE_TOKEN_PATH = ROOT / "secrets" / "google_token.pickle"
GOOGLE_CONFIG_PATH = ROOT / "data" / "google_config.json"
INTEGRATION_LOG_PATH = ROOT / "data" / "google_integrations.log"

# Google API scopes for different services
API_SCOPES = {
    "drive": [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file"
    ],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify"
    ],
    "calendar": [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events"
    ],
    "sheets": [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ],
    "docs": [
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/documents.readonly"
    ],
    "all": []  # Will be populated with all scopes
}

# Populate all scopes
for scopes in API_SCOPES.values():
    API_SCOPES["all"].extend(scopes)
API_SCOPES["all"] = list(set(API_SCOPES["all"]))


class GoogleIntegration:
    """Manages Google API authentication and service integration."""
    
    def __init__(self):
        self.authenticated = False
        self.credentials = None
        self.services = {}
        self._load_config()
        
    def _load_config(self):
        """Load Google integration configuration."""
        if GOOGLE_CONFIG_PATH.exists():
            with open(GOOGLE_CONFIG_PATH, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "enabled_services": [],
                "last_sync": None,
                "api_usage": {},
                "auto_enable": True
            }
    
    def _save_config(self):
        """Save Google integration configuration."""
        with open(GOOGLE_CONFIG_PATH, "w") as f:
            json.dump(self.config, f, indent=2)
    
    def _log_action(self, action: str, details: Dict[str, Any]):
        """Log Google integration actions."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(INTEGRATION_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def is_setup_complete(self) -> bool:
        """Check if Google credentials are configured."""
        return GOOGLE_CREDENTIALS_PATH.exists()
    
    def setup_credentials(self, client_id: str, client_secret: str, project_id: str):
        """Set up Google OAuth credentials."""
        credentials_data = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["http://localhost:8080"]
            },
            "project_id": project_id
        }
        
        GOOGLE_CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GOOGLE_CREDENTIALS_PATH, "w") as f:
            json.dump(credentials_data, f, indent=2)
        
        self._log_action("credentials_configured", {"project_id": project_id})
        return True
    
    def authenticate(self, services: List[str] = None) -> Dict[str, Any]:
        """Authenticate with Google OAuth."""
        if not self.is_setup_complete():
            return {"success": False, "error": "Google credentials not configured"}
        
        if services is None:
            services = ["drive", "gmail", "calendar", "sheets"]
        
        # Get required scopes
        scopes = []
        for service in services:
            if service in API_SCOPES:
                scopes.extend(API_SCOPES[service])
        
        scopes = list(set(scopes))
        
        try:
            from google_auth_oauthlib.flow import Flow
            from google.auth.transport.requests import Request
            
            # Load credentials
            with open(GOOGLE_CREDENTIALS_PATH, "r") as f:
                credentials_config = json.load(f)
            
            # Create OAuth flow
            flow = Flow.from_client_config(
                credentials_config,
                scopes=scopes,
                redirect_uri="http://localhost:8080"
            )
            
            # Start OAuth callback server
            auth_result = self._run_oauth_flow(flow)
            
            if auth_result["success"]:
                self.credentials = auth_result["credentials"]
                self.authenticated = True
                
                # Save credentials
                with open(GOOGLE_TOKEN_PATH, "wb") as f:
                    pickle.dump(self.credentials, f)
                
                # Enable services
                for service in services:
                    if service not in self.config["enabled_services"]:
                        self.config["enabled_services"].append(service)
                
                self._save_config()
                self._log_action("authenticated", {"services": services})
                
                return {"success": True, "services": services}
            else:
                return auth_result
                
        except ImportError as e:
            return {"success": False, "error": f"Missing Google libraries: {e}"}
        except Exception as e:
            self._log_action("auth_error", {"error": str(e)})
            return {"success": False, "error": str(e)}
    
    def _run_oauth_flow(self, flow) -> Dict[str, Any]:
        """Run OAuth flow with local callback server."""
        result = {"success": False, "credentials": None}
        
        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal result
                parsed = urlparse(self.path)
                
                if parsed.path == "/":
                    # Extract authorization code
                    params = parse_qs(parsed.query)
                    if "code" in params:
                        try:
                            # Exchange code for credentials
                            flow.fetch_token(code=params["code"][0])
                            result["success"] = True
                            result["credentials"] = flow.credentials
                            
                            self.send_response(200)
                            self.send_header("Content-Type", "text/html")
                            self.end_headers()
                            self.wfile.write(b"""
                                <html>
                                <body>
                                    <h2>Authentication Successful!</h2>
                                    <p>You can close this window and return to Jarvis.</p>
                                </body>
                                </html>
                            """)
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(f"Error: {str(e)}".encode())
                    else:
                        self.send_response(400)
                        self.end_headers()
                        self.wfile.write(b"Authorization code not found")
            
            def log_message(self, format, *args):
                pass  # Suppress logging
        
        # Start local server
        server = HTTPServer(("localhost", 8080), OAuthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        # Open browser for authentication
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        
        webbrowser.open(auth_url)
        
        # Wait for authentication
        thread.join(timeout=60)
        server.shutdown()
        
        return result
    
    def load_existing_credentials(self) -> bool:
        """Load existing Google credentials."""
        if not GOOGLE_TOKEN_PATH.exists():
            return False
        
        try:
            from google.auth.transport.requests import Request
            
            with open(GOOGLE_TOKEN_PATH, "rb") as f:
                self.credentials = pickle.load(f)
            
            # Refresh if expired
            if self.credentials.expired and self.credentials.refresh_token:
                self.credentials.refresh(Request())
                with open(GOOGLE_TOKEN_PATH, "wb") as f:
                    pickle.dump(self.credentials, f)
            
            self.authenticated = True
            return True
            
        except Exception as e:
            self._log_action("load_credentials_error", {"error": str(e)})
            return False
    
    def get_service(self, service_name: str):
        """Get authenticated Google service client."""
        if not self.authenticated:
            if not self.load_existing_credentials():
                return None
        
        if service_name in self.services:
            return self.services[service_name]
        
        try:
            from googleapiclient.discovery import build
            
            service_map = {
                "drive": "drive",
                "gmail": "gmail",
                "calendar": "calendar",
                "sheets": "sheets",
                "docs": "docs"
            }
            
            if service_name not in service_map:
                return None
            
            version_map = {
                "drive": "v3",
                "gmail": "v1",
                "calendar": "v3",
                "sheets": "v4",
                "docs": "v1"
            }
            
            service = build(
                service_map[service_name],
                version_map[service_name],
                credentials=self.credentials
            )
            
            self.services[service_name] = service
            return service
            
        except Exception as e:
            self._log_action("service_error", {"service": service_name, "error": str(e)})
            return None
    
    def discover_apis(self) -> List[Dict[str, Any]]:
        """Discover available Google APIs."""
        try:
            from googleapiclient.discovery import build
            
            # Build API discovery service
            discovery = build("discovery", "v1", credentials=self.credentials)
            
            # List APIs
            result = discovery.apis().list(
                preferred=True,
                fields="items(name,title,description,version,discoveryRestUrl)"
            ).execute()
            
            apis = []
            for api in result.get("items", []):
                apis.append({
                    "name": api["name"],
                    "title": api["title"],
                    "description": api.get("description", ""),
                    "version": api["version"],
                    "url": api.get("discoveryRestUrl", "")
                })
            
            self._log_action("apis_discovered", {"count": len(apis)})
            return apis
            
        except Exception as e:
            self._log_action("discovery_error", {"error": str(e)})
            return []
    
    def enable_api(self, api_name: str, project_id: str = None) -> bool:
        """Enable a Google API for the project."""
        try:
            from googleapiclient.discovery import build
            
            if not project_id:
                project_id = self.config.get("project_id")
            
            if not project_id:
                return False
            
            # Build Service Usage API
            service_usage = build("serviceusage", "v1", credentials=self.credentials)
            
            # Enable the API
            operation = service_usage.services().enable(
                name=f"projects/{project_id}/services/{api_name}.googleapis.com"
            ).execute()
            
            self._log_action("api_enabled", {"api": api_name})
            return True
            
        except Exception as e:
            self._log_action("enable_api_error", {"api": api_name, "error": str(e)})
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get Google integration status."""
        return {
            "authenticated": self.authenticated,
            "credentials_exist": self.is_setup_complete(),
            "enabled_services": self.config["enabled_services"],
            "last_sync": self.config["last_sync"],
            "services_count": len(self.services)
        }


# Global integration instance
_integration: Optional[GoogleIntegration] = None


def get_google_integration() -> GoogleIntegration:
    """Get the global Google integration instance."""
    global _integration
    if not _integration:
        _integration = GoogleIntegration()
    return _integration
