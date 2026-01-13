"""Sensitive data filtering for logs."""
import re
import logging
from typing import List, Tuple, Pattern, Any


class SensitiveDataFilter(logging.Filter):
    """Filter sensitive data from log messages."""
    
    PATTERNS: List[Tuple[Pattern, str]] = [
        (re.compile(r'(api[_-]?key\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{20,})(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(secret\s*[:=]\s*["\']?)([a-zA-Z0-9_-]{16,})(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(password\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(token\s*[:=]\s*["\']?)([a-zA-Z0-9_.-]{20,})(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(bearer\s+)([a-zA-Z0-9_.-]+)', re.IGNORECASE), r'\1***MASKED***'),
        (re.compile(r'(private[_-]?key\s*[:=]\s*["\']?)([^\s"\']+)(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(["\']?Authorization["\']?\s*:\s*["\']?)([^"\'}\]]+)(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'(["\']?X-API-Key["\']?\s*:\s*["\']?)([^"\'}\]]+)(["\']?)', re.IGNORECASE), r'\1***MASKED***\3'),
        (re.compile(r'\b([0-9]{13,16})\b'), lambda m: m.group(1)[:4] + '****' + m.group(1)[-4:]),
        (re.compile(r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b'), lambda m: m.group(1)[:3] + '***@***'),
        (re.compile(r'([1-9A-HJ-NP-Za-km-z]{32,44})'), lambda m: m.group(1)[:6] + '...' + m.group(1)[-4:] if len(m.group(1)) > 20 else m.group(1)),
        (re.compile(r'(0x[a-fA-F0-9]{40})'), lambda m: m.group(1)[:10] + '...' + m.group(1)[-4:]),
    ]
    
    def __init__(self, name: str = '', additional_patterns: List[Tuple[str, str]] = None):
        super().__init__(name)
        if additional_patterns:
            for pattern, replacement in additional_patterns:
                self.PATTERNS.append((re.compile(pattern), replacement))
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.mask_sensitive(str(record.msg))
        
        if record.args:
            record.args = tuple(
                self.mask_sensitive(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def mask_sensitive(self, text: str) -> str:
        """Mask sensitive data in text."""
        for pattern, replacement in self.PATTERNS:
            if callable(replacement):
                text = pattern.sub(replacement, text)
            else:
                text = pattern.sub(replacement, text)
        return text


def mask_dict(data: dict, sensitive_keys: List[str] = None) -> dict:
    """Mask sensitive values in a dictionary."""
    if sensitive_keys is None:
        sensitive_keys = [
            'password', 'secret', 'token', 'key', 'api_key', 'apikey',
            'authorization', 'auth', 'credential', 'private_key'
        ]
    
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        if any(sk in key_lower for sk in sensitive_keys):
            if isinstance(value, str) and len(value) > 4:
                result[key] = value[:2] + '***' + value[-2:]
            else:
                result[key] = '***MASKED***'
        elif isinstance(value, dict):
            result[key] = mask_dict(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                mask_dict(item, sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    
    return result


def setup_sensitive_logging():
    """Add sensitive data filter to all handlers."""
    filter_instance = SensitiveDataFilter()
    
    for handler in logging.root.handlers:
        handler.addFilter(filter_instance)
    
    logging.root.addFilter(filter_instance)


sensitive_filter = SensitiveDataFilter()
