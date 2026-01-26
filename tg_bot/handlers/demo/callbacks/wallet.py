"""
Demo Bot - Wallet Callback Handler

Handles: wallet_menu, wallet_create, export_key, receive_sol, send_sol, token_holdings, etc.
"""

import logging
from typing import Any, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_wallet(
    ctx,
    action: str,
    data: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    state: Dict[str, Any],
) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Handle wallet callbacks.

    Args:
        ctx: DemoContextLoader instance
        action: The action
        data: Full callback data
        update: Telegram update
        context: Bot context
        state: Shared state dict

    Returns:
        Tuple of (text, keyboard)
    """
    theme = ctx.JarvisTheme
    DemoMenuBuilder = ctx.DemoMenuBuilder
    wallet_address = state.get("wallet_address", "Not configured")
    sol_balance = state.get("sol_balance", 0.0)
    usd_value = state.get("usd_value", 0.0)

    if action == "wallet_menu" or action == "balance":
        # Fetch token holdings
        token_holdings = []
        total_holdings_usd = 0.0
        try:
            engine = await ctx.get_demo_engine()
            if engine and hasattr(engine, 'get_token_holdings'):
                holdings = await engine.get_token_holdings()
                if holdings:
                    token_holdings = holdings
                    total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
        except Exception:
            pass

        return DemoMenuBuilder.wallet_menu(
            wallet_address=wallet_address,
            sol_balance=sol_balance,
            usd_value=usd_value,
            has_wallet=wallet_address != "Not configured",
            token_holdings=token_holdings,
            total_holdings_usd=total_holdings_usd,
        )

    elif action == "token_holdings":
        # Detailed token holdings view
        token_holdings = []
        total_holdings_usd = 0.0
        try:
            engine = await ctx.get_demo_engine()
            if engine and hasattr(engine, 'get_token_holdings'):
                holdings = await engine.get_token_holdings()
                if holdings:
                    token_holdings = holdings
                    total_holdings_usd = sum(h.get("value_usd", 0) for h in holdings)
        except Exception:
            pass

        return DemoMenuBuilder.token_holdings_view(
            holdings=token_holdings,
            total_value=total_holdings_usd,
        )

    elif action == "wallet_activity":
        # Wallet transaction history
        transactions = []
        try:
            engine = await ctx.get_demo_engine()
            if engine and hasattr(engine, 'get_transaction_history'):
                transactions = await engine.get_transaction_history()
        except Exception:
            pass

        return DemoMenuBuilder.wallet_activity_view(transactions=transactions)

    elif action == "send_sol":
        return DemoMenuBuilder.send_sol_view(sol_balance=sol_balance)

    elif action == "receive_sol":
        text = f"""
{theme.COIN} *RECEIVE SOL*
{'=' * 20}

Your wallet address:
`{wallet_address}`

_Tap the address to copy_

{theme.WARNING} Only send SOL and Solana
   tokens to this address!

{'=' * 20}
_QR code coming in V2_
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{theme.COPY} Copy Address", callback_data="demo:copy_address")],
            [InlineKeyboardButton(f"{theme.BACK} Back", callback_data="demo:wallet_menu")],
        ])
        return text, keyboard

    elif action == "export_key_confirm":
        return DemoMenuBuilder.export_key_confirm()

    elif action == "wallet_reset_confirm":
        return DemoMenuBuilder.wallet_reset_confirm()

    elif action == "wallet_import":
        return DemoMenuBuilder.wallet_import_prompt()

    elif action == "import_mode_key":
        context.user_data["import_mode"] = "key"
        context.user_data["awaiting_wallet_import"] = True
        return DemoMenuBuilder.wallet_import_input(import_type="key")

    elif action == "import_mode_seed":
        context.user_data["import_mode"] = "seed"
        context.user_data["awaiting_wallet_import"] = True
        return DemoMenuBuilder.wallet_import_input(import_type="seed")

    elif action == "export_key":
        # Show actual private key (SENSITIVE)
        try:
            from bots.treasury.wallet import SecureWallet
            from tg_bot.handlers.demo.demo_trading import _get_demo_wallet_password, _get_demo_wallet_dir

            wallet_password = _get_demo_wallet_password()
            if not wallet_password:
                raise ValueError("Demo wallet password not configured")
            wallet = SecureWallet(
                master_password=wallet_password,
                wallet_dir=_get_demo_wallet_dir(),
            )
            private_key = wallet.get_private_key()
            wallet_address = wallet.get_address()

            text, keyboard = DemoMenuBuilder.export_key_show(
                private_key=private_key,
                wallet_address=wallet_address,
            )
            logger.warning(f"Private key exported for wallet {wallet_address[:8]}...")
            return text, keyboard
        except Exception as e:
            logger.error(f"Failed to export key: {e}")
            return DemoMenuBuilder.error_message(f"Could not export key: {str(e)[:50]}")

    elif action == "wallet_create":
        # Generate new wallet
        try:
            from bots.treasury.wallet import SecureWallet
            from tg_bot.handlers.demo.demo_trading import _get_demo_wallet_password, _get_demo_wallet_dir

            wallet_password = _get_demo_wallet_password()
            if not wallet_password:
                raise ValueError("Demo wallet password not configured")
            wallet = SecureWallet(
                master_password=wallet_password,
                wallet_dir=_get_demo_wallet_dir(),
            )
            wallet_info = wallet.create_wallet(label="Demo Treasury", is_treasury=True)
            return DemoMenuBuilder.success_message(
                action="Wallet Generated",
                details=f"New Solana wallet created and encrypted.\n\nAddress:\n`{wallet_info.address}`\n\nSend SOL to fund your trading!",
            )
        except Exception as e:
            return DemoMenuBuilder.error_message(f"Wallet creation failed: {e}")

    # Default
    return DemoMenuBuilder.wallet_menu(
        wallet_address=wallet_address,
        sol_balance=sol_balance,
        usd_value=usd_value,
        has_wallet=wallet_address != "Not configured",
    )
