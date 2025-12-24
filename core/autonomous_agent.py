"""
Advanced Autonomous Agent System for Jarvis.
Integrates latest autonomous agent capabilities and frameworks.
"""

import json
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, browser_automation, ability_acquisition, storage_utils, self_healing

ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "data" / "autonomous_agents"
AGENT_LOG_PATH = ROOT / "data" / "autonomous_agents.log"


class AutonomousAgent:
    """Advanced autonomous agent with multi-step reasoning and tool use."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(AGENT_PATH)
        self.md_storage = storage_utils.get_md_storage(AGENT_PATH)
        self.healing = self_healing.get_self_healing()
        
        # Latest autonomous agent capabilities
        self.capabilities = {
            "multi_step_planning": True,
            "tool_selection": True,
            "code_execution": True,
            "web_automation": True,
            "memory_integration": True,
            "self_improvement": True,
            "error_recovery": True,
            "goal_decomposition": True,
            "self_healing": True
        }
        
        # Agent tools
        self.tools = {
            "browser": self._browser_tool,
            "terminal": self._terminal_tool,
            "file_ops": self._file_ops_tool,
            "web_search": self._web_search_tool,
            "code_analysis": self._code_analysis_tool,
            "ability_acquisition": self._ability_acquisition_tool
        }
        
    def _log_agent(self, action: str, details: Dict[str, Any]):
        """Log agent activity."""
        self.storage.log_event("agent_log", action, details)
    
    def execute_autonomous_task(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute an autonomous task with multi-step planning."""
        task_id = f"task_{int(time.time())}"
        
        task_data = {
            "task_id": task_id,
            "goal": goal,
            "context": context or {},
            "status": "planning",
            "steps": [],
            "results": [],
            "start_time": datetime.now().isoformat()
        }
        
        self._log_agent("task_started", {"task_id": task_id, "goal": goal})
        
        try:
            # Step 1: Goal decomposition
            plan = self._decompose_goal(goal, context)
            task_data["steps"] = plan["steps"]
            task_data["status"] = "executing"
            
            # Step 2: Execute plan
            results = []
            for i, step in enumerate(plan["steps"]):
                self._log_agent("step_started", {
                    "task_id": task_id,
                    "step": i,
                    "description": step["description"]
                })
                
                step_result = self._execute_step(step, context)
                results.append(step_result)
                
                self._log_agent("step_completed", {
                    "task_id": task_id,
                    "step": i,
                    "result": step_result["status"]
                })
                
                # Check if we need to adjust plan based on results
                if step_result.get("status") in ["failed", "healed_failed"] and step.get("critical", False):
                    task_data["status"] = "failed"
                    break
                elif step_result.get("status") == "healed_success":
                    self._log_agent("healing_successful", {
                        "task_id": task_id,
                        "step": i,
                        "healing_attempts": step_result.get("healing_attempts", 0)
                    })
            
            task_data["results"] = results
            task_data["status"] = "completed"
            task_data["end_time"] = datetime.now().isoformat()
            
            # Step 3: Synthesize results
            final_result = self._synthesize_results(goal, results)
            task_data["final_result"] = final_result
            
            # Update agent learning
            self._update_agent_learning(task_data)
            
        except Exception as e:
            task_data["status"] = "error"
            task_data["error"] = str(e)
            self._log_agent("task_error", {"task_id": task_id, "error": str(e)})
        
        # Save task data
        self.storage.save_txt(f"task_{task_id}", task_data)
        
        return task_data
    
    def _decompose_goal(self, goal: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Decompose goal into executable steps."""
        decomposition_prompt = f"""Decompose this autonomous goal into specific, executable steps:

Goal: {goal}
Context: {json.dumps(context or {}, indent=2)}

Available tools:
- browser: Web automation and data extraction
- terminal: Execute system commands
- file_ops: File operations and analysis
- web_search: Search for information
- code_analysis: Analyze and generate code
- ability_acquisition: Find and integrate new abilities

Return a JSON plan with steps. Each step should have:
1. description (clear action)
2. tool (which tool to use)
3. parameters (tool-specific parameters)
4. critical (if this step must succeed)
5. expected_output (what this step should produce)

Example format:
{{
  "steps": [
    {{
      "description": "Search for information",
      "tool": "web_search",
      "parameters": {{"query": "latest AI models"}},
      "critical": false,
      "expected_output": "search results"
    }}
  ]
}}"""
        
        try:
            response = providers.generate_text(decomposition_prompt, max_output_tokens=800)
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                return plan
        except Exception as e:
            pass
        
        # Fallback plan
        return {
            "steps": [
                {
                    "description": "Analyze goal requirements",
                    "tool": "web_search",
                    "parameters": {"query": goal},
                    "critical": True,
                    "expected_output": "analysis"
                }
            ]
        }
    
    def _execute_step(self, step: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a single step with self-healing on failure."""
        tool_name = step.get("tool", "web_search")
        parameters = step.get("parameters", {})
        
        if tool_name in self.tools:
            try:
                result = self.tools[tool_name](parameters, context)
                return {
                    "status": "success",
                    "result": result,
                    "tool": tool_name,
                    "parameters": parameters
                }
            except Exception as e:
                error_msg = str(e)
                healing_context = {
                    "tool": tool_name,
                    "parameters": parameters,
                    "step_description": step.get("description", ""),
                    "command": parameters.get("command", ""),
                    "file_path": parameters.get("path", ""),
                    "url": parameters.get("url", "")
                }
                
                # Attempt self-healing
                self._log_agent("healing_started", {
                    "tool": tool_name,
                    "error": error_msg,
                    "context": healing_context
                })
                
                healing_result = self.healing.heal_failure(error_msg, healing_context)
                
                if healing_result["healed"]:
                    # Retry the original action after healing
                    try:
                        result = self.tools[tool_name](parameters, context)
                        return {
                            "status": "healed_success",
                            "result": result,
                            "tool": tool_name,
                            "parameters": parameters,
                            "healing_applied": healing_result["final_solution"],
                            "healing_attempts": len(healing_result["attempts"])
                        }
                    except Exception as retry_error:
                        return {
                            "status": "healed_failed",
                            "error": str(retry_error),
                            "original_error": error_msg,
                            "tool": tool_name,
                            "parameters": parameters,
                            "healing_result": healing_result
                        }
                else:
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "tool": tool_name,
                        "parameters": parameters,
                        "healing_attempted": True,
                        "healing_result": healing_result
                    }
        else:
            return {
                "status": "failed",
                "error": f"Unknown tool: {tool_name}",
                "tool": tool_name,
                "parameters": parameters
            }
    
    def _browser_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """Browser automation tool."""
        browser = browser_automation.get_browser_automation()
        
        if "url" in parameters:
            return browser.extract_data_from_page(parameters["url"])
        elif "action" in parameters:
            return browser.execute_browser_action(parameters["action"])
        else:
            return {"error": "No valid browser action specified"}
    
    def _terminal_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """Terminal execution tool."""
        command = parameters.get("command", "")
        if not command:
            return {"error": "No command specified"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out"}
        except Exception as e:
            return {"error": str(e)}
    
    def _file_ops_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """File operations tool."""
        operation = parameters.get("operation", "")
        file_path = parameters.get("path", "")
        
        if operation == "read" and file_path:
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                return {"content": content}
            except Exception as e:
                return {"error": str(e)}
        elif operation == "write" and file_path and "content" in parameters:
            try:
                with open(file_path, "w") as f:
                    f.write(parameters["content"])
                return {"status": "success"}
            except Exception as e:
                return {"error": str(e)}
        else:
            return {"error": "Invalid file operation"}
    
    def _web_search_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """Web search tool."""
        query = parameters.get("query", "")
        if not query:
            return {"error": "No search query specified"}
        
        try:
            # Use providers to search
            search_prompt = f"Search for: {query}. Provide top 5 results with URLs and brief descriptions."
            response = providers.generate_text(search_prompt, max_output_tokens=400)
            return {"results": response}
        except Exception as e:
            return {"error": str(e)}
    
    def _code_analysis_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """Code analysis tool."""
        code = parameters.get("code", "")
        task = parameters.get("task", "analyze")
        
        if not code:
            return {"error": "No code provided"}
        
        try:
            if task == "analyze":
                analysis_prompt = f"Analyze this code for quality, security, and improvements:\n\n{code}"
                response = providers.generate_text(analysis_prompt, max_output_tokens=400)
                return {"analysis": response}
            elif task == "improve":
                improve_prompt = f"Improve this code with better practices and optimizations:\n\n{code}"
                response = providers.generate_text(improve_prompt, max_output_tokens=600)
                return {"improved_code": response}
            else:
                return {"error": "Unknown code task"}
        except Exception as e:
            return {"error": str(e)}
    
    def _ability_acquisition_tool(self, parameters: Dict[str, Any], context: Optional[Dict[str, Any]]) -> Any:
        """Ability acquisition tool."""
        ability_type = parameters.get("type", "general")
        
        try:
            acq = ability_acquisition.get_ability_acquisition()
            
            if ability_type == "research":
                discoveries = acq.discover_open_source_models()
                return {"discoveries": discoveries}
            elif ability_type == "acquire":
                result = acq.run_acquisition_cycle()
                return {"acquisition_result": result}
            else:
                return {"error": "Unknown ability task"}
        except Exception as e:
            return {"error": str(e)}
    
    def _synthesize_results(self, goal: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize step results into final outcome."""
        synthesis_prompt = f"""Synthesize these step results into a comprehensive answer for the original goal:

Original Goal: {goal}

Step Results:
{json.dumps(results, indent=2)}

Provide:
1. Summary of what was accomplished
2. Key findings and insights
3. Recommendations or next steps
4. Any limitations or issues encountered"""
        
        try:
            response = providers.generate_text(synthesis_prompt, max_output_tokens=600)
            return {
                "synthesis": response,
                "goal": goal,
                "steps_completed": len(results),
                "success_rate": sum(1 for r in results if r.get("status") == "success") / len(results) if results else 0
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _update_agent_learning(self, task_data: Dict[str, Any]):
        """Update agent learning from task execution."""
        # Extract patterns from successful tasks
        if task_data.get("status") == "completed":
            # Learn from successful patterns
            pattern = {
                "goal_type": self._classify_goal(task_data["goal"]),
                "successful_steps": [step["description"] for step in task_data["steps"]],
                "tools_used": list(set([r.get("tool", "unknown") for r in task_data["results"] if r.get("status") == "success"])),
                "learned_at": datetime.now().isoformat()
            }
            self.storage.append_txt("learned_patterns", pattern)
    
    def _classify_goal(self, goal: str) -> str:
        """Classify the type of goal."""
        goal_lower = goal.lower()
        
        if any(word in goal_lower for word in ["research", "search", "find", "information"]):
            return "research"
        elif any(word in goal_lower for word in ["code", "program", "develop", "implement"]):
            return "development"
        elif any(word in goal_lower for word in ["analyze", "review", "examine"]):
            return "analysis"
        elif any(word in goal_lower for word in ["automate", "script", "tool"]):
            return "automation"
        else:
            return "general"
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status and capabilities including healing stats."""
        # Load learned patterns
        patterns = self.storage.load_txt("learned_patterns", "list") or []
        
        # Count recent tasks
        recent_tasks = self.storage.get_latest_entries("agent_log", 20)
        completed_tasks = len([t for t in recent_tasks if isinstance(t, dict) and t.get("details", {}).get("status") == "completed"])
        failed_tasks = len([t for t in recent_tasks if isinstance(t, dict) and t.get("details", {}).get("status") == "failed"])
        healed_tasks = len([t for t in recent_tasks if isinstance(t, dict) and "healing" in str(t.get("details", {})).lower()])
        
        # Get healing statistics
        healing_stats = self.healing.get_healing_stats()
        
        return {
            "capabilities": self.capabilities,
            "available_tools": list(self.tools.keys()),
            "tasks_completed": completed_tasks,
            "tasks_failed": failed_tasks,
            "tasks_healed": healed_tasks,
            "learned_patterns": len(patterns),
            "healing_stats": healing_stats,
            "current_state": "active"
        }


# Global agent instance
_agent: Optional[AutonomousAgent] = None


def get_autonomous_agent() -> AutonomousAgent:
    """Get the global autonomous agent instance."""
    global _agent
    if not _agent:
        _agent = AutonomousAgent()
    return _agent
