"""Utility functions for demo input handlers."""

from telegram.ext import ContextTypes


def resolve_token_ref(context: ContextTypes.DEFAULT_TYPE, token_ref: str) -> str:
    """
    Resolve a token reference ID to actual token address.
    
    Args:
        context: Bot context containing token_registry
        token_ref: Token reference ID (e.g., "tok_001")
        
    Returns:
        Token address string
    """
    registry = context.user_data.get("token_registry", {})
    return registry.get(token_ref, token_ref)


def register_token_id(context: ContextTypes.DEFAULT_TYPE, token_address: str) -> str:
    """
    Register a token address and get a short reference ID.
    
    Args:
        context: Bot context
        token_address: Full Solana token address
        
    Returns:
        Short reference ID for callbacks
    """
    registry = context.user_data.setdefault("token_registry", {})
    reverse_registry = context.user_data.setdefault("token_reverse_registry", {})
    
    # Check if already registered
    if token_address in reverse_registry:
        return reverse_registry[token_address]
    
    # Generate new ID
    token_id = f"tok_{len(registry):03d}"
    registry[token_id] = token_address
    reverse_registry[token_address] = token_id
    
    return token_id
