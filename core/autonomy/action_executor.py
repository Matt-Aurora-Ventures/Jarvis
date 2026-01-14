"""
Action Executor - Bridges Observation to Execution

Connects:
- ObservationalDaemon (generates hypotheses)
- MemoryDrivenBehaviorEngine (has goals/tasks)
- Autonomous systems (X bot, trading, etc.)

This module actually EXECUTES the learnings.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "execution"
DATA_DIR.mkdir(parents=True, exist_ok=True)

EXECUTION_LOG = DATA_DIR / "execution_log.jsonl"
PENDING_TASKS = DATA_DIR / "pending_tasks.json"


class ActionType(Enum):
    """Types of actions that can be executed."""
    POST_TWEET = "post_tweet"
    SEND_ALERT = "send_alert"
    UPDATE_CONFIG = "update_config"
    RESEARCH_TOPIC = "research_topic"
    TRADE_SIGNAL = "trade_signal"
    CREATE_CONTENT = "create_content"
    ENGAGEMENT = "engagement"
    SHELL_COMMAND = "shell_command"
    MEMORY_UPDATE = "memory_update"


class ExecutionStatus(Enum):
    """Status of action execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutableAction:
    """An action that can be executed."""
    action_id: str
    action_type: ActionType
    description: str
    parameters: Dict[str, Any]
    source: str  # observation, memory, learning, manual
    confidence: float
    priority: int  # 1-10
    created_at: float
    execute_after: Optional[float] = None  # Delayed execution
    max_retries: int = 1
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["action_type"] = self.action_type.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutableAction":
        data["action_type"] = ActionType(data["action_type"])
        data["status"] = ExecutionStatus(data["status"])
        return cls(**data)


class ActionExecutor:
    """
    Executes actions derived from observations and learnings.

    This is the "doing" part of the autonomous system.
    """

    def __init__(self):
        self._running = False
        self._action_queue: List[ExecutableAction] = []
        self._handlers: Dict[ActionType, Callable] = {}
        self._execution_count = 0
        self._last_execution = 0.0
        self._cooldown = 30  # Minimum seconds between executions
        self._load_pending()
        self._register_default_handlers()

    def _load_pending(self):
        """Load pending actions from disk."""
        try:
            if PENDING_TASKS.exists():
                data = json.loads(PENDING_TASKS.read_text())
                self._action_queue = [ExecutableAction.from_dict(a) for a in data]
                logger.info(f"Loaded {len(self._action_queue)} pending actions")
        except Exception as e:
            logger.error(f"Failed to load pending actions: {e}")

    def _save_pending(self):
        """Save pending actions to disk."""
        try:
            pending = [a.to_dict() for a in self._action_queue
                      if a.status == ExecutionStatus.PENDING]
            PENDING_TASKS.write_text(json.dumps(pending, indent=2))
        except Exception as e:
            logger.error(f"Failed to save pending actions: {e}")

    def _log_execution(self, action: ExecutableAction):
        """Log action execution to file."""
        try:
            with open(EXECUTION_LOG, "a") as f:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "action_id": action.action_id,
                    "action_type": action.action_type.value,
                    "description": action.description[:100],
                    "status": action.status.value,
                    "source": action.source,
                    "confidence": action.confidence,
                    "result": action.result
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log execution: {e}")

    def _register_default_handlers(self):
        """Register default action handlers."""
        self._handlers[ActionType.POST_TWEET] = self._handle_post_tweet
        self._handlers[ActionType.SEND_ALERT] = self._handle_send_alert
        self._handlers[ActionType.RESEARCH_TOPIC] = self._handle_research
        self._handlers[ActionType.CREATE_CONTENT] = self._handle_create_content
        self._handlers[ActionType.ENGAGEMENT] = self._handle_engagement
        self._handlers[ActionType.MEMORY_UPDATE] = self._handle_memory_update
        self._handlers[ActionType.TRADE_SIGNAL] = self._handle_trade_signal

    def register_handler(self, action_type: ActionType, handler: Callable):
        """Register a custom action handler."""
        self._handlers[action_type] = handler

    def queue_action(self, action: ExecutableAction):
        """Add an action to the execution queue."""
        # Deduplicate by description
        existing = any(a.description == action.description
                      and a.status == ExecutionStatus.PENDING
                      for a in self._action_queue)
        if not existing:
            self._action_queue.append(action)
            self._save_pending()
            logger.info(f"Queued action: {action.description[:50]}")

    def queue_from_hypothesis(self, hypothesis: Dict[str, Any]):
        """Convert an observation hypothesis to an executable action."""
        try:
            category = hypothesis.get("category", "")
            confidence = hypothesis.get("confidence", 0.5)

            # Map hypothesis categories to action types
            category_map = {
                "command_alias": ActionType.SHELL_COMMAND,
                "error_fix": ActionType.SEND_ALERT,
                "workflow": ActionType.CREATE_CONTENT,
                "trading_pattern": ActionType.TRADE_SIGNAL,
            }

            action_type = category_map.get(category, ActionType.MEMORY_UPDATE)

            action = ExecutableAction(
                action_id=f"hyp_{int(time.time())}_{hash(hypothesis.get('description', '')) % 10000}",
                action_type=action_type,
                description=hypothesis.get("description", ""),
                parameters=hypothesis.get("proposal", {}),
                source="observation",
                confidence=confidence,
                priority=int(confidence * 10),
                created_at=time.time()
            )

            self.queue_action(action)

        except Exception as e:
            logger.error(f"Failed to queue from hypothesis: {e}")

    def queue_from_memory_goal(self, goal: Dict[str, Any], action: Dict[str, Any]):
        """Convert a memory-driven goal/action to executable action."""
        try:
            title = action.get("title", "")

            # Determine action type from title
            title_lower = title.lower()
            if "research" in title_lower:
                action_type = ActionType.RESEARCH_TOPIC
            elif "tweet" in title_lower or "post" in title_lower:
                action_type = ActionType.POST_TWEET
            elif "alert" in title_lower or "notify" in title_lower:
                action_type = ActionType.SEND_ALERT
            elif "trade" in title_lower or "buy" in title_lower or "sell" in title_lower:
                action_type = ActionType.TRADE_SIGNAL
            else:
                action_type = ActionType.CREATE_CONTENT

            executable = ExecutableAction(
                action_id=action.get("id", f"mem_{int(time.time())}"),
                action_type=action_type,
                description=action.get("description", title),
                parameters={
                    "goal_id": goal.get("id"),
                    "goal_title": goal.get("title"),
                    "action_title": title
                },
                source="memory",
                confidence=0.8,  # Memory-driven actions have high confidence
                priority=action.get("priority", 5),
                created_at=time.time()
            )

            self.queue_action(executable)

        except Exception as e:
            logger.error(f"Failed to queue from memory goal: {e}")

    async def process_queue(self) -> List[Dict[str, Any]]:
        """Process pending actions in the queue."""
        results = []
        now = time.time()

        # Cooldown check
        if now - self._last_execution < self._cooldown:
            return results

        # Sort by priority and confidence
        pending = [a for a in self._action_queue
                   if a.status == ExecutionStatus.PENDING
                   and (a.execute_after is None or now >= a.execute_after)]

        pending.sort(key=lambda a: (-a.priority, -a.confidence))

        for action in pending[:3]:  # Process max 3 per cycle
            result = await self._execute_action(action)
            results.append(result)
            self._last_execution = time.time()

            # Brief pause between actions
            await asyncio.sleep(1)

        self._save_pending()
        return results

    async def _execute_action(self, action: ExecutableAction) -> Dict[str, Any]:
        """Execute a single action."""
        logger.info(f"Executing: {action.description[:50]} ({action.action_type.value})")
        action.status = ExecutionStatus.RUNNING

        try:
            handler = self._handlers.get(action.action_type)
            if handler:
                result = await handler(action)
                action.status = ExecutionStatus.SUCCESS
                action.result = result
                self._execution_count += 1
            else:
                logger.warning(f"No handler for action type: {action.action_type}")
                action.status = ExecutionStatus.SKIPPED
                action.result = {"error": "No handler registered"}

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            action.status = ExecutionStatus.FAILED
            action.result = {"error": str(e)}

        self._log_execution(action)
        return action.to_dict()

    # =========================================================================
    # Action Handlers
    # =========================================================================

    async def _handle_post_tweet(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle tweet posting action."""
        try:
            from bots.twitter.autonomous_engine import get_autonomous_engine
            engine = get_autonomous_engine()

            params = action.parameters
            content_type = params.get("content_type", "market_update")

            # Generate and post using the engine
            if content_type == "token":
                draft = await engine.generate_trending_token_call(
                    specific_token=params.get("token")
                )
            elif content_type == "agentic":
                draft = await engine.generate_agentic_thought()
            elif content_type == "sentiment":
                draft = await engine.generate_social_sentiment_tweet()
            else:
                draft = await engine.generate_market_update()

            if draft:
                tweet_id = await engine.post_tweet(draft)
                if tweet_id:
                    return {"success": True, "tweet_id": tweet_id}

            return {"success": False, "error": "No content generated"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_send_alert(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle alert/notification action."""
        try:
            import aiohttp
            import os

            params = action.parameters
            message = params.get("message", action.description)

            # Send to Telegram
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_BUY_BOT_CHAT_ID")

            if bot_token and chat_id:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json={
                        "chat_id": chat_id,
                        "text": f"[Auto Alert]\n{message}",
                        "parse_mode": "HTML"
                    }) as resp:
                        result = await resp.json()
                        return {"success": result.get("ok", False)}

            return {"success": False, "error": "No Telegram credentials"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_research(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle research action."""
        try:
            from core.autonomous_learner import research_topic

            params = action.parameters
            topic = params.get("topic", action.description)

            result = research_topic(topic)
            return {"success": True, "research": result}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_create_content(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle content creation action."""
        try:
            params = action.parameters
            content_type = params.get("type", "insight")
            topic = params.get("topic", action.description)

            # Store as pending content idea
            content_file = DATA_DIR / "content_ideas.jsonl"
            with open(content_file, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "type": content_type,
                    "topic": topic,
                    "source": action.source,
                    "confidence": action.confidence
                }) + "\n")

            return {"success": True, "stored": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_engagement(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle engagement action (reply, like, etc.)."""
        try:
            from bots.twitter.autonomous_engine import get_autonomous_engine
            engine = get_autonomous_engine()

            # Generate engagement content
            draft = await engine.generate_interaction_tweet()
            if draft:
                tweet_id = await engine.post_tweet(draft)
                return {"success": bool(tweet_id), "tweet_id": tweet_id}

            return {"success": False, "error": "No engagement content"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_memory_update(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle memory update action."""
        try:
            from core.memory_driven_behavior import get_memory_behavior_engine
            engine = get_memory_behavior_engine()

            params = action.parameters

            # Record as a learning
            engine.working_set.record_memory_decision(
                decision_type="autonomous_learning",
                memory_context=action.description,
                decision=f"Learned from {action.source}",
                confidence=action.confidence
            )

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_trade_signal(self, action: ExecutableAction) -> Dict[str, Any]:
        """Handle trade signal action - logs only, doesn't execute trades."""
        try:
            params = action.parameters

            # Log the signal without executing
            signal_file = DATA_DIR / "trade_signals.jsonl"
            with open(signal_file, "a") as f:
                f.write(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "signal": params,
                    "description": action.description,
                    "confidence": action.confidence,
                    "source": action.source,
                    "action": "logged_only"  # We don't auto-trade
                }) + "\n")

            # Optionally alert
            if action.confidence >= 0.8:
                await self._handle_send_alert(ExecutableAction(
                    action_id=f"alert_{action.action_id}",
                    action_type=ActionType.SEND_ALERT,
                    description=f"High confidence signal: {action.description}",
                    parameters={"message": f"Trade Signal ({action.confidence:.0%}): {action.description}"},
                    source="trade_signal",
                    confidence=action.confidence,
                    priority=9,
                    created_at=time.time()
                ))

            return {"success": True, "logged": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # Integration Methods
    # =========================================================================

    async def sync_from_observation_daemon(self):
        """Pull hypotheses from ObservationalDaemon and queue them."""
        try:
            from core.observation_daemon import get_daemon
            daemon = get_daemon()

            if daemon:
                queued = daemon.get_queued_improvements()
                for hypothesis in queued:
                    if hypothesis.confidence >= 0.6:
                        self.queue_from_hypothesis(asdict(hypothesis))

                logger.info(f"Synced {len(queued)} hypotheses from daemon")

        except Exception as e:
            logger.error(f"Failed to sync from daemon: {e}")

    async def sync_from_memory_engine(self):
        """Pull pending actions from MemoryDrivenBehaviorEngine."""
        try:
            from core.memory_driven_behavior import get_memory_behavior_engine
            engine = get_memory_behavior_engine()

            # Get pending actions
            from core.memory_driven_behavior import TaskStatus
            pending = engine.working_set.get_next_actions(TaskStatus.PENDING, limit=10)

            # Get active goals for context
            goals = engine.working_set.get_active_goals()
            goals_by_id = {g.id: g for g in goals}

            for action in pending:
                goal = goals_by_id.get(action.goal_id)
                if goal:
                    self.queue_from_memory_goal(goal.to_dict(), action.to_dict())

            logger.info(f"Synced {len(pending)} actions from memory engine")

        except Exception as e:
            logger.error(f"Failed to sync from memory engine: {e}")

    async def run_continuous(self, interval: int = 60):
        """Run the executor continuously."""
        self._running = True
        logger.info("Action executor starting continuous loop")

        while self._running:
            try:
                # Sync from sources
                await self.sync_from_observation_daemon()
                await self.sync_from_memory_engine()

                # Process queue
                results = await self.process_queue()

                if results:
                    logger.info(f"Processed {len(results)} actions")

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Executor loop error: {e}")
                await asyncio.sleep(30)

        logger.info("Action executor stopped")

    def stop(self):
        """Stop the executor."""
        self._running = False

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        pending = len([a for a in self._action_queue
                      if a.status == ExecutionStatus.PENDING])
        completed = len([a for a in self._action_queue
                        if a.status == ExecutionStatus.SUCCESS])
        failed = len([a for a in self._action_queue
                     if a.status == ExecutionStatus.FAILED])

        return {
            "total_queued": len(self._action_queue),
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "execution_count": self._execution_count,
            "last_execution": datetime.fromtimestamp(self._last_execution).isoformat()
                if self._last_execution > 0 else None
        }


# Singleton
_action_executor: Optional[ActionExecutor] = None


def get_action_executor() -> ActionExecutor:
    """Get singleton action executor instance."""
    global _action_executor
    if _action_executor is None:
        _action_executor = ActionExecutor()
    return _action_executor


async def start_executor():
    """Start the action executor as a background task."""
    executor = get_action_executor()
    await executor.run_continuous()
