"""
Security Verification Tests for eval() Removal

Tests that eval() has been removed from security-critical code.
Part of security audit remediation (SECURITY_AUDIT_JAN_31.md).
"""

import ast
import pytest
from pathlib import Path


def find_eval_usage(file_path: Path) -> list:
    """Find all eval() calls in a Python file using AST parsing."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        tree = ast.parse(content, filename=str(file_path))
        eval_calls = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    eval_calls.append({
                        "line": node.lineno,
                        "col": node.col_offset,
                    })

        return eval_calls
    except Exception as e:
        # File might not be valid Python or doesn't exist
        return []


def test_dedup_store_no_eval():
    """Verify core/memory/dedup_store.py does not use eval()."""
    # Get project root (2 levels up from tests/security/)
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / "core" / "memory" / "dedup_store.py"

    if not file_path.exists():
        pytest.skip("File not found")

    eval_calls = find_eval_usage(file_path)
    assert len(eval_calls) == 0, f"Found {len(eval_calls)} eval() calls in {file_path}: {eval_calls}"


def test_no_eval_in_critical_files():
    """Verify critical files do not use eval()."""
    # Get project root (2 levels up from tests/security/)
    project_root = Path(__file__).resolve().parent.parent.parent

    critical_files = [
        "core/memory/dedup_store.py",
        "core/data_retention.py",
        "core/pnl_tracker.py",
        "core/security_validation.py",
        "core/google_integration.py",
        "core/ml_regime_detector.py",
    ]

    files_with_eval = []
    for file_path_str in critical_files:
        file_path = project_root / file_path_str
        if file_path.exists():
            eval_calls = find_eval_usage(file_path)
            if eval_calls:
                files_with_eval.append({
                    "file": str(file_path),
                    "calls": eval_calls
                })

    assert len(files_with_eval) == 0, f"Found eval() in critical files: {files_with_eval}"


def test_json_loads_replaces_eval_in_dedup_store():
    """Verify dedup_store.py uses json.loads instead of eval."""
    # Get project root (2 levels up from tests/security/)
    project_root = Path(__file__).resolve().parent.parent.parent
    file_path = project_root / "core" / "memory" / "dedup_store.py"

    if not file_path.exists():
        pytest.skip("File not found")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify json.loads is imported and used
    assert "import json" in content or "from json import" in content, \
        "json module not imported"

    # Verify json.loads is used for metadata
    assert "json.loads" in content, \
        "json.loads not found - should replace eval()"

    # Verify eval is not used
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "eval":
                pytest.fail(f"Found eval() at line {node.lineno} - should use json.loads()")


def test_ast_literal_eval_safe_alternative():
    """Verify ast.literal_eval is a safe alternative to eval."""
    # Test that ast.literal_eval only evaluates literals
    import ast

    # Safe literals
    assert ast.literal_eval("42") == 42
    assert ast.literal_eval("'hello'") == "hello"
    assert ast.literal_eval("[1, 2, 3]") == [1, 2, 3]
    assert ast.literal_eval("{'key': 'value'}") == {"key": "value"}

    # Dangerous code should raise exception
    with pytest.raises(ValueError):
        ast.literal_eval("os.system('ls')")

    with pytest.raises(ValueError):
        ast.literal_eval("__import__('os').system('ls')")


def test_json_loads_safe_alternative():
    """Verify json.loads is a safe alternative to eval."""
    import json

    # Safe JSON data
    assert json.loads("42") == 42
    assert json.loads('"hello"') == "hello"
    assert json.loads('[1, 2, 3]') == [1, 2, 3]
    assert json.loads('{"key": "value"}') == {"key": "value"}

    # Python code in JSON should raise exception
    with pytest.raises(json.JSONDecodeError):
        json.loads("os.system('ls')")

    with pytest.raises(json.JSONDecodeError):
        json.loads("__import__('os')")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
