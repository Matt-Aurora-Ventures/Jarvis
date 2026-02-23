"""
/wallet command handler for user wallet management.

Commands:
- /wallet - Show balance + address (auto-creates if no wallet)
- /wallet export - Show private key (DM only, with warning)
- /wallet import <key> - Import existing wallet
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler

from tg_bot.core.wallet_manager import get_wallet_manager

logger = logging.getLogger(__name__)


async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Main /wallet command handler.
    
    Usage:
    - /wallet - Show balance and address
    - /wallet export - Export private key (DM only)
    - /wallet import <private_key> - Import wallet
    """
    user = update.effective_user
    chat = update.effective_chat
    message = update.message
    
    if not user or not message:
        return
    
    user_id = user.id
    is_dm = chat.type == "private"
    args = context.args or []
    
    manager = get_wallet_manager()
    
    # Handle subcommands
    if args and args[0].lower() == "export":
        await _handle_export(update, context, user_id, is_dm, manager)
        return
    
    if args and args[0].lower() == "import":
        await _handle_import(update, context, user_id, is_dm, args, manager)
        return
    
    # Default: show wallet info
    await _handle_show_wallet(update, context, user_id, manager)


async def _handle_show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               user_id: int, manager) -> None:
    """Show wallet balance and address, create if doesn't exist."""
    
    wallet = await manager.get_wallet(user_id)
    
    if not wallet:
        # Auto-create wallet for new users
        wallet, private_key = await manager.create_wallet(user_id)
        
        # SECURITY: Do NOT auto-send private keys (even via DM).
        # Users can explicitly export in a private chat with /wallet export.
        await update.message.reply_text(
            "🔑 *NEW WALLET CREATED!*\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*Address:*\n`{wallet.public_key}`\n\n"
            "🔐 *Private key is NOT shown automatically.*\n"
            "To export it, open a DM with this bot and run: `\/wallet export`\n\n"
            "💰 Fund this wallet to start trading!\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Commands:\n"
            "• `/wallet` - Check balance\n"
            "• `/wallet export` - Show private key (DM only)\n"
            "• `/wallet import <key>` - Import existing wallet",
            parse_mode="Markdown"
        )
        return
    
    # Existing wallet - show balance
    balance = await manager.get_balance_sol(user_id)
    balance_str = f"{balance:.4f} SOL" if balance is not None else "Unable to fetch"
    
    # Get SOL price for USD value
    usd_value = ""
    if balance is not None:
        try:
            from bots.treasury.jupiter import JupiterClient
            jupiter = JupiterClient()
            sol_price = await jupiter.get_sol_price()
            if sol_price > 0:
                usd_value = f" (${balance * sol_price:.2f})"
        except Exception:
            pass

    await update.message.reply_text(
        "💰 *YOUR WALLET*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Address:*\n`{wallet.public_key}`\n\n"
        f"*Balance:* {balance_str}{usd_value}\n\n"
        f"[View on Solscan](https://solscan.io/account/{wallet.public_key})\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Commands:\n"
        "• `/wallet export` - Show private key (DM only)\n"
        "• `/wallet import <key>` - Replace with existing wallet",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def _handle_export(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          user_id: int, is_dm: bool, manager) -> None:
    """Export private key (DM only for security)."""
    
    if not is_dm:
        await update.message.reply_text(
            "⚠️ *SECURITY: Private keys can only be exported in DM*\n\n"
            "Send `/wallet export` directly to me in a private chat.",
            parse_mode="Markdown"
        )
        return
    
    wallet = await manager.get_wallet(user_id)
    if not wallet:
        await update.message.reply_text(
            "❌ No wallet found. Use `/wallet` to create one first.",
            parse_mode="Markdown"
        )
        return
    
    private_key = await manager.export_private_key(user_id)
    if not private_key:
        await update.message.reply_text(
            "❌ Failed to decrypt wallet. Contact support.",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(
        "🔐 *PRIVATE KEY EXPORT*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ *CRITICAL SECURITY WARNING*\n"
        "• NEVER share this with anyone\n"
        "• NEVER paste in websites\n"
        "• Store offline in secure location\n"
        "• Anyone with this key can drain your wallet\n\n"
        f"*Address:*\n`{wallet.public_key}`\n\n"
        f"*Private Key:*\n`{private_key}`\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🗑️ Delete this message after saving!",
        parse_mode="Markdown"
    )


async def _handle_import(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          user_id: int, is_dm: bool, args: list, manager) -> None:
    """Import existing wallet from private key."""
    
    if not is_dm:
        await update.message.reply_text(
            "⚠️ *SECURITY: Import wallets only in DM*\n\n"
            "Never paste private keys in group chats!\n"
            "Send `/wallet import <your_private_key>` directly to me.",
            parse_mode="Markdown"
        )
        return
    
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/wallet import <private_key>`\n\n"
            "Your private key should be a base58 string (like from Phantom export).",
            parse_mode="Markdown"
        )
        return
    
    private_key = args[1]
    
    # Check if user already has a wallet
    existing = await manager.get_wallet(user_id)
    if existing:
        await update.message.reply_text(
            "⚠️ *You already have a wallet!*\n\n"
            f"Current: `{existing.public_key}`\n\n"
            "Importing a new wallet will REPLACE your current one.\n"
            "Make sure you've exported the current key!\n\n"
            "To confirm, use:\n"
            "`/wallet import <key> --confirm`",
            parse_mode="Markdown"
        )
        if "--confirm" not in args:
            return
    
    # Try to import
    wallet = await manager.import_wallet(user_id, private_key)
    
    if not wallet:
        await update.message.reply_text(
            "❌ *Invalid private key*\n\n"
            "Make sure you're using a valid Solana private key in base58 format.\n"
            "This is typically 64-88 characters.",
            parse_mode="Markdown"
        )
        return
    
    balance = await manager.get_balance_sol(user_id)
    balance_str = f"{balance:.4f} SOL" if balance is not None else "Unable to fetch"
    
    await update.message.reply_text(
        "✅ *WALLET IMPORTED*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"*Address:*\n`{wallet.public_key}`\n\n"
        f"*Balance:* {balance_str}\n\n"
        "🗑️ Delete the message with your private key!",
        parse_mode="Markdown"
    )


def get_wallet_handlers():
    """Return handlers to register."""
    return [
        CommandHandler("wallet", wallet_command),
    ]
