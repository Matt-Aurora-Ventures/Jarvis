"""
UI-TARS Browser Automation Helper

This script helps configure and use UI-TARS for browser testing.
Uses Qwen 2.5vl as the VLM for vision-language understanding.

For web automation specifically, UI-TARS recommends Midscene.js:
https://github.com/nicepkg/midscene

UI-TARS itself handles:
- Screenshot analysis
- Action parsing (click, type, scroll)
- Coordinate grounding
"""

import os
from typing import Optional, Tuple, Dict, Any

# UI-TARS action parser
from ui_tars.action_parser import parse_action_to_structure_output, parsing_response_to_pyautogui_code

# Default screen dimensions
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


class UITarsConfig:
    """Configuration for UI-TARS VLM integration"""

    def __init__(self):
        # VLM Provider options:
        # 1. Qwen 2.5vl (recommended by UI-TARS)
        # 2. OpenAI GPT-4V
        # 3. Claude with vision

        self.model_type = "qwen25vl"  # Default model type
        self.vlm_base_url = os.getenv("QWEN_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
        self.vlm_api_key = os.getenv("QWEN_API_KEY", "")
        self.vlm_model = os.getenv("QWEN_MODEL", "qwen-vl-max")

        # Alternative: Use OpenAI GPT-4V
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Screen dimensions
        self.screen_width = DEFAULT_WIDTH
        self.screen_height = DEFAULT_HEIGHT

    def configure_qwen(self, api_key: str, model: str = "qwen-vl-max"):
        """Configure Qwen 2.5vl as VLM"""
        self.vlm_api_key = api_key
        self.vlm_model = model
        self.model_type = "qwen25vl"

    def configure_openai(self, api_key: str, model: str = "gpt-4-vision-preview"):
        """Configure OpenAI GPT-4V as VLM"""
        self.openai_api_key = api_key
        self.vlm_model = model
        self.model_type = "gpt4v"


class UITarsBrowserAgent:
    """Browser automation agent using UI-TARS"""

    def __init__(self, config: Optional[UITarsConfig] = None):
        self.config = config or UITarsConfig()

    def parse_action(self, vlm_response: str) -> Dict[str, Any]:
        """
        Parse VLM response into structured action

        Args:
            vlm_response: Raw text response from VLM describing the action

        Returns:
            Parsed action dict with type, coordinates, text, etc.
        """
        parsed = parse_action_to_structure_output(
            vlm_response,
            factor=1000,  # Coordinate normalization factor
            origin_resized_height=self.config.screen_height,
            origin_resized_width=self.config.screen_width,
            model_type=self.config.model_type
        )
        return parsed

    def action_to_code(self, parsed_action: Dict[str, Any]) -> str:
        """
        Convert parsed action to PyAutoGUI code

        Args:
            parsed_action: Parsed action dict from parse_action()

        Returns:
            Executable PyAutoGUI code string
        """
        code = parsing_response_to_pyautogui_code(
            responses=parsed_action,
            image_height=self.config.screen_height,
            image_width=self.config.screen_width
        )
        return code

    def execute_action(self, vlm_response: str, dry_run: bool = True) -> Tuple[str, bool]:
        """
        Parse and optionally execute an action

        Args:
            vlm_response: Raw VLM response
            dry_run: If True, only return code without executing

        Returns:
            Tuple of (code, success)
        """
        try:
            parsed = self.parse_action(vlm_response)
            code = self.action_to_code(parsed)

            if dry_run:
                print(f"[DRY RUN] Would execute:\n{code}")
                return code, True
            else:
                # Execute the PyAutoGUI code
                exec(code)
                return code, True
        except Exception as e:
            print(f"Error executing action: {e}")
            return str(e), False


def test_ui_tars():
    """Test UI-TARS installation"""
    print("Testing UI-TARS installation...")

    config = UITarsConfig()
    agent = UITarsBrowserAgent(config)

    # Test with a sample VLM response
    # Format: "action(click, x=500, y=300)" or similar
    test_response = "click(500, 300)"

    try:
        parsed = agent.parse_action(test_response)
        print(f"✅ UI-TARS parse_action works")
        print(f"   Parsed: {parsed}")

        code = agent.action_to_code(parsed)
        print(f"✅ UI-TARS action_to_code works")
        print(f"   Code: {code}")

        return True
    except Exception as e:
        print(f"❌ UI-TARS test failed: {e}")
        return False


def main():
    """Main entry point for UI-TARS browser testing"""
    print("=" * 60)
    print("UI-TARS Browser Automation Setup")
    print("=" * 60)

    # Test installation
    if test_ui_tars():
        print("\n✅ UI-TARS is ready!")
        print("\nTo use UI-TARS for browser automation:")
        print("1. Configure VLM (Qwen 2.5vl or GPT-4V)")
        print("2. Take screenshots of the browser")
        print("3. Send screenshot + task to VLM")
        print("4. Parse VLM response with UI-TARS")
        print("5. Execute parsed actions")
        print("\nFor web-specific automation, also check:")
        print("https://github.com/nicepkg/midscene")
    else:
        print("\n❌ UI-TARS setup incomplete")


if __name__ == "__main__":
    main()
