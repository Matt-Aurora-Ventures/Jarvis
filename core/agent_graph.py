"""Agentic state graph for planning, execution, and reflection."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from core import agent_router, autonomous_agent, context_manager, error_recovery, memory, providers, safety, semantic_memory


@dataclass
class AgentState:
    goal: str
    context: Dict[str, Any]
    plan: Dict[str, Any] = field(default_factory=dict)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    reflections: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    cycle: int = 0
    status: str = "initialized"
    summary: str = ""


class GraphAgent:
    """Cyclic agent with planner, executor, observer, and reflector nodes."""

    def __init__(self) -> None:
        self._router = agent_router.ModelRouter()
        self._executor = autonomous_agent.AutonomousAgent()
        self._error_manager = error_recovery.get_error_manager()

    def run(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        execute: bool = False,
        max_cycles: int = 2,
        max_step_retries: int = 1,
    ) -> Dict[str, Any]:
        state = AgentState(goal=goal, context=self._build_context(goal, context))

        for cycle in range(max_cycles):
            state.cycle = cycle + 1
            state.status = "planning"
            state.plan = self._plan(state)
            state.steps = list(state.plan.get("steps", []))

            if not execute:
                state.status = "planned"
                return self._render_state(state, include_results=False)

            state.status = "executing"
            needs_replan = self._execute_steps(state, max_step_retries)
            if not needs_replan:
                break

        state.status = "completed" if state.results else "no_results"
        state.summary = self._summarize(state) if execute else ""
        return self._render_state(state, include_results=True)

    def _build_context(self, goal: str, extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        context_bundle = {
            "master": asdict(context_manager.load_master_context()),
            "activity": asdict(context_manager.load_activity_context()),
            "conversation": asdict(context_manager.load_conversation_context()),
            "memory_recent": memory.fetch_recent_entries(limit=6),
            "memory_hits": semantic_memory.search(goal),
            "provider_status": providers.provider_status(),
        }
        if extra:
            context_bundle["extra"] = extra
        return context_bundle

    def _call_model(self, role: str, prompt: str, max_output_tokens: int) -> str:
        decision = self._router.route(role, prompt)
        limit = min(max_output_tokens, decision.max_output_tokens)

        if decision.provider == "ollama" and decision.model:
            try:
                return providers.ask_ollama_model(
                    prompt,
                    model=decision.model,
                    max_output_tokens=limit,
                )
            except Exception as exc:
                self._error_manager.handle_error(
                    exc,
                    {"phase": "model_call", "provider": "ollama", "model": decision.model},
                )

        response = providers.generate_text(prompt, max_output_tokens=limit)
        if not response:
            raise RuntimeError("No model response")
        return response

    def _plan(self, state: AgentState) -> Dict[str, Any]:
        available_tools = ", ".join(sorted(self._executor.tools.keys()))
        prompt = (
            "You are the Planner node. Convert the goal into an executable JSON plan.\n"
            "Return ONLY JSON with a 'steps' array. Each step requires: description, tool, parameters, "
            "critical (true/false), expected_output.\n\n"
            f"Available tools: {available_tools}\n\n"
            f"Goal: {state.goal}\n\n"
            f"Context: {json.dumps(state.context, indent=2)[:4000]}"
        )
        try:
            response = self._call_model("planner", prompt, max_output_tokens=900)
            plan = self._parse_json(response)
            if isinstance(plan, dict) and plan.get("steps"):
                return plan
        except Exception as exc:
            self._error_manager.handle_error(exc, {"phase": "plan", "goal": state.goal})

        return {
            "steps": [
                {
                    "description": "Gather high-level context about the goal",
                    "tool": "web_search",
                    "parameters": {"query": state.goal},
                    "critical": True,
                    "expected_output": "search results",
                }
            ]
        }

    def _execute_steps(self, state: AgentState, max_step_retries: int) -> bool:
        for step in state.steps:
            attempts = 0
            while attempts <= max_step_retries:
                try:
                    result = self._executor._execute_step(step, state.context)
                except Exception as exc:
                    self._error_manager.handle_error(exc, {"phase": "execute", "step": step})
                    result = {
                        "status": "failed",
                        "error": str(exc),
                        "tool": step.get("tool", "unknown"),
                        "parameters": step.get("parameters", {}),
                    }

                tool_name = result.get("tool") or step.get("tool", "unknown")
                state.context.setdefault("tool_results", []).append(result)
                state.context["last_result"] = result
                if result.get("status") in {"success", "healed_success"}:
                    state.context.pop("last_error", None)
                else:
                    state.context["last_error"] = result.get("error", "step_failed")
                context_manager.add_action_result(
                    f"tool:{tool_name}",
                    result.get("status") in {"success", "healed_success"},
                    self._summarize_result(result),
                )

                state.results.append(result)
                if result.get("status") in {"success", "healed_success"}:
                    break

                attempts += 1
                reflection = self._reflect(step, result, state)
                state.reflections.append(reflection)

                action = str(reflection.get("action", "abort")).lower()
                if action == "retry" and attempts <= max_step_retries:
                    continue
                if action == "update_step":
                    updated_step = reflection.get("updated_step")
                    if isinstance(updated_step, dict):
                        step = updated_step
                        continue
                if action == "replan":
                    state.status = "replan"
                    return True

                state.errors.append(result.get("error", "step_failed"))
                if step.get("critical"):
                    return False
                break

        return False

    def _reflect(self, step: Dict[str, Any], result: Dict[str, Any], state: AgentState) -> Dict[str, Any]:
        prompt = (
            "You are the Reflector node. Diagnose the failure and suggest next action. "
            "Return ONLY JSON with keys: action (retry|update_step|replan|abort), reason, lesson (optional), "
            "updated_step (optional).\n\n"
            f"Goal: {state.goal}\n"
            f"Step: {json.dumps(step, indent=2)}\n"
            f"Result: {json.dumps(result, indent=2)}"
        )
        try:
            response = self._call_model("reflector", prompt, max_output_tokens=600)
            reflection = self._parse_json(response)
            if isinstance(reflection, dict) and reflection.get("action"):
                lesson = str(reflection.get("lesson", "")).strip()
                if lesson:
                    memory.append_entry(
                        lesson,
                        source="reflection",
                        context=safety.SafetyContext(apply=True, dry_run=False),
                    )
                return reflection
        except Exception as exc:
            self._error_manager.handle_error(exc, {"phase": "reflect", "step": step})

        return {
            "action": "abort",
            "reason": "reflection_failed",
        }

    def _summarize(self, state: AgentState) -> str:
        prompt = (
            "Summarize the execution results for the user. Keep it concise and actionable.\n\n"
            f"Goal: {state.goal}\n"
            f"Results: {json.dumps(state.results, indent=2)[:4000]}"
        )
        try:
            return self._call_model("observer", prompt, max_output_tokens=300)
        except Exception as exc:
            self._error_manager.handle_error(exc, {"phase": "summarize", "goal": state.goal})
            return "Summary unavailable."

    @staticmethod
    def _summarize_result(result: Dict[str, Any]) -> str:
        payload = result.get("error") or result.get("result") or ""
        if not payload:
            payload = result
        if isinstance(payload, (dict, list)):
            return json.dumps(payload)[:200]
        return str(payload)[:200]

    def _parse_json(self, text: str) -> Optional[Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        payload = self._extract_json_object(text)
        if payload:
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
        return None

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        if not text:
            return None
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for idx in range(start, len(text)):
            if text[idx] == "{":
                depth += 1
            elif text[idx] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
        return None


    def _render_state(self, state: AgentState, include_results: bool) -> Dict[str, Any]:
        payload = {
            "goal": state.goal,
            "status": state.status,
            "cycle": state.cycle,
            "plan": state.plan,
            "errors": state.errors,
        }
        if include_results:
            payload.update(
                {
                    "results": state.results,
                    "reflections": state.reflections,
                    "summary": getattr(state, "summary", ""),
                }
            )
        return payload
