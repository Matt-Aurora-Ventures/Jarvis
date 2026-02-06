"""Tests for core.exceptions.base module."""
import pytest
from typing import Dict, Any


class TestJarvisError:
    """Tests for JarvisError base exception."""

    def test_jarvis_error_inherits_from_exception(self):
        """JarvisError should inherit from Exception."""
        from core.exceptions.base import JarvisError

        assert issubclass(JarvisError, Exception)

    def test_jarvis_error_with_message_only(self):
        """JarvisError should accept just a message."""
        from core.exceptions.base import JarvisError

        error = JarvisError("Something went wrong")
        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"

    def test_jarvis_error_with_code(self):
        """JarvisError should accept a code."""
        from core.exceptions.base import JarvisError

        error = JarvisError("Error occurred", code="ERR_001")
        assert error.code == "ERR_001"
        assert error.message == "Error occurred"

    def test_jarvis_error_with_details(self):
        """JarvisError should accept details dict."""
        from core.exceptions.base import JarvisError

        details = {"field": "email", "reason": "invalid format"}
        error = JarvisError("Validation failed", code="VAL_001", details=details)
        assert error.details == details

    def test_jarvis_error_default_code(self):
        """JarvisError should have a default code."""
        from core.exceptions.base import JarvisError

        error = JarvisError("Error")
        assert error.code is not None
        assert isinstance(error.code, str)

    def test_jarvis_error_to_dict(self):
        """JarvisError.to_dict() should return proper structure."""
        from core.exceptions.base import JarvisError

        error = JarvisError(
            "Something failed",
            code="TEST_001",
            details={"key": "value"}
        )
        result = error.to_dict()

        assert isinstance(result, dict)
        assert result["message"] == "Something failed"
        assert result["code"] == "TEST_001"
        assert result["details"] == {"key": "value"}

    def test_jarvis_error_to_dict_without_details(self):
        """JarvisError.to_dict() should handle missing details."""
        from core.exceptions.base import JarvisError

        error = JarvisError("Error", code="TEST_001")
        result = error.to_dict()

        assert "message" in result
        assert "code" in result
        # details should be empty dict or not present
        assert result.get("details") == {} or "details" not in result

    def test_jarvis_error_from_dict(self):
        """JarvisError.from_dict() should reconstruct the error."""
        from core.exceptions.base import JarvisError

        data = {
            "message": "Reconstructed error",
            "code": "REC_001",
            "details": {"source": "test"}
        }
        error = JarvisError.from_dict(data)

        assert isinstance(error, JarvisError)
        assert error.message == "Reconstructed error"
        assert error.code == "REC_001"
        assert error.details == {"source": "test"}

    def test_jarvis_error_from_dict_minimal(self):
        """JarvisError.from_dict() should work with minimal data."""
        from core.exceptions.base import JarvisError

        data = {"message": "Minimal error"}
        error = JarvisError.from_dict(data)

        assert error.message == "Minimal error"

    def test_jarvis_error_can_be_raised_and_caught(self):
        """JarvisError should be raiseable and catchable."""
        from core.exceptions.base import JarvisError

        with pytest.raises(JarvisError) as exc_info:
            raise JarvisError("Test error", code="TEST_001")

        assert exc_info.value.message == "Test error"
        assert exc_info.value.code == "TEST_001"

    def test_jarvis_error_preserves_cause(self):
        """JarvisError should preserve the original cause."""
        from core.exceptions.base import JarvisError

        original = ValueError("Original error")
        try:
            raise JarvisError("Wrapped error") from original
        except JarvisError as e:
            assert e.__cause__ is original
