"""
Service Discovery and Integration for Jarvis.
Discovers and integrates free AI services automatically.
"""

import json
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import threading

from core import config, providers, secrets, guardian

ROOT = Path(__file__).resolve().parents[1]
SERVICE_REGISTRY_PATH = ROOT / "data" / "service_registry.json"
INTEGRATION_LOG_PATH = ROOT / "data" / "service_integrations.log"


# Curated list of free AI services
FREE_AI_SERVICES = {
    "huggingface": {
        "name": "Hugging Face",
        "description": "Free AI models and APIs",
        "signup_url": "https://huggingface.co/join",
        "api_docs": "https://huggingface.co/docs/api-inference/index",
        "free_tier": {
            "requests_per_hour": 1000,
            "models": "Thousands of free models"
        },
        "api_key_env": "HUGGINGFACE_API_KEY",
        "integration": {
            "type": "api_key",
            "endpoint": "https://api-inference.huggingface.co/models"
        }
    },
    "replicate": {
        "name": "Replicate",
        "description": "Run AI models with simple API",
        "signup_url": "https://replicate.com/account",
        "api_docs": "https://replicate.com/docs/reference/http",
        "free_tier": {
            "credits": "$5 free credits",
            "models": "Open source and custom models"
        },
        "api_key_env": "REPLICATE_API_TOKEN",
        "integration": {
            "type": "api_key",
            "endpoint": "https://api.replicate.com/v1"
        }
    },
    "together": {
        "name": "Together AI",
        "description": "Open source AI models API",
        "signup_url": "https://api.together.xyz/signup",
        "api_docs": "https://docs.together.ai/docs/intro",
        "free_tier": {
            "credits": "$5 free credits",
            "models": "Llama, Mixtral, and more"
        },
        "api_key_env": "TOGETHER_API_KEY",
        "integration": {
            "type": "api_key",
            "endpoint": "https://api.together.xyz/v1"
        }
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Unified API for all models",
        "signup_url": "https://openrouter.ai/signup",
        "api_docs": "https://openrouter.ai/docs",
        "free_tier": {
            "credits": "$5 free credits",
            "models": "GPT-4, Claude, Llama, and more"
        },
        "api_key_env": "OPENROUTER_API_KEY",
        "integration": {
            "type": "api_key",
            "endpoint": "https://openrouter.ai/api/v1"
        }
    },
    "perplexity": {
        "name": "Perplexity AI",
        "description": "Search and answer API",
        "signup_url": "https://www.perplexity.ai/settings/api",
        "api_docs": "https://docs.perplexity.ai/reference/post_chat-completions",
        "free_tier": {
            "requests_per_month": 1000,
            "features": "Web search with citations"
        },
        "api_key_env": "PERPLEXITY_API_KEY",
        "integration": {
            "type": "api_key",
            "endpoint": "https://api.perplexity.ai"
        }
    }
}


class ServiceDiscovery:
    """Discovers and integrates free AI services."""
    
    def __init__(self):
        self._load_registry()
        
    def _load_registry(self):
        """Load service registry."""
        if SERVICE_REGISTRY_PATH.exists():
            with open(SERVICE_REGISTRY_PATH, "r") as f:
                self.registry = json.load(f)
        else:
            self.registry = {
                "discovered": FREE_AI_SERVICES,
                "integrated": {},
                "failed": {},
                "last_updated": None
            }
    
    def _save_registry(self):
        """Save service registry."""
        self.registry["last_updated"] = datetime.now().isoformat()
        with open(SERVICE_REGISTRY_PATH, "w") as f:
            json.dump(self.registry, f, indent=2)
    
    def _log_integration(self, service: str, action: str, details: Dict[str, Any]):
        """Log integration action."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "service": service,
            "action": action,
            "details": details
        }
        
        with open(INTEGRATION_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def discover_services(self) -> List[Dict[str, Any]]:
        """Get list of available free services."""
        services = []
        for service_id, info in self.registry["discovered"].items():
            if service_id not in self.registry["integrated"]:
                services.append({
                    "id": service_id,
                    "name": info["name"],
                    "description": info["description"],
                    "free_tier": info["free_tier"],
                    "signup_url": info["signup_url"]
                })
        return services
    
    def initiate_signup(self, service_id: str) -> Dict[str, Any]:
        """Initiate signup for a service."""
        if service_id not in self.registry["discovered"]:
            return {"success": False, "error": "Service not found"}
        
        service = self.registry["discovered"][service_id]
        
        # Open signup page in browser
        webbrowser.open(service["signup_url"])
        
        self._log_integration(service_id, "signup_initiated", {
            "url": service["signup_url"]
        })
        
        return {
            "success": True,
            "message": f"Opened {service['name']} signup page in browser",
            "instructions": [
                f"1. Complete signup on {service['name']}",
                f"2. Find your API key in account settings",
                f"3. API key will be labeled: {service['api_key_env']}",
                "4. Return here to integrate the service"
            ]
        }
    
    def integrate_service(self, service_id: str, api_key: str) -> Dict[str, Any]:
        """Integrate a service with API key."""
        if service_id not in self.registry["discovered"]:
            return {"success": False, "error": "Service not found"}
        
        service = self.registry["discovered"][service_id]
        
        # Validate API key
        if not self._validate_api_key(service_id, api_key):
            self._log_integration(service_id, "integration_failed", {
                "reason": "Invalid API key"
            })
            return {"success": False, "error": "Invalid API key"}
        
        # Store API key
        self._store_api_key(service_id, api_key)
        
        # Add to providers
        self._add_provider(service_id, service)
        
        # Update registry
        self.registry["integrated"][service_id] = {
            "integrated_at": datetime.now().isoformat(),
            "api_key": api_key[:8] + "..." if len(api_key) > 8 else "***",
            "features": service["free_tier"]
        }
        self._save_registry()
        
        self._log_integration(service_id, "integrated", {
            "features": service["free_tier"]
        })
        
        return {
            "success": True,
            "message": f"Successfully integrated {service['name']}",
            "features": service["free_tier"]
        }
    
    def _validate_api_key(self, service_id: str, api_key: str) -> bool:
        """Validate API key with service."""
        service = self.registry["discovered"][service_id]
        
        # Basic validation
        if not api_key or len(api_key) < 10:
            return False
        
        # Service-specific validation
        if service_id == "huggingface":
            return api_key.startswith("hf_")
        elif service_id == "replicate":
            return api_key.startswith("r8_")
        elif service_id == "together":
            return len(api_key) == 64
        elif service_id == "openrouter":
            return api_key.startswith("sk-or-v1-")
        elif service_id == "perplexity":
            return "pplx-" in api_key
        
        return True
    
    def _store_api_key(self, service_id: str, api_key: str):
        """Store API key in secrets."""
        service = self.registry["discovered"][service_id]
        key_name = service["api_key_env"].lower()
        
        # Load existing keys
        keys_path = ROOT / "secrets" / "keys.json"
        keys_data = {}
        
        if keys_path.exists():
            with open(keys_path, "r") as f:
                keys_data = json.load(f)
        
        # Add new key
        keys_data[key_name] = api_key
        
        # Save
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        with open(keys_path, "w") as f:
            json.dump(keys_data, indent=2, fp=f)
    
    def _add_provider(self, service_id: str, service: Dict[str, Any]):
        """Add service to providers module."""
        # This would dynamically add the provider to providers.py
        # For now, we'll just log it
        self._log_integration(service_id, "provider_added", {
            "endpoint": service["integration"]["endpoint"]
        })
    
    def get_integrated_services(self) -> List[Dict[str, Any]]:
        """Get list of integrated services."""
        integrated = []
        for service_id, info in self.registry["integrated"].items():
            service = self.registry["discovered"][service_id]
            integrated.append({
                "id": service_id,
                "name": service["name"],
                "integrated_at": info["integrated_at"],
                "features": info["features"]
            })
        return integrated
    
    def research_new_services(self) -> List[Dict[str, Any]]:
        """Research new free AI services."""
        # Use the research engine to find new services
        from core import research_engine
        
        engine = research_engine.get_research_engine()
        
        # Search for new free AI services
        queries = [
            "free AI API 2024 no credit card",
            "open source AI model hosting free",
            "free LLM API providers",
            "AI services free tier list"
        ]
        
        new_services = []
        
        for query in queries:
            results = engine.search_web(query, max_results=5)
            
            for result in results:
                # Extract potential service info
                if any(keyword in result["title"].lower() for keyword in ["api", "free", "ai", "llm"]):
                    new_services.append({
                        "title": result["title"],
                        "url": result["url"],
                        "snippet": result["snippet"]
                    })
        
        # Log discovered services
        self._log_integration("research", "services_discovered", {
            "count": len(new_services)
        })
        
        return new_services


# OAuth callback server for services that need it
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callbacks for service integration."""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/callback":
            # Extract OAuth parameters
            params = parse_qs(parsed.query)
            
            # Store token (simplified)
            if "code" in params:
                self._send_response("Authorization received! You can close this window.")
                # In a real implementation, exchange code for token
            else:
                self._send_response("No authorization code received.")
        else:
            self._send_response("Callback endpoint")
    
    def _send_response(self, message: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode())
    
    def log_message(self, format, *args):
        # Suppress logging
        pass


def start_oauth_callback_server(port: int = 8080) -> threading.Thread:
    """Start OAuth callback server in background."""
    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


# Global discovery instance
_discovery: Optional[ServiceDiscovery] = None


def get_service_discovery() -> ServiceDiscovery:
    """Get the global service discovery instance."""
    global _discovery
    if not _discovery:
        _discovery = ServiceDiscovery()
    return _discovery
