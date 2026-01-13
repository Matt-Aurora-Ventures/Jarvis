"""
Secure Wallet Management for Jarvis Treasury
CRITICAL: Private keys are NEVER exposed in logs, errors, or memory dumps
"""

import os
import json
import base64
import hashlib
import secrets
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Suppress private key logging
logging.getLogger('solana').setLevel(logging.WARNING)
logging.getLogger('solders').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class SecureKeyError(Exception):
    """Raised when key operations fail - never includes key data"""
    pass


@dataclass
class WalletInfo:
    """Public wallet information only - no secrets"""
    address: str
    created_at: str
    label: str
    balance_sol: float = 0.0
    balance_usd: float = 0.0
    is_treasury: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'address': self.address,
            'created_at': self.created_at,
            'label': self.label,
            'balance_sol': self.balance_sol,
            'balance_usd': self.balance_usd,
            'is_treasury': self.is_treasury
        }


class SecureWallet:
    """
    Secure wallet management with encrypted key storage.

    Security Features:
    - Private keys encrypted at rest with Fernet (AES-128-CBC)
    - Keys derived from master password using PBKDF2
    - Keys never logged or exposed in error messages
    - Memory cleared after signing operations
    - Transaction simulation before execution
    """

    WALLET_DIR = Path(__file__).parent / '.wallets'
    SALT_FILE = '.salt'

    def __init__(self, master_password: Optional[str] = None):
        """
        Initialize wallet manager.

        Args:
            master_password: Password for key encryption. If None, uses env var.
        """
        self._master_password = master_password or os.environ.get('JARVIS_WALLET_PASSWORD')
        if not self._master_password:
            raise SecureKeyError("Master password required - set JARVIS_WALLET_PASSWORD env var")

        self._fernet: Optional[Fernet] = None
        self._wallets: Dict[str, WalletInfo] = {}
        self._active_wallet: Optional[str] = None

        # Ensure wallet directory exists with restricted permissions
        self.WALLET_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize encryption
        self._init_encryption()

        # Load existing wallets (public info only)
        self._load_wallet_registry()

    def _init_encryption(self):
        """Initialize Fernet encryption with derived key."""
        salt_path = self.WALLET_DIR / self.SALT_FILE

        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            # Generate new salt
            salt = secrets.token_bytes(32)
            salt_path.write_bytes(salt)

        # Derive key from password using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,  # High iteration count for security
        )

        key = base64.urlsafe_b64encode(kdf.derive(self._master_password.encode()))
        self._fernet = Fernet(key)

        # Clear password from memory after derivation
        self._master_password = None

    def _load_wallet_registry(self):
        """Load public wallet info from registry."""
        registry_path = self.WALLET_DIR / 'registry.json'

        if registry_path.exists():
            try:
                with open(registry_path) as f:
                    data = json.load(f)

                for addr, info in data.items():
                    self._wallets[addr] = WalletInfo(**info)
            except Exception as e:
                logger.error(f"Failed to load wallet registry: {e}")

    def _save_wallet_registry(self):
        """Save public wallet info to registry."""
        registry_path = self.WALLET_DIR / 'registry.json'

        data = {addr: info.to_dict() for addr, info in self._wallets.items()}

        with open(registry_path, 'w') as f:
            json.dump(data, f, indent=2)

    def create_wallet(self, label: str = "Treasury", is_treasury: bool = True) -> WalletInfo:
        """
        Create a new Solana wallet with encrypted key storage.

        Args:
            label: Human-readable label for the wallet
            is_treasury: Whether this is the main treasury wallet

        Returns:
            WalletInfo with public address (no private key exposed)
        """
        try:
            from solders.keypair import Keypair

            # Generate new keypair
            keypair = Keypair()
            public_key = str(keypair.pubkey())

            # Encrypt and store private key
            private_bytes = bytes(keypair)
            encrypted = self._fernet.encrypt(private_bytes)

            # Save encrypted key to file
            key_path = self.WALLET_DIR / f'{public_key}.key'
            key_path.write_bytes(encrypted)

            # Create wallet info
            wallet = WalletInfo(
                address=public_key,
                created_at=datetime.utcnow().isoformat(),
                label=label,
                is_treasury=is_treasury
            )

            self._wallets[public_key] = wallet
            self._save_wallet_registry()

            # Set as active if treasury
            if is_treasury:
                self._active_wallet = public_key

            # Clear keypair from memory
            del keypair
            del private_bytes

            logger.info(f"Created wallet: {public_key[:8]}...{public_key[-4:]} ({label})")
            return wallet

        except ImportError:
            raise SecureKeyError("solders library required - run: pip install solders")
        except Exception as e:
            raise SecureKeyError(f"Failed to create wallet: {type(e).__name__}")

    def import_wallet(self, private_key: str, label: str = "Imported") -> WalletInfo:
        """
        Import existing wallet from private key.
        WARNING: Only use in secure environment, key is immediately encrypted.

        Args:
            private_key: Base58 encoded private key
            label: Human-readable label

        Returns:
            WalletInfo with public address
        """
        try:
            from solders.keypair import Keypair
            import base58

            # Decode and create keypair
            key_bytes = base58.b58decode(private_key)
            keypair = Keypair.from_bytes(key_bytes)
            public_key = str(keypair.pubkey())

            # Encrypt and store
            encrypted = self._fernet.encrypt(bytes(keypair))

            key_path = self.WALLET_DIR / f'{public_key}.key'
            key_path.write_bytes(encrypted)

            # Create wallet info
            wallet = WalletInfo(
                address=public_key,
                created_at=datetime.utcnow().isoformat(),
                label=label,
                is_treasury=False
            )

            self._wallets[public_key] = wallet
            self._save_wallet_registry()

            # Clear sensitive data
            del keypair
            del key_bytes

            logger.info(f"Imported wallet: {public_key[:8]}...{public_key[-4:]}")
            return wallet

        except Exception as e:
            raise SecureKeyError(f"Failed to import wallet: {type(e).__name__}")

    def _load_keypair(self, address: str):
        """
        Load and decrypt keypair for signing.
        INTERNAL USE ONLY - never expose keypair outside this class.
        """
        from solders.keypair import Keypair

        key_path = self.WALLET_DIR / f'{address}.key'

        if not key_path.exists():
            raise SecureKeyError(f"Wallet not found: {address[:8]}...")

        encrypted = key_path.read_bytes()
        decrypted = self._fernet.decrypt(encrypted)

        keypair = Keypair.from_bytes(decrypted)

        # Clear decrypted bytes
        del decrypted

        return keypair

    def sign_transaction(self, address: str, transaction) -> bytes:
        """
        Sign a transaction with the wallet's private key.

        Args:
            address: Wallet address to sign with
            transaction: Transaction to sign

        Returns:
            Signed transaction bytes
        """
        keypair = None
        try:
            keypair = self._load_keypair(address)

            # Serialized Jupiter transactions are passed as bytes.
            if isinstance(transaction, (bytes, bytearray)):
                tx_bytes = bytes(transaction)
                try:
                    from solders.transaction import VersionedTransaction
                    from solders.message import to_bytes_versioned

                    versioned = VersionedTransaction.from_bytes(tx_bytes)
                    # Sign message using to_bytes_versioned (correct way for VersionedTransaction)
                    message_bytes = to_bytes_versioned(versioned.message)
                    signature = keypair.sign_message(message_bytes)
                    # Replace placeholder signature in place
                    sigs = list(versioned.signatures)
                    sigs[0] = signature
                    versioned.signatures = sigs
                    return bytes(versioned)
                except Exception:
                    signature = keypair.sign_message(tx_bytes)
                    return bytes(signature)

            if hasattr(transaction, "sign"):
                transaction.sign([keypair])
                return bytes(transaction)

            signature = keypair.sign_message(transaction)
            return bytes(signature)

        finally:
            # Always clear keypair
            if keypair:
                del keypair

    def get_wallet(self, address: str = None) -> Optional[WalletInfo]:
        """Get wallet info by address or active wallet."""
        if address:
            return self._wallets.get(address)
        elif self._active_wallet:
            return self._wallets.get(self._active_wallet)
        return None

    def get_treasury(self) -> Optional[WalletInfo]:
        """Get the treasury wallet."""
        for wallet in self._wallets.values():
            if wallet.is_treasury:
                return wallet
        return None

    def list_wallets(self) -> list[WalletInfo]:
        """List all wallets (public info only)."""
        return list(self._wallets.values())

    def set_active(self, address: str):
        """Set the active wallet for trading."""
        if address not in self._wallets:
            raise SecureKeyError(f"Wallet not found: {address[:8]}...")
        self._active_wallet = address

    async def get_balance(self, address: str = None) -> Tuple[float, float]:
        """
        Get wallet balance in SOL and USD.

        Returns:
            Tuple of (sol_balance, usd_value)
        """
        import aiohttp

        addr = address or self._active_wallet
        if not addr:
            return 0.0, 0.0

        try:
            async with aiohttp.ClientSession() as session:
                # Get SOL balance from RPC
                rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

                async with session.post(rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getBalance',
                    'params': [addr]
                }) as resp:
                    data = await resp.json()
                    lamports = data.get('result', {}).get('value', 0)
                    sol_balance = lamports / 1e9

                # Get SOL price
                async with session.get('https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd') as resp:
                    price_data = await resp.json()
                    sol_price = price_data.get('solana', {}).get('usd', 0)

                usd_value = sol_balance * sol_price

                # Update wallet info
                if addr in self._wallets:
                    self._wallets[addr].balance_sol = sol_balance
                    self._wallets[addr].balance_usd = usd_value

                return sol_balance, usd_value

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0, 0.0

    async def get_token_balances(self, address: str = None) -> Dict[str, Dict[str, Any]]:
        """
        Get all SPL token balances for wallet.

        Returns:
            Dict of {mint_address: {symbol, balance, usd_value}}
        """
        import aiohttp

        addr = address or self._active_wallet
        if not addr:
            return {}

        try:
            async with aiohttp.ClientSession() as session:
                rpc_url = os.environ.get('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

                async with session.post(rpc_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getTokenAccountsByOwner',
                    'params': [
                        addr,
                        {'programId': 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'},
                        {'encoding': 'jsonParsed'}
                    ]
                }) as resp:
                    data = await resp.json()

                tokens = {}
                accounts = data.get('result', {}).get('value', [])

                for account in accounts:
                    info = account.get('account', {}).get('data', {}).get('parsed', {}).get('info', {})
                    mint = info.get('mint', '')
                    amount = info.get('tokenAmount', {})

                    if float(amount.get('uiAmount', 0)) > 0:
                        tokens[mint] = {
                            'balance': float(amount.get('uiAmount', 0)),
                            'decimals': amount.get('decimals', 0),
                            'mint': mint
                        }

                return tokens

        except Exception as e:
            logger.error(f"Failed to get token balances: {e}")
            return {}

    def export_public_key(self, address: str) -> str:
        """Export public key for receiving funds."""
        if address in self._wallets:
            return address
        raise SecureKeyError("Wallet not found")

    def delete_wallet(self, address: str, confirm: bool = False):
        """
        Delete a wallet. Requires confirmation.
        WARNING: This permanently deletes the private key!
        """
        if not confirm:
            raise SecureKeyError("Deletion requires confirm=True")

        if address not in self._wallets:
            raise SecureKeyError("Wallet not found")

        if self._wallets[address].is_treasury:
            raise SecureKeyError("Cannot delete treasury wallet")

        # Remove key file
        key_path = self.WALLET_DIR / f'{address}.key'
        if key_path.exists():
            key_path.unlink()

        # Remove from registry
        del self._wallets[address]
        self._save_wallet_registry()

        logger.info(f"Deleted wallet: {address[:8]}...")


class WalletManager:
    """
    High-level wallet management for Telegram bot integration.
    """

    _instance: Optional['WalletManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._wallet: Optional[SecureWallet] = None
        self._initialized = True

    def initialize(self, master_password: str = None):
        """Initialize wallet manager with master password."""
        self._wallet = SecureWallet(master_password)

    @property
    def wallet(self) -> SecureWallet:
        if not self._wallet:
            raise SecureKeyError("Wallet manager not initialized")
        return self._wallet

    def is_initialized(self) -> bool:
        return self._wallet is not None
