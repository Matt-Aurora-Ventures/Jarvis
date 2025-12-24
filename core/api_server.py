"""
API Server for Jarvis Frontend.
Provides REST endpoints for the Electron/React frontend.
"""

import json
import os
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from core import config, conversation, passive, providers, proactive, secrets, state

ROOT = Path(__file__).resolve().parents[1]
PORT = 8765


class JarvisAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Jarvis API."""

    def _send_json(self, data: Dict[str, Any], status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _read_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length:
            body = self.rfile.read(content_length)
            return json.loads(body.decode())
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/stats":
            self._handle_stats()
        elif path == "/api/settings/keys":
            self._handle_get_keys()
        elif path == "/api/suggestions":
            self._handle_suggestions()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/chat":
            self._handle_chat()
        elif path == "/api/research":
            self._handle_research()
        elif path == "/api/settings/keys":
            self._handle_save_key()
        elif path == "/api/voice/start":
            self._handle_voice_start()
        elif path == "/api/voice/stop":
            self._handle_voice_stop()
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_status(self):
        """Get system status."""
        current_state = state.read_state()
        self._send_json({
            "daemon": "running" if current_state.get("daemon_running") else "stopped",
            "voice": current_state.get("mic_status", "off"),
            "monitoring": "on" if current_state.get("passive_observation") else "off",
            "chat_active": current_state.get("chat_active", False),
        })

    def _handle_stats(self):
        """Get dashboard statistics."""
        try:
            activity = passive.summarize_activity(hours=24)
            suggestions = proactive.get_recent_suggestions(count=10)
            
            self._send_json({
                "activeTime": "8h 30m",  # TODO: Calculate from activity logs
                "tasksCompleted": 12,
                "suggestionsGiven": len(suggestions),
                "focusScore": 85,
            })
        except Exception as e:
            self._send_json({
                "activeTime": "0h 0m",
                "tasksCompleted": 0,
                "suggestionsGiven": 0,
                "focusScore": 0,
            })

    def _handle_chat(self):
        """Handle chat message."""
        body = self._read_body()
        message = body.get("message", "")
        
        if not message:
            self._send_json({"error": "No message provided"}, 400)
            return

        try:
            response = conversation.generate_response(message)
            self._send_json({"response": response})
        except Exception as e:
            self._send_json({"response": f"Error: {str(e)}"}, 500)

    def _handle_research(self):
        """Handle research request."""
        body = self._read_body()
        topic = body.get("topic", "")
        depth = body.get("depth", "medium")
        
        if not topic:
            self._send_json({"error": "No topic provided"}, 400)
            return

        try:
            results = proactive.research_topic(topic, depth)
            self._send_json(results)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_get_keys(self):
        """Get masked API keys."""
        keys = {}
        providers_list = ["gemini", "groq", "anthropic", "openai", "trello", "github"]
        
        for provider in providers_list:
            key = ""
            if provider == "gemini":
                key = secrets.get_gemini_key()
            elif provider == "groq":
                key = secrets.get_groq_key()
            elif provider == "anthropic":
                key = secrets.get_anthropic_key()
            elif provider == "openai":
                key = secrets.get_openai_key()
            
            # Mask the key for display
            if key:
                keys[provider] = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
            else:
                keys[provider] = ""
        
        self._send_json(keys)

    def _handle_save_key(self):
        """Save an API key."""
        body = self._read_body()
        provider = body.get("provider", "")
        key = body.get("key", "")
        
        if not provider or not key:
            self._send_json({"error": "Provider and key required"}, 400)
            return

        try:
            keys_path = ROOT / "secrets" / "keys.json"
            keys_data = {}
            
            if keys_path.exists():
                with open(keys_path, "r") as f:
                    keys_data = json.load(f)
            
            # Map provider to key name
            key_names = {
                "gemini": "google_api_key",
                "groq": "groq_api_key",
                "anthropic": "anthropic_api_key",
                "openai": "openai_api_key",
                "trello": "trello_api_key",
                "github": "github_token",
            }
            
            if provider in key_names:
                keys_data[key_names[provider]] = key
                
                keys_path.parent.mkdir(parents=True, exist_ok=True)
                with open(keys_path, "w") as f:
                    json.dump(keys_data, indent=2, fp=f)
                
                self._send_json({"success": True})
            else:
                self._send_json({"error": "Unknown provider"}, 400)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_suggestions(self):
        """Get recent suggestions."""
        try:
            suggestions = proactive.get_recent_suggestions(count=10)
            self._send_json({"suggestions": suggestions})
        except Exception as e:
            self._send_json({"suggestions": []})

    def _handle_voice_start(self):
        """Start voice listening."""
        state.update_state(mic_status="listening")
        self._send_json({"success": True})

    def _handle_voice_stop(self):
        """Stop voice listening."""
        state.update_state(mic_status="off")
        self._send_json({"success": True})

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def run_server(port: int = PORT):
    """Run the API server."""
    server = HTTPServer(("0.0.0.0", port), JarvisAPIHandler)
    print(f"Jarvis API server running on http://localhost:{port}")
    server.serve_forever()


def start_server_thread(port: int = PORT) -> threading.Thread:
    """Start the API server in a background thread."""
    thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    run_server()
