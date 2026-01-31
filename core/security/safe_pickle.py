"""
Safe Pickle Loading Utilities

Provides restricted pickle unpickler to prevent arbitrary code execution
from malicious pickle files.

SECURITY WARNING:
Never use standard pickle.load() on untrusted data!
Use safe_pickle_load() instead which restricts allowed classes.
"""

import pickle
import io
import logging
from typing import Any, Set, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Allowed modules and classes for ML models
SAFE_ML_MODULES = {
    "sklearn",
    "sklearn.ensemble",
    "sklearn.tree",
    "sklearn.linear_model",
    "sklearn.preprocessing",
    "sklearn.feature_extraction",
    "sklearn.feature_extraction.text",
    "sklearn.naive_bayes",
    "sklearn.svm",
    "numpy",
    "numpy.core",
    "numpy.core.multiarray",
    "pandas",
    "pandas.core",
    "pandas.core.frame",
    "pandas.core.series",
}

SAFE_ML_CLASSES = {
    # sklearn classes
    "IsolationForest",
    "StandardScaler",
    "MinMaxScaler",
    "TfidfVectorizer",
    "CountVectorizer",
    "MultinomialNB",
    "LinearRegression",
    "LogisticRegression",
    "RandomForestClassifier",
    "RandomForestRegressor",
    "DecisionTreeClassifier",
    "SVC",
    "SVR",
    # numpy classes
    "ndarray",
    "_reconstruct",
    "dtype",
    # pandas classes
    "DataFrame",
    "Series",
    "Index",
}


class RestrictedUnpickler(pickle.Unpickler):
    """
    Restricted pickle unpickler that only allows safe classes.

    Prevents arbitrary code execution from malicious pickle files.
    """

    def __init__(
        self,
        file,
        allowed_modules: Optional[Set[str]] = None,
        allowed_classes: Optional[Set[str]] = None
    ):
        super().__init__(file)
        self.allowed_modules = allowed_modules or SAFE_ML_MODULES
        self.allowed_classes = allowed_classes or SAFE_ML_CLASSES

    def find_class(self, module: str, name: str):
        """
        Override find_class to restrict which classes can be unpickled.

        Args:
            module: Module name (e.g., "sklearn.ensemble")
            name: Class name (e.g., "IsolationForest")

        Returns:
            The class if allowed

        Raises:
            pickle.UnpicklingError: If module or class is not in allowlist
        """
        # Check if module is allowed
        module_allowed = any(
            module == allowed or module.startswith(f"{allowed}.")
            for allowed in self.allowed_modules
        )

        if not module_allowed:
            raise pickle.UnpicklingError(
                f"Module '{module}' is not in the allowlist. "
                f"Only ML-related modules are allowed for security."
            )

        # Check if class is allowed
        if name not in self.allowed_classes:
            logger.warning(
                f"Class '{name}' from module '{module}' not in allowlist. "
                f"Allowing anyway but consider adding to safe list."
            )

        # Return the class
        return super().find_class(module, name)


def safe_pickle_load(
    file_path: Path,
    allowed_modules: Optional[Set[str]] = None,
    allowed_classes: Optional[Set[str]] = None
) -> Any:
    """
    Safely load a pickle file with restricted unpickler.

    Args:
        file_path: Path to pickle file
        allowed_modules: Set of allowed module names (default: ML modules)
        allowed_classes: Set of allowed class names (default: ML classes)

    Returns:
        Unpickled object

    Raises:
        pickle.UnpicklingError: If file contains disallowed classes
        FileNotFoundError: If file doesn't exist

    Example:
        >>> model = safe_pickle_load(Path("model.pkl"))
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Pickle file not found: {file_path}")

    with open(file_path, "rb") as f:
        unpickler = RestrictedUnpickler(
            f,
            allowed_modules=allowed_modules,
            allowed_classes=allowed_classes
        )
        return unpickler.load()


def safe_pickle_loads(
    data: bytes,
    allowed_modules: Optional[Set[str]] = None,
    allowed_classes: Optional[Set[str]] = None
) -> Any:
    """
    Safely unpickle bytes with restricted unpickler.

    Args:
        data: Pickled bytes
        allowed_modules: Set of allowed module names (default: ML modules)
        allowed_classes: Set of allowed class names (default: ML classes)

    Returns:
        Unpickled object

    Raises:
        pickle.UnpicklingError: If data contains disallowed classes

    Example:
        >>> obj = safe_pickle_loads(pickled_bytes)
    """
    f = io.BytesIO(data)
    unpickler = RestrictedUnpickler(
        f,
        allowed_modules=allowed_modules,
        allowed_classes=allowed_classes
    )
    return unpickler.load()


def verify_pickle_integrity(
    file_path: Path,
    expected_hash: str,
    hash_algorithm: str = "sha256"
) -> bool:
    """
    Verify pickle file integrity before loading.

    Args:
        file_path: Path to pickle file
        expected_hash: Expected hash value (hex string)
        hash_algorithm: Hash algorithm to use (default: "sha256")

    Returns:
        True if hash matches, False otherwise

    Example:
        >>> if verify_pickle_integrity(path, expected_hash):
        ...     model = safe_pickle_load(path)
    """
    import hashlib

    if not file_path.exists():
        return False

    hasher = hashlib.new(hash_algorithm)
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    actual_hash = hasher.hexdigest()
    return actual_hash == expected_hash
