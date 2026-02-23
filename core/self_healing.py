"""
Self-Healing System for Jarvis Autonomous Agent.
Automatically detects, diagnoses, and fixes failed actions using online research.
"""

import json
import re
import shlex
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, guardian, providers, storage_utils, safe_subprocess

ROOT = Path(__file__).resolve().parents[1]
HEALING_PATH = ROOT / "data" / "self_healing"


class SelfHealing:
    """Self-healing system for autonomous agent failures."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(HEALING_PATH)
        self.md_storage = storage_utils.get_md_storage(HEALING_PATH)
        
        # Common error patterns and solutions
        self.error_patterns = {
            "permission_denied": {
                "keywords": ["permission denied", "access denied", "sudo", "admin"],
                "research_query": "fix permission denied error {context}",
                "solution_types": ["chmod", "sudo", "ownership", "permissions"]
            },
            "module_not_found": {
                "keywords": ["module not found", "no module named", "import error"],
                "research_query": "install missing python module {module_name}",
                "solution_types": ["pip install", "conda install", "environment setup"]
            },
            "network_error": {
                "keywords": ["connection", "network", "timeout", "unreachable"],
                "research_query": "fix network connection error {context}",
                "solution_types": ["network config", "firewall", "dns", "proxy"]
            },
            "syntax_error": {
                "keywords": ["syntax error", "invalid syntax", "parse error"],
                "research_query": "fix syntax error in {language}",
                "solution_types": ["code correction", "syntax fix", "debugging"]
            },
            "dependency_error": {
                "keywords": ["dependency", "missing", "version conflict", "requirements"],
                "research_query": "resolve dependency conflict {context}",
                "solution_types": ["pip install", "version fix", "requirements.txt"]
            },
            "file_not_found": {
                "keywords": ["file not found", "no such file", "directory"],
                "research_query": "fix file not found error {context}",
                "solution_types": ["file creation", "path fix", "directory structure"]
            }
        }
    
    def analyze_failure(self, error: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a failure and determine healing strategy."""
        analysis = {
            "error_type": "unknown",
            "severity": "medium",
            "research_needed": True,
            "solution_attempts": [],
            "timestamp": datetime.now().isoformat(),
            "error_message": error,
            "context": context
        }
        
        # Classify error type
        error_lower = error.lower()
        for error_type, pattern in self.error_patterns.items():
            if any(keyword in error_lower for keyword in pattern["keywords"]):
                analysis["error_type"] = error_type
                analysis["research_query"] = pattern["research_query"].format(**context)
                analysis["solution_types"] = pattern["solution_types"]
                break
        
        # Determine severity
        if any(keyword in error_lower for keyword in ["critical", "fatal", "crash"]):
            analysis["severity"] = "high"
        elif any(keyword in error_lower for keyword in ["warning", "minor"]):
            analysis["severity"] = "low"
        
        # Log analysis
        self.storage.log_event("failure_analysis", "error_analyzed", analysis)
        
        return analysis
    
    def research_solution(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Research solutions online for the identified error."""
        solutions = []
        
        try:
            # Generate research query
            base_query = analysis.get("research_query", f"fix error: {analysis['error_message']}")
            context_info = analysis.get("context", {})
            
            # Add context to query
            if "tool" in context_info:
                base_query += f" using {context_info['tool']}"
            if "command" in context_info:
                base_query += f" for command '{context_info['command']}'"
            
            # Research online
            research_prompt = f"""Research solutions for this error:

Error: {analysis['error_message']}
Type: {analysis['error_type']}
Context: {json.dumps(context_info, indent=2)}

Search for: {base_query}

Provide 3-5 specific solutions with:
1. Clear description of the solution
2. Exact commands or code to execute
3. Success probability (high/medium/low)
4. Risk level (low/medium/high)
5. Prerequisites needed

Format as JSON array of objects."""
            
            response = providers.generate_text(research_prompt, max_output_tokens=800)
            
            # Extract solutions from response
            solutions = self._extract_solutions(response)
            
        except Exception as e:
            # Fallback solutions based on error type
            solutions = self._get_fallback_solutions(analysis)
        
        # Log research results
        self.storage.log_event("solution_research", "solutions_found", {
            "error_type": analysis["error_type"],
            "solutions_count": len(solutions),
            "solutions": solutions
        })
        
        return solutions
    
    def _extract_solutions(self, response: str) -> List[Dict[str, Any]]:
        """Extract solutions from AI response."""
        solutions = []
        
        try:
            # Try to extract JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                solutions = json.loads(json_match.group())
                return solutions
        except Exception as e:
            pass
        
        # Fallback: parse text response
        lines = response.split('\n')
        current_solution = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for solution patterns
            if line.startswith(('1.', '2.', '3.', '4.', '5.')):
                if current_solution:
                    solutions.append(current_solution)
                current_solution = {
                    "description": line[2:].strip(),
                    "commands": [],
                    "success_probability": "medium",
                    "risk_level": "low",
                    "prerequisites": []
                }
            elif line.startswith('-') or line.startswith('*'):
                if "command" in line.lower():
                    current_solution["commands"].append(line[1:].strip())
                elif "prerequisite" in line.lower():
                    current_solution["prerequisites"].append(line[1:].strip())
        
        if current_solution:
            solutions.append(current_solution)
        
        return solutions
    
    def _get_fallback_solutions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get fallback solutions when online research fails."""
        error_type = analysis["error_type"]
        context = analysis.get("context", {})
        
        fallback_solutions = {
            "permission_denied": [
                {
                    "description": "Try with sudo privileges",
                    "commands": [f"sudo {context.get('command', '')}"],
                    "success_probability": "high",
                    "risk_level": "medium",
                    "prerequisites": ["sudo access"]
                }
            ],
            "module_not_found": [
                {
                    "description": "Install missing module with pip",
                    "commands": ["pip install <module_name>"],
                    "success_probability": "high",
                    "risk_level": "low",
                    "prerequisites": ["pip", "internet"]
                }
            ],
            "network_error": [
                {
                    "description": "Check internet connectivity",
                    "commands": ["ping google.com", "curl -I https://google.com"],
                    "success_probability": "medium",
                    "risk_level": "low",
                    "prerequisites": []
                }
            ],
            "file_not_found": [
                {
                    "description": "Create missing file or directory",
                    "commands": ["mkdir -p <directory>", "touch <file>"],
                    "success_probability": "high",
                    "risk_level": "low",
                    "prerequisites": []
                }
            ]
        }
        
        return fallback_solutions.get(error_type, [{
            "description": "Retry the operation",
            "commands": [context.get('command', '')],
            "success_probability": "low",
            "risk_level": "low",
            "prerequisites": []
        }])
    
    def attempt_solution(self, solution: Dict[str, Any], original_context: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to apply a solution."""
        attempt = {
            "solution": solution,
            "start_time": datetime.now().isoformat(),
            "commands_executed": [],
            "results": [],
            "success": False,
            "error": None
        }
        
        try:
            for command in solution.get("commands", []):
                # Replace placeholders
                if original_context:
                    command = self._replace_placeholders(command, original_context)
                
                # Execute command — split into argv list to avoid shell injection
                try:
                    cmd_args = shlex.split(command)
                except ValueError:
                    attempt["error"] = f"Malformed command (shell parse failed): {command}"
                    break
                # Allowlist of safe command prefixes from LLM output
                _SAFE_PREFIXES = ("pip", "python", "python3", "pip3", "git", "npm", "node")
                if not cmd_args or cmd_args[0] not in _SAFE_PREFIXES:
                    attempt["error"] = f"Command blocked (not in allowlist): {command}"
                    break
                result = subprocess.run(
                    cmd_args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                attempt["commands_executed"].append(command)
                attempt["results"].append({
                    "command": command,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                
                # Check if command succeeded
                if result.returncode != 0:
                    attempt["error"] = f"Command failed: {command}\nError: {result.stderr}"
                    break
            
            # If all commands succeeded
            if not attempt["error"]:
                attempt["success"] = True
            
        except subprocess.TimeoutExpired:
            attempt["error"] = "Solution attempt timed out"
        except Exception as e:
            attempt["error"] = str(e)
        
        attempt["end_time"] = datetime.now().isoformat()
        
        # Log attempt
        self.storage.log_event("solution_attempt", "attempt_completed", attempt)
        
        return attempt
    
    def _replace_placeholders(self, command: str, context: Dict[str, Any]) -> str:
        """Replace placeholders in command with context values."""
        replacements = {
            "<module_name>": context.get("module_name", "unknown"),
            "<directory>": context.get("directory", ""),
            "<file>": context.get("file_path", ""),
            "<command>": context.get("command", ""),
        }
        
        for placeholder, value in replacements.items():
            command = command.replace(placeholder, str(value))
        
        return command
    
    def heal_failure(self, error: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Main healing process - analyze, research, and attempt solutions."""
        healing_session = {
            "error": error,
            "context": context,
            "start_time": datetime.now().isoformat(),
            "analysis": None,
            "solutions": [],
            "attempts": [],
            "healed": False,
            "final_solution": None
        }
        
        try:
            # Step 1: Analyze the failure
            analysis = self.analyze_failure(error, context)
            healing_session["analysis"] = analysis
            
            # Step 2: Research solutions
            solutions = self.research_solution(analysis)
            healing_session["solutions"] = solutions
            
            # Step 3: Attempt solutions (in order of success probability)
            sorted_solutions = sorted(
                solutions,
                key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("success_probability", "low"), 1),
                reverse=True
            )
            
            for solution in sorted_solutions:
                # Skip high-risk solutions initially
                if solution.get("risk_level") == "high" and healing_session["attempts"]:
                    continue
                
                attempt = self.attempt_solution(solution, context)
                healing_session["attempts"].append(attempt)
                
                if attempt["success"]:
                    healing_session["healed"] = True
                    healing_session["final_solution"] = solution
                    break
            
            # Step 4: Learn from the healing process
            self._learn_from_healing(healing_session)
            
        except Exception as e:
            healing_session["error"] = str(e)
        
        healing_session["end_time"] = datetime.now().isoformat()
        
        # Log healing session
        self.storage.save_txt(f"healing_session_{int(time.time())}", healing_session)
        
        return healing_session
    
    def _learn_from_healing(self, session: Dict[str, Any]):
        """Learn from healing sessions to improve future attempts."""
        if session["healed"] and session["final_solution"]:
            learning = {
                "error_type": session["analysis"]["error_type"],
                "error_pattern": session["error"][:100],  # First 100 chars
                "successful_solution": session["final_solution"],
                "context": session["context"],
                "learned_at": datetime.now().isoformat()
            }
            
            self.storage.append_txt("learned_solutions", learning)
    
    def get_healing_stats(self) -> Dict[str, Any]:
        """Get statistics about healing performance."""
        learned_solutions = self.storage.load_txt("learned_solutions", "list") or []
        recent_sessions = self.storage.get_latest_entries("healing_session", 10)
        
        healed_count = len([s for s in recent_sessions if s.get("details", {}).get("healed", False)])
        
        return {
            "learned_solutions": len(learned_solutions),
            "recent_sessions": len(recent_sessions),
            "success_rate": healed_count / len(recent_sessions) if recent_sessions else 0,
            "common_error_types": self._get_common_error_types()
        }
    
    def _get_common_error_types(self) -> Dict[str, int]:
        """Get statistics on common error types."""
        error_counts = {}
        recent_sessions = self.storage.get_latest_entries("healing_session", 50)
        
        for session in recent_sessions:
            error_type = session.get("details", {}).get("analysis", {}).get("error_type", "unknown")
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        return error_counts


# Global healing instance
_healing: Optional[SelfHealing] = None


def get_self_healing() -> SelfHealing:
    """Get the global self-healing instance."""
    global _healing
    if not _healing:
        _healing = SelfHealing()
    return _healing
