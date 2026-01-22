"""
Tool Registry - Central registry for all tools with execution and logging.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .contract import (
    Tool,
    ToolContract,
    ToolCall,
    ToolResult,
    ToolCategory,
    get_contract,
)
from .replay import get_call_log

logger = logging.getLogger(__name__)

# Singleton instance
_registry: Optional["ToolRegistry"] = None


class ToolRegistry:
    """
    Central registry for all tools.

    Provides:
    - Tool registration and discovery
    - Execution with logging
    - Cost tracking
    - Approval gating
    """

    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.contracts: Dict[str, ToolContract] = {}
        self.stats: Dict[str, Dict[str, Any]] = {}

        # Approval callbacks
        self._approval_callbacks: List[Callable] = []

    def register(self, func: Callable) -> Callable:
        """Register a tool function."""
        contract = get_contract(func)
        if not contract:
            raise ValueError(f"Function {func.__name__} has no @Tool decorator")

        self.tools[contract.name] = func
        self.contracts[contract.name] = contract
        self.stats[contract.name] = {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "total_cost": 0.0,
            "total_duration_ms": 0.0,
        }

        logger.info(f"Registered tool: {contract.name} v{contract.version}")
        return func

    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self.tools.get(name)

    def get_contract(self, name: str) -> Optional[ToolContract]:
        """Get a tool's contract."""
        return self.contracts.get(name)

    def list_tools(
        self,
        category: Optional[ToolCategory] = None,
        tag: Optional[str] = None,
    ) -> List[str]:
        """List registered tools, optionally filtered."""
        tools = []
        for name, contract in self.contracts.items():
            if category and contract.category != category:
                continue
            if tag and tag not in contract.tags:
                continue
            tools.append(name)
        return tools

    def on_approval_required(self, callback: Callable) -> None:
        """Register a callback for when approval is required."""
        self._approval_callbacks.append(callback)

    async def execute(
        self,
        tool_name: str,
        caller_id: Optional[str] = None,
        caller_component: Optional[str] = None,
        session_id: Optional[str] = None,
        skip_approval: bool = False,
        **inputs,
    ) -> ToolResult:
        """
        Execute a tool with full logging.

        Returns a ToolResult with the outputs or error.
        """
        call_log = get_call_log()

        # Check tool exists
        tool = self.tools.get(tool_name)
        contract = self.contracts.get(tool_name)
        if not tool or not contract:
            return ToolResult(
                call_id="",
                success=False,
                error=f"Unknown tool: {tool_name}",
                error_type="ToolNotFound",
            )

        # Validate inputs
        is_valid, reason = contract.validate_inputs(inputs)
        if not is_valid:
            return ToolResult(
                call_id="",
                success=False,
                error=reason,
                error_type="ValidationError",
            )

        # Create call record
        call = ToolCall(
            id="",  # Will be auto-generated
            tool_name=tool_name,
            inputs=inputs,
            caller_id=caller_id,
            caller_component=caller_component,
            session_id=session_id,
        )

        # Check approval
        if contract.requires_approval and not skip_approval:
            approved = await self._request_approval(call, contract)
            if not approved:
                return ToolResult(
                    call_id=call.id,
                    success=False,
                    error="Approval denied",
                    error_type="ApprovalDenied",
                )

        # Log the call
        await call_log.log_call(call)

        # Execute
        result = ToolResult(
            call_id=call.id,
            success=False,
            started_at=datetime.utcnow(),
        )

        start_time = time.time()

        try:
            outputs = await tool(**inputs)

            result.success = True
            result.outputs = outputs if isinstance(outputs, dict) else {"result": outputs}
            result.actual_cost = contract.cost_estimate

            # Update stats
            self.stats[tool_name]["calls"] += 1
            self.stats[tool_name]["successes"] += 1
            self.stats[tool_name]["total_cost"] += result.actual_cost

        except Exception as e:
            result.success = False
            result.error = str(e)
            result.error_type = type(e).__name__

            # Update stats
            self.stats[tool_name]["calls"] += 1
            self.stats[tool_name]["failures"] += 1

            logger.error(f"Tool {tool_name} failed: {e}")

        finally:
            result.completed_at = datetime.utcnow()
            result.duration_ms = (time.time() - start_time) * 1000
            self.stats[tool_name]["total_duration_ms"] += result.duration_ms

            # Log the result
            await call_log.log_result(result)

        return result

    async def _request_approval(
        self,
        call: ToolCall,
        contract: ToolContract,
    ) -> bool:
        """Request approval for a tool call."""
        for callback in self._approval_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    approved = await callback(call, contract)
                else:
                    approved = callback(call, contract)

                if not approved:
                    return False
            except Exception as e:
                logger.error(f"Approval callback error: {e}")
                return False

        return True

    async def replay(
        self,
        call_id: str,
    ) -> Optional[ToolResult]:
        """Replay a previous tool call."""
        call_log = get_call_log()

        # Get the original call
        call = await call_log.get_call(call_id)
        if not call:
            return None

        # Re-execute with same inputs
        return await self.execute(
            tool_name=call.tool_name,
            caller_id=call.caller_id,
            caller_component=call.caller_component,
            session_id=call.session_id,
            skip_approval=True,  # Already approved originally
            **call.inputs,
        )

    def get_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """Get execution statistics."""
        if tool_name:
            return self.stats.get(tool_name, {})
        return self.stats.copy()

    def describe(self, tool_name: str) -> Optional[str]:
        """Get a human-readable description of a tool."""
        contract = self.contracts.get(tool_name)
        if not contract:
            return None

        lines = [
            f"*{contract.name}* v{contract.version}",
            contract.description,
            "",
            "*Inputs:*",
        ]

        for name, typ in contract.input_schema.items():
            required = "required" if name in contract.required_inputs else "optional"
            lines.append(f"  • {name}: {typ.__name__} ({required})")

        if contract.output_schema:
            lines.append("\n*Outputs:*")
            for name, typ in contract.output_schema.items():
                lines.append(f"  • {name}: {typ.__name__}")

        if contract.side_effects:
            lines.append("\n*Side Effects:*")
            for effect in contract.side_effects:
                lines.append(f"  ⚠️ {effect}")

        lines.append(f"\n*Category:* {contract.category.value}")
        lines.append(f"*Cost:* ${contract.cost_estimate:.4f}")
        lines.append(f"*Retry Safe:* {'Yes' if contract.retry_safe else 'No'}")

        return "\n".join(lines)


def get_tool_registry() -> ToolRegistry:
    """Get or create the singleton tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
