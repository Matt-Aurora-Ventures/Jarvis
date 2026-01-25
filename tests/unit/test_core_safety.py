"""
Unit tests for core/safety.py

Tests cover:
- SafetyContext dataclass initialization and attributes
- resolve_mode() flag parsing and validation
- confirm_apply() user input handling
- allow_action() combination of dry_run and confirmation
- Edge cases and error conditions
"""

import pytest
from unittest.mock import patch, MagicMock
from io import StringIO

from core.safety import SafetyContext, resolve_mode, confirm_apply, allow_action


class TestSafetyContextDataclass:
    """Tests for SafetyContext dataclass."""

    def test_safety_context_apply_true_dry_run_false(self):
        """Test SafetyContext with apply=True, dry_run=False."""
        ctx = SafetyContext(apply=True, dry_run=False)
        assert ctx.apply is True
        assert ctx.dry_run is False

    def test_safety_context_apply_false_dry_run_true(self):
        """Test SafetyContext with apply=False, dry_run=True."""
        ctx = SafetyContext(apply=False, dry_run=True)
        assert ctx.apply is False
        assert ctx.dry_run is True

    def test_safety_context_both_false(self):
        """Test SafetyContext with both flags False."""
        ctx = SafetyContext(apply=False, dry_run=False)
        assert ctx.apply is False
        assert ctx.dry_run is False

    def test_safety_context_both_true(self):
        """Test SafetyContext allows both True (validation is in resolve_mode)."""
        ctx = SafetyContext(apply=True, dry_run=True)
        assert ctx.apply is True
        assert ctx.dry_run is True

    def test_safety_context_equality(self):
        """Test SafetyContext instances with same values are equal."""
        ctx1 = SafetyContext(apply=True, dry_run=False)
        ctx2 = SafetyContext(apply=True, dry_run=False)
        assert ctx1 == ctx2

    def test_safety_context_inequality(self):
        """Test SafetyContext instances with different values are not equal."""
        ctx1 = SafetyContext(apply=True, dry_run=False)
        ctx2 = SafetyContext(apply=False, dry_run=True)
        assert ctx1 != ctx2

    def test_safety_context_repr(self):
        """Test SafetyContext has meaningful repr."""
        ctx = SafetyContext(apply=True, dry_run=False)
        repr_str = repr(ctx)
        assert "SafetyContext" in repr_str
        assert "apply=True" in repr_str
        assert "dry_run=False" in repr_str

    def test_safety_context_immutability_attempt(self):
        """Test SafetyContext is a frozen dataclass (if configured) or mutable."""
        ctx = SafetyContext(apply=True, dry_run=False)
        # Standard dataclass is mutable - this tests current behavior
        ctx.apply = False
        assert ctx.apply is False

    def test_safety_context_default_values_not_provided(self):
        """Test SafetyContext requires both arguments."""
        with pytest.raises(TypeError):
            SafetyContext()  # type: ignore

    def test_safety_context_missing_dry_run(self):
        """Test SafetyContext requires dry_run argument."""
        with pytest.raises(TypeError):
            SafetyContext(apply=True)  # type: ignore


class TestResolveModeFunction:
    """Tests for resolve_mode() function."""

    def test_resolve_mode_apply_flag_only(self):
        """Test resolve_mode with only --apply flag."""
        ctx = resolve_mode(apply_flag=True, dry_run_flag=False)
        assert ctx.apply is True
        assert ctx.dry_run is False

    def test_resolve_mode_dry_run_flag_only(self):
        """Test resolve_mode with only --dry-run flag."""
        ctx = resolve_mode(apply_flag=False, dry_run_flag=True)
        assert ctx.apply is False
        assert ctx.dry_run is True

    def test_resolve_mode_neither_flag_defaults_to_dry_run(self):
        """Test resolve_mode defaults to dry_run when neither flag specified."""
        ctx = resolve_mode(apply_flag=False, dry_run_flag=False)
        assert ctx.apply is False
        assert ctx.dry_run is True

    def test_resolve_mode_both_flags_raises_error(self):
        """Test resolve_mode raises ValueError when both flags specified."""
        with pytest.raises(ValueError) as exc_info:
            resolve_mode(apply_flag=True, dry_run_flag=True)
        assert "--apply" in str(exc_info.value)
        assert "--dry-run" in str(exc_info.value)
        assert "not both" in str(exc_info.value)

    def test_resolve_mode_returns_safety_context_type(self):
        """Test resolve_mode returns SafetyContext instance."""
        ctx = resolve_mode(apply_flag=True, dry_run_flag=False)
        assert isinstance(ctx, SafetyContext)

    def test_resolve_mode_error_message_contains_guidance(self):
        """Test resolve_mode error message helps users understand the issue."""
        with pytest.raises(ValueError) as exc_info:
            resolve_mode(apply_flag=True, dry_run_flag=True)
        error_msg = str(exc_info.value)
        assert "Choose" in error_msg or "either" in error_msg


class TestConfirmApplyFunction:
    """Tests for confirm_apply() function."""

    def test_confirm_apply_returns_true_when_apply_typed(self):
        """Test confirm_apply returns True when user types 'APPLY'."""
        with patch('builtins.input', return_value='APPLY'):
            result = confirm_apply("Delete all files")
        assert result is True

    def test_confirm_apply_returns_false_when_wrong_input(self):
        """Test confirm_apply returns False when user types wrong input."""
        with patch('builtins.input', return_value='yes'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_false_when_empty_input(self):
        """Test confirm_apply returns False when user types nothing."""
        with patch('builtins.input', return_value=''):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_false_when_lowercase_apply(self):
        """Test confirm_apply is case-sensitive (apply != APPLY)."""
        with patch('builtins.input', return_value='apply'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_false_when_mixed_case_apply(self):
        """Test confirm_apply is case-sensitive (Apply != APPLY)."""
        with patch('builtins.input', return_value='Apply'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_true_with_leading_whitespace(self):
        """Test confirm_apply strips leading whitespace."""
        with patch('builtins.input', return_value='  APPLY'):
            result = confirm_apply("Test action")
        assert result is True

    def test_confirm_apply_returns_true_with_trailing_whitespace(self):
        """Test confirm_apply strips trailing whitespace."""
        with patch('builtins.input', return_value='APPLY  '):
            result = confirm_apply("Test action")
        assert result is True

    def test_confirm_apply_returns_true_with_both_whitespace(self):
        """Test confirm_apply strips both leading and trailing whitespace."""
        with patch('builtins.input', return_value='  APPLY  '):
            result = confirm_apply("Test action")
        assert result is True

    def test_confirm_apply_returns_false_with_extra_text(self):
        """Test confirm_apply returns False with extra text."""
        with patch('builtins.input', return_value='APPLY please'):
            result = confirm_apply("Test action")
        assert result is False

    def test_confirm_apply_prompt_contains_action_label(self):
        """Test confirm_apply prompt includes the action label."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Delete important files")
        call_args = mock_input.call_args[0][0]
        assert "Delete important files" in call_args

    def test_confirm_apply_prompt_contains_apply_instruction(self):
        """Test confirm_apply prompt tells user to type APPLY."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Some action")
        call_args = mock_input.call_args[0][0]
        assert "APPLY" in call_args

    def test_confirm_apply_returns_false_when_cancel_typed(self):
        """Test confirm_apply returns False when user types 'cancel'."""
        with patch('builtins.input', return_value='cancel'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_false_when_no_typed(self):
        """Test confirm_apply returns False when user types 'no'."""
        with patch('builtins.input', return_value='no'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_returns_false_when_n_typed(self):
        """Test confirm_apply returns False when user types 'n'."""
        with patch('builtins.input', return_value='n'):
            result = confirm_apply("Delete all files")
        assert result is False

    def test_confirm_apply_with_unicode_action_label(self):
        """Test confirm_apply handles unicode in action label."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Delete file with unicode: \u2713")
        call_args = mock_input.call_args[0][0]
        assert "\u2713" in call_args

    def test_confirm_apply_with_special_characters(self):
        """Test confirm_apply handles special characters in action label."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Delete <file>; rm -rf /")
        call_args = mock_input.call_args[0][0]
        assert "<file>" in call_args


class TestAllowActionFunction:
    """Tests for allow_action() function."""

    def test_allow_action_dry_run_returns_false_without_prompt(self):
        """Test allow_action returns False in dry_run mode without prompting."""
        ctx = SafetyContext(apply=False, dry_run=True)
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            result = allow_action(ctx, "Delete files")
        assert result is False
        mock_input.assert_not_called()

    def test_allow_action_apply_mode_prompts_and_returns_true(self):
        """Test allow_action prompts and returns True when user types APPLY."""
        ctx = SafetyContext(apply=True, dry_run=False)
        with patch('builtins.input', return_value='APPLY'):
            result = allow_action(ctx, "Delete files")
        assert result is True

    def test_allow_action_apply_mode_prompts_and_returns_false(self):
        """Test allow_action prompts and returns False when user declines."""
        ctx = SafetyContext(apply=True, dry_run=False)
        with patch('builtins.input', return_value='no'):
            result = allow_action(ctx, "Delete files")
        assert result is False

    def test_allow_action_passes_action_label_to_confirm(self):
        """Test allow_action passes the action_label to confirm_apply."""
        ctx = SafetyContext(apply=True, dry_run=False)
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            allow_action(ctx, "Specific action label")
        call_args = mock_input.call_args[0][0]
        assert "Specific action label" in call_args

    def test_allow_action_dry_run_context_always_safe(self):
        """Test allow_action never allows actions in dry_run mode."""
        ctx = SafetyContext(apply=False, dry_run=True)
        # Even with APPLY ready to be typed, dry_run should prevent
        with patch('builtins.input', return_value='APPLY'):
            result = allow_action(ctx, "Dangerous action")
        assert result is False


class TestSafetyContextIntegration:
    """Integration tests combining SafetyContext with functions."""

    def test_resolve_mode_to_allow_action_apply_path(self):
        """Test full flow from resolve_mode to allow_action in apply mode."""
        ctx = resolve_mode(apply_flag=True, dry_run_flag=False)
        with patch('builtins.input', return_value='APPLY'):
            result = allow_action(ctx, "Integration test action")
        assert result is True

    def test_resolve_mode_to_allow_action_dry_run_path(self):
        """Test full flow from resolve_mode to allow_action in dry_run mode."""
        ctx = resolve_mode(apply_flag=False, dry_run_flag=True)
        result = allow_action(ctx, "Integration test action")
        assert result is False

    def test_resolve_mode_default_to_allow_action(self):
        """Test default (no flags) goes to dry_run and blocks action."""
        ctx = resolve_mode(apply_flag=False, dry_run_flag=False)
        result = allow_action(ctx, "Default mode action")
        assert result is False

    def test_multiple_sequential_allow_actions_dry_run(self):
        """Test multiple allow_action calls in dry_run all return False."""
        ctx = SafetyContext(apply=False, dry_run=True)
        results = [
            allow_action(ctx, "Action 1"),
            allow_action(ctx, "Action 2"),
            allow_action(ctx, "Action 3"),
        ]
        assert all(r is False for r in results)

    def test_multiple_sequential_allow_actions_apply_mode(self):
        """Test multiple allow_action calls in apply mode each prompt."""
        ctx = SafetyContext(apply=True, dry_run=False)
        mock_input = MagicMock(side_effect=['APPLY', 'no', 'APPLY'])
        with patch('builtins.input', mock_input):
            results = [
                allow_action(ctx, "Action 1"),
                allow_action(ctx, "Action 2"),
                allow_action(ctx, "Action 3"),
            ]
        assert results == [True, False, True]
        assert mock_input.call_count == 3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_confirm_apply_with_newline_in_input(self):
        """Test confirm_apply handles newline characters."""
        with patch('builtins.input', return_value='APPLY\n'):
            result = confirm_apply("Test")
        # strip() should handle this
        assert result is True

    def test_confirm_apply_with_tab_in_input(self):
        """Test confirm_apply handles tab characters."""
        with patch('builtins.input', return_value='\tAPPLY\t'):
            result = confirm_apply("Test")
        assert result is True

    def test_confirm_apply_empty_action_label(self):
        """Test confirm_apply works with empty action label."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            result = confirm_apply("")
        assert result is True

    def test_allow_action_empty_action_label(self):
        """Test allow_action works with empty action label."""
        ctx = SafetyContext(apply=True, dry_run=False)
        with patch('builtins.input', return_value='APPLY'):
            result = allow_action(ctx, "")
        assert result is True

    def test_confirm_apply_very_long_action_label(self):
        """Test confirm_apply handles very long action labels."""
        long_label = "A" * 10000
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            result = confirm_apply(long_label)
        assert result is True
        assert long_label in mock_input.call_args[0][0]

    def test_safety_context_with_none_values(self):
        """Test SafetyContext behavior with None values (type coercion)."""
        ctx = SafetyContext(apply=None, dry_run=None)  # type: ignore
        # None is falsy, so dry_run check should treat as False
        assert ctx.apply is None
        assert ctx.dry_run is None

    def test_allow_action_with_none_dry_run(self):
        """Test allow_action when dry_run is None (falsy)."""
        ctx = SafetyContext(apply=True, dry_run=None)  # type: ignore
        with patch('builtins.input', return_value='APPLY'):
            result = allow_action(ctx, "Test")
        # None is falsy, so should prompt
        assert result is True


class TestInputHandling:
    """Tests for various input scenarios."""

    def test_confirm_apply_keyboard_interrupt(self):
        """Test confirm_apply behavior on KeyboardInterrupt."""
        with patch('builtins.input', side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):
                confirm_apply("Test action")

    def test_confirm_apply_eof_error(self):
        """Test confirm_apply behavior on EOFError."""
        with patch('builtins.input', side_effect=EOFError):
            with pytest.raises(EOFError):
                confirm_apply("Test action")

    def test_confirm_apply_with_only_whitespace(self):
        """Test confirm_apply with only whitespace input."""
        with patch('builtins.input', return_value='   '):
            result = confirm_apply("Test")
        assert result is False

    def test_confirm_apply_apply_with_number_suffix(self):
        """Test confirm_apply rejects 'APPLY123'."""
        with patch('builtins.input', return_value='APPLY123'):
            result = confirm_apply("Test")
        assert result is False


class TestContextModeLogic:
    """Tests for mode logic and state transitions."""

    def test_dry_run_mode_is_safe_default(self):
        """Test that dry_run is the safe default when nothing specified."""
        ctx = resolve_mode(False, False)
        assert ctx.dry_run is True
        assert ctx.apply is False

    def test_apply_mode_requires_explicit_flag(self):
        """Test that apply mode requires explicit --apply flag."""
        # Without explicit apply flag, should be dry_run
        ctx = resolve_mode(False, False)
        assert ctx.apply is False

        # With explicit apply flag
        ctx = resolve_mode(True, False)
        assert ctx.apply is True

    def test_context_states_are_mutually_exclusive_via_resolve(self):
        """Test resolve_mode ensures apply and dry_run cannot both be True."""
        # Valid: apply only
        ctx = resolve_mode(True, False)
        assert ctx.apply is True and ctx.dry_run is False

        # Valid: dry_run only
        ctx = resolve_mode(False, True)
        assert ctx.apply is False and ctx.dry_run is True

        # Invalid: both
        with pytest.raises(ValueError):
            resolve_mode(True, True)


class TestPromptFormatting:
    """Tests for prompt message formatting."""

    def test_prompt_includes_type_apply_instruction(self):
        """Test the prompt tells user to 'Type APPLY'."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("any action")
        prompt = mock_input.call_args[0][0]
        assert "Type APPLY" in prompt

    def test_prompt_ends_with_input_marker(self):
        """Test the prompt ends with '> ' for user input."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("any action")
        prompt = mock_input.call_args[0][0]
        assert prompt.endswith("> ")

    def test_prompt_contains_confirm_keyword(self):
        """Test the prompt contains 'confirm' keyword."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("any action")
        prompt = mock_input.call_args[0][0]
        assert "confirm" in prompt.lower()


class TestTypeSafety:
    """Tests for type-related behaviors."""

    def test_safety_context_rejects_string_for_bool(self):
        """Test SafetyContext with string values (Python allows but should check)."""
        # Python is dynamically typed - this will work but may cause issues
        ctx = SafetyContext(apply="true", dry_run="false")  # type: ignore
        # String "false" is truthy!
        assert bool(ctx.dry_run) is True

    def test_safety_context_integer_coercion(self):
        """Test SafetyContext with integer values."""
        ctx = SafetyContext(apply=1, dry_run=0)  # type: ignore
        # 1 is truthy, 0 is falsy
        assert bool(ctx.apply) is True
        assert bool(ctx.dry_run) is False

    def test_resolve_mode_with_truthy_values(self):
        """Test resolve_mode with truthy non-boolean values."""
        # 1 is truthy, 0 is falsy
        ctx = resolve_mode(apply_flag=1, dry_run_flag=0)  # type: ignore
        assert ctx.apply is True
        assert ctx.dry_run is False


class TestActionLabelVariations:
    """Tests for various action label inputs."""

    def test_action_label_with_newlines(self):
        """Test action label containing newlines."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Line1\nLine2\nLine3")
        prompt = mock_input.call_args[0][0]
        assert "Line1\nLine2\nLine3" in prompt

    def test_action_label_with_quotes(self):
        """Test action label containing quotes."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply('Delete "important" file')
        prompt = mock_input.call_args[0][0]
        assert '"important"' in prompt

    def test_action_label_with_paths(self):
        """Test action label containing file paths."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply("Delete /home/user/file.txt")
        prompt = mock_input.call_args[0][0]
        assert "/home/user/file.txt" in prompt

    def test_action_label_with_windows_paths(self):
        """Test action label containing Windows paths."""
        mock_input = MagicMock(return_value='APPLY')
        with patch('builtins.input', mock_input):
            confirm_apply(r"Delete C:\Users\test\file.txt")
        prompt = mock_input.call_args[0][0]
        assert r"C:\Users\test\file.txt" in prompt
