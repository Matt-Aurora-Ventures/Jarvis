"""
Security Verification Tests for Pickle Protection

Tests that safe_pickle_load blocks malicious pickle files.
Part of security audit remediation (SECURITY_AUDIT_JAN_31.md).
"""

import pickle
import io
import pytest
from pathlib import Path
from core.security.safe_pickle import safe_pickle_load, safe_pickle_loads, RestrictedUnpickler


class MaliciousClass:
    """Malicious class that executes code on unpickling."""

    def __reduce__(self):
        """Return exploit code to execute on unpickle."""
        import os
        return (os.system, ("echo 'EXPLOIT EXECUTED' > /tmp/exploit_test.txt",))


class SafeMLModel:
    """Simulates a safe sklearn model."""
    pass


def test_safe_pickle_blocks_malicious_class(tmp_path):
    """Verify safe_pickle_load blocks classes not in allowlist."""
    # Create malicious pickle file
    malicious_file = tmp_path / "malicious.pkl"
    with open(malicious_file, "wb") as f:
        pickle.dump(MaliciousClass(), f)

    # Verify safe_pickle_load blocks it
    with pytest.raises(pickle.UnpicklingError, match="Module.*not in the allowlist"):
        safe_pickle_load(malicious_file)


def test_safe_pickle_allows_sklearn(tmp_path):
    """Verify safe_pickle_load allows sklearn classes."""
    # This test requires sklearn installed
    pytest.importorskip("sklearn")

    from sklearn.ensemble import IsolationForest

    # Create legitimate sklearn model
    model = IsolationForest(random_state=42)
    model_file = tmp_path / "model.pkl"

    with open(model_file, "wb") as f:
        pickle.dump(model, f)

    # Verify safe_pickle_load allows it
    loaded_model = safe_pickle_load(model_file)
    assert isinstance(loaded_model, IsolationForest)


def test_safe_pickle_loads_blocks_malicious_bytes():
    """Verify safe_pickle_loads blocks malicious pickled bytes."""
    # Create malicious pickle bytes
    malicious_bytes = pickle.dumps(MaliciousClass())

    # Verify safe_pickle_loads blocks it
    with pytest.raises(pickle.UnpicklingError, match="Module.*not in the allowlist"):
        safe_pickle_loads(malicious_bytes)


def test_safe_pickle_custom_allowlist(tmp_path):
    """Verify safe_pickle_load works with custom allowlist."""
    # Create a custom class
    class CustomSafeClass:
        def __init__(self):
            self.value = 42

    custom_file = tmp_path / "custom.pkl"
    obj = CustomSafeClass()

    with open(custom_file, "wb") as f:
        pickle.dump(obj, f)

    # Try to load with default allowlist (should warn but allow)
    loaded = safe_pickle_load(custom_file)
    assert loaded.value == 42

    # Try to load with custom allowlist that includes our module
    custom_modules = {"test_pickle_security", "__main__"}
    custom_classes = {"CustomSafeClass"}

    loaded2 = safe_pickle_load(
        custom_file,
        allowed_modules=custom_modules,
        allowed_classes=custom_classes
    )
    assert loaded2.value == 42


def test_restricted_unpickler_blocks_os_system():
    """Verify RestrictedUnpickler blocks os.system exploit."""
    # Create exploit pickle that tries to execute os.system
    import os
    exploit_bytes = pickle.dumps(os.system)

    # Verify it's blocked
    f = io.BytesIO(exploit_bytes)
    unpickler = RestrictedUnpickler(f)

    with pytest.raises(pickle.UnpicklingError, match="Module.*not in the allowlist"):
        unpickler.load()


def test_restricted_unpickler_blocks_eval():
    """Verify RestrictedUnpickler blocks eval exploit."""
    # Create exploit pickle that tries to use eval
    exploit_bytes = pickle.dumps(eval)

    # Verify it's blocked
    f = io.BytesIO(exploit_bytes)
    unpickler = RestrictedUnpickler(f)

    with pytest.raises(pickle.UnpicklingError, match="Module.*not in the allowlist"):
        unpickler.load()


def test_safe_pickle_file_not_found():
    """Verify safe_pickle_load raises FileNotFoundError for missing files."""
    nonexistent = Path("/tmp/does_not_exist_12345.pkl")

    with pytest.raises(FileNotFoundError, match="Pickle file not found"):
        safe_pickle_load(nonexistent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
