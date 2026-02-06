"""
Full Computer Control via Open Interpreter.

This gives LLMs the ability to do ANYTHING you can do on your computer:
- Run commands
- Edit files
- Control applications
- Browse the web
- Manage processes
- And more

Installation:
    pip install open-interpreter

Usage:
    from core.automation.computer_control import ComputerController, ask_computer

    # Quick usage
    result = await ask_computer("Create a new folder called 'test' on my desktop")

    # Full control
    controller = ComputerController()
    result = await controller.execute("Open notepad and type 'hello world'")
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Check for Open Interpreter
try:
    from interpreter import interpreter
    HAS_INTERPRETER = True
except ImportError:
    HAS_INTERPRETER = False
    logger.warning("Open Interpreter not installed. Run: pip install open-interpreter")


class ComputerController:
    """
    Full computer control via Open Interpreter.

    Can execute any task you could do manually:
    - File operations
    - Application control
    - System commands
    - Web browsing
    - Code execution
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        provider: str = "anthropic",
        auto_run: bool = True,
        safe_mode: bool = True,
        offline: bool = False,
    ):
        """
        Initialize computer controller.

        Args:
            model: LLM model to use
            provider: "anthropic", "openai", or "local"
            auto_run: Automatically execute code without confirmation
            safe_mode: Restrict dangerous operations
            offline: Use local models only
        """
        if not HAS_INTERPRETER:
            raise ImportError(
                "Open Interpreter required. Install with:\n"
                "pip install open-interpreter"
            )

        self.model = model
        self.provider = provider
        self.auto_run = auto_run
        self.safe_mode = safe_mode
        self.offline = offline

        self._setup_interpreter()

    def _setup_interpreter(self):
        """Configure the interpreter."""
        # Model configuration
        if self.provider == "anthropic":
            interpreter.llm.model = f"anthropic/{self.model}"
            interpreter.llm.api_key = os.getenv("ANTHROPIC_API_KEY")
        elif self.provider == "openai":
            interpreter.llm.model = f"openai/{self.model}"
            interpreter.llm.api_key = os.getenv("OPENAI_API_KEY")
        elif self.provider == "local":
            # Use local models via Ollama
            interpreter.llm.model = "ollama/codellama"
            interpreter.offline = True

        # Behavior configuration
        interpreter.auto_run = self.auto_run
        interpreter.safe_mode = "auto" if self.safe_mode else "off"

        # Computer control features
        interpreter.computer.import_computer_api = True

        # System message for Jarvis context
        interpreter.system_message = """
You are Jarvis, an AI assistant with full computer control.
You can execute any task the user requests on their computer.

Guidelines:
1. Be efficient - use the most direct approach
2. Be safe - don't delete important files without confirmation
3. Be informative - explain what you're doing
4. Use Python for complex tasks, shell for simple ones

You have access to:
- File system (read, write, delete, move)
- Applications (open, control, close)
- System commands (any shell command)
- Web browser automation
- Code execution (Python, JavaScript, shell)
"""

    async def execute(
        self,
        task: str,
        context: str = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a computer control task.

        Args:
            task: Natural language description of what to do
            context: Additional context about the task
            stream: Whether to stream output

        Returns:
            Dict with 'success', 'output', 'code_executed'
        """
        full_task = task
        if context:
            full_task = f"{task}\n\nContext: {context}"

        try:
            # Run in executor to not block async
            loop = asyncio.get_event_loop()

            if stream:
                # Streaming mode - collect chunks (do not yield to avoid async generator)
                messages = []
                for chunk in interpreter.chat(full_task, stream=True):
                    messages.append(chunk)
                output = messages
            else:
                # Non-streaming - returns complete result
                output = await loop.run_in_executor(
                    None,
                    lambda: interpreter.chat(full_task, stream=False)
                )

            return {
                'success': True,
                'output': output,
                'task': task,
            }

        except Exception as e:
            logger.error(f"Computer control error: {e}")
            return {
                'success': False,
                'error': str(e),
                'task': task,
            }

    async def chat(self, message: str) -> str:
        """
        Simple chat interface - returns just the response text.

        Useful for ClawdBots that just need a string response.
        """
        result = await self.execute(message)
        if result.get('success'):
            # Extract text from output
            output = result.get('output', [])
            if isinstance(output, list):
                text_parts = []
                for msg in output:
                    if isinstance(msg, dict) and msg.get('type') == 'message':
                        text_parts.append(msg.get('content', ''))
                return '\n'.join(text_parts)
            return str(output)
        return f"Error: {result.get('error', 'Unknown error')}"

    def reset(self):
        """Reset conversation history."""
        interpreter.messages = []


class SafeComputerController(ComputerController):
    """
    Computer controller with additional safety restrictions.

    Good for automated/unattended operations.
    """

    BLOCKED_COMMANDS = [
        'rm -rf /',
        'format',
        'del /s /q',
        'shutdown',
        'reboot',
    ]

    def __init__(self, **kwargs):
        kwargs['safe_mode'] = True
        kwargs['auto_run'] = False  # Require confirmation
        super().__init__(**kwargs)

        # Additional restrictions
        interpreter.system_message += """

SAFETY RESTRICTIONS:
- Never delete system files
- Never format drives
- Never shutdown/reboot without explicit permission
- Never access sensitive credentials
- Always confirm destructive operations
"""


# Convenience functions for ClawdBots

async def ask_computer(task: str, safe: bool = True) -> str:
    """
    Quick computer control for ClawdBots.

    Args:
        task: What to do in natural language
        safe: Use safe mode (recommended)

    Returns:
        Response string

    Usage:
        from core.automation.computer_control import ask_computer

        result = await ask_computer("What files are in my Downloads folder?")
        result = await ask_computer("Open Chrome and go to google.com")
    """
    if safe:
        controller = SafeComputerController()
    else:
        controller = ComputerController()

    return await controller.chat(task)


async def run_task(task: str) -> Dict[str, Any]:
    """
    Execute a computer task and return full result.

    Usage:
        from core.automation.computer_control import run_task

        result = await run_task("Create a Python script that prints hello world")
        if result['success']:
            print("Output:", result['output'])
    """
    controller = ComputerController()
    return await controller.execute(task)


if __name__ == "__main__":
    # Test
    async def test():
        print("Testing computer control...")
        result = await ask_computer("What is the current directory?")
        print(f"Result: {result}")

    asyncio.run(test())
