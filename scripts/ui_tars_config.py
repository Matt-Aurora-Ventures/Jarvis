"""
UI-TARS VLM Configuration

Configures the Vision-Language Model for UI-TARS browser automation.
Supports multiple providers: Qwen 2.5vl, OpenAI GPT-4V, Anthropic Claude.

Usage:
    python scripts/ui_tars_config.py --test
    python scripts/ui_tars_config.py --provider openai
    python scripts/ui_tars_config.py --provider anthropic
"""

import os
import sys
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any

# Load API keys from Claude CLI .env if available
def load_claude_env():
    """Load environment variables from Claude CLI .env file"""
    claude_env = Path.home() / ".claude" / ".env"
    if claude_env.exists():
        with open(claude_env, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if not os.getenv(key):
                        os.environ[key] = value

# Auto-load Claude CLI keys
load_claude_env()

# UI-TARS imports
try:
    from ui_tars.action_parser import parse_action_to_structure_output, parsing_response_to_pyautogui_code
    UI_TARS_AVAILABLE = True
except ImportError:
    UI_TARS_AVAILABLE = False
    print("Warning: UI-TARS not installed. Run: pip install ui-tars")


class VLMProvider:
    """Base class for VLM providers"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def analyze_screenshot(self, image_path: str, task: str) -> str:
        """Analyze screenshot and return action description"""
        raise NotImplementedError


class OpenAIVLM(VLMProvider):
    """OpenAI GPT-4V provider"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "gpt-4o"  # Latest vision model
        self.base_url = "https://api.openai.com/v1/chat/completions"

    def analyze_screenshot(self, image_path: str, task: str) -> str:
        import requests

        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine media type
        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a GUI automation assistant. Analyze the screenshot and determine what action to take.

Output the action in this format:
- click(x, y) - click at coordinates
- type(text) - type text
- scroll(direction, amount) - scroll up/down
- drag(x1, y1, x2, y2) - drag from point to point

Coordinates should be pixel positions on the screen."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Task: {task}\n\nAnalyze this screenshot and tell me what action to take."},
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}}
                        ]
                    }
                ],
                "max_tokens": 300
            }
        )

        result = response.json()
        if "error" in result:
            raise Exception(f"OpenAI API error: {result['error']}")

        return result["choices"][0]["message"]["content"]


class AnthropicVLM(VLMProvider):
    """Anthropic Claude provider with vision"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "claude-sonnet-4-6"
        self.base_url = "https://api.anthropic.com/v1/messages"

    def analyze_screenshot(self, image_path: str, task: str) -> str:
        import requests

        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine media type
        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"

        response = requests.post(
            self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "max_tokens": 300,
                "system": """You are a GUI automation assistant. Analyze the screenshot and determine what action to take.

Output the action in this format:
- click(x, y) - click at coordinates
- type(text) - type text
- scroll(direction, amount) - scroll up/down
- drag(x1, y1, x2, y2) - drag from point to point

Coordinates should be pixel positions on the screen.""",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Task: {task}\n\nAnalyze this screenshot and tell me what action to take."},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            }
                        ]
                    }
                ]
            }
        )

        result = response.json()
        if "error" in result:
            raise Exception(f"Anthropic API error: {result['error']}")

        return result["content"][0]["text"]


class XaiVLM(VLMProvider):
    """xAI Grok provider (if vision supported)"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "grok-2-vision-1212"  # Vision model
        self.base_url = "https://api.x.ai/v1/chat/completions"

    def analyze_screenshot(self, image_path: str, task: str) -> str:
        import requests

        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": """You are a GUI automation assistant. Analyze the screenshot and determine what action to take.

Output the action in this format:
- click(x, y) - click at coordinates
- type(text) - type text
- scroll(direction, amount) - scroll up/down

Coordinates should be pixel positions on the screen."""
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Task: {task}"},
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}}
                        ]
                    }
                ],
                "max_tokens": 300
            }
        )

        result = response.json()
        if "error" in result:
            raise Exception(f"xAI API error: {result['error']}")

        return result["choices"][0]["message"]["content"]


class GroqVLM(VLMProvider):
    """Groq provider with Llama 4 vision model (FREE tier available)"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"  # Latest vision model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    def analyze_screenshot(self, image_path: str, task: str) -> str:
        import requests

        # Encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        ext = Path(image_path).suffix.lower()
        media_type = "image/png" if ext == ".png" else "image/jpeg"

        response = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"""You are a UI testing assistant. Analyze this screenshot and identify issues.

Task: {task}

Look for:
1. Layout problems (overlapping, misaligned elements)
2. Broken or missing components
3. Styling issues
4. Accessibility problems
5. Any visible errors

List all issues found with specific descriptions."""},
                            {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}}
                        ]
                    }
                ],
                "max_tokens": 1024
            }
        )

        result = response.json()
        if "error" in result:
            raise Exception(f"Groq API error: {result['error']}")

        return result["choices"][0]["message"]["content"]


class UITarsAutomation:
    """Main UI-TARS automation class with VLM integration"""

    def __init__(self, provider: str = "auto"):
        self.vlm: Optional[VLMProvider] = None
        self.screen_width = 1920
        self.screen_height = 1080

        # Auto-detect provider based on available API keys
        if provider == "auto":
            provider = self._detect_provider()

        self._init_provider(provider)

    def _detect_provider(self) -> str:
        """Auto-detect which VLM provider to use based on env vars"""
        # Prioritize Groq (free tier) first
        if os.getenv("GROQ_API_KEY"):
            return "groq"
        if os.getenv("XAI_API_KEY"):
            return "xai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("QWEN_API_KEY"):
            return "qwen"
        return "none"

    def _init_provider(self, provider: str):
        """Initialize the VLM provider"""
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.vlm = OpenAIVLM(api_key)
                print(f"[OK] Initialized OpenAI GPT-4V")
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                self.vlm = AnthropicVLM(api_key)
                print(f"[OK] Initialized Anthropic Claude Vision")
        elif provider == "xai":
            api_key = os.getenv("XAI_API_KEY")
            if api_key:
                self.vlm = XaiVLM(api_key)
                print(f"[OK] Initialized xAI Grok Vision")
        elif provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                self.vlm = GroqVLM(api_key)
                print(f"[OK] Initialized Groq LLaMA Vision (FREE tier)")
        else:
            print(f"[!] No VLM provider configured. Set one of:")
            print("   - OPENAI_API_KEY (GPT-4V)")
            print("   - ANTHROPIC_API_KEY (Claude Vision)")
            print("   - XAI_API_KEY (Grok Vision)")

    def take_screenshot(self, output_path: str = "screenshot.png") -> str:
        """Take a screenshot of the current screen"""
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(output_path)
            return output_path
        except Exception as e:
            print(f"Screenshot failed: {e}")
            return ""

    def analyze_and_act(self, task: str, screenshot_path: Optional[str] = None, dry_run: bool = True) -> Dict[str, Any]:
        """
        Analyze screen and determine action

        Args:
            task: What to do (e.g., "Click the login button")
            screenshot_path: Path to screenshot (takes one if not provided)
            dry_run: If True, don't execute, just show what would happen

        Returns:
            Dict with action details and optional execution result
        """
        if not self.vlm:
            return {"error": "No VLM configured", "success": False}

        # Take screenshot if not provided
        if not screenshot_path:
            screenshot_path = self.take_screenshot()
            if not screenshot_path:
                return {"error": "Failed to take screenshot", "success": False}

        try:
            # Get action from VLM
            action_text = self.vlm.analyze_screenshot(screenshot_path, task)
            print(f"VLM Response: {action_text}")

            # Parse with UI-TARS if available
            if UI_TARS_AVAILABLE:
                parsed = parse_action_to_structure_output(
                    action_text,
                    factor=1000,
                    origin_resized_height=self.screen_height,
                    origin_resized_width=self.screen_width,
                    model_type="gpt4v"  # Compatible format
                )

                code = parsing_response_to_pyautogui_code(
                    responses=parsed,
                    image_height=self.screen_height,
                    image_width=self.screen_width
                )

                result = {
                    "success": True,
                    "action_text": action_text,
                    "parsed": parsed,
                    "pyautogui_code": code,
                    "dry_run": dry_run
                }

                if not dry_run:
                    print(f"Executing: {code}")
                    exec(code)
                    result["executed"] = True
                else:
                    print(f"[DRY RUN] Would execute:\n{code}")

                return result
            else:
                return {
                    "success": True,
                    "action_text": action_text,
                    "note": "UI-TARS not installed, cannot parse to PyAutoGUI"
                }

        except Exception as e:
            return {"error": str(e), "success": False}


def test_ui_tars_config():
    """Test UI-TARS configuration"""
    print("=" * 60)
    print("UI-TARS Configuration Test")
    print("=" * 60)

    # Check UI-TARS
    status = "[OK] Installed" if UI_TARS_AVAILABLE else "[X] Not installed"
    print(f"\n1. UI-TARS Package: {status}")

    # Check API keys
    print("\n2. API Keys:")
    keys = {
        "OPENAI_API_KEY": "OpenAI GPT-4V",
        "ANTHROPIC_API_KEY": "Anthropic Claude",
        "XAI_API_KEY": "xAI Grok",
        "QWEN_API_KEY": "Qwen 2.5vl"
    }

    found_key = None
    for key, name in keys.items():
        value = os.getenv(key)
        if value:
            print(f"   [OK] {key}: Set ({name})")
            if not found_key:
                found_key = key
        else:
            print(f"   [--] {key}: Not set")

    # Initialize automation
    print("\n3. VLM Provider:")
    automation = UITarsAutomation(provider="auto")

    if automation.vlm:
        print(f"   [OK] Ready to use!")
        print("\n4. Quick Test:")
        print("   To test browser automation:")
        print("   >>> from scripts.ui_tars_config import UITarsAutomation")
        print("   >>> auto = UITarsAutomation()")
        print("   >>> auto.analyze_and_act('Click the search button', dry_run=True)")
    else:
        print("   [X] No VLM provider available")
        print("\n   To configure, set one of these environment variables:")
        print("   - export OPENAI_API_KEY=sk-...")
        print("   - export ANTHROPIC_API_KEY=sk-ant-...")
        print("   - export XAI_API_KEY=xai-...")

    return automation.vlm is not None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="UI-TARS VLM Configuration")
    parser.add_argument("--test", action="store_true", help="Test configuration")
    parser.add_argument("--provider", choices=["openai", "anthropic", "xai", "auto"],
                       default="auto", help="VLM provider to use")
    parser.add_argument("--task", type=str, help="Task to perform")
    parser.add_argument("--screenshot", type=str, help="Screenshot path")
    parser.add_argument("--execute", action="store_true", help="Actually execute (not dry run)")

    args = parser.parse_args()

    if args.test:
        test_ui_tars_config()
    elif args.task:
        automation = UITarsAutomation(provider=args.provider)
        result = automation.analyze_and_act(
            args.task,
            screenshot_path=args.screenshot,
            dry_run=not args.execute
        )
        print(json.dumps(result, indent=2, default=str))
    else:
        test_ui_tars_config()


if __name__ == "__main__":
    main()
