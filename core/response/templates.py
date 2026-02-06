"""
Response Templates - Pre-defined response templates for common scenarios.

Provides consistent formatting for error messages, success notifications,
trade alerts, portfolio summaries, and other common response types.

Example:
    from core.response.templates import error_response, success_response

    error_msg = error_response("Invalid token address")
    success_msg = success_response("Trade executed successfully")
"""

from typing import Optional, Union


# =============================================================================
# Basic Response Templates
# =============================================================================

def error_response(message: str, code: Optional[str] = None) -> str:
    """
    Format an error response message.

    Args:
        message: Error message to display
        code: Optional error code

    Returns:
        Formatted error message string
    """
    prefix = "Error"
    if code:
        return f"[X] {prefix} ({code}): {message}"
    return f"[X] {prefix}: {message}"


def success_response(message: str, details: Optional[str] = None) -> str:
    """
    Format a success response message.

    Args:
        message: Success message to display
        details: Optional additional details

    Returns:
        Formatted success message string
    """
    result = f"[OK] Success: {message}"
    if details:
        result += f"\n{details}"
    return result


def loading_response(message: Optional[str] = None) -> str:
    """
    Format a loading/processing response.

    Args:
        message: Optional custom loading message

    Returns:
        Formatted loading message string
    """
    if message:
        return f"[...] {message}"
    return "[...] Processing, please wait..."


def confirmation_response(action: str, dangerous: bool = False) -> str:
    """
    Format a confirmation prompt.

    Args:
        action: Description of the action to confirm
        dangerous: If True, add warning about irreversibility

    Returns:
        Formatted confirmation prompt string
    """
    if dangerous:
        return (
            f"[!] Warning: You are about to {action}.\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to proceed?"
        )
    return f"[?] Confirm: Are you sure you want to {action}?"


def info_response(message: str) -> str:
    """
    Format an informational response.

    Args:
        message: Information to display

    Returns:
        Formatted info message string
    """
    return f"[i] {message}"


def warning_response(message: str) -> str:
    """
    Format a warning response.

    Args:
        message: Warning message to display

    Returns:
        Formatted warning message string
    """
    return f"[!] Warning: {message}"


# =============================================================================
# Trade Response Templates
# =============================================================================

def trade_success(
    action: str,
    token: str,
    amount: float,
    price: Optional[float] = None,
    tx_hash: Optional[str] = None
) -> str:
    """
    Format a successful trade notification.

    Args:
        action: Trade action (BUY, SELL)
        token: Token symbol
        amount: Trade amount
        price: Optional execution price
        tx_hash: Optional transaction hash

    Returns:
        Formatted trade success message
    """
    lines = [
        f"[OK] Trade Executed",
        f"Action: {action}",
        f"Token: {token}",
        f"Amount: {format_amount(amount)}",
    ]

    if price is not None:
        lines.append(f"Price: {format_price(price)}")

    if tx_hash:
        short_hash = f"{tx_hash[:8]}...{tx_hash[-8:]}" if len(tx_hash) > 20 else tx_hash
        lines.append(f"TX: {short_hash}")

    return "\n".join(lines)


def trade_failed(
    action: str,
    token: str,
    reason: str,
    error_code: Optional[str] = None
) -> str:
    """
    Format a failed trade notification.

    Args:
        action: Trade action that failed (BUY, SELL)
        token: Token symbol
        reason: Failure reason
        error_code: Optional error code

    Returns:
        Formatted trade failure message
    """
    lines = [
        f"[X] Trade Failed",
        f"Action: {action}",
        f"Token: {token}",
        f"Reason: {reason}",
    ]

    if error_code:
        lines.append(f"Code: {error_code}")

    return "\n".join(lines)


# =============================================================================
# Portfolio Response Templates
# =============================================================================

def portfolio_summary(
    balance_sol: float,
    balance_usd: float,
    positions: int,
    total_pnl: float,
    win_rate: Optional[float] = None
) -> str:
    """
    Format a portfolio summary.

    Args:
        balance_sol: SOL balance
        balance_usd: USD value
        positions: Number of open positions
        total_pnl: Total P&L in USD
        win_rate: Optional win rate percentage

    Returns:
        Formatted portfolio summary
    """
    pnl_indicator = "+" if total_pnl >= 0 else ""

    lines = [
        "*Portfolio Summary*",
        "",
        f"Balance: {balance_sol:.4f} SOL",
        f"Value: ${balance_usd:,.2f}",
        f"Positions: {positions}",
        f"Total P&L: {pnl_indicator}${total_pnl:,.2f}",
    ]

    if win_rate is not None:
        lines.append(f"Win Rate: {win_rate:.1f}%")

    return "\n".join(lines)


def position_summary(
    token: str,
    entry_price: float,
    current_price: float,
    pnl_pct: float,
    value_usd: float,
    quantity: Optional[float] = None
) -> str:
    """
    Format a single position summary.

    Args:
        token: Token symbol
        entry_price: Entry price
        current_price: Current price
        pnl_pct: P&L percentage
        value_usd: Position value in USD
        quantity: Optional token quantity

    Returns:
        Formatted position summary
    """
    pnl_indicator = "+" if pnl_pct >= 0 else ""

    lines = [
        f"*{token}*",
        f"Entry: {format_price(entry_price)}",
        f"Current: {format_price(current_price)}",
        f"P&L: {pnl_indicator}{pnl_pct:.2f}%",
        f"Value: ${value_usd:,.2f}",
    ]

    if quantity is not None:
        lines.insert(1, f"Qty: {format_amount(quantity)}")

    return "\n".join(lines)


# =============================================================================
# Alert Response Templates
# =============================================================================

def price_alert(
    token: str,
    target_price: float,
    current_price: float,
    direction: str = "reached"
) -> str:
    """
    Format a price alert notification.

    Args:
        token: Token symbol
        target_price: Target price that triggered alert
        current_price: Current price
        direction: Alert direction (above, below, reached)

    Returns:
        Formatted price alert
    """
    return (
        f"[!] *Price Alert*\n"
        f"Token: {token}\n"
        f"Target: {format_price(target_price)} ({direction})\n"
        f"Current: {format_price(current_price)}"
    )


def position_alert(
    token: str,
    alert_type: str,
    trigger_price: float,
    current_pnl_pct: float
) -> str:
    """
    Format a position alert notification.

    Args:
        token: Token symbol
        alert_type: Type of alert (take_profit, stop_loss)
        trigger_price: Price that triggered the alert
        current_pnl_pct: Current P&L percentage

    Returns:
        Formatted position alert
    """
    type_display = "Take Profit" if "profit" in alert_type.lower() else "Stop Loss"
    pnl_indicator = "+" if current_pnl_pct >= 0 else ""

    return (
        f"[!] *{type_display} Triggered*\n"
        f"Token: {token}\n"
        f"Trigger Price: {format_price(trigger_price)}\n"
        f"P&L: {pnl_indicator}{current_pnl_pct:.2f}%"
    )


# =============================================================================
# Formatting Helpers
# =============================================================================

def format_price(price: float) -> str:
    """
    Format a price value appropriately.

    Args:
        price: Price value to format

    Returns:
        Formatted price string
    """
    if price >= 1:
        return f"${price:,.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    elif price >= 0.0001:
        return f"${price:.6f}"
    else:
        return f"${price:.8f}"


def format_percentage(value: float, include_sign: bool = True) -> str:
    """
    Format a percentage value.

    Args:
        value: Percentage value
        include_sign: Whether to include + for positive values

    Returns:
        Formatted percentage string
    """
    sign = "+" if include_sign and value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_amount(value: float, decimals: int = 2) -> str:
    """
    Format an amount with appropriate precision.

    Args:
        value: Amount to format
        decimals: Number of decimal places

    Returns:
        Formatted amount string
    """
    if value >= 1000:
        return f"{value:,.{decimals}f}"
    elif value >= 1:
        return f"{value:.{decimals}f}"
    else:
        # For small values, show more precision
        return f"{value:.{max(decimals, 6)}f}"
