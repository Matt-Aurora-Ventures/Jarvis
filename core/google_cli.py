"""
Google CLI Integration for Jarvis.
Provides access to Google Cloud CLI tools and services.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, research_engine

ROOT = Path(__file__).resolve().parents[1]
GOOGLE_CLI_PATH = ROOT / "data" / "google_cli"
GOOGLE_CLI_LOG_PATH = ROOT / "data" / "google_cli.log"


class GoogleCLI:
    """Manages Google CLI interactions and capabilities."""
    
    def __init__(self):
        self.cli_db = GOOGLE_CLI_PATH / "cli_data.json"
        self._ensure_directories()
        self._load_cli_data()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        GOOGLE_CLI_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_cli_data(self):
        """Load CLI data and capabilities."""
        if self.cli_db.exists():
            with open(self.cli_db, "r") as f:
                self.cli_data = json.load(f)
        else:
            self.cli_data = {
                "available_commands": [],
                "installed_tools": [],
                "project_info": {},
                "services_enabled": [],
                "usage_history": []
            }
    
    def _save_cli_data(self):
        """Save CLI data."""
        with open(self.cli_db, "w") as f:
            json.dump(self.cli_data, f, indent=2)
    
    def _log_cli_action(self, action: str, details: Dict[str, Any]):
        """Log CLI activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(GOOGLE_CLI_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def check_gcloud_installation(self) -> Dict[str, Any]:
        """Check if Google Cloud CLI is installed and configured."""
        try:
            # Check if gcloud is available
            result = subprocess.run(
                ["gcloud", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                
                # Check if authenticated
                auth_result = subprocess.run(
                    ["gcloud", "auth", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                is_authenticated = "ACTIVE" in auth_result.stdout
                
                # Get current project
                project_result = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                current_project = project_result.stdout.strip() if project_result.returncode == 0 else None
                
                status = {
                    "installed": True,
                    "version": version_info,
                    "authenticated": is_authenticated,
                    "current_project": current_project,
                    "timestamp": datetime.now().isoformat()
                }
                
                self.cli_data["project_info"] = status
                self._save_cli_data()
                
                return status
            else:
                return {"installed": False, "error": result.stderr}
                
        except subprocess.TimeoutExpired:
            return {"installed": False, "error": "Timeout checking gcloud"}
        except FileNotFoundError:
            return {"installed": False, "error": "gcloud not found"}
        except Exception as e:
            return {"installed": False, "error": str(e)}
    
    def install_gcloud(self) -> Dict[str, Any]:
        """Attempt to install Google Cloud CLI."""
        try:
            # Try to install using curl (Linux/Mac)
            install_script = """
            curl https://sdk.cloud.google.com | bash
            exec -l $SHELL
            """
            
            result = subprocess.run(
                ["bash", "-c", install_script],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )
            
            if result.returncode == 0:
                self._log_cli_action("gcloud_installed", {"success": True})
                return {"success": True, "message": "gcloud installed successfully"}
            else:
                self._log_cli_action("gcloud_install_failed", {
                    "error": result.stderr
                })
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            self._log_cli_action("gcloud_install_error", {"error": str(e)})
            return {"success": False, "error": str(e)}
    
    def discover_available_services(self) -> List[Dict[str, Any]]:
        """Discover available Google Cloud services."""
        services = []
        
        # Common Google Cloud services for automation
        common_services = [
            {"name": "compute", "description": "Compute Engine for virtual machines"},
            {"name": "storage", "description": "Cloud Storage for data storage"},
            {"name": "functions", "description": "Cloud Functions for serverless code"},
            {"name": "run", "description": "Cloud Run for containerized apps"},
            {"name": "pubsub", "description": "Pub/Sub for messaging"},
            {"name": "bigquery", "description": "BigQuery for data analytics"},
            {"name": "aiplatform", "description": "AI Platform for ML models"},
            {"name": "translate", "description": "Translation API"},
            {"name": "vision", "description": "Vision API for image analysis"},
            {"name": "speech", "description": "Speech-to-Text API"}
        ]
        
        # Check which services are available
        for service in common_services:
            try:
                result = subprocess.run(
                    ["gcloud", "services", "list", "--enabled", f"--filter=service.name:{service['name']}*"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and service['name'] in result.stdout:
                    service["enabled"] = True
                    services.append(service)
                else:
                    service["enabled"] = False
                    services.append(service)
                    
            except Exception as e:
                service["enabled"] = False
                services.append(service)
        
        self.cli_data["services_enabled"] = services
        self._save_cli_data()
        
        return services
    
    def enable_service(self, service_name: str) -> Dict[str, Any]:
        """Enable a Google Cloud service."""
        try:
            result = subprocess.run(
                ["gcloud", "services", "enable", f"{service_name}.googleapis.com"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self._log_cli_action("service_enabled", {"service": service_name})
                return {"success": True, "message": f"Service {service_name} enabled"}
            else:
                self._log_cli_action("service_enable_failed", {
                    "service": service_name,
                    "error": result.stderr
                })
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            self._log_cli_action("service_enable_error", {
                "service": service_name,
                "error": str(e)
            })
            return {"success": False, "error": str(e)}
    
    def create_function(self, function_name: str, code: str, runtime: str = "python39") -> Dict[str, Any]:
        """Create a Cloud Function."""
        try:
            # Create function directory
            function_dir = GOOGLE_CLI_PATH / "functions" / function_name
            function_dir.mkdir(parents=True, exist_ok=True)
            
            # Write main.py
            main_py = function_dir / "main.py"
            with open(main_py, "w") as f:
                f.write(code)
            
            # Write requirements.txt
            requirements = function_dir / "requirements.txt"
            with open(requirements, "w") as f:
                f.write("functions-framework\n")
            
            # Deploy function
            deploy_cmd = [
                "gcloud", "functions", "deploy", function_name,
                "--runtime", runtime,
                "--trigger-http",
                "--allow-unauthenticated",
                "--source", str(function_dir)
            ]
            
            result = subprocess.run(
                deploy_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self._log_cli_action("function_created", {
                    "function": function_name,
                    "runtime": runtime
                })
                return {"success": True, "message": f"Function {function_name} deployed"}
            else:
                self._log_cli_action("function_create_failed", {
                    "function": function_name,
                    "error": result.stderr
                })
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            self._log_cli_action("function_create_error", {
                "function": function_name,
                "error": str(e)
            })
            return {"success": False, "error": str(e)}
    
    def create_vm_instance(self, instance_name: str, zone: str = "us-central1-a") -> Dict[str, Any]:
        """Create a VM instance."""
        try:
            create_cmd = [
                "gcloud", "compute", "instances", "create", instance_name,
                "--zone", zone,
                "--machine-type", "e2-micro",
                "--image-family", "debian-11",
                "--image-project", "debian-cloud",
                "--boot-disk-size", "10GB"
            ]
            
            result = subprocess.run(
                create_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self._log_cli_action("vm_created", {
                    "instance": instance_name,
                    "zone": zone
                })
                return {"success": True, "message": f"VM {instance_name} created"}
            else:
                self._log_cli_action("vm_create_failed", {
                    "instance": instance_name,
                    "error": result.stderr
                })
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            self._log_cli_action("vm_create_error", {
                "instance": instance_name,
                "error": str(e)
            })
            return {"success": False, "error": str(e)}
    
    def list_resources(self, resource_type: str) -> List[Dict[str, Any]]:
        """List Google Cloud resources."""
        resources = []
        
        try:
            if resource_type == "instances":
                result = subprocess.run(
                    ["gcloud", "compute", "instances", "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            elif resource_type == "functions":
                result = subprocess.run(
                    ["gcloud", "functions", "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            elif resource_type == "buckets":
                result = subprocess.run(
                    ["gsutil", "ls", "-"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
            else:
                return resources
            
            if result.returncode == 0:
                if resource_type in ["instances", "functions"]:
                    resources = json.loads(result.stdout)
                else:
                    # Parse gsutil output
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            resources.append({"name": line.strip()})
            
            self._log_cli_action("resources_listed", {
                "type": resource_type,
                "count": len(resources)
            })
            
        except Exception as e:
            self._log_cli_action("resource_list_error", {
                "type": resource_type,
                "error": str(e)
            })
        
        return resources
    
    def run_bigquery_query(self, query: str) -> Dict[str, Any]:
        """Run a BigQuery query."""
        try:
            # Create temporary query file
            query_file = GOOGLE_CLI_PATH / "temp_query.sql"
            with open(query_file, "w") as f:
                f.write(query)
            
            result = subprocess.run(
                ["bq", "query", "--format=json", str(query_file)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # Clean up
            query_file.unlink(missing_ok=True)
            
            if result.returncode == 0:
                query_results = json.loads(result.stdout)
                self._log_cli_action("bigquery_executed", {
                    "rows": len(query_results.get("rows", []))
                })
                return {"success": True, "data": query_results}
            else:
                self._log_cli_action("bigquery_failed", {
                    "error": result.stderr
                })
                return {"success": False, "error": result.stderr}
                
        except Exception as e:
            self._log_cli_action("bigquery_error", {"error": str(e)})
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get Google CLI status and capabilities."""
        gcloud_status = self.check_gcloud_installation()
        services = self.discover_available_services()
        
        return {
            "gcloud": gcloud_status,
            "services": services,
            "enabled_services": [s for s in services if s.get("enabled", False)],
            "total_services": len(services)
        }


# Global Google CLI instance
_google_cli: Optional[GoogleCLI] = None


def get_google_cli() -> GoogleCLI:
    """Get the global Google CLI instance."""
    global _google_cli
    if not _google_cli:
        _google_cli = GoogleCLI()
    return _google_cli
