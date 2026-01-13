"""Input sanitization utilities."""
import html
import re
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

DANGEROUS_PATTERNS = [
    re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),
    re.compile(r'data:', re.IGNORECASE),
]

SQL_INJECTION_PATTERNS = [
    re.compile(r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)", re.IGNORECASE),
    re.compile(r"(--|;|/\*|\*/)", re.IGNORECASE),
]


def sanitize_string(value: str, max_length: int = 10000, allow_html: bool = False) -> str:
    """Sanitize a string input."""
    if not isinstance(value, str):
        value = str(value)
    
    value = value.replace('\x00', '')
    
    if not allow_html:
        value = html.escape(value)
    else:
        for pattern in DANGEROUS_PATTERNS:
            value = pattern.sub('', value)
    
    return value[:max_length]


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal."""
    filename = filename.replace('..', '')
    filename = filename.replace('/', '').replace('\\', '')
    dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
    for char in dangerous_chars:
        filename = filename.replace(char, '')
    
    return filename[:255]


def sanitize_dict(data: Dict[str, Any], max_depth: int = 10) -> Dict[str, Any]:
    """Recursively sanitize a dictionary."""
    if max_depth <= 0:
        return {}
    
    result = {}
    for key, value in data.items():
        clean_key = sanitize_string(str(key), max_length=100)
        
        if isinstance(value, str):
            result[clean_key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[clean_key] = sanitize_dict(value, max_depth - 1)
        elif isinstance(value, list):
            result[clean_key] = sanitize_list(value, max_depth - 1)
        else:
            result[clean_key] = value
    
    return result


def sanitize_list(data: List[Any], max_depth: int = 10) -> List[Any]:
    """Recursively sanitize a list."""
    if max_depth <= 0:
        return []
    
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(sanitize_string(item))
        elif isinstance(item, dict):
            result.append(sanitize_dict(item, max_depth - 1))
        elif isinstance(item, list):
            result.append(sanitize_list(item, max_depth - 1))
        else:
            result.append(item)
    
    return result


def check_sql_injection(value: str) -> bool:
    """Check if a string contains potential SQL injection."""
    for pattern in SQL_INJECTION_PATTERNS:
        if pattern.search(value):
            logger.warning(f"Potential SQL injection detected: {value[:50]}...")
            return True
    return False


def sanitize_url(url: str) -> Optional[str]:
    """Sanitize and validate a URL."""
    from urllib.parse import urlparse, urlunparse
    
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ('http', 'https', ''):
            return None
        
        if not parsed.netloc and not parsed.path:
            return None
        
        return urlunparse(parsed)
    except Exception:
        return None
