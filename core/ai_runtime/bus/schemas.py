"""
Message Bus Schemas

Defines valid message types and their expected payloads.
"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class MessageSchema:
    """Schema definition for bus messages."""

    msg_type: str
    required_fields: List[str]
    optional_fields: List[str]

    def validate(self, payload: Dict[str, Any]) -> bool:
        """Validate that payload matches schema."""
        for field in self.required_fields:
            if field not in payload:
                return False
        return True


# Define valid message schemas
SCHEMAS = {
    "insight": MessageSchema(
        msg_type="insight",
        required_fields=["agent", "insight"],
        optional_fields=["evidence", "confidence"],
    ),
    "request": MessageSchema(
        msg_type="request",
        required_fields=["request_type", "params"],
        optional_fields=["timeout"],
    ),
    "response": MessageSchema(
        msg_type="response",
        required_fields=["request_id", "result"],
        optional_fields=["error"],
    ),
    "error": MessageSchema(
        msg_type="error",
        required_fields=["error_type", "message"],
        optional_fields=["traceback", "component"],
    ),
}


def validate_message_payload(msg_type: str, payload: Dict[str, Any]) -> bool:
    """Validate a message payload against its schema."""
    schema = SCHEMAS.get(msg_type)
    if not schema:
        return False
    return schema.validate(payload)
