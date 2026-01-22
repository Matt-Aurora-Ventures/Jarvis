"""
Agent Capabilities Definitions

Defines what each agent type is allowed to do.
"""
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AgentCapabilities:
    """What an agent is allowed to do."""

    can_observe: bool = True
    can_suggest: bool = True
    can_write_code: bool = False
    can_execute_shell: bool = False
    can_access_secrets: bool = False
    can_modify_files: bool = False
    can_send_messages: bool = False  # External messages (email, telegram, etc)

    def to_prompt_text(self) -> str:
        """Generate capability description for agent's system prompt."""
        allowed = []
        forbidden = []

        for cap, enabled in [
            ("observe application behavior and logs", self.can_observe),
            ("suggest improvements", self.can_suggest),
            ("write or modify code", self.can_write_code),
            ("execute shell commands", self.can_execute_shell),
            ("access secrets or credentials", self.can_access_secrets),
            ("modify files directly", self.can_modify_files),
            ("send external messages", self.can_send_messages),
        ]:
            if enabled:
                allowed.append(cap)
            else:
                forbidden.append(cap)

        return f"""
ALLOWED ACTIONS:
{chr(10).join(f"- {a}" for a in allowed)}

FORBIDDEN ACTIONS (you must NEVER attempt these):
{chr(10).join(f"- {f}" for f in forbidden)}
"""

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary for serialization."""
        return {
            "can_observe": self.can_observe,
            "can_suggest": self.can_suggest,
            "can_write_code": self.can_write_code,
            "can_execute_shell": self.can_execute_shell,
            "can_access_secrets": self.can_access_secrets,
            "can_modify_files": self.can_modify_files,
            "can_send_messages": self.can_send_messages,
        }


# Predefined capability sets
TELEGRAM_AGENT_CAPABILITIES = AgentCapabilities(
    can_observe=True,
    can_suggest=True,
    can_write_code=False,
    can_execute_shell=False,
    can_access_secrets=False,
    can_modify_files=False,
    can_send_messages=False,
)

API_AGENT_CAPABILITIES = AgentCapabilities(
    can_observe=True,
    can_suggest=True,
    can_write_code=False,
    can_execute_shell=False,
    can_access_secrets=False,
    can_modify_files=False,
    can_send_messages=False,
)

WEB_AGENT_CAPABILITIES = AgentCapabilities(
    can_observe=True,
    can_suggest=True,
    can_write_code=False,
    can_execute_shell=False,
    can_access_secrets=False,
    can_modify_files=False,
    can_send_messages=False,
)

SUPERVISOR_CAPABILITIES = AgentCapabilities(
    can_observe=True,
    can_suggest=True,
    can_write_code=False,
    can_execute_shell=False,
    can_access_secrets=False,
    can_modify_files=False,
    can_send_messages=False,
)
