"""Handle wallet import input."""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from ..demo_ui import DemoMenuBuilder

logger = logging.getLogger(__name__)


def _get_demo_wallet_password() -> str:
    """Get demo wallet password from environment."""
    import os
    return os.getenv("DEMO_WALLET_PASSWORD", "")


def _get_demo_wallet_dir() -> str:
    """Get demo wallet directory."""
    from pathlib import Path
    return str(Path(__file__).parents[4] / "data" / "demo_wallets")


async def handle_wallet_import(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    text: str
) -> bool:
    """
    Handle wallet import input (seed phrase or private key).
    
    Args:
        update: Telegram update
        context: Bot context
        text: User input (seed phrase or private key)
        
    Returns:
        True if handled, False if not applicable
    """
    if not context.user_data.get("awaiting_wallet_import"):
        return False
        
    context.user_data["awaiting_wallet_import"] = False
    import_mode = context.user_data.get("import_mode", "key")

    try:
        from bots.treasury.wallet import SecureWallet
        from core.wallet_service import WalletService

        wallet_password = _get_demo_wallet_password()
        if not wallet_password:
            raise ValueError("Demo wallet password not configured")

        wallet_service = WalletService()
        private_key = None

        if import_mode == "seed":
            words = text.strip().split()
            if len(words) not in [12, 24]:
                raise ValueError(f"Seed phrase must be 12 or 24 words, got {len(words)}")
            wallet_data, _ = await wallet_service.import_wallet(
                seed_phrase=text.strip(),
                user_password=wallet_password,
            )
            private_key = wallet_data.private_key
        else:
            if len(text.strip()) < 64:
                raise ValueError("Private key too short (min 64 chars)")
            wallet_data, _ = await wallet_service.import_from_private_key(
                private_key=text.strip(),
                user_password=wallet_password,
            )
            private_key = wallet_data.private_key

        secure_wallet = SecureWallet(
            master_password=wallet_password,
            wallet_dir=_get_demo_wallet_dir(),
        )
        wallet_info = secure_wallet.import_wallet(private_key, label="Demo Imported")
        wallet_address = wallet_info.address

        result_text, keyboard = DemoMenuBuilder.wallet_import_result(
            success=True,
            wallet_address=wallet_address,
        )
        logger.info(f"Wallet imported: {wallet_address[:8]}...")

    except Exception as exc:
        logger.error(f"Wallet import failed: {exc}")
        result_text, keyboard = DemoMenuBuilder.wallet_import_result(
            success=False,
            error=str(exc)[:100],
        )

    await update.message.reply_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )
    
    return True
