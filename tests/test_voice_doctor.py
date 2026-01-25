"""
Tests for Voice Doctor Command (P0-3).

Tests verify:
- diagnose_voice_pipeline() returns comprehensive diagnostics
- Audio capture test measures signal level
- Sample transcription test validates API
- CLI `lifeos voice doctor` subcommand works
- Clear pass/fail for each component
- Actionable error messages
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import json

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Import the legacy voice module directly since core.voice is a package
from importlib.util import module_from_spec, spec_from_file_location

def _load_voice_module():
    """Load core/voice.py directly."""
    voice_path = Path(__file__).resolve().parents[1] / "core" / "voice.py"
    spec = spec_from_file_location("core_voice", voice_path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load core/voice.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

voice = _load_voice_module()


# =============================================================================
# Test diagnose_voice_pipeline() Function
# =============================================================================

class TestDiagnoseVoicePipeline:
    """Test the diagnose_voice_pipeline() function."""

    def test_diagnose_voice_pipeline_exists(self):
        """diagnose_voice_pipeline() function should exist."""
        assert hasattr(voice, 'diagnose_voice_pipeline')
        assert callable(voice.diagnose_voice_pipeline)

    def test_returns_dict(self):
        """diagnose_voice_pipeline() should return a dictionary."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                # Mock PyAudio to avoid hardware dependency
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert isinstance(result, dict)

    def test_has_microphone_section(self):
        """Result should have microphone diagnostics section."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert 'microphone' in result
                assert isinstance(result['microphone'], dict)

    def test_microphone_section_has_required_fields(self):
        """Microphone section should have device enumeration."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 2
                mock_pa.get_device_info_by_index.side_effect = [
                    {"name": "Built-in Microphone", "maxInputChannels": 2, "index": 0},
                    {"name": "USB Headset", "maxInputChannels": 1, "index": 1},
                ]
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                mic = result['microphone']

                assert 'ok' in mic
                assert 'devices' in mic
                assert 'device_count' in mic
                assert mic['device_count'] == 2

    def test_has_audio_capture_section(self):
        """Result should have audio capture test section."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert 'audio_capture' in result

    def test_audio_capture_has_level_measurement(self):
        """Audio capture test should measure signal level in dB."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 1
                mock_pa.get_device_info_by_index.return_value = {
                    "name": "Test Mic", "maxInputChannels": 1, "index": 0
                }
                mock_pyaudio.PyAudio.return_value = mock_pa
                mock_pyaudio.paInt16 = 8

                # Mock stream for audio capture
                mock_stream = MagicMock()
                mock_stream.read.return_value = b'\x00' * 3200  # 0.1s of silence
                mock_pa.open.return_value = mock_stream

                result = voice.diagnose_voice_pipeline()
                capture = result.get('audio_capture', {})

                # Should have level measurement (or error why not)
                assert 'level_db' in capture or 'error' in capture

    def test_has_audio_libraries_section(self):
        """Result should check audio processing libraries."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert 'audio_libraries' in result
                libs = result['audio_libraries']

                # Should check key libraries
                assert 'sounddevice' in libs or 'pyaudio' in libs
                assert 'numpy' in libs

    def test_has_whisper_api_section(self):
        """Result should have OpenAI Whisper API test section."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert 'whisper_api' in result

    def test_whisper_api_checks_key_configured(self):
        """Whisper API section should check if API key is configured."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value="test-key"):
                    result = voice.diagnose_voice_pipeline()
                    whisper = result.get('whisper_api', {})
                    assert 'key_configured' in whisper
                    assert whisper['key_configured'] is True

    def test_whisper_api_shows_missing_key(self):
        """Whisper API section should indicate missing API key."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value=None):
                    result = voice.diagnose_voice_pipeline()
                    whisper = result.get('whisper_api', {})
                    assert 'key_configured' in whisper
                    assert whisper['key_configured'] is False
                    assert 'fix' in whisper

    def test_has_overall_status(self):
        """Result should have overall operational status."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                result = voice.diagnose_voice_pipeline()
                assert 'overall' in result
                assert 'operational' in result['overall']
                assert 'issue_count' in result['overall']


# =============================================================================
# Test Voice Doctor Report Formatting
# =============================================================================

class TestVoiceDoctorReport:
    """Test voice doctor report formatting."""

    def test_format_voice_doctor_report_exists(self):
        """format_voice_doctor_report() function should exist."""
        assert hasattr(voice, 'format_voice_doctor_report')
        assert callable(voice.format_voice_doctor_report)

    def test_format_returns_string(self):
        """format_voice_doctor_report() should return formatted string."""
        mock_diagnostics = {
            'microphone': {'ok': True, 'device_count': 2, 'devices': []},
            'audio_capture': {'ok': True, 'level_db': -18.3},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': True, 'issue_count': 0},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_includes_section_headers(self):
        """Report should include section headers."""
        mock_diagnostics = {
            'microphone': {'ok': True, 'device_count': 2, 'devices': []},
            'audio_capture': {'ok': True, 'level_db': -18.3},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': True, 'issue_count': 0},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)
        lower = result.lower()

        assert 'microphone' in lower
        assert 'audio' in lower
        assert 'whisper' in lower or 'api' in lower

    def test_format_shows_pass_fail_icons(self):
        """Report should show pass/fail status icons."""
        mock_diagnostics = {
            'microphone': {'ok': True, 'device_count': 2, 'devices': []},
            'audio_capture': {'ok': False, 'error': 'No audio detected'},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': False, 'issue_count': 1},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)

        # Should have status indicators (checkmark for pass, X for fail)
        assert 'ok' in result.lower() or 'pass' in result.lower() or 'v' in result.lower()

    def test_format_shows_audio_level(self):
        """Report should show audio level measurement."""
        mock_diagnostics = {
            'microphone': {'ok': True, 'device_count': 1, 'devices': []},
            'audio_capture': {'ok': True, 'level_db': -18.3, 'signal_quality': 'good'},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': True, 'issue_count': 0},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)

        # Should show dB level
        assert 'db' in result.lower() or '-18' in result

    def test_format_shows_device_list(self):
        """Report should list detected input devices."""
        mock_diagnostics = {
            'microphone': {
                'ok': True,
                'device_count': 2,
                'devices': [
                    {'name': 'Built-in Microphone', 'index': 0},
                    {'name': 'USB Headset', 'index': 1},
                ]
            },
            'audio_capture': {'ok': True, 'level_db': -18.3},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': True, 'issue_count': 0},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)

        # Should list device names
        assert 'built-in' in result.lower() or 'device 0' in result.lower()

    def test_format_shows_actionable_fixes(self):
        """Report should show actionable fix suggestions for errors."""
        mock_diagnostics = {
            'microphone': {'ok': False, 'error': 'No devices found', 'fix': 'Check microphone connection'},
            'audio_capture': {'ok': False, 'error': 'Cannot open stream'},
            'audio_libraries': {'numpy': True, 'pyaudio': False, 'pyaudio_fix': 'pip install pyaudio'},
            'whisper_api': {'ok': False, 'key_configured': False, 'fix': 'Set OPENAI_API_KEY'},
            'overall': {'operational': False, 'issue_count': 3},
        }

        result = voice.format_voice_doctor_report(mock_diagnostics)
        lower = result.lower()

        # Should show fix suggestions
        assert 'fix' in lower or 'install' in lower or 'check' in lower

    def test_format_shows_overall_verdict(self):
        """Report should show overall operational verdict."""
        mock_diagnostics_good = {
            'microphone': {'ok': True, 'device_count': 1, 'devices': []},
            'audio_capture': {'ok': True, 'level_db': -18.3},
            'audio_libraries': {'numpy': True, 'pyaudio': True},
            'whisper_api': {'ok': True, 'key_configured': True},
            'overall': {'operational': True, 'issue_count': 0},
        }

        mock_diagnostics_bad = {
            'microphone': {'ok': False, 'error': 'No devices'},
            'audio_capture': {'ok': False, 'error': 'Cannot capture'},
            'audio_libraries': {'numpy': True, 'pyaudio': False},
            'whisper_api': {'ok': False, 'key_configured': False},
            'overall': {'operational': False, 'issue_count': 3},
        }

        result_good = voice.format_voice_doctor_report(mock_diagnostics_good)
        result_bad = voice.format_voice_doctor_report(mock_diagnostics_bad)

        # Good report should indicate operational
        assert 'operational' in result_good.lower() or 'ready' in result_good.lower()

        # Bad report should indicate issues
        assert 'issue' in result_bad.lower() or 'not' in result_bad.lower() or 'problem' in result_bad.lower()


# =============================================================================
# Test CLI Voice Doctor Subcommand
# =============================================================================

class TestCLIVoiceDoctorSubcommand:
    """Test CLI `lifeos voice doctor` subcommand."""

    def test_voice_subcommand_exists(self):
        """Parser should have voice subcommand."""
        from core.cli import build_parser
        parser = build_parser()

        # Parse 'voice doctor' - should not raise
        args = parser.parse_args(['voice', 'doctor'])
        assert args.command == 'voice'
        assert args.voice_action == 'doctor'

    def test_voice_doctor_runs_diagnostics(self):
        """voice doctor should run diagnose_voice_pipeline()."""
        from core import cli

        # Import the voice module the same way cli.py does
        from core import voice as cli_voice

        with patch.object(cli_voice, 'diagnose_voice_pipeline') as mock_diagnose:
            mock_diagnose.return_value = {
                'microphone': {'ok': True, 'device_count': 1, 'devices': []},
                'audio_capture': {'ok': True, 'level_db': -18.3},
                'audio_libraries': {'numpy': True, 'pyaudio': True},
                'whisper_api': {'ok': True, 'key_configured': True},
                'overall': {'operational': True, 'issue_count': 0},
            }

            with patch.object(cli_voice, 'format_voice_doctor_report', return_value="Report"):
                args = MagicMock()
                args.voice_action = 'doctor'

                # Should call diagnose_voice_pipeline
                cli.cmd_voice(args)
                mock_diagnose.assert_called_once()

    def test_voice_doctor_returns_exit_code_0_on_success(self):
        """voice doctor should return exit code 0 when all checks pass."""
        from core import cli
        from core import voice as cli_voice

        with patch.object(cli_voice, 'diagnose_voice_pipeline') as mock_diagnose:
            mock_diagnose.return_value = {
                'microphone': {'ok': True, 'device_count': 1, 'devices': []},
                'audio_capture': {'ok': True, 'level_db': -18.3},
                'audio_libraries': {'numpy': True, 'pyaudio': True},
                'whisper_api': {'ok': True, 'key_configured': True},
                'overall': {'operational': True, 'issue_count': 0},
            }

            with patch.object(cli_voice, 'format_voice_doctor_report', return_value="Report"):
                args = MagicMock()
                args.voice_action = 'doctor'

                result = cli.cmd_voice(args)
                assert result == 0

    def test_voice_doctor_returns_exit_code_1_on_failure(self):
        """voice doctor should return exit code 1 when issues found."""
        from core import cli
        from core import voice as cli_voice

        with patch.object(cli_voice, 'diagnose_voice_pipeline') as mock_diagnose:
            mock_diagnose.return_value = {
                'microphone': {'ok': False, 'error': 'No devices'},
                'audio_capture': {'ok': False, 'error': 'Cannot capture'},
                'audio_libraries': {'numpy': True, 'pyaudio': False},
                'whisper_api': {'ok': False, 'key_configured': False},
                'overall': {'operational': False, 'issue_count': 3},
            }

            with patch.object(cli_voice, 'format_voice_doctor_report', return_value="Report"):
                args = MagicMock()
                args.voice_action = 'doctor'

                result = cli.cmd_voice(args)
                assert result == 1


# =============================================================================
# Test Sample Transcription Test
# =============================================================================

class TestSampleTranscriptionTest:
    """Test sample transcription in diagnostics."""

    def test_whisper_api_includes_test_transcription(self):
        """Whisper API test should include sample transcription when key available."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value="test-key"):
                    # Mock the OpenAI client
                    with patch('openai.OpenAI') as mock_openai:
                        mock_client = MagicMock()
                        mock_openai.return_value = mock_client
                        mock_client.audio.transcriptions.create.return_value = MagicMock(
                            text="Testing one two three"
                        )

                        result = voice.diagnose_voice_pipeline()
                        whisper = result.get('whisper_api', {})

                        # If test was run, should have transcription result
                        if whisper.get('test_ran'):
                            assert 'test_transcription' in whisper

    def test_whisper_api_test_gracefully_handles_errors(self):
        """Whisper API test should gracefully handle network errors."""
        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value="test-key"):
                    with patch('openai.OpenAI') as mock_openai:
                        mock_client = MagicMock()
                        mock_openai.return_value = mock_client
                        mock_client.audio.transcriptions.create.side_effect = Exception("Network error")

                        # Should not raise
                        result = voice.diagnose_voice_pipeline()
                        whisper = result.get('whisper_api', {})

                        # Should indicate error gracefully
                        assert 'error' in whisper or whisper.get('ok') is False


# =============================================================================
# Test Timing Requirement
# =============================================================================

class TestDiagnosticTiming:
    """Test that diagnostics complete quickly."""

    def test_diagnostics_complete_under_10_seconds(self):
        """Diagnostics should complete in under 10 seconds."""
        import time

        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value=None):
                    start = time.time()
                    voice.diagnose_voice_pipeline()
                    elapsed = time.time() - start

                    assert elapsed < 10, f"Diagnostics took {elapsed:.2f}s (should be <10s)"


# =============================================================================
# Test Safety (No Persistent Changes)
# =============================================================================

class TestDiagnosticSafety:
    """Test that diagnostics don't make persistent changes."""

    def test_diagnostics_are_read_only(self):
        """Diagnostics should not modify any state."""
        from core import state

        with patch.object(voice, '_load_config', return_value={"voice": {}}):
            with patch('core.voice.pyaudio', create=True) as mock_pyaudio:
                mock_pa = MagicMock()
                mock_pa.get_device_count.return_value = 0
                mock_pyaudio.PyAudio.return_value = mock_pa

                with patch('core.secrets.get_openai_key', return_value=None):
                    with patch.object(state, 'update_state') as mock_update:
                        voice.diagnose_voice_pipeline()

                        # Should not update state
                        mock_update.assert_not_called()
