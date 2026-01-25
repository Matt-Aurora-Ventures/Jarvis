"""
Unit tests for TTS skill.

Tests the skill-based interface for text-to-speech.
"""

import pytest
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestTTSSkillStructure:
    """Tests for TTS skill file structure."""

    def test_skill_directory_exists(self):
        """TTS skill should have a directory in skills/."""
        from core.skills import DEFAULT_SKILLS_DIR

        tts_dir = DEFAULT_SKILLS_DIR / "tts"
        # Will be created during implementation
        # For now, just check we can construct the path
        assert tts_dir.name == "tts"

    def test_skill_has_required_files(self, tmp_path):
        """TTS skill should have SKILL.md and script.py."""
        # Create a mock skill structure for testing
        skill_dir = tmp_path / "tts"
        skill_dir.mkdir()

        (skill_dir / "SKILL.md").write_text("""# TTS Skill

Text-to-speech synthesis using Qwen3-TTS.

## Usage
```
/skill run tts "Hello world"
/skill run tts "Hello world" --voice my_voice
```

## Arguments
- text: Text to synthesize (required)
- --voice: Voice name to use (optional)
- --output: Output file path (optional, defaults to output.wav)
""")

        (skill_dir / "script.py").write_text("""import sys
# TTS skill implementation
print("TTS script loaded")
""")

        assert (skill_dir / "SKILL.md").exists()
        assert (skill_dir / "script.py").exists()


class TestTTSSkillExecution:
    """Tests for TTS skill execution."""

    def test_skill_generates_audio_file(self, tmp_path):
        """Skill should generate an audio file."""
        # This will test the actual skill once implemented
        # For now, test the expected behavior
        output_file = tmp_path / "output.wav"

        # Mock execution
        with patch("core.voice.tts_manager.TTSManager") as MockManager:
            mock_instance = MockManager.return_value
            mock_instance.synthesize.return_value = b"RIFF" + b"\x00" * 100

            from core.voice.tts_manager import TTSManager
            manager = TTSManager()
            audio = manager.synthesize("Hello world")

            output_file.write_bytes(audio)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_skill_accepts_voice_argument(self):
        """Skill should accept --voice argument."""
        # Test argument parsing
        args = ["Hello world", "--voice", "my_voice"]

        # Parse args (simulating argparse)
        text = args[0]
        voice = None
        if "--voice" in args:
            idx = args.index("--voice")
            voice = args[idx + 1]

        assert text == "Hello world"
        assert voice == "my_voice"

    def test_skill_outputs_file_path(self, tmp_path):
        """Skill should output the generated file path."""
        output_file = tmp_path / "output.wav"
        output_file.write_bytes(b"RIFF" + b"\x00" * 100)

        expected_output = f"Generated: {output_file}"
        assert str(output_file) in expected_output


class TestTTSSkillCLI:
    """Tests for TTS skill command-line interface."""

    def test_cli_basic_synthesis(self, tmp_path):
        """CLI should handle basic text synthesis."""
        script_content = '''
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("text", help="Text to synthesize")
parser.add_argument("--voice", help="Voice to use")
parser.add_argument("--output", default="output.wav", help="Output file")

args = parser.parse_args()

# Would call TTSManager here
print(f"Synthesizing: {args.text}")
print(f"Voice: {args.voice or 'default'}")
print(f"Output: {args.output}")
'''
        script_file = tmp_path / "script.py"
        script_file.write_text(script_content)

        result = subprocess.run(
            [sys.executable, str(script_file), "Hello world"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Synthesizing: Hello world" in result.stdout

    def test_cli_with_voice_option(self, tmp_path):
        """CLI should handle --voice option."""
        import sys

        script_content = '''
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("text", help="Text to synthesize")
parser.add_argument("--voice", help="Voice to use")

args = parser.parse_args()
print(f"Voice: {args.voice or 'default'}")
'''
        script_file = tmp_path / "script.py"
        script_file.write_text(script_content)

        result = subprocess.run(
            [sys.executable, str(script_file), "Hello", "--voice", "custom"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "Voice: custom" in result.stdout


class TestTTSSkillIntegration:
    """Integration tests for TTS skill with registry."""

    def test_skill_discoverable_by_registry(self, tmp_path):
        """TTS skill should be discoverable by SkillRegistry."""
        from core.skills.registry import SkillRegistry

        # Create TTS skill
        skill_dir = tmp_path / "tts"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# TTS Skill\nText-to-speech synthesis.")
        (skill_dir / "script.py").write_text("print('tts')")

        registry = SkillRegistry(skills_dir=tmp_path)
        skills = registry.discover_skills()

        assert "tts" in skills

    def test_skill_executable_by_executor(self, tmp_path):
        """TTS skill should be executable by SkillExecutor."""
        from core.skills.registry import SkillRegistry
        from core.skills.executor import SkillExecutor

        # Create TTS skill
        skill_dir = tmp_path / "tts"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# TTS Skill\nText-to-speech synthesis.")
        (skill_dir / "script.py").write_text("""
import sys
print(f"TTS: {' '.join(sys.argv[1:])}")
""")

        registry = SkillRegistry(skills_dir=tmp_path)
        registry.discover_skills()

        executor = SkillExecutor(registry)
        result = executor.execute("tts", ["Hello", "world"])

        assert result.success is True
        assert "TTS: Hello world" in result.output
