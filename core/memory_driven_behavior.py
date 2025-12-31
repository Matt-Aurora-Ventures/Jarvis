#!/usr/bin/env python3
"""
Memory-Driven Behavior System
Makes Jarvis use memory to plan and follow through consistently
Addresses the "memory retention is inconsistent / not driving behavior" issue
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum

from core import memory, providers, safety

ROOT = Path(__file__).resolve().parents[1]
WORKING_SET_PATH = ROOT / "data" / "working_set.db"
MEMORY_DECISIONS_PATH = ROOT / "data" / "memory_decisions.jsonl"


class GoalStatus(Enum):
    """Status of goals in working set."""
    ACTIVE = "active"
    PAUSED = "paused" 
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStatus(Enum):
    """Status of next actions."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class Goal:
    """Active goal that drives behavior."""
    id: str
    title: str
    description: str
    status: GoalStatus
    priority: int  # 1-10, higher = more important
    created_at: datetime
    updated_at: datetime
    progress: float  # 0.0-1.0
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        result["status"] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["status"] = GoalStatus(data["status"])
        return cls(**data)


@dataclass
class NextAction:
    """Next action to advance a goal."""
    id: str
    goal_id: str
    title: str
    description: str
    status: TaskStatus
    priority: int
    created_at: datetime
    due_at: Optional[datetime]
    completed_at: Optional[datetime]
    dependencies: List[str]  # IDs of other actions
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["due_at"] = self.due_at.isoformat() if self.due_at else None
        result["completed_at"] = self.completed_at.isoformat() if self.completed_at else None
        result["status"] = self.status.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NextAction":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["due_at"] = datetime.fromisoformat(data["due_at"]) if data["due_at"] else None
        data["completed_at"] = datetime.fromisoformat(data["completed_at"]) if data["completed_at"] else None
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class WorkingSetManager:
    """Manages the working set of goals and next actions."""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize working set database."""
        WORKING_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            # Goals table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    progress REAL DEFAULT 0.0,
                    metadata TEXT
                )
            """)
            
            # Next actions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS next_actions (
                    id TEXT PRIMARY KEY,
                    goal_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    due_at TEXT,
                    completed_at TEXT,
                    dependencies TEXT,
                    metadata TEXT,
                    FOREIGN KEY (goal_id) REFERENCES goals (id)
                )
            """)
            
            # Memory decisions table - tracks how memory influenced decisions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    decision_type TEXT NOT NULL,
                    memory_context TEXT,
                    decision TEXT,
                    outcome TEXT,
                    confidence REAL
                )
            """)
            
            conn.commit()
    
    def add_goal(self, title: str, description: str, priority: int = 5, metadata: Dict[str, Any] = None) -> Goal:
        """Add a new goal to the working set."""
        goal_id = f"goal_{int(time.time())}_{hash(title) % 10000}"
        now = datetime.now()
        
        goal = Goal(
            id=goal_id,
            title=title,
            description=description,
            status=GoalStatus.ACTIVE,
            priority=priority,
            created_at=now,
            updated_at=now,
            progress=0.0,
            metadata=metadata or {}
        )
        
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            conn.execute("""
                INSERT INTO goals 
                (id, title, description, status, priority, created_at, updated_at, progress, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                goal.id, goal.title, goal.description, goal.status.value,
                goal.priority, goal.created_at.isoformat(), goal.updated_at.isoformat(),
                goal.progress, json.dumps(goal.metadata)
            ))
            conn.commit()
        
        return goal
    
    def get_active_goals(self) -> List[Goal]:
        """Get all active goals."""
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            cursor = conn.execute("""
                SELECT * FROM goals 
                WHERE status = ? 
                ORDER BY priority DESC, updated_at ASC
            """, (GoalStatus.ACTIVE.value,))
            
            goals = []
            for row in cursor.fetchall():
                goal = Goal(
                    id=row[0], title=row[1], description=row[2],
                    status=GoalStatus(row[3]), priority=row[4],
                    created_at=datetime.fromisoformat(row[5]),
                    updated_at=datetime.fromisoformat(row[6]),
                    progress=row[7], metadata=json.loads(row[8] or "{}")
                )
                goals.append(goal)
            
            return goals
    
    def update_goal_progress(self, goal_id: str, progress: float, status: GoalStatus = None):
        """Update goal progress and optionally status."""
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            updates = ["progress = ?", "updated_at = ?"]
            params = [progress, datetime.now().isoformat()]
            
            if status:
                updates.append("status = ?")
                params.append(status.value)
            
            params.append(goal_id)
            
            conn.execute(f"""
                UPDATE goals 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()
    
    def add_next_action(self, goal_id: str, title: str, description: str, 
                       priority: int = 5, due_at: datetime = None,
                       dependencies: List[str] = None) -> NextAction:
        """Add a next action for a goal."""
        action_id = f"action_{int(time.time())}_{hash(title) % 10000}"
        now = datetime.now()
        
        action = NextAction(
            id=action_id,
            goal_id=goal_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now,
            due_at=due_at,
            completed_at=None,
            dependencies=dependencies or [],
            metadata={}
        )
        
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            conn.execute("""
                INSERT INTO next_actions 
                (id, goal_id, title, description, status, priority, created_at, due_at, dependencies, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                action.id, action.goal_id, action.title, action.description,
                action.status.value, action.priority, action.created_at.isoformat(),
                action.due_at.isoformat() if action.due_at else None,
                json.dumps(action.dependencies), json.dumps(action.metadata)
            ))
            conn.commit()
        
        return action
    
    def get_next_actions(self, status: TaskStatus = None, limit: int = 10) -> List[NextAction]:
        """Get next actions, optionally filtered by status."""
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            query = """
                SELECT * FROM next_actions
                WHERE 1=1
            """
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            query += " ORDER BY priority DESC, created_at ASC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(query, params)
            
            actions = []
            for row in cursor.fetchall():
                action = NextAction(
                    id=row[0], goal_id=row[1], title=row[2], description=row[3],
                    status=TaskStatus(row[4]), priority=row[5],
                    created_at=datetime.fromisoformat(row[6]),
                    due_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    dependencies=json.loads(row[9] or "[]"),
                    metadata=json.loads(row[10] or "{}")
                )
                actions.append(action)
            
            return actions
    
    def complete_action(self, action_id: str):
        """Mark a next action as completed."""
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            conn.execute("""
                UPDATE next_actions 
                SET status = ?, completed_at = ?
                WHERE id = ?
            """, (TaskStatus.COMPLETED.value, datetime.now().isoformat(), action_id))
            conn.commit()
    
    def record_memory_decision(self, decision_type: str, memory_context: str, 
                              decision: str, outcome: str = "", confidence: float = 0.5):
        """Record how memory influenced a decision."""
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            conn.execute("""
                INSERT INTO memory_decisions 
                (timestamp, decision_type, memory_context, decision, outcome, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(), decision_type, memory_context,
                decision, outcome, confidence
            ))
            conn.commit()


class MemoryAnalyzer:
    """Analyzes memory to extract actionable insights."""
    
    def __init__(self):
        self.insight_cache = {}
        self.last_analysis_time = 0
    
    def analyze_recent_memory(self, hours_back: int = 24) -> Dict[str, Any]:
        """Analyze recent memory entries for patterns and insights."""
        # Cache analysis for 5 minutes
        now = time.time()
        if now - self.last_analysis_time < 300:
            return self.insight_cache
        
        # Get recent memory entries
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        recent_entries = memory.get_factual_entries()
        
        # Filter by time
        filtered_entries = []
        for entry in recent_entries:
            entry_time = datetime.fromtimestamp(entry.get("timestamp", 0))
            if entry_time > cutoff_time:
                filtered_entries.append(entry)
        
        analysis = {
            "total_entries": len(filtered_entries),
            "sources": self._analyze_sources(filtered_entries),
            "themes": self._extract_themes(filtered_entries),
            "patterns": self._identify_patterns(filtered_entries),
            "action_items": self._extract_action_items(filtered_entries),
            "goals_suggested": self._suggest_goals(filtered_entries)
        }
        
        self.insight_cache = analysis
        self.last_analysis_time = now
        return analysis
    
    def _analyze_sources(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze sources of memory entries."""
        sources = {}
        for entry in entries:
            source = entry.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1
        return sources
    
    def _extract_themes(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Extract recurring themes from memory entries."""
        # Simple keyword-based theme extraction
        theme_keywords = {
            "trading": ["trading", "crypto", "market", "bot", "strategy"],
            "ai_development": ["ai", "model", "training", "neural", "algorithm"],
            "automation": ["automation", "script", "task", "workflow"],
            "research": ["research", "study", "analysis", "findings"],
            "improvement": ["improve", "enhance", "optimize", "fix"],
            "learning": ["learn", "study", "understand", "knowledge"]
        }
        
        theme_counts = {theme: 0 for theme in theme_keywords}
        total_text = " ".join([entry.get("text", "").lower() for entry in entries])
        
        for theme, keywords in theme_keywords.items():
            for keyword in keywords:
                theme_counts[theme] += total_text.count(keyword)
        
        # Return themes with at least 2 mentions
        significant_themes = [
            theme for theme, count in theme_counts.items() if count >= 2
        ]
        
        return significant_themes
    
    def _identify_patterns(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Identify patterns in memory entries."""
        patterns = []
        
        # Time-based patterns
        if len(entries) > 10:
            patterns.append("High activity volume detected")
        
        # Source patterns
        sources = self._analyze_sources(entries)
        if "voice_chat_user" in sources and sources["voice_chat_user"] > 5:
            patterns.append("Frequent user voice interactions")
        
        # Content patterns (simple)
        error_count = sum(1 for entry in entries if "error" in entry.get("text", "").lower())
        if error_count > 2:
            patterns.append("Multiple errors encountered")
        
        success_count = sum(1 for entry in entries if any(word in entry.get("text", "").lower() for word in ["success", "completed", "done"]))
        if success_count > 3:
            patterns.append("Multiple successful completions")
        
        return patterns
    
    def _extract_action_items(self, entries: List[Dict[str, Any]]) -> List[str]:
        """Extract actionable items from memory entries."""
        action_items = []
        
        # Look for action-oriented language
        action_keywords = ["need to", "should", "must", "let's", "we need", "implement", "create", "fix", "add"]
        
        for entry in entries:
            text = entry.get("text", "").lower()
            for keyword in action_keywords:
                if keyword in text:
                    # Extract sentence containing the keyword
                    sentences = text.split(".")
                    for sentence in sentences:
                        if keyword in sentence:
                            action_item = sentence.strip().capitalize()
                            if len(action_item) > 10:  # Filter very short items
                                action_items.append(action_item)
                            break
        
        return action_items[:5]  # Limit to top 5
    
    def _suggest_goals(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest goals based on memory analysis."""
        goals = []
        
        themes = self._extract_themes(entries)
        action_items = self._extract_action_items(entries)
        
        # Map themes to goal suggestions
        theme_goal_map = {
            "trading": {
                "title": "Improve Trading Bot Performance",
                "description": "Enhance trading strategies and reduce risk",
                "priority": 7
            },
            "ai_development": {
                "title": "Advance AI Capabilities",
                "description": "Implement new AI features and improvements",
                "priority": 8
            },
            "automation": {
                "title": "Expand Automation Workflows",
                "description": "Automate more tasks and processes",
                "priority": 6
            },
            "research": {
                "title": "Conduct Focused Research",
                "description": "Research specific topics for actionable insights",
                "priority": 5
            }
        }
        
        for theme in themes:
            if theme in theme_goal_map:
                goal_info = theme_goal_map[theme]
                goals.append({
                    "suggested_by": f"Theme: {theme}",
                    "evidence_count": themes.count(theme),
                    **goal_info
                })
        
        # Suggest goals from action items
        if len(action_items) >= 3:
            goals.append({
                "suggested_by": "Action items detected",
                "evidence_count": len(action_items),
                "title": "Address Action Items",
                "description": f"Process {len(action_items)} identified action items",
                "priority": 6
            })
        
        return goals


class MemoryDrivenBehaviorEngine:
    """Main engine that drives behavior based on memory analysis."""
    
    def __init__(self):
        self.working_set = WorkingSetManager()
        self.analyzer = MemoryAnalyzer()
        self.last_decision_time = 0
        self.decision_cooldown = 300  # 5 minutes between decisions
    
    def get_next_action(self) -> Optional[NextAction]:
        """Get the next action to execute based on working set."""
        # Get pending actions, ordered by priority
        pending_actions = self.working_set.get_next_actions(TaskStatus.PENDING, limit=5)
        
        if not pending_actions:
            return None
        
        # Check for dependencies
        for action in pending_actions:
            if self._are_dependencies_met(action):
                return action
        
        # If no actions with met dependencies, return highest priority
        return pending_actions[0] if pending_actions else None
    
    def _are_dependencies_met(self, action: NextAction) -> bool:
        """Check if all dependencies for an action are met."""
        if not action.dependencies:
            return True
        
        for dep_id in action.dependencies:
            # Check if dependency action is completed
            dep_actions = self.working_set.get_next_actions()
            dep_completed = any(
                a.id == dep_id and a.status == TaskStatus.COMPLETED 
                for a in dep_actions
            )
            if not dep_completed:
                return False
        
        return True
    
    def analyze_and_plan(self) -> Dict[str, Any]:
        """Analyze memory and create/update goals and actions."""
        if time.time() - self.last_decision_time < self.decision_cooldown:
            return {"status": "cooldown", "message": "Decision cooldown active"}
        
        # Analyze recent memory
        analysis = self.analyzer.analyze_recent_memory()
        
        # Get current active goals
        active_goals = self.working_set.get_active_goals()
        
        decisions = []
        
        # Suggest new goals based on analysis
        suggested_goals = analysis.get("goals_suggested", [])
        for suggestion in suggested_goals:
            # Check if similar goal already exists
            similar_exists = any(
                suggestion["title"].lower() in goal.title.lower() or 
                goal.title.lower() in suggestion["title"].lower()
                for goal in active_goals
            )
            
            if not similar_exists and suggestion["priority"] >= 5:
                # Create new goal
                new_goal = self.working_set.add_goal(
                    title=suggestion["title"],
                    description=suggestion["description"],
                    priority=suggestion["priority"],
                    metadata={
                        "suggested_by": "memory_analysis",
                        "evidence": suggestion["suggested_by"],
                        "evidence_count": suggestion.get("evidence_count", 0)
                    }
                )
                
                decisions.append({
                    "type": "goal_created",
                    "goal_id": new_goal.id,
                    "goal_title": new_goal.title,
                    "reason": suggestion["suggested_by"]
                })
        
        # Create actions from action items
        action_items = analysis.get("action_items", [])
        for item in action_items[:3]:  # Limit to top 3
            # Find most relevant active goal
            target_goal = None
            if active_goals:
                # Simple relevance scoring based on keyword overlap
                best_score = 0
                for goal in active_goals:
                    score = len(set(item.lower().split()) & set(goal.title.lower().split()))
                    if score > best_score:
                        best_score = score
                        target_goal = goal
            
            if target_goal:
                new_action = self.working_set.add_next_action(
                    goal_id=target_goal.id,
                    title=f"Address: {item[:50]}...",
                    description=item,
                    priority=6
                )
                
                decisions.append({
                    "type": "action_created",
                    "action_id": new_action.id,
                    "goal_id": target_goal.id,
                    "reason": "memory_action_item"
                })
        
        # Record the decision process
        memory_context = f"Themes: {analysis.get('themes', [])}, Patterns: {analysis.get('patterns', [])}"
        decision_summary = f"Created {len(decisions)} new items from memory analysis"
        
        self.working_set.record_memory_decision(
            decision_type="analyze_and_plan",
            memory_context=memory_context,
            decision=decision_summary,
            outcome=json.dumps(decisions),
            confidence=0.7
        )
        
        self.last_decision_time = time.time()
        
        return {
            "status": "completed",
            "analysis": analysis,
            "decisions": decisions,
            "active_goals_count": len(active_goals),
            "pending_actions_count": len(self.working_set.get_next_actions(TaskStatus.PENDING))
        }
    
    def execute_action(self, action: NextAction) -> Dict[str, Any]:
        """Execute a next action and update state."""
        # Mark action as in progress
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            conn.execute("""
                UPDATE next_actions 
                SET status = ?
                WHERE id = ?
            """, (TaskStatus.IN_PROGRESS.value, action.id))
            conn.commit()
        
        # Execute action based on type/pattern
        result = self._execute_action_logic(action)
        
        # Mark as completed
        self.working_set.complete_action(action.id)
        
        # Update goal progress
        self._update_goal_progress_after_action(action)
        
        return result
    
    def _execute_action_logic(self, action: NextAction) -> Dict[str, Any]:
        """Execute the actual logic for an action."""
        title_lower = action.title.lower()
        
        # Research actions
        if "research" in title_lower:
            return self._execute_research_action(action)
        
        # Implementation actions
        elif "implement" in title_lower or "create" in title_lower:
            return self._execute_implementation_action(action)
        
        # Fix actions
        elif "fix" in title_lower or "address" in title_lower:
            return self._execute_fix_action(action)
        
        # Default action
        else:
            return self._execute_generic_action(action)
    
    def _execute_research_action(self, action: NextAction) -> Dict[str, Any]:
        """Execute a research action."""
        try:
            # Extract research topic from action description
            topic = action.description
            
            # Use enhanced search pipeline
            from core.enhanced_search_pipeline import get_enhanced_search_pipeline
            pipeline = get_enhanced_search_pipeline()
            
            search_result = pipeline.search(topic, intent="research")
            
            if search_result["success"]:
                # Store results in memory
                memory.append_entry(
                    text=f"Researched {topic}: Found {search_result['total_found']} results",
                    source="memory_driven_research",
                    context=safety.SafetyContext(apply=True, dry_run=False)
                )
                
                return {
                    "status": "success",
                    "action_type": "research",
                    "results_count": search_result["total_found"],
                    "details": f"Research completed for {topic}"
                }
            else:
                return {
                    "status": "failed",
                    "action_type": "research",
                    "error": "Search failed",
                    "details": f"Research failed for {topic}"
                }
                
        except Exception as e:
            return {
                "status": "error",
                "action_type": "research",
                "error": str(e),
                "details": "Exception during research"
            }
    
    def _execute_implementation_action(self, action: NextAction) -> Dict[str, Any]:
        """Execute an implementation action."""
        # For now, log the implementation intent
        memory.append_entry(
            text=f"Implementation planned: {action.description}",
            source="memory_driven_implementation",
            context=safety.SafetyContext(apply=True, dry_run=False)
        )
        
        return {
            "status": "planned",
            "action_type": "implementation",
            "details": f"Implementation planned: {action.title}"
        }
    
    def _execute_fix_action(self, action: NextAction) -> Dict[str, Any]:
        """Execute a fix action."""
        # For now, log the fix intent
        memory.append_entry(
            text=f"Fix identified: {action.description}",
            source="memory_driven_fix",
            context=safety.SafetyContext(apply=True, dry_run=False)
        )
        
        return {
            "status": "identified",
            "action_type": "fix",
            "details": f"Fix identified: {action.title}"
        }
    
    def _execute_generic_action(self, action: NextAction) -> Dict[str, Any]:
        """Execute a generic action."""
        memory.append_entry(
            text=f"Action processed: {action.description}",
            source="memory_driven_action",
            context=safety.SafetyContext(apply=True, dry_run=False)
        )
        
        return {
            "status": "processed",
            "action_type": "generic",
            "details": f"Action processed: {action.title}"
        }
    
    def _update_goal_progress_after_action(self, action: NextAction):
        """Update goal progress after completing an action."""
        # Get the goal for this action
        with sqlite3.connect(WORKING_SET_PATH) as conn:
            cursor = conn.execute("""
                SELECT * FROM goals WHERE id = ?
            """, (action.goal_id,))
            
            goal_row = cursor.fetchone()
            if goal_row:
                # Simple progress calculation: increase by 10% per action
                current_progress = goal_row[7]  # progress column
                new_progress = min(1.0, current_progress + 0.1)
                
                # Check if goal should be marked complete
                new_status = GoalStatus.ACTIVE
                if new_progress >= 1.0:
                    new_status = GoalStatus.COMPLETED
                
                conn.execute("""
                    UPDATE goals 
                    SET progress = ?, status = ?, updated_at = ?
                    WHERE id = ?
                """, (new_progress, new_status.value, datetime.now().isoformat(), action.goal_id))
                conn.commit()


# Global instance
_behavior_engine = None

def get_memory_behavior_engine() -> MemoryDrivenBehaviorEngine:
    """Get the global memory-driven behavior engine."""
    global _behavior_engine
    if _behavior_engine is None:
        _behavior_engine = MemoryDrivenBehaviorEngine()
    return _behavior_engine


if __name__ == "__main__":
    # Test the memory-driven behavior system
    engine = get_memory_behavior_engine()
    
    # Analyze memory and plan
    plan_result = engine.analyze_and_plan()
    print("Memory Analysis and Planning:")
    print(json.dumps(plan_result, indent=2, default=str))
    
    # Get next action
    next_action = engine.get_next_action()
    if next_action:
        print(f"\nNext Action: {next_action.title}")
        print(f"Description: {next_action.description}")
        
        # Execute action
        result = engine.execute_action(next_action)
        print(f"Execution Result: {result}")
    else:
        print("\nNo pending actions available")
