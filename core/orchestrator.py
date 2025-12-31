"""
Orchestrator: The Jarvis Brain.

A single continuous loop that:
1. OBSERVE - What's happening?
2. INTERPRET - What does it mean?
3. PLAN - What should I do?
4. ACT - Execute with discipline
5. REVIEW - Did it work?
6. LEARN - Update knowledge

Key principles:
- One active objective at a time
- Every action has explicit "why" and success criteria
- Post-action learning closes the feedback loop
- Cooldowns prevent thrashing
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core import config, objectives, memory, safety, state
from core.objectives import Objective, ObjectiveStatus, ObjectiveSource

# Agent imports (lazy to avoid circular imports)
_agent_registry = None

def _get_agent_registry():
    """Lazy load agent registry."""
    global _agent_registry
    if _agent_registry is None:
        try:
            from core.agents.registry import initialize_agents
            _agent_registry = initialize_agents()
        except Exception:
            _agent_registry = None
    return _agent_registry


ROOT = Path(__file__).resolve().parents[1]
BRAIN_LOG = ROOT / "data" / "brain" / "loop_log.jsonl"


class LoopPhase(str, Enum):
    OBSERVE = "observe"
    INTERPRET = "interpret"
    PLAN = "plan"
    ACT = "act"
    REVIEW = "review"
    LEARN = "learn"
    IDLE = "idle"


@dataclass
class Observation:
    """What the system observes about current state."""
    timestamp: float
    active_app: str = ""
    idle_seconds: float = 0
    pending_objectives: int = 0
    active_objective: Optional[str] = None
    user_input: Optional[str] = None
    system_events: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Interpretation:
    """What the observation means."""
    should_act: bool
    reason: str
    urgency: int = 5  # 1-10
    suggested_action: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """What action to take."""
    objective_id: str
    action_name: str
    action_params: Dict[str, Any]
    expected_outcome: str
    success_criteria: List[str]
    why: str  # Explicit reasoning
    fallback: Optional[str] = None


@dataclass
class ActionResult:
    """Result of executing an action."""
    success: bool
    output: str
    error: str = ""
    duration_ms: int = 0
    side_effects: List[str] = field(default_factory=list)


@dataclass
class Review:
    """Post-action review."""
    plan: Plan
    result: ActionResult
    criteria_met: List[bool]
    overall_success: bool
    gap_analysis: str = ""


@dataclass
class Learning:
    """What we learned from this cycle."""
    timestamp: float
    objective_id: str
    action: str
    success: bool
    insight: str
    should_remember: bool = False


@dataclass
class LoopState:
    """Current state of the brain loop."""
    phase: LoopPhase
    cycle_count: int
    last_action_at: float
    cooldown_until: float
    errors_in_row: int
    current_objective: Optional[str]


class Orchestrator:
    """
    The Jarvis Brain - single loop coordinating all action.

    Usage:
        orchestrator = Orchestrator()
        orchestrator.start()  # Runs in background thread
        # or
        orchestrator.run_loop()  # Blocks
    """

    def __init__(
        self,
        min_cooldown_seconds: float = 2.0,
        max_cooldown_seconds: float = 60.0,
        max_errors_before_pause: int = 5,
    ):
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Configuration
        self.min_cooldown = min_cooldown_seconds
        self.max_cooldown = max_cooldown_seconds
        self.max_errors = max_errors_before_pause

        # State
        self._state = LoopState(
            phase=LoopPhase.IDLE,
            cycle_count=0,
            last_action_at=0,
            cooldown_until=0,
            errors_in_row=0,
            current_objective=None,
        )

        # Pluggable components (set these to customize behavior)
        self.observer: Optional[Callable[[], Observation]] = None
        self.interpreter: Optional[Callable[[Observation], Interpretation]] = None
        self.planner: Optional[Callable[[Objective, Observation], Plan]] = None
        self.executor: Optional[Callable[[Plan], ActionResult]] = None
        self.reviewer: Optional[Callable[[Plan, ActionResult], Review]] = None
        self.learner: Optional[Callable[[Review], Learning]] = None

        # Ensure log directory
        BRAIN_LOG.parent.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Start the brain loop in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self.run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the brain loop."""
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def run_loop(self) -> None:
        """Main brain loop. Blocks until stopped."""
        self._log_event("brain_start", {"cycle": self._state.cycle_count})

        while self.running:
            try:
                self._run_single_cycle()
            except Exception as e:
                self._handle_error(e)

            # Respect cooldown
            self._wait_cooldown()

        self._log_event("brain_stop", {"cycle": self._state.cycle_count})

    def _run_single_cycle(self) -> None:
        """Execute one complete brain cycle."""
        self._state.cycle_count += 1
        cycle_start = time.time()

        # 1. OBSERVE
        self._state.phase = LoopPhase.OBSERVE
        observation = self._observe()

        # 2. INTERPRET
        self._state.phase = LoopPhase.INTERPRET
        interpretation = self._interpret(observation)

        if not interpretation.should_act:
            self._state.phase = LoopPhase.IDLE
            self._set_cooldown(self.min_cooldown)
            return

        # 3. PLAN
        self._state.phase = LoopPhase.PLAN
        objective = self._get_or_activate_objective()
        if not objective:
            self._state.phase = LoopPhase.IDLE
            self._set_cooldown(self.min_cooldown)
            return

        plan = self._plan(objective, observation)
        if not plan:
            self._state.phase = LoopPhase.IDLE
            return

        # 4. ACT
        self._state.phase = LoopPhase.ACT
        result = self._act(plan)
        self._state.last_action_at = time.time()

        # 5. REVIEW
        self._state.phase = LoopPhase.REVIEW
        review = self._review(plan, result)

        # 6. LEARN
        self._state.phase = LoopPhase.LEARN
        learning = self._learn(review)

        # Update objective based on outcome
        self._update_objective(objective, review)

        # Log cycle completion
        cycle_duration = int((time.time() - cycle_start) * 1000)
        self._log_event("cycle_complete", {
            "cycle": self._state.cycle_count,
            "duration_ms": cycle_duration,
            "success": review.overall_success,
            "objective": objective.id,
            "action": plan.action_name,
        })

        # Adjust cooldown based on outcome
        if review.overall_success:
            self._state.errors_in_row = 0
            self._set_cooldown(self.min_cooldown)
        else:
            self._state.errors_in_row += 1
            backoff = min(
                self.max_cooldown,
                self.min_cooldown * (2 ** self._state.errors_in_row)
            )
            self._set_cooldown(backoff)

    def _observe(self) -> Observation:
        """Gather observations about current state."""
        if self.observer:
            return self.observer()

        # Default observation
        obj_manager = objectives.get_manager()
        active = obj_manager.get_active()
        queue = obj_manager.get_queue(limit=5)

        # Try to get system state
        current_state = state.read_state()
        idle_seconds = current_state.get("idle_seconds", 0)

        return Observation(
            timestamp=time.time(),
            active_app=current_state.get("frontmost_app", ""),
            idle_seconds=idle_seconds,
            pending_objectives=len(queue),
            active_objective=active.id if active else None,
            system_events=[],
            context={
                "running": current_state.get("running", False),
                "voice_enabled": current_state.get("voice_enabled", False),
            },
        )

    def _interpret(self, observation: Observation) -> Interpretation:
        """Interpret observation and decide whether to act."""
        if self.interpreter:
            return self.interpreter(observation)

        # Default interpretation logic
        should_act = False
        reason = "no action needed"
        urgency = 1

        # Check for user input
        if observation.user_input:
            should_act = True
            reason = "user input received"
            urgency = 10

        # Check for pending objectives
        elif observation.pending_objectives > 0 and not observation.active_objective:
            should_act = True
            reason = f"{observation.pending_objectives} objectives pending"
            urgency = 5

        # Check for active objective
        elif observation.active_objective:
            should_act = True
            reason = "continuing active objective"
            urgency = 7

        # Check idle time for background work
        elif observation.idle_seconds > 60:
            should_act = observation.pending_objectives > 0
            reason = "user idle, can do background work"
            urgency = 3

        return Interpretation(
            should_act=should_act,
            reason=reason,
            urgency=urgency,
        )

    def _get_or_activate_objective(self) -> Optional[Objective]:
        """Get active objective or activate next from queue."""
        obj_manager = objectives.get_manager()
        active = obj_manager.get_active()

        if active:
            self._state.current_objective = active.id
            return active

        # Activate next
        next_obj = obj_manager.activate_next()
        if next_obj:
            self._state.current_objective = next_obj.id
            self._log_event("objective_activated", {
                "id": next_obj.id,
                "description": next_obj.description,
                "priority": next_obj.priority,
            })
        return next_obj

    def _plan(self, objective: Objective, observation: Observation) -> Optional[Plan]:
        """Create a plan to advance the objective."""
        if self.planner:
            return self.planner(objective, observation)

        # Default: create a simple plan based on objective
        # In full implementation, this would call the LLM for planning
        return Plan(
            objective_id=objective.id,
            action_name="process_objective",
            action_params={"description": objective.description},
            expected_outcome="objective progressed",
            success_criteria=[c.description for c in objective.success_criteria],
            why=f"Advancing objective: {objective.description}",
        )

    def _act(self, plan: Plan) -> ActionResult:
        """Execute the planned action using agents or direct execution."""
        start = time.time()

        # Use custom executor if provided
        if self.executor:
            result = self.executor(plan)
            result.duration_ms = int((time.time() - start) * 1000)
            return result

        # Try to route to specialized agents
        registry = _get_agent_registry()
        if registry:
            try:
                from core.agents.base import AgentTask

                # Create agent task from plan
                agent_task = AgentTask(
                    id=f"brain_{self._state.cycle_count}",
                    objective_id=plan.objective_id,
                    description=plan.action_params.get("description", plan.why),
                    context=plan.action_params,
                    max_steps=10,
                    timeout_seconds=120,
                )

                # Route to best agent
                agent_result = registry.route_and_execute(agent_task)

                self._log_event("agent_executed", {
                    "action": plan.action_name,
                    "agent_success": agent_result.success,
                    "agent_steps": agent_result.steps_taken,
                    "duration_ms": agent_result.duration_ms,
                })

                return ActionResult(
                    success=agent_result.success,
                    output=str(agent_result.output)[:1000] if agent_result.output else "",
                    error=agent_result.error,
                    duration_ms=agent_result.duration_ms,
                    side_effects=agent_result.learnings,
                )

            except Exception as e:
                self._log_event("agent_error", {
                    "error": str(e)[:200],
                })
                # Fall through to default handling

        # Default: log that we would execute
        self._log_event("action_executed", {
            "action": plan.action_name,
            "params": plan.action_params,
            "why": plan.why,
        })

        return ActionResult(
            success=True,
            output="action logged (no agent matched)",
            duration_ms=int((time.time() - start) * 1000),
        )

    def _review(self, plan: Plan, result: ActionResult) -> Review:
        """Review the action result against expectations."""
        if self.reviewer:
            return self.reviewer(plan, result)

        # Default: simple success check
        criteria_met = [result.success] * len(plan.success_criteria)
        overall_success = result.success

        gap = ""
        if not overall_success:
            gap = f"Expected: {plan.expected_outcome}, Got: {result.error or result.output}"

        return Review(
            plan=plan,
            result=result,
            criteria_met=criteria_met,
            overall_success=overall_success,
            gap_analysis=gap,
        )

    def _learn(self, review: Review) -> Learning:
        """Extract learnings from the review."""
        if self.learner:
            return self.learner(review)

        # Default: create basic learning
        insight = ""
        should_remember = False

        if not review.overall_success:
            insight = f"Action '{review.plan.action_name}' failed: {review.gap_analysis}"
            should_remember = True
        elif review.result.duration_ms > 5000:
            insight = f"Action '{review.plan.action_name}' was slow ({review.result.duration_ms}ms)"
            should_remember = True

        learning = Learning(
            timestamp=time.time(),
            objective_id=review.plan.objective_id,
            action=review.plan.action_name,
            success=review.overall_success,
            insight=insight,
            should_remember=should_remember,
        )

        # Store learning if significant
        if should_remember:
            ctx = safety.SafetyContext(apply=True, dry_run=False)
            memory.append_entry(
                text=f"[LEARNING] {insight}",
                source="brain_learning",
                context=ctx,
            )
            self._log_event("learning_recorded", asdict(learning))

        return learning

    def _update_objective(self, objective: Objective, review: Review) -> None:
        """Update objective status based on review."""
        obj_manager = objectives.get_manager()

        # Check if all success criteria are met
        if review.overall_success and all(review.criteria_met):
            # Check if the objective itself is complete
            # This is a simplification - in reality we'd check specific criteria
            obj_manager.complete(
                objective.id,
                outcome=review.result.output,
                criteria_results={
                    c: True for c in review.plan.success_criteria
                },
            )
            self._state.current_objective = None
            self._log_event("objective_completed", {
                "id": objective.id,
                "description": objective.description,
            })

        elif not review.overall_success:
            # Increment failure count but don't fail yet
            if self._state.errors_in_row >= self.max_errors:
                obj_manager.fail(
                    objective.id,
                    reason=review.gap_analysis,
                    requeue=True,  # Allow retry
                )
                self._state.current_objective = None
                self._log_event("objective_failed", {
                    "id": objective.id,
                    "reason": review.gap_analysis,
                })

    def _set_cooldown(self, seconds: float) -> None:
        """Set cooldown until next cycle."""
        self._state.cooldown_until = time.time() + seconds

    def _wait_cooldown(self) -> None:
        """Wait until cooldown expires."""
        remaining = self._state.cooldown_until - time.time()
        if remaining > 0:
            time.sleep(min(remaining, 1.0))  # Check every second for stop signal

    def _handle_error(self, error: Exception) -> None:
        """Handle errors in the loop."""
        self._state.errors_in_row += 1
        self._log_event("loop_error", {
            "error": str(error)[:500],
            "errors_in_row": self._state.errors_in_row,
        })

        # Exponential backoff
        backoff = min(
            self.max_cooldown,
            self.min_cooldown * (2 ** self._state.errors_in_row)
        )
        self._set_cooldown(backoff)

        # Pause if too many errors
        if self._state.errors_in_row >= self.max_errors:
            self._log_event("loop_paused", {
                "reason": "too many errors",
                "errors": self._state.errors_in_row,
            })
            self._set_cooldown(self.max_cooldown * 2)

    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log an event to the brain log."""
        entry = {
            "timestamp": time.time(),
            "event": event_type,
            "cycle": self._state.cycle_count,
            "phase": self._state.phase.value,
            **data,
        }
        try:
            with open(BRAIN_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # Don't let logging failures break the loop

    def get_state(self) -> Dict[str, Any]:
        """Get current brain state for monitoring."""
        return {
            "running": self.running,
            "phase": self._state.phase.value,
            "cycle_count": self._state.cycle_count,
            "current_objective": self._state.current_objective,
            "errors_in_row": self._state.errors_in_row,
            "last_action_at": self._state.last_action_at,
            "cooldown_until": self._state.cooldown_until,
        }

    # --- Public API for external triggers ---

    def inject_user_input(self, text: str) -> None:
        """Inject user input to be processed in next cycle."""
        with self._lock:
            # Create immediate objective from user input
            obj = objectives.create_objective(
                description=text,
                success_criteria=[{
                    "description": "user request processed",
                    "metric": "response_given",
                    "target": True,
                }],
                priority=10,  # User input is highest priority
                source=ObjectiveSource.USER,
            )
            self._log_event("user_input_injected", {
                "objective_id": obj.id,
                "text": text[:200],
            })

    def inject_system_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Inject a system event for processing."""
        with self._lock:
            self._log_event("system_event_injected", {
                "event_type": event_type,
                **data,
            })


# Global instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get the global Orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


def start_brain() -> Orchestrator:
    """Start the brain loop."""
    orch = get_orchestrator()
    orch.start()
    return orch


def stop_brain() -> None:
    """Stop the brain loop."""
    if _orchestrator:
        _orchestrator.stop()


def inject_input(text: str) -> None:
    """Inject user input for processing."""
    get_orchestrator().inject_user_input(text)


def brain_status() -> Dict[str, Any]:
    """Get brain status."""
    return get_orchestrator().get_state()
