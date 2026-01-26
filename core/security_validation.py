"""Input validation utilities for secure user input handling.

Prevents injection attacks, malformed data, and ensures type safety.
Use throughout Telegram handlers, FastAPI endpoints, and WebSocket handlers.

Usage:
    from core.validation import validate_token_address, validate_amount
    
    # In Telegram handler
    token_address = validate_token_address(user_input)
    amount_sol = validate_amount(amount, min_val=0.01, max_val=100.0)
"""

import re
import logging
from typing import Optional, Union
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


def validate_token_address(address: str) -> str:
    """Validate Solana token address format.
    
    Args:
        address: Token address string
        
    Returns:
        Validated address (trimmed)
        
    Raises:
        ValidationError: If address format is invalid
    """
    if not address:
        raise ValidationError("Token address cannot be empty")
    
    address = address.strip()
    
    # Solana addresses are base58 encoded, typically 32-44 characters
    if len(address) < 32 or len(address) > 44:
        raise ValidationError(
            f"Invalid token address length: {len(address)} "
            "(expected 32-44 characters)"
        )
    
    # Check for valid base58 characters
    base58_pattern = r'^[1-9A-HJ-NP-Za-km-z]+$'
    if not re.match(base58_pattern, address):
        raise ValidationError(
            "Invalid token address: contains non-base58 characters"
        )
    
    return address


def validate_amount(
    amount: Union[str, float, int, Decimal],
    min_val: float = 0.0,
    max_val: float = 1000.0,
    field_name: str = "amount"
) -> Decimal:
    """Validate trade amount.
    
    Args:
        amount: Amount value (any numeric type)
        min_val: Minimum allowed value (exclusive)
        max_val: Maximum allowed value (inclusive)
        field_name: Field name for error messages
        
    Returns:
        Validated amount as Decimal
        
    Raises:
        ValidationError: If amount is invalid or out of range
    """
    try:
        amount_decimal = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(
            f"Invalid {field_name}: must be a valid number"
        )
    
    if amount_decimal <= Decimal(str(min_val)):
        raise ValidationError(
            f"{field_name} must be greater than {min_val}"
        )
    
    if amount_decimal > Decimal(str(max_val)):
        raise ValidationError(
            f"{field_name} must be less than or equal to {max_val}"
        )
    
    return amount_decimal


def validate_percentage(
    percentage: Union[str, float, int],
    min_val: float = 0.0,
    max_val: float = 500.0,
    field_name: str = "percentage"
) -> float:
    """Validate percentage value (for TP/SL, slippage, etc.).
    
    Args:
        percentage: Percentage value
        min_val: Minimum allowed percentage
        max_val: Maximum allowed percentage  
        field_name: Field name for error messages
        
    Returns:
        Validated percentage as float
        
    Raises:
        ValidationError: If percentage is invalid or out of range
    """
    try:
        pct_float = float(percentage)
    except (ValueError, TypeError):
        raise ValidationError(
            f"Invalid {field_name}: must be a valid number"
        )
    
    if pct_float < min_val:
        raise ValidationError(
            f"{field_name} must be at least {min_val}%"
        )
    
    if pct_float > max_val:
        raise ValidationError(
            f"{field_name} must be at most {max_val}%"
        )
    
    return pct_float


def validate_user_id(user_id: Union[str, int]) -> int:
    """Validate Telegram user ID.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        Validated user ID as int
        
    Raises:
        ValidationError: If user ID is invalid
    """
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise ValidationError("Invalid user ID: must be an integer")
    
    if user_id_int <= 0:
        raise ValidationError("Invalid user ID: must be positive")
    
    # Telegram user IDs are typically < 10 digits
    if user_id_int > 9999999999:
        raise ValidationError("Invalid user ID: too large")
    
    return user_id_int


def validate_callback_data(data: str, max_length: int = 64) -> str:
    """Validate Telegram callback query data.
    
    Args:
        data: Callback data string
        max_length: Maximum allowed length (Telegram limit: 64 bytes)
        
    Returns:
        Validated data string
        
    Raises:
        ValidationError: If data is invalid
    """
    if not data:
        raise ValidationError("Callback data cannot be empty")
    
    # Check byte length (Telegram limit)
    if len(data.encode('utf-8')) > max_length:
        raise ValidationError(
            f"Callback data too long: {len(data.encode('utf-8'))} bytes "
            f"(max {max_length})"
        )
    
    # Prevent injection attempts
    if any(char in data for char in [';', '&', '|', '`', '$', '\n', '\r']):
        raise ValidationError(
            "Callback data contains forbidden characters"
        )
    
    return data


def validate_message_text(
    text: str,
    min_length: int = 1,
    max_length: int = 4096,
    allow_empty: bool = False
) -> str:
    """Validate Telegram message text.
    
    Args:
        text: Message text
        min_length: Minimum text length
        max_length: Maximum text length (Telegram limit: 4096)
        allow_empty: Allow empty strings
        
    Returns:
        Validated and trimmed text
        
    Raises:
        ValidationError: If text is invalid
    """
    if not text and not allow_empty:
        raise ValidationError("Message text cannot be empty")
    
    text = text.strip() if text else ""
    
    if len(text) < min_length and not allow_empty:
        raise ValidationError(
            f"Message text too short: {len(text)} characters "
            f"(min {min_length})"
        )
    
    if len(text) > max_length:
        raise ValidationError(
            f"Message text too long: {len(text)} characters "
            f"(max {max_length})"
        )
    
    return text


def sanitize_sql_identifier(identifier: str) -> str:
    """Sanitize SQL table/column names.
    
    IMPORTANT: Use parameterized queries instead when possible!
    This is only for dynamic table/column names that cannot be parameterized.
    
    Args:
        identifier: SQL identifier (table or column name)
        
    Returns:
        Sanitized identifier
        
    Raises:
        ValidationError: If identifier contains forbidden characters
    """
    # Only allow alphanumeric and underscore
    if not re.match(r'^[a-zA-Z0-9_]+$', identifier):
        raise ValidationError(
            f"Invalid SQL identifier: {identifier}\n"
            "Only alphanumeric characters and underscores allowed"
        )
    
    # Prevent SQL keywords
    sql_keywords = {
        'select', 'insert', 'update', 'delete', 'drop', 'create',
        'alter', 'truncate', 'exec', 'execute', 'union', 'declare'
    }
    
    if identifier.lower() in sql_keywords:
        raise ValidationError(
            f"SQL identifier cannot be a reserved keyword: {identifier}"
        )
    
    return identifier


def validate_url(url: str, allowed_schemes: Optional[list] = None) -> str:
    """Validate URL format.
    
    Args:
        url: URL string
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])
        
    Returns:
        Validated URL
        
    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")
    
    allowed_schemes = allowed_schemes or ['http', 'https']
    
    # Basic URL pattern check
    url_pattern = r'^(https?|wss?)://.+\..+'
    if not re.match(url_pattern, url):
        raise ValidationError(f"Invalid URL format: {url}")
    
    # Check scheme
    scheme = url.split('://')[0].lower()
    if scheme not in allowed_schemes:
        raise ValidationError(
            f"URL scheme '{scheme}' not allowed. "
            f"Allowed schemes: {', '.join(allowed_schemes)}"
        )
    
    return url


# Convenience function for batch validation
def validate_trade_params(
    token_address: str,
    amount_sol: Union[str, float],
    slippage_pct: Union[str, float],
    take_profit_pct: Optional[Union[str, float]] = None,
    stop_loss_pct: Optional[Union[str, float]] = None
) -> dict:
    """Validate all trade parameters at once.
    
    Args:
        token_address: Solana token address
        amount_sol: Amount in SOL
        slippage_pct: Slippage percentage
        take_profit_pct: Optional take profit percentage
        stop_loss_pct: Optional stop loss percentage
        
    Returns:
        Dict of validated parameters
        
    Raises:
        ValidationError: If any parameter is invalid
    """
    validated = {}
    
    try:
        validated['token_address'] = validate_token_address(token_address)
        validated['amount_sol'] = validate_amount(
            amount_sol,
            min_val=0.001,  # Min 0.001 SOL
            max_val=1000.0,  # Max 1000 SOL
            field_name="amount"
        )
        validated['slippage_pct'] = validate_percentage(
            slippage_pct,
            min_val=0.1,
            max_val=50.0,
            field_name="slippage"
        )
        
        if take_profit_pct is not None:
            validated['take_profit_pct'] = validate_percentage(
                take_profit_pct,
                min_val=1.0,     # Min 1% profit
                max_val=1000.0,  # Max 1000% profit
                field_name="take_profit"
            )
        
        if stop_loss_pct is not None:
            validated['stop_loss_pct'] = validate_percentage(
                stop_loss_pct,
                min_val=1.0,    # Min 1% loss
                max_val=99.0,   # Max 99% loss
                field_name="stop_loss"
            )
        
        return validated
        
    except ValidationError as e:
        logger.warning(f"Trade parameter validation failed: {e}")
        raise
