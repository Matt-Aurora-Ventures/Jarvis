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

from core import config, conversation, passive, providers, proactive, secrets, state, autonomous_learner, autonomous_controller, research_engine, prompt_distiller, service_discovery, google_integration, google_manager, ability_acquisition

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
        elif path == "/api/autonomous":
            self._handle_autonomous()
        elif path == "/api/autonomous/enable":
            self._handle_enable_autonomous()
        elif path == "/api/autonomous/status":
            self._handle_autonomous_status()
        elif path == "/api/research":
            self._handle_research()
        elif path == "/api/research/topics":
            self._handle_research_topics()
        elif path == "/api/learning":
            self._handle_learning_report()
        elif path == "/api/services/discover":
            self._handle_discover_services()
        elif path == "/api/services/signup":
            self._handle_service_signup()
        elif path == "/api/services/integrate":
            self._handle_service_integrate()
        elif path == "/api/services/integrated":
            self._handle_integrated_services()
        elif path == "/api/google/setup":
            self._handle_google_setup()
        elif path == "/api/google/authenticate":
            self._handle_google_authenticate()
        elif path == "/api/google/status":
            self._handle_google_status()
        elif path == "/api/google/sync":
            self._handle_google_sync()
        elif path == "/api/abilities/discover":
            self._handle_discover_abilities()
        elif path == "/api/abilities/acquire":
            self._handle_acquire_abilities()
        elif path == "/api/abilities/status":
            self._handle_abilities_status()
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
            response = conversation.generate_response(message, "")
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

    def _handle_autonomous(self):
        """Get autonomous learner summary."""
        try:
            summary = autonomous_learner.get_autonomous_summary()
            self._send_json(summary)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_enable_autonomous(self):
        """Enable/disable autonomous improvements."""
        body = self._read_body()
        enable = body.get("enable", False)
        
        try:
            autonomous_learner.enable_autonomous_improvements(enable)
            self._send_json({"success": True, "enabled": enable})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_autonomous_status(self):
        """Get detailed autonomous controller status."""
        try:
            controller = autonomous_controller.get_autonomous_controller()
            status = controller.get_status()
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_research(self):
        """Handle research request."""
        body = self._read_body()
        topic = body.get("topic", "")
        
        if not topic:
            self._send_json({"error": "Topic required"}, 400)
            return
        
        try:
            engine = research_engine.get_research_engine()
            result = engine.research_topic(topic, max_pages=5)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_research_topics(self):
        """Get research topics and queue."""
        try:
            controller = autonomous_controller.get_autonomous_controller()
            topics = controller.schedule["priority_topics"]
            self._send_json({"topics": topics})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_learning_report(self):
        """Get comprehensive learning report."""
        try:
            distiller = prompt_distiller.get_prompt_distiller()
            report = distiller.get_learning_report()
            self._send_json(report)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_discover_services(self):
        """Get available services for integration."""
        try:
            discovery = service_discovery.get_service_discovery()
            services = discovery.discover_services()
            self._send_json({"services": services})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_service_signup(self):
        """Initiate signup for a service."""
        body = self._read_body()
        service_id = body.get("service_id", "")
        
        if not service_id:
            self._send_json({"error": "service_id required"}, 400)
            return
        
        try:
            discovery = service_discovery.get_service_discovery()
            result = discovery.initiate_signup(service_id)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_service_integrate(self):
        """Integrate a service with API key."""
        body = self._read_body()
        service_id = body.get("service_id", "")
        api_key = body.get("api_key", "")
        
        if not service_id or not api_key:
            self._send_json({"error": "service_id and api_key required"}, 400)
            return
        
        try:
            discovery = service_discovery.get_service_discovery()
            result = discovery.integrate_service(service_id, api_key)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_integrated_services(self):
        """Get list of integrated services."""
        try:
            discovery = service_discovery.get_service_discovery()
            services = discovery.get_integrated_services()
            self._send_json({"services": services})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_setup(self):
        """Set up Google credentials."""
        body = self._read_body()
        client_id = body.get("client_id", "")
        client_secret = body.get("client_secret", "")
        project_id = body.get("project_id", "")
        
        if not all([client_id, client_secret, project_id]):
            self._send_json({"error": "All fields required: client_id, client_secret, project_id"}, 400)
            return
        
        try:
            integration = google_integration.get_google_integration()
            success = integration.setup_credentials(client_id, client_secret, project_id)
            if success:
                self._send_json({"success": True, "message": "Google credentials configured"})
            else:
                self._send_json({"error": "Failed to configure credentials"}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_authenticate(self):
        """Authenticate with Google."""
        body = self._read_body()
        services = body.get("services", ["drive", "gmail", "calendar", "sheets"])
        
        try:
            integration = google_integration.get_google_integration()
            result = integration.authenticate(services)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_status(self):
        """Get Google integration status."""
        try:
            integration = google_integration.get_google_integration()
            status = integration.get_status()
            
            # Add sync status
            manager = google_manager.get_google_manager()
            status["last_sync_results"] = {}
            
            return self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_google_sync(self):
        """Trigger Google services sync."""
        body = self._read_body()
        service = body.get("service", "all")
        
        try:
            manager = google_manager.get_google_manager()
            results = {}
            
            if service in ["all", "drive"]:
                results["drive"] = manager.sync_drive()
            
            if service in ["all", "gmail"]:
                results["gmail"] = manager.scan_gmail()
            
            if service in ["all", "calendar"]:
                results["calendar"] = manager.sync_calendar()
            
            if service in ["all", "analyze"]:
                results["analysis"] = manager.analyze_drive_content()
            
            self._send_json({"success": True, "results": results})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_discover_abilities(self):
        """Discover new open-source abilities."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            discoveries = acquisition.discover_open_source_models()
            self._send_json({"success": True, "discoveries": discoveries})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_acquire_abilities(self):
        """Trigger ability acquisition cycle."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            result = acquisition.run_acquisition_cycle()
            self._send_json({"success": True, "result": result})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_abilities_status(self):
        """Get ability acquisition status."""
        try:
            acquisition = ability_acquisition.get_ability_acquisition()
            status = acquisition.get_status()
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

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
