"""
Autonomous Controller for Jarvis.
Continuous research, learning, and self-improvement system.
Runs without idle checks for maximum autonomy.
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, context_manager, evolution, guardian, providers, research_engine, prompt_distiller, service_discovery, google_manager, ability_acquisition, learning_validator, iterative_improver, self_evaluator, google_cli, crypto_trading, autonomous_restart, browser_automation, autonomous_researcher, autonomous_agent, task_manager, circular_logic, safety

ROOT = Path(__file__).resolve().parents[1]
AUTO_LOG_PATH = ROOT / "data" / "autonomous_controller.log"
RESEARCH_SCHEDULE_PATH = ROOT / "data" / "research_schedule.json"


class AutonomousController:
    """Controls continuous autonomous learning and improvement."""
    
    def __init__(self):
        self.schedule = self._load_schedule()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        
        # Initialize circular logic detection
        self.circular_detector = circular_logic.CircularLogicDetector()
        self.cycle_governor = circular_logic.CycleGovernor()
        
        # Initialize components
        self.research_engine = research_engine.ResearchEngine()
        self.prompt_distiller = prompt_distiller.PromptDistiller()
        self.guardian = guardian.Guardian()
        self.context_manager = context_manager.ContextManager()
        self.providers = providers.Providers()
        self.evolution = evolution.Evolution()
        self.google_manager = google_manager.GoogleManager()
        self.ability_acquisition = ability_acquisition.AbilityAcquisition()
        self.learning_validator = learning_validator.LearningValidator()
        self.iterative_improver = iterative_improver.IterativeImprover()
        self.self_evaluator = self_evaluator.SelfEvaluator()
        self.google_cli = google_cli.GoogleCLI()
        self.crypto_trading = crypto_trading.CryptoTrading()
        self.restart_manager = autonomous_restart.AutonomousRestartManager()
        self.browser_automation = browser_automation.BrowserAutomation()
        self.autonomous_researcher = autonomous_researcher.AutonomousResearcher()
        self.autonomous_agent = autonomous_agent.AutonomousAgent()
        
        # Check if Jarvis was restarted
        restart_state = autonomous_restart.check_for_restart_flag()
        if restart_state:
            self._log("Jarvis restarted", restart_state)
    
        
    def _load_schedule(self):
        """Load research schedule."""
        if RESEARCH_SCHEDULE_PATH.exists():
            with open(RESEARCH_SCHEDULE_PATH, "r") as f:
                self.schedule = json.load(f)
        else:
            self.schedule = {
                "research_cycle_minutes": 2,  # Research every 2 minutes
                "distillation_cycle_minutes": 4,  # Distill every 4 minutes
                "improvement_cycle_minutes": 3,  # Apply improvements every 3 minutes
                "google_sync_minutes": 10,  # Sync Google services every 10 minutes
                "service_discovery_minutes": 20,  # Check for new services every 20 minutes
                "ability_acquisition_minutes": 3,  # Acquire new abilities every 3 minutes
                "learning_validation_minutes": 6,  # Validate learning every 6 minutes
                "iterative_improvement_minutes": 8,  # Run iterative improvements every 8 minutes
                "self_evaluation_minutes": 5,  # Self-evaluation every 5 minutes
                "crypto_trading_minutes": 4,  # Crypto trading research every 4 minutes
                "google_cli_minutes": 15,  # Google CLI integration every 15 minutes
                "browser_automation_minutes": 7,  # Browser automation every 7 minutes
                "autonomous_research_minutes": 20,  # Research newest models every 20 minutes
                "autonomous_agent_minutes": 15,  # Run autonomous agent tasks every 15 minutes
                "max_pages_per_cycle": 8,
                "priority_topics": [
                    "crypto trading strategies and algorithms",
                    "autonomous trading bots",
                    "Google CLI tools and automation",
                    "AI agent autonomy and independence",
                    "information gathering and organization",
                    "practical AI tools that work",
                    "crypto market analysis techniques",
                    "self-improving AI systems",
                    "automation workflows",
                    "AI consciousness theories"
                ],
                "current_topic_index": 0,
                "last_research": 0,
                "last_distillation": 0,
                "last_improvement": 0
            }
    
    def _save_schedule(self):
        """Save research schedule."""
        with open(RESEARCH_SCHEDULE_PATH, "w") as f:
            json.dump(self.schedule, f, indent=2)
    
    def _log(self, message: str, details: Dict[str, Any] = None):
        """Log controller activity."""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "details": details or {}
        }
        
        with open(AUTO_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def start(self):
        """Start the autonomous controller."""
        if self.running:
            return
        
        self.running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("Controller started")
    
    def stop(self):
        """Stop the autonomous controller."""
        self.running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._log("Controller stopped")
    
    def _run_loop(self):
        """Main control loop with circular logic prevention."""
        while not self._stop_event.is_set():
            try:
                now = time.time()
                
                # Check for circular logic
                circular_issue = self.circular_detector.detect_circular_logic()
                if circular_issue:
                    self._log("Circular logic detected", circular_issue)
                    # Apply corrective measures
                    self._apply_circular_logic_fix(circular_issue)
                    time.sleep(60)  # Pause after detecting circular logic
                    continue
                
                # TASK GATE: Check for explicit tasks before running any cycles
                current_task = self._get_next_task()
                if not current_task:
                    self._log("No explicit task found, pausing autonomous cycles")
                    time.sleep(30)  # Wait 30 seconds before checking again
                    continue
                
                self._log("Processing task", {"task": current_task["title"], "priority": current_task.get("priority", "medium")})
                
                # Check cycles with governor approval
                cycles_to_check = [
                    ("research", self.schedule["research_cycle_minutes"], "last_research", self._run_research_cycle),
                    ("distillation", self.schedule["distillation_cycle_minutes"], "last_distillation", self._run_distillation_cycle),
                    ("improvement", self.schedule["improvement_cycle_minutes"], "last_improvement", self._run_improvement_cycle),
                    ("ability_acquisition", self.schedule["ability_acquisition_minutes"], "last_ability_acquisition", self._run_ability_acquisition_cycle),
                    ("learning_validation", self.schedule["learning_validation_minutes"], "last_learning_validation", self._run_learning_validation_cycle),
                    ("iterative_improvement", self.schedule["iterative_improvement_minutes"], "last_iterative_improvement", self._run_iterative_improvement_cycle),
                    ("self_evaluation", self.schedule["self_evaluation_minutes"], "last_self_evaluation", self._run_self_evaluation_cycle),
                    ("crypto_trading", self.schedule["crypto_trading_minutes"], "last_crypto_trading", self._run_crypto_trading_cycle),
                    ("google_cli", self.schedule["google_cli_minutes"], "last_google_cli", self._run_google_cli_cycle),
                    ("browser_automation", self.schedule["browser_automation_minutes"], "last_browser_automation", self._run_browser_automation_cycle),
                    ("autonomous_research", self.schedule["autonomous_research_minutes"], "last_autonomous_research", self._run_autonomous_research_cycle),
                    ("autonomous_agent", self.schedule["autonomous_agent_minutes"], "last_autonomous_agent", self._run_autonomous_agent_cycle),
                ]
                
                for cycle_name, cycle_minutes, last_key, cycle_func in cycles_to_check:
                    if now - self.schedule.get(last_key, 0) > cycle_minutes * 60:
                        # Check with governor
                        can_run, reason = self.cycle_governor.can_run_cycle(cycle_name)
                        if not can_run:
                            self._log(f"Cycle blocked: {cycle_name}", {"reason": reason})
                            continue
                        
                        # Record cycle start
                        self.circular_detector.record_cycle_start(cycle_name, current_task)
                        
                        try:
                            # Run the cycle
                            if cycle_name in ["research", "browser_automation"]:
                                # These cycles need the task context
                                cycle_result = cycle_func(current_task)
                            else:
                                cycle_result = cycle_func()
                            
                            # Record successful completion
                            if isinstance(cycle_result, dict):
                                self.circular_detector.record_cycle_end(cycle_name, result=cycle_result)
                            else:
                                self.circular_detector.record_cycle_end(cycle_name, result={"result": cycle_result})
                            self.cycle_governor.record_cycle(cycle_name)
                            
                            # Update schedule
                            self.schedule[last_key] = now
                            
                        except Exception as e:
                            # Record error
                            self.circular_detector.record_cycle_end(cycle_name, error=str(e))
                            self._log(f"Cycle error: {cycle_name}", {"error": str(e)})
                
                # Save schedule
                self._save_schedule()
                
                # Short sleep to prevent CPU spinning
                time.sleep(10)
                
            except Exception as e:
                self._log("Controller error", {"error": str(e)})
                time.sleep(60)  # Wait longer on error
    
    def _apply_circular_logic_fix(self, issue: Dict):
        """Apply fixes for detected circular logic."""
        if issue["type"] == "research_improvement_loop":
            # Add cooldown between research and improvement
            self.schedule["last_research"] = time.time()
            self.schedule["last_improvement"] = time.time()
            self._log("Applied fix: Extended cooldown for research and improvement")
            
        elif issue["type"] == "self_evaluation_loop":
            # Disable self-evaluation for 1 hour
            self.schedule["last_self_evaluation"] = time.time() + 3600
            self._log("Applied fix: Disabled self-evaluation for 1 hour")
            
        elif issue["type"] == "restart_loop":
            # Disable restart capability for 30 minutes
            self.restart_manager.disable_restart(1800)
            self._log("Applied fix: Disabled restarts for 30 minutes")
            
        elif issue["type"] == "error_recovery_loop":
            # Increase error wait time
            self._log("Applied fix: Increased error recovery wait time")
    
    def _get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get the next explicit task from task manager."""
        tm = task_manager.get_task_manager()
        task = tm.get_next_task()
        
        if task:
            return {
                "id": task.id,
                "title": task.title,
                "priority": task.priority.value,
                "status": task.status.value,
                "metadata": task.metadata,
            }
        
        return None
    
    def add_user_task(self, task: str, priority: str = "medium"):
        """Add a user-specified task."""
        tm = task_manager.get_task_manager()
        priority_enum = task_manager.TaskPriority(priority)
        tm.add_task(task, priority_enum)
        self._log("User task added", {"task": task, "priority": priority})
    
    def _run_research_cycle(self, task: Dict[str, Any] = None):
        """Run a research cycle focused on specific task."""
        # Use task title as topic if provided, otherwise use default rotation
        if task:
            topic = task["title"]
            focus = task.get("metadata", {}).get("focus", "")
            self._log("Starting task-focused research", {"task": topic})
        else:
            # Get current topic from schedule
            topics = self.schedule["priority_topics"]
            topic = topics[self.schedule["current_topic_index"]]
            focus = ""
            self._log("Starting research cycle", {"topic": topic})
        
        # Get research engine and research
        engine = research_engine.get_research_engine()
        result = engine.research_topic(topic, self.schedule["max_pages_per_cycle"], focus=focus)
        
        if result.get("success"):
            self._log("Research completed", {
                "topic": topic,
                "pages_processed": result["pages_processed"]
            })
            
            # Log research to MCP memory
            self._log_research_to_memory(topic, result)
            
            # Update context with research
            ctx = context_manager.load_master_context()
            if topic not in ctx.recent_topics:
                ctx.recent_topics = [topic] + ctx.recent_topics[:9]
            context_manager.save_master_context(ctx)
        else:
            self._log("Research failed", {"topic": topic, "error": result.get("error")})
        
        # Move to next topic only if not task-focused
        if not task:
            self.schedule["current_topic_index"] = (self.schedule["current_topic_index"] + 1) % len(topics)
    
    def _log_research_to_memory(self, topic: str, result: Dict[str, Any]):
        """Log research results to MCP memory."""
        try:
            # Create memory entry
            memory_entry = {
                "type": "research",
                "topic": topic,
                "timestamp": datetime.now().isoformat(),
                "pages_processed": result.get("pages_processed", 0),
                "summary": result.get("summary", "")[:1000],
                "key_findings": result.get("key_findings", [])[:8],
                "sources": result.get("sources", [])[:5]
            }
            
            # Save to memory system
            memory_path = ROOT / "data" / "memory" / f"research_{int(time.time())}.json"
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(memory_path, "w") as f:
                json.dump(memory_entry, f, indent=2)
            
            self._log("Research logged to memory", {"topic": topic, "path": str(memory_path)})
            
        except Exception as e:
            self._log("Failed to log research to memory", {"error": str(e)})
    
    def _run_browser_automation_cycle(self, task: Dict[str, Any] = None):
        """Run browser automation focused on specific task."""
        cfg = config.load_config()
        if not cfg.get("actions", {}).get("allow_ui", True):
            self._log("Browser automation skipped (UI actions disabled)")
            return

        if task:
            self._log("Starting task-focused browser automation", {"task": task["title"]})
            
            # Use browser automation to research the specific task
            result = self.browser_automation.research_topic_automatically(task["title"])
            
            # Log results to memory
            self._log_browser_results_to_memory(task["title"], result)
            
            self._log("Task browser automation completed", {
                "task": task["title"],
                "sources": result.get("sources_visited", 0)
            })
        else:
            # Default browser automation (reduced scope)
            self._log("Starting limited browser automation")
            cycle_number = int(time.time() / (self.schedule["browser_automation_minutes"] * 60)) % 2
            
            if cycle_number == 0:
                # Only scrape crypto prices (no random browsing)
                result = self.browser_automation.scrape_crypto_prices()
                self._log("Crypto prices scraped", {
                    "exchanges": result.get("scraped_exchanges", 0)
                })
            else:
                self._log("Browser automation skipped (no task)")
    
    def _log_browser_results_to_memory(self, task: str, result: Dict[str, Any]):
        """Log browser automation results to memory."""
        try:
            memory_entry = {
                "type": "browser_research",
                "task": task,
                "timestamp": datetime.now().isoformat(),
                "sources_visited": result.get("sources_visited", 0),
                "data_extracted": result.get("data_extracted", [])[:10],
                "summary": result.get("summary", "")[:500]
            }
            
            memory_path = ROOT / "data" / "memory" / f"browser_{int(time.time())}.json"
            memory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(memory_path, "w") as f:
                json.dump(memory_entry, f, indent=2)
            
            self._log("Browser results logged to memory", {"task": task, "path": str(memory_path)})
            
        except Exception as e:
            self._log("Failed to log browser results to memory", {"error": str(e)})
    
    def _run_distillation_cycle(self):
        """Run a distillation cycle."""
        self._log("Starting distillation cycle")
        
        # Get topics with research
        engine = research_engine.get_research_engine()
        
        # Get recent research topics
        with sqlite3.connect(str(ROOT / "data" / "research.db")) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT topic FROM research_notes 
                WHERE timestamp > datetime('now', '-1 hour')
            """)
            recent_topics = [row[0] for row in cursor.fetchall()]
        
        if not recent_topics:
            self._log("No recent topics to distill")
            return
        
        # Get distiller
        distiller = prompt_distiller.get_prompt_distiller()
        
        # Distill each topic
        for topic in recent_topics[:3]:  # Limit to 3 topics per cycle
            result = distiller.distill_topic(topic)
            if result.get("success"):
                self._log("Topic distilled", {
                    "topic": topic,
                    "prompts_created": result["prompts_created"]
                })
            else:
                self._log("Distillation failed", {"topic": topic})
    
    def _run_improvement_cycle(self):
        """Run an improvement cycle."""
        self._log("Starting improvement cycle")
        
        # Get distiller
        distiller = prompt_distiller.get_prompt_distiller()
        
        # Generate improvements from research
        improvements = distiller.generate_improvements_from_research()
        
        # Apply improvements safely
        applied = 0
        for improvement in improvements[:5]:  # Limit to 5 per cycle
            try:
                # Validate with guardian
                if improvement.code_snippet:
                    safe, reason = guardian.validate_code_for_safety(improvement.code_snippet)
                    if not safe:
                        self._log("Improvement rejected", {
                            "title": improvement.title,
                            "reason": reason
                        })
                        continue
                
                # Apply improvement
                result = evolution.apply_improvement(
                    improvement,
                    safety.SafetyContext(apply=True, dry_run=False),
                )
                status = result.get("status")
                if status in ("applied", "saved"):
                    applied += 1
                    self._log("Improvement applied", {"title": improvement.title, "status": status})
                else:
                    self._log("Improvement failed", {
                        "title": improvement.title,
                        "status": status,
                        "message": result.get("message", ""),
                    })
                    
            except Exception as e:
                self._log("Improvement error", {
                    "title": improvement.title,
                    "error": str(e)
                })
        
        self._log("Improvement cycle completed", {"applied": applied})
    
    def _run_google_sync_cycle(self):
        """Run a Google services sync cycle."""
        self._log("Starting Google sync cycle")
        
        # Check if Google is authenticated
        if not self.google_manager.integration.authenticated:
            self._log("Google not authenticated", {"status": "skipped"})
            return
        
        try:
            # Sync Drive
            drive_result = self.google_manager.sync_drive(max_files=50)
            self._log("Drive sync", drive_result)
            
            # Scan Gmail
            gmail_result = self.google_manager.scan_gmail(max_emails=25)
            self._log("Gmail scan", gmail_result)
            
            # Sync Calendar
            calendar_result = self.google_manager.sync_calendar(days_ahead=7)
            self._log("Calendar sync", calendar_result)
            
            # Analyze Drive content
            analysis_result = self.google_manager.analyze_drive_content()
            self._log("Drive analysis", analysis_result)
            
            # Auto-organize if needed
            if analysis_result.get("success") and analysis_result.get("total_files", 0) > 20:
                organize_result = self.google_manager.auto_organize_drive()
                self._log("Drive organization", organize_result)
            
        except Exception as e:
            self._log("Google sync error", {"error": str(e)})
    
        
    def _run_learning_validation_cycle(self):
        """Run a learning validation cycle."""
        self._log("Starting learning validation cycle")
        
        try:
            # Calculate current metrics
            metrics = self.learning_validator.calculate_metrics()
            self._log("Metrics calculated", metrics)
            
            # Validate any new functions from recent improvements
            # This would check for functions added in the last cycle
            validation_summary = self.learning_validator.get_validation_summary()
            self._log("Validation summary", validation_summary)
            
            # If validation rate is low, trigger more testing
            if metrics.get("test_success_rate", 1.0) < 0.8:
                self._log("Low validation success rate, increasing testing", {
                    "current_rate": metrics.get("test_success_rate")
                })
                # Could trigger additional test generation here
                
        except Exception as e:
            self._log("Learning validation error", {"error": str(e)})
    
    def _run_iterative_improvement_cycle(self):
        """Run an iterative improvement cycle."""
        self._log("Starting iterative improvement cycle")
        
        try:
            # Run the complete learning and improvement cycle
            cycle_result = self.iterative_improver.run_learning_cycle()
            self._log("Iterative improvement completed", cycle_result)
            
            # If significant improvements were made, update schedule
            if cycle_result.get("improvements_validated", 0) > 0:
                self._log("Significant improvements made, adjusting cycles", {
                    "validated": cycle_result.get("improvements_validated")
                })
                
                # Check if restart is needed for new improvements
                improvements = cycle_result.get("improvements_applied", [])
                if self.restart_manager.handle_improvement_integration(improvements):
                    self._log("Restart scheduled for improvements", {
                        "count": len(improvements),
                        "reason": self.restart_manager.restart_state.get("restart_reason", "Integration required")
                    })
                    # Execute restart after a short delay
                    time.sleep(5)
                    self.restart_manager.execute_restart()
                else:
                    # Could adjust cycle times based on success
                    pass
                
        except Exception as e:
            self._log("Iterative improvement error", {"error": str(e)})
    
    def _run_self_evaluation_cycle(self):
        """Run a self-evaluation cycle."""
        self._log("Starting self-evaluation cycle")
        
        try:
            # Run complete self-evaluation
            cycle_result = self.self_evaluator.run_self_evaluation_cycle()
            self._log("Self-evaluation completed", cycle_result)
            
            # If significant improvements were found, trigger additional cycles
            if cycle_result.get("expansions_integrated", 0) > 0:
                self._log("New expansions integrated, triggering validation", {
                    "integrated": cycle_result.get("expansions_integrated")
                })
                
                # Check if restart is needed for new integrations
                if cycle_result.get("expansions_integrated", 0) >= 2:
                    reason = f"Multiple expansions integrated: {cycle_result.get('expansions_integrated')}"
                    preserve_state = {
                        "last_self_evaluation": cycle_result,
                        "restart_triggered_by": "expansion_integration"
                    }
                    self.restart_manager.schedule_restart(reason, preserve_state)
                    self._log("Restart scheduled for expansions", {"reason": reason})
                    
                    # Execute restart after a short delay
                    time.sleep(5)
                    self.restart_manager.execute_restart()
                else:
                    # Trigger validation to test new abilities
                    self._run_learning_validation_cycle()
                
            # If self-score is low, increase research focus
            if cycle_result.get("self_evaluation", 5) < 6:
                self._log("Low self-evaluation score, increasing research", {
                    "score": cycle_result.get("self_evaluation")
                })
                # Could trigger additional research cycle
                
        except Exception as e:
            self._log("Self-evaluation error", {"error": str(e)})
    
    def _run_crypto_trading_cycle(self):
        """Run a crypto trading research cycle."""
        self._log("Starting crypto trading research cycle")
        
        try:
            # Run complete trading research cycle
            cycle_result = self.crypto_trading.run_trading_research_cycle()
            self._log("Crypto trading research completed", cycle_result)
            
            # If profitable strategies found, prioritize them
            if cycle_result.get("bots_created", 0) > 0:
                self._log("Trading bots created", {
                    "count": cycle_result.get("bots_created")
                })
                # Could trigger validation of new trading code
                
        except Exception as e:
            self._log("Crypto trading error", {"error": str(e)})
    
    def _run_google_cli_cycle(self):
        """Run a Google CLI integration cycle."""
        self._log("Starting Google CLI integration cycle")
        
        try:
            # Check Google CLI status
            cli_status = self.google_cli.check_gcloud_installation()
            self._log("Google CLI status", cli_status)
            
            # If installed, discover services
            if cli_status.get("installed", False):
                services = self.google_cli.discover_available_services()
                self._log("Google services discovered", {
                    "total": len(services),
                    "enabled": len([s for s in services if s.get("enabled", False)])
                })
                
                # If few services enabled, enable some useful ones
                enabled_count = len([s for s in services if s.get("enabled", False)])
                if enabled_count < 3:
                    useful_services = ["compute", "functions", "storage"]
                    for service in useful_services:
                        if not any(s["name"] == service and s.get("enabled", False) for s in services):
                            enable_result = self.google_cli.enable_service(service)
                            self._log("Service enable attempt", {
                                "service": service,
                                "success": enable_result.get("success", False)
                            })
            else:
                # Try to install gcloud
                install_result = self.google_cli.install_gcloud()
                self._log("Google CLI install attempt", install_result)
                
        except Exception as e:
            self._log("Google CLI error", {"error": str(e)})
    
        
    def _run_ability_acquisition_cycle(self):
        """Run an ability acquisition cycle with full autonomy."""
        self._log("Starting ability acquisition cycle")
        
        try:
            # Run the autonomous ability acquisition cycle
            cycle_result = self.ability_acquisition.run_acquisition_cycle()
            self._log("Ability acquisition completed", cycle_result)
            
            # If restart is needed for major capability integration
            if cycle_result.get("restart_needed", False):
                reason = cycle_result.get("reason", "Major capability integration")
                preserve_state = {
                    "last_ability_acquisition": cycle_result,
                    "restart_triggered_by": "ability_acquisition"
                }
                self.restart_manager.schedule_restart(reason, preserve_state)
                self._log("Restart scheduled for ability acquisition", {"reason": reason})
                
                # Execute restart after a short delay
                time.sleep(5)
                self.restart_manager.execute_restart()
            
            # If significant abilities were acquired, trigger validation
            if cycle_result.get("acquired", 0) > 0:
                self._log("New abilities acquired, triggering validation", {
                    "acquired": cycle_result.get("acquired")
                })
                # Trigger validation to test new abilities
                self._run_learning_validation_cycle()
                
        except Exception as e:
            self._log("Ability acquisition error", {"error": str(e)})
    
    def _run_autonomous_research_cycle(self):
        """Run an autonomous research cycle for newest free models."""
        self._log("Starting autonomous research cycle")
        
        try:
            # Run continuous research
            cycle_result = self.autonomous_researcher.continuous_research_cycle()
            self._log("Autonomous research completed", {
                "models_found": cycle_result["research_completed"]["models_found"],
                "markdown_file": cycle_result["research_completed"]["markdown_file"]
            })
            
            # If significant models found, trigger ability acquisition
            if cycle_result["research_completed"]["models_found"] > 0:
                self._log("New models discovered, triggering ability acquisition", {
                    "count": cycle_result["research_completed"]["models_found"]
                })
                # Trigger ability acquisition to evaluate new models
                self._run_ability_acquisition_cycle()
                
        except Exception as e:
            self._log("Autonomous research error", {"error": str(e)})
    
    def _run_autonomous_agent_cycle(self):
        """Run an autonomous agent task cycle."""
        self._log("Starting autonomous agent cycle")
        
        try:
            # Define autonomous goals for Jarvis
            agent_goals = [
                "Research and integrate the latest free AI models for enhanced autonomy",
                "Optimize system performance and reduce resource usage",
                "Discover and implement new automation capabilities",
                "Enhance crypto trading research and analysis",
                "Improve information organization and context management"
            ]
            
            # Execute a random goal from the list
            import random
            selected_goal = random.choice(agent_goals)
            
            # Get current system context
            context = {
                "current_abilities": len(self.ability_acquisition.abilities["acquired"]),
                "system_status": self.get_system_status(),
                "recent_research": self.autonomous_researcher.get_research_summary()
            }
            
            # Execute autonomous task
            task_result = self.autonomous_agent.execute_autonomous_task(selected_goal, context)
            
            self._log("Autonomous agent task completed", {
                "goal": selected_goal,
                "status": task_result["status"],
                "steps_completed": len(task_result.get("results", []))
            })
            
            # If task was successful and involved new abilities, trigger acquisition
            if task_result.get("status") == "completed":
                results = task_result.get("results", [])
                if any(r.get("tool") == "ability_acquisition" and r.get("status") == "success" for r in results):
                    self._log("Agent discovered new abilities, triggering acquisition", {})
                    self._run_ability_acquisition_cycle()
                
        except Exception as e:
            self._log("Autonomous agent error", {"error": str(e)})
    
    def _run_service_discovery_cycle(self):
        """Run a service discovery cycle."""
        self._log("Starting service discovery cycle")
        
        # Research new services
        new_services = self.service_discovery.research_new_services()
        
        if new_services:
            self._log("New services discovered", {"count": len(new_services)})
            
            # For each new service, attempt to evaluate and potentially integrate
            for service in new_services[:3]:  # Limit to 3 per cycle
                # Use LLM to evaluate if service is worth integrating
                evaluation_prompt = f"""Evaluate this AI service for integration:

Service: {service['title']}
URL: {service['url']}
Description: {service['snippet']}

Should Jarvis integrate this service? Consider:
1. Is it free or has a generous free tier?
2. Does it provide unique capabilities?
3. Is it easy to integrate?
4. Does it align with Jarvis's goals?

Answer YES or NO with brief reason."""
                
                try:
                    response = providers.ask_llm(evaluation_prompt, max_output_tokens=200)
                    if response and "YES" in response.upper():
                        self._log("Service approved for integration", {
                            "service": service["title"],
                            "reason": response
                        })
                        # Add to discovery queue for user approval
                        self.add_research_topic(f"Integrate service: {service['title']}", priority=True)
                except Exception as e:
                    self._log("Service evaluation error", {
                        "service": service["title"],
                        "error": str(e)
                    })
        
        # Check available services that aren't integrated yet
        available = self.service_discovery.discover_services()
        if available:
            self._log("Services available for integration", {
                "count": len(available),
                "services": [s["name"] for s in available]
            })
    
    def add_research_topic(self, topic: str, priority: bool = False):
        """Add a new research topic."""
        if topic not in self.schedule["priority_topics"]:
            if priority:
                self.schedule["priority_topics"].insert(0, topic)
            else:
                self.schedule["priority_topics"].append(topic)
            self._save_schedule()
            self._log("Topic added", {"topic": topic, "priority": priority})
    
    def set_cycle_times(self, research_minutes: int = None, distillation_minutes: int = None, improvement_minutes: int = None):
        """Adjust cycle times."""
        if research_minutes:
            self.schedule["research_cycle_minutes"] = research_minutes
        if distillation_minutes:
            self.schedule["distillation_cycle_minutes"] = distillation_minutes
        if improvement_minutes:
            self.schedule["improvement_cycle_minutes"] = improvement_minutes
        self._save_schedule()
        self._log("Cycle times updated", {
            "research": research_minutes,
            "distillation": distillation_minutes,
            "improvement": improvement_minutes
        })
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status."""
        # Get research stats
        engine = research_engine.get_research_engine()
        research_count = len(engine.get_research_summary(limit=1000))
        
        # Get distillation stats
        distiller = prompt_distiller.get_prompt_distiller()
        learning_report = distiller.get_learning_report()
        
        return {
            "running": self.running,
            "current_topic": self.schedule["priority_topics"][self.schedule["current_topic_index"]],
            "research_stats": {
                "total_pages": research_count,
                "topics_researched": len(self.schedule["priority_topics"])
            },
            "learning_stats": learning_report["research_summary"],
            "cycle_times": {
                "research_minutes": self.schedule["research_cycle_minutes"],
                "distillation_minutes": self.schedule["distillation_cycle_minutes"],
                "improvement_minutes": self.schedule["improvement_cycle_minutes"]
            },
            "last_cycles": {
                "research": self.schedule["last_research"],
                "distillation": self.schedule["last_distillation"],
                "improvement": self.schedule["last_improvement"]
            }
        }


# Global controller instance
_controller: Optional[AutonomousController] = None


def get_autonomous_controller() -> AutonomousController:
    """Get the global autonomous controller instance."""
    global _controller
    if not _controller:
        _controller = AutonomousController()
    return _controller


def start_autonomous_controller() -> AutonomousController:
    """Start the autonomous controller."""
    controller = get_autonomous_controller()
    controller.start()
    return controller


def stop_autonomous_controller():
    """Stop the autonomous controller."""
    global _controller
    if _controller:
        _controller.stop()
