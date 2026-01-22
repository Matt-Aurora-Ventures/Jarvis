"""
Tool Contract - Defines strict schemas for tool inputs and outputs.
"""

import functools
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, get_type_hints
import inspect

T = TypeVar("T")


class ToolCategory(Enum):
    """Categories of tools by side effect."""
    READ_ONLY = "read_only"       # No side effects
    WRITE = "write"               # Creates/modifies data
    EXTERNAL_API = "external_api" # Calls external services
    FINANCIAL = "financial"       # Involves money/tokens
    BROADCAST = "broadcast"       # Sends to multiple recipients


@dataclass
class ToolContract:
    """
    Contract defining a tool's interface.

    Every tool must have a contract specifying:
    - What inputs it accepts
    - What outputs it produces
    - What side effects it has
    - How it can fail
    """
    name: str
    description: str
    version: str = "1.0.0"

    # Schema
    input_schema: Dict[str, Type] = field(default_factory=dict)
    output_schema: Dict[str, Type] = field(default_factory=dict)
    required_inputs: List[str] = field(default_factory=list)
    optional_inputs: Dict[str, Any] = field(default_factory=dict)

    # Side effects
    category: ToolCategory = ToolCategory.READ_ONLY
    side_effects: List[str] = field(default_factory=list)
    modifies: List[str] = field(default_factory=list)  # What resources it modifies

    # Failure modes
    failure_modes: List[str] = field(default_factory=list)
    retry_safe: bool = True  # Safe to retry on failure

    # Cost
    cost_estimate: float = 0.0
    latency_estimate_ms: float = 100.0

    # Metadata
    tags: List[str] = field(default_factory=list)
    requires_approval: bool = False

    def validate_inputs(self, inputs: Dict[str, Any]) -> tuple[bool, str]:
        """Validate inputs against the schema."""
        # Check required inputs
        for required in self.required_inputs:
            if required not in inputs:
                return False, f"Missing required input: {required}"

        # Check types
        for name, value in inputs.items():
            if name in self.input_schema:
                expected_type = self.input_schema[name]
                if not isinstance(value, expected_type):
                    return False, f"Invalid type for {name}: expected {expected_type.__name__}, got {type(value).__name__}"

        return True, "Valid"

    def validate_outputs(self, outputs: Dict[str, Any]) -> tuple[bool, str]:
        """Validate outputs against the schema."""
        for name, expected_type in self.output_schema.items():
            if name not in outputs:
                return False, f"Missing output: {name}"
            if not isinstance(outputs[name], expected_type):
                return False, f"Invalid type for {name}: expected {expected_type.__name__}"

        return True, "Valid"


@dataclass
class ToolCall:
    """
    Record of a tool invocation.

    Stores all information needed to:
    - Audit the call
    - Replay the call
    - Debug issues
    """
    id: str
    tool_name: str
    inputs: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Caller info
    caller_id: Optional[str] = None
    caller_component: Optional[str] = None
    session_id: Optional[str] = None

    # For deduplication
    input_hash: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.input_hash:
            self.input_hash = hashlib.sha256(
                json.dumps(self.inputs, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_name": self.tool_name,
            "inputs": self.inputs,
            "timestamp": self.timestamp.isoformat(),
            "caller_id": self.caller_id,
            "caller_component": self.caller_component,
            "session_id": self.session_id,
            "input_hash": self.input_hash,
        }


@dataclass
class ToolResult:
    """
    Result of a tool invocation.
    """
    call_id: str
    success: bool
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_type: Optional[str] = None

    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0

    # Cost tracking
    actual_cost: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "success": self.success,
            "outputs": self.outputs,
            "error": self.error,
            "error_type": self.error_type,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "actual_cost": self.actual_cost,
        }


def Tool(
    name: str,
    description: str,
    inputs: Optional[Dict[str, Type]] = None,
    outputs: Optional[Dict[str, Type]] = None,
    side_effects: Optional[List[str]] = None,
    category: ToolCategory = ToolCategory.READ_ONLY,
    cost_estimate: float = 0.0,
    retry_safe: bool = True,
    requires_approval: bool = False,
    version: str = "1.0.0",
):
    """
    Decorator to define a tool with a contract.

    Usage:
        @Tool(
            name="get_price",
            description="Get token price",
            inputs={"token": str},
            outputs={"price": float},
        )
        async def get_price(token: str) -> dict:
            return {"price": 100.0}
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Extract input schema from type hints if not provided
        type_hints = get_type_hints(func)
        sig = inspect.signature(func)

        input_schema = inputs or {}
        if not input_schema:
            for param_name, param in sig.parameters.items():
                if param_name != "return" and param_name in type_hints:
                    input_schema[param_name] = type_hints[param_name]

        # Determine required vs optional inputs
        required = []
        optional_defaults = {}
        for param_name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            else:
                optional_defaults[param_name] = param.default

        # Create contract
        contract = ToolContract(
            name=name,
            description=description,
            version=version,
            input_schema=input_schema,
            output_schema=outputs or {},
            required_inputs=required,
            optional_inputs=optional_defaults,
            category=category,
            side_effects=side_effects or [],
            cost_estimate=cost_estimate,
            retry_safe=retry_safe,
            requires_approval=requires_approval,
        )

        # Attach contract to function
        func._tool_contract = contract

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Validate inputs
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            is_valid, reason = contract.validate_inputs(dict(bound_args.arguments))
            if not is_valid:
                raise ValueError(f"Invalid tool inputs: {reason}")

            # Execute
            result = await func(*args, **kwargs)

            # Validate outputs (if dict)
            if isinstance(result, dict) and contract.output_schema:
                is_valid, reason = contract.validate_outputs(result)
                if not is_valid:
                    raise ValueError(f"Invalid tool outputs: {reason}")

            return result

        return wrapper

    return decorator


def get_contract(func: Callable) -> Optional[ToolContract]:
    """Get the contract for a tool function."""
    return getattr(func, "_tool_contract", None)
