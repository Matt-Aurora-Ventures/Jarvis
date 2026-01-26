"""
Treasury Trader

Simple trading interface for ape buttons and external consumers.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .types import Position, TradeDirection
from .trading_engine import TradingEngine
from .trading_risk import RiskChecker

logger = logging.getLogger(__name__)

# Import wallet
try:
    from ..wallet import SecureWallet, WalletInfo
except ImportError:
    SecureWallet = None
    WalletInfo = None

# Import Jupiter client
try:
    from ..jupiter import JupiterClient
except ImportError:
    JupiterClient = None

# Import emergency stop mechanism
try:
    from core.trading.emergency_stop import get_emergency_stop_manager
    EMERGENCY_STOP_AVAILABLE = True
except ImportError:
    EMERGENCY_STOP_AVAILABLE = False
    get_emergency_stop_manager = None


class _SimpleWallet:
    """
    Minimal wallet wrapper for direct keypair usage.

    Provides the interface TradingEngine expects without
    the complexity of SecureWallet encryption.
    """

    def __init__(self, keypair, address: str):
        self._keypair = keypair
        self._address = address
        self._treasury_info = WalletInfo(
            address=address,
            created_at="",
            label="Treasury",
            is_treasury=True,
        ) if WalletInfo else None

    def get_treasury(self):
        """Return the treasury wallet info."""
        return self._treasury_info

    async def get_balance(self, address: str = None) -> Tuple[float, float]:
        """Get wallet balance in SOL and USD."""
        import aiohttp
        from aiohttp import ClientTimeout
        try:
            target = address or self._address
            rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

            timeout = ClientTimeout(total=60, connect=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [target]
                }
                async with session.post(rpc_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.warning(f"RPC getBalance failed with status {resp.status}")
                        return 0.0, 0.0

                    data = await resp.json()
                    lamports = data.get("result", {}).get("value", 0)
                    sol_balance = lamports / 1e9

                    # Get SOL price
                    sol_price = 0.0
                    try:
                        cg_url = "https://api.coingecko.com/api/v3/simple/price"
                        params = {"ids": "solana", "vs_currencies": "usd"}
                        async with session.get(cg_url, params=params) as cg_resp:
                            if cg_resp.status == 200:
                                cg_data = await cg_resp.json()
                                sol_price = float(cg_data.get("solana", {}).get("usd", 0) or 0)
                    except Exception:
                        pass

                    if sol_price <= 0:
                        try:
                            sol_mint = "So11111111111111111111111111111111111111112"
                            ds_url = f"https://api.dexscreener.com/latest/dex/tokens/{sol_mint}"
                            async with session.get(ds_url) as ds_resp:
                                if ds_resp.status == 200:
                                    ds_data = await ds_resp.json()
                                    pairs = ds_data.get("pairs") or []
                                    sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                                    if sol_pairs:
                                        best = max(sol_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                                        sol_price = float(best.get("priceUsd") or 0)
                        except Exception:
                            pass

                    return sol_balance, sol_balance * sol_price if sol_price > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0, 0.0

    async def get_token_balances(self, address: str = None) -> Dict[str, Dict]:
        """Get token balances for the wallet."""
        return {}

    def sign_transaction(self, address: str, transaction) -> bytes:
        """Sign a transaction with the keypair."""
        tx_bytes = transaction
        if isinstance(transaction, (bytes, bytearray)):
            tx_bytes = bytes(transaction)
        if isinstance(tx_bytes, (bytes, bytearray)):
            try:
                from solders.transaction import VersionedTransaction

                versioned = VersionedTransaction.from_bytes(tx_bytes)
                signed_tx = VersionedTransaction(versioned.message, [self._keypair])
                return bytes(signed_tx)
            except Exception:
                signature = self._keypair.sign_message(tx_bytes)
                return bytes(signature)

        if hasattr(transaction, "sign"):
            transaction.sign([self._keypair])
            try:
                return bytes(transaction)
            except Exception:
                return b""

        signature = self._keypair.sign_message(transaction)
        return bytes(signature)

    @property
    def keypair(self):
        """Get the underlying keypair for signing."""
        return self._keypair


class TreasuryTrader:
    """
    Simple trading interface for ape buttons.

    Provides a clean execute_buy_with_tp_sl method that handles:
    - Wallet initialization
    - Jupiter quote fetching
    - Trade execution with TP/SL orders
    """

    _instances: Dict[str, "TreasuryTrader"] = {}

    def __new__(cls, profile: str = "treasury"):
        """Singleton per profile (treasury, demo, etc.)."""
        key = (profile or "treasury").strip().lower()
        if key not in cls._instances:
            inst = super().__new__(cls)
            inst._profile = key
            inst._env_prefix = "" if key == "treasury" else f"{key.upper()}_"
            inst._engine = None
            inst._initialized = False
            inst._live_mode = False
            cls._instances[key] = inst
        return cls._instances[key]

    def __init__(self, profile: str = "treasury"):
        """No-op; profile config is handled in __new__."""
        pass

    def _get_env(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Read env var with profile prefix fallback."""
        if self._env_prefix:
            value = os.environ.get(f"{self._env_prefix}{key}")
            if value not in (None, ""):
                return value
        return os.environ.get(key, default)

    def _get_wallet_password(self) -> Optional[str]:
        """Resolve wallet password with profile-aware env keys."""
        for key in ("TREASURY_WALLET_PASSWORD", "JARVIS_WALLET_PASSWORD", "WALLET_PASSWORD"):
            value = self._get_env(key)
            if value:
                return value
        return None

    def _get_wallet_dir(self) -> Path:
        """Resolve wallet directory for this profile."""
        custom_dir = self._get_env("WALLET_DIR", "")
        if custom_dir:
            return Path(custom_dir).expanduser()
        if self._profile == "treasury" and SecureWallet:
            return SecureWallet.WALLET_DIR
        root = Path(__file__).resolve().parents[3]
        return root / "bots" / "treasury" / f".wallets-{self._profile}"

    def _default_keypair_path(self) -> Path:
        """Default keypair path for the profile."""
        root = Path(__file__).resolve().parents[3]
        if self._profile == "treasury":
            return root / "data" / "treasury_keypair.json"
        return root / "data" / f"{self._profile}_treasury_keypair.json"

    def _load_encrypted_keypair(self, keypair_path):
        """Load and decrypt keypair from encrypted treasury_keypair.json."""
        import json
        import base64

        try:
            with open(keypair_path) as f:
                data = json.load(f)

            if 'encrypted_key' in data and 'salt' in data and 'nonce' in data:
                password = os.environ.get('JARVIS_WALLET_PASSWORD', '')
                if not password:
                    logger.warning("JARVIS_WALLET_PASSWORD not set - cannot decrypt keypair")
                    return None
                salt = base64.b64decode(data['salt'])
                nonce = base64.b64decode(data['nonce'])
                encrypted_key = base64.b64decode(data['encrypted_key'])

                try:
                    import nacl.secret
                    import nacl.pwhash

                    key = nacl.pwhash.argon2id.kdf(
                        nacl.secret.SecretBox.KEY_SIZE,
                        password.encode(),
                        salt,
                        opslimit=nacl.pwhash.argon2id.OPSLIMIT_MODERATE,
                        memlimit=nacl.pwhash.argon2id.MEMLIMIT_MODERATE,
                    )

                    box = nacl.secret.SecretBox(key)
                    decrypted = box.decrypt(encrypted_key, nonce)

                    from solders.keypair import Keypair
                    return Keypair.from_bytes(decrypted)

                except ImportError:
                    logger.warning("PyNaCl not installed, trying Fernet")

                try:
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.fernet import Fernet

                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=480000,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                    fernet = Fernet(key)
                    decrypted = fernet.decrypt(encrypted_key)

                    from solders.keypair import Keypair
                    return Keypair.from_bytes(decrypted)

                except Exception as e:
                    logger.error(f"Fernet decryption failed: {e}")

            elif isinstance(data, list):
                from solders.keypair import Keypair
                return Keypair.from_bytes(bytes(data))

            if 'pubkey' in data:
                logger.warning(f"Found encrypted keypair for {data['pubkey'][:8]}... but could not decrypt")

        except Exception as e:
            logger.error(f"Failed to load keypair: {e}")

        return None

    async def _ensure_initialized(self) -> Tuple[bool, str]:
        """Initialize wallet and jupiter client if not already done."""
        if self._initialized and self._engine:
            return True, "Already initialized"

        try:
            wallet = None
            treasury_address = None
            keypair = None

            # Use centralized KeyManager for treasury profile only
            if self._profile == "treasury":
                try:
                    from core.security.key_manager import get_key_manager
                    key_manager = get_key_manager()
                    keypair = key_manager.load_treasury_keypair()

                    if keypair:
                        treasury_address = str(keypair.pubkey())
                        wallet = _SimpleWallet(keypair, treasury_address)
                        logger.info(f"Loaded treasury via KeyManager: {treasury_address[:8]}...")
                except ImportError:
                    logger.warning("KeyManager not available, using legacy loader")

            # Fallback to legacy loading
            if not wallet:
                root = Path(__file__).resolve().parents[3]
                env_paths = (root / "tg_bot" / ".env", root / ".env")
                try:
                    from dotenv import load_dotenv
                    for env_path in env_paths:
                        if env_path.exists():
                            load_dotenv(env_path, override=False)
                except Exception:
                    pass

                if not self._get_wallet_password():
                    for env_path in env_paths:
                        if not env_path.exists():
                            continue
                        try:
                            for line in env_path.read_text(encoding="utf-8").splitlines():
                                line = line.strip()
                                if not line or line.startswith("#") or "=" not in line:
                                    continue
                                key, value = line.split("=", 1)
                                key = key.strip()
                                value = value.strip().strip('"').strip("'")
                                if key and key not in os.environ:
                                    os.environ[key] = value
                        except Exception:
                            continue

                env_path_str = (self._get_env("TREASURY_KEYPAIR_PATH", "") or self._get_env("TREASURY_WALLET_PATH", "")).strip()
                keypair_path = Path(env_path_str).expanduser() if env_path_str else self._default_keypair_path()

                if keypair_path.exists():
                    try:
                        keypair = self._load_encrypted_keypair(keypair_path)
                        if keypair:
                            treasury_address = str(keypair.pubkey())
                            logger.info(f"Loaded treasury keypair: {treasury_address[:8]}...")
                            wallet = _SimpleWallet(keypair, treasury_address)
                    except Exception as kp_err:
                        logger.warning(f"Keypair load failed: {kp_err}")

            # Fallback to SecureWallet
            if not wallet and SecureWallet:
                wallet_password = self._get_wallet_password()
                if not wallet_password:
                    logger.warning("Wallet password not set - running in simulation mode")
                    return False, "No wallet found - check treasury_keypair.json or wallet password env var"

                try:
                    secure_wallet = SecureWallet(
                        master_password=wallet_password,
                        wallet_dir=self._get_wallet_dir(),
                    )
                    treasury = secure_wallet.get_treasury()
                    if treasury:
                        wallet = secure_wallet
                        treasury_address = treasury.address
                except Exception as wallet_err:
                    logger.warning(f"SecureWallet init failed: {wallet_err}")

            if not wallet:
                return False, "No treasury wallet found - create data/treasury_keypair.json"

            # Initialize Jupiter client
            rpc_url = self._get_env("SOLANA_RPC_URL", None)
            jupiter = JupiterClient(rpc_url=rpc_url)

            admin_ids = []
            admin_ids_str = self._get_env("TREASURY_ADMIN_IDS") or self._get_env("TELEGRAM_ADMIN_IDS", "")
            if admin_ids_str:
                admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

            # Create trading engine
            live_mode = str(self._get_env("TREASURY_LIVE_MODE", "false")).lower() in ("1", "true", "yes", "on")
            self._live_mode = live_mode
            use_bags_env = str(self._get_env("USE_BAGS_TRADING", "")).lower() in ("1", "true", "yes", "on")
            use_bags = True if (self._profile != "treasury") else use_bags_env
            self._engine = TradingEngine(
                wallet=wallet,
                jupiter=jupiter,
                dry_run=not live_mode,
                max_positions=50,
                admin_user_ids=admin_ids,
                use_bags=use_bags,
                state_profile=self._profile if self._profile != "treasury" else None,
            )
            await self._engine.initialize_order_manager()

            self._initialized = True
            logger.info(f"TreasuryTrader initialized with wallet {treasury_address[:8]}...")
            return True, f"Initialized with {treasury_address[:8]}..."

        except Exception as e:
            logger.error(f"Failed to initialize TreasuryTrader: {e}")
            return False, str(e)

    def get_tp_sl_levels(self, entry_price: float, sentiment_grade: str) -> Tuple[float, float]:
        """Calculate take profit and stop loss prices."""
        return RiskChecker.get_tp_sl_levels(entry_price, sentiment_grade)

    async def execute_buy_with_tp_sl(
        self,
        token_mint: str,
        amount_sol: float,
        take_profit_price: float,
        stop_loss_price: float,
        token_symbol: str = "",
        user_id: Optional[int] = None,
        sentiment_grade: str = "B",
    ) -> Dict[str, Any]:
        """
        Execute a buy trade with take profit and stop loss.

        Args:
            token_mint: Token contract address (can be partial)
            amount_sol: Amount in SOL to spend
            take_profit_price: Take profit target price
            stop_loss_price: Stop loss target price
            token_symbol: Token symbol for logging
            user_id: User ID for authorization
            sentiment_grade: Sentiment grade for TP/SL config

        Returns:
            Dict with success, tx_signature, error, and message
        """
        # Check emergency stop FIRST
        if EMERGENCY_STOP_AVAILABLE:
            emergency_manager = get_emergency_stop_manager()
            allowed, reason = emergency_manager.is_trading_allowed(token_mint)
            if not allowed:
                logger.warning(f"Trade blocked by emergency stop: {reason}")
                return {
                    "success": False,
                    "error": f"EMERGENCY STOP: {reason}",
                    "tx_signature": "",
                }

        # Initialize if needed
        initialized, init_msg = await self._ensure_initialized()
        if not initialized:
            return {
                "success": False,
                "error": init_msg,
                "tx_signature": "",
            }
        if user_id is None:
            return {
                "success": False,
                "error": "User ID required for trade authorization",
                "tx_signature": "",
            }

        try:
            # Resolve partial contract address if needed
            logger.info(f"Resolving token: mint={token_mint}, symbol={token_symbol}")
            full_mint = await self._resolve_token_mint(token_mint, token_symbol)
            if not full_mint:
                logger.error(f"Failed to resolve token address for {token_symbol or token_mint}")
                return {
                    "success": False,
                    "error": f"Could not resolve token address for {token_symbol or token_mint}",
                    "tx_signature": "",
                }
            logger.info(f"Resolved to: {full_mint}")

            # Get current price
            current_price = await self._engine.jupiter.get_token_price(full_mint)
            if current_price <= 0:
                return {
                    "success": False,
                    "error": "Could not fetch current token price",
                    "tx_signature": "",
                }

            # Validate TP/SL inputs
            try:
                tp_val = float(take_profit_price)
            except (TypeError, ValueError):
                tp_val = 0.0
            try:
                sl_val = float(stop_loss_price)
            except (TypeError, ValueError):
                sl_val = 0.0

            if tp_val <= 0 or sl_val <= 0 or tp_val <= current_price or sl_val >= current_price:
                fallback_tp, fallback_sl = self.get_tp_sl_levels(current_price, sentiment_grade)
                logger.warning(
                    "Invalid TP/SL provided; falling back to defaults | "
                    f"tp={take_profit_price} sl={stop_loss_price} entry={current_price:.6f}"
                )
                take_profit_price = fallback_tp
                stop_loss_price = fallback_sl
            else:
                take_profit_price = tp_val
                stop_loss_price = sl_val

            # Get SOL price for USD conversion
            sol_price = await self._engine.jupiter.get_token_price(JupiterClient.SOL_MINT)
            amount_usd = amount_sol * sol_price

            # Calculate custom TP/SL percentages
            tp_pct = (take_profit_price - current_price) / current_price
            sl_pct = (current_price - stop_loss_price) / current_price

            # Get token info for symbol
            token_info = await self._engine.jupiter.get_token_info(full_mint)
            symbol = token_symbol or (token_info.symbol if token_info else "UNKNOWN")

            logger.info(
                f"Executing buy: {symbol} | {amount_sol:.4f} SOL (${amount_usd:.2f}) | "
                f"Entry: ${current_price:.6f} | TP: ${take_profit_price:.6f} | SL: ${stop_loss_price:.6f}"
            )

            # Open position through trading engine
            success, message, position = await self._engine.open_position(
                token_mint=full_mint,
                token_symbol=symbol,
                direction=TradeDirection.LONG,
                amount_usd=amount_usd,
                sentiment_grade=sentiment_grade,
                custom_tp=tp_pct,
                custom_sl=sl_pct,
                user_id=user_id,
            )

            if success and position:
                return {
                    "success": True,
                    "tx_signature": message.split(": ")[-1] if ": " in message else "",
                    "message": message,
                    "position_id": position.id,
                    "entry_price": position.entry_price,
                    "amount_tokens": position.amount,
                }
            else:
                return {
                    "success": False,
                    "error": message,
                    "tx_signature": "",
                }

        except Exception as e:
            logger.error(f"Trade execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "tx_signature": "",
            }

    async def _resolve_token_mint(self, partial_mint: str, symbol: str = "") -> Optional[str]:
        """Resolve a partial token mint to full address."""
        if len(partial_mint) >= 32:
            logger.info(f"Token mint already full length: {partial_mint[:12]}...")
            return partial_mint

        import aiohttp

        logger.info(f"Resolving partial mint '{partial_mint}' with symbol '{symbol}'")
        try:
            from aiohttp import ClientTimeout
            timeout = ClientTimeout(total=60, connect=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                search_term = symbol or partial_mint
                url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"
                logger.info(f"DexScreener search: {url}")

                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pairs = data.get("pairs", [])

                        solana_pairs = [
                            p for p in pairs
                            if p.get("chainId") == "solana"
                            and (
                                p.get("baseToken", {}).get("symbol", "").upper() == search_term.upper()
                                or search_term.upper() in p.get("baseToken", {}).get("name", "").upper()
                                or p.get("baseToken", {}).get("address", "").startswith(partial_mint)
                            )
                        ]

                        if solana_pairs:
                            best = max(solana_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                            full_address = best.get("baseToken", {}).get("address")
                            if full_address:
                                logger.info(f"Resolved {search_term} to {full_address[:8]}...")
                                return full_address
        except Exception as e:
            logger.error(f"Failed to resolve token mint: {e}")

        return None

    async def get_balance(self) -> Tuple[float, float]:
        """Get treasury balance in SOL and USD."""
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return 0.0, 0.0
        return await self._engine.get_portfolio_value()

    async def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return []
        return self._engine.get_open_positions()

    async def close_position(self, position_id: str, user_id: int = None) -> Tuple[bool, str]:
        """Close a position by ID."""
        initialized, msg = await self._ensure_initialized()
        if not initialized:
            return False, msg
        return await self._engine.close_position(position_id, user_id=user_id)

    async def monitor_and_close_breached_positions(self) -> List[Dict[str, Any]]:
        """Check all positions and close any that have breached their stop loss."""
        initialized, msg = await self._ensure_initialized()
        if not initialized:
            return []
        return await self._engine.monitor_stop_losses()

    async def get_position_health(self) -> Dict[str, Any]:
        """Get health status of all positions."""
        initialized, _ = await self._ensure_initialized()
        if not initialized:
            return {"healthy": False, "error": "Not initialized"}

        positions = self._engine.get_open_positions()
        if not positions:
            return {"healthy": True, "positions": [], "alerts": []}

        alerts = []
        position_status = []

        for pos in positions:
            if pos.entry_price > 0:
                pnl_pct = ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
            else:
                pnl_pct = 0

            status = "OK"
            if pos.current_price <= pos.stop_loss_price:
                status = "SL_BREACHED"
                alerts.append(f"{pos.token_symbol} has breached SL ({pnl_pct:+.1f}%)")
            elif pnl_pct <= -50:
                status = "CRITICAL"
                alerts.append(f"{pos.token_symbol} down {pnl_pct:.1f}%")
            elif pnl_pct <= -20:
                status = "WARNING"
            elif pos.current_price >= pos.take_profit_price:
                status = "TP_HIT"
                alerts.append(f"{pos.token_symbol} hit TP ({pnl_pct:+.1f}%)")

            position_status.append({
                "id": pos.id,
                "symbol": pos.token_symbol,
                "entry": pos.entry_price,
                "current": pos.current_price,
                "pnl_pct": pnl_pct,
                "tp": pos.take_profit_price,
                "sl": pos.stop_loss_price,
                "status": status,
            })

        return {
            "healthy": len(alerts) == 0,
            "positions": position_status,
            "alerts": alerts,
        }
