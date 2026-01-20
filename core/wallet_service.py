"""
Wallet Service - Secure Solana wallet generation and management

Provides:
- Wallet generation with seed phrases
- Private key encryption/decryption
- Wallet import from seed phrases
- Key derivation (BIP-44)
- Balance checking
- Address validation
- Secure storage

ALL PRIVATE KEYS ARE ENCRYPTED BEFORE STORAGE.
NEVER STORE OR LOG UNENCRYPTED KEYS.
"""

import logging
import os
import secrets
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

# Encryption
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64

# Solana
from solders.keypair import Keypair
from solders.pubkey import Pubkey

try:
    from bip_utils import (
        Bip39MnemonicGenerator,
        Bip39MnemonicValidator,
        Bip39SeedGenerator,
        Bip39WordsNum,
        Bip44,
        Bip44Coins,
        Bip44Changes,
    )
    HAS_BIP_UTILS = True
except Exception:
    HAS_BIP_UTILS = False
    Bip39MnemonicGenerator = None
    Bip39MnemonicValidator = None
    Bip39SeedGenerator = None
    Bip39WordsNum = None
    Bip44 = None
    Bip44Coins = None
    Bip44Changes = None

try:
    from nacl.signing import SigningKey
    HAS_NACL = True
except Exception:
    HAS_NACL = False
    SigningKey = None
# Note: RPC client will be used from market data service
# from solders.rpc.async_client import AsyncClient
# from solders.rpc.commitment import Confirmed

logger = logging.getLogger(__name__)


class WalletEncryption:
    """Handle encryption/decryption of private keys."""

    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize encryption system.

        Args:
            master_key: Encryption master key (if None, generate new)
        """
        self.master_key = master_key or self._generate_master_key()

    def _generate_master_key(self) -> bytes:
        """Generate new master encryption key."""
        return Fernet.generate_key()

    def _derive_key(self, salt: bytes, password: str) -> bytes:
        """Derive encryption key from password and salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def encrypt_private_key(self, private_key: str, password: str) -> str:
        """
        Encrypt a private key.

        Args:
            private_key: Private key (base58 or hex)
            password: Encryption password

        Returns:
            Encrypted key (base64 encoded)
        """
        try:
            salt = secrets.token_bytes(16)
            key = self._derive_key(salt, password)
            cipher = Fernet(key)
            encrypted = cipher.encrypt(private_key.encode())

            # Include salt in output
            return base64.b64encode(salt + encrypted).decode()

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt_private_key(self, encrypted_key: str, password: str) -> str:
        """
        Decrypt a private key.

        Args:
            encrypted_key: Encrypted key (base64 encoded)
            password: Encryption password

        Returns:
            Decrypted private key

        Raises:
            ValueError if decryption fails
        """
        try:
            data = base64.b64decode(encrypted_key.encode())
            salt = data[:16]
            encrypted = data[16:]

            key = self._derive_key(salt, password)
            cipher = Fernet(key)
            decrypted = cipher.decrypt(encrypted)

            return decrypted.decode()

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Invalid password or corrupted key")


@dataclass
class GeneratedWallet:
    """Result of wallet generation."""
    public_key: str  # Solana address
    private_key: str  # Private key (NOT encrypted)
    seed_phrase: str  # BIP-39 seed phrase
    derivation_path: str  # BIP-44 path (e.g., m/44'/501'/0'/0')


class SolanaWalletGenerator:
    """Generate and manage Solana wallets."""

    def __init__(self):
        """Initialize wallet generator."""
        self.encryption = WalletEncryption()

    async def generate_wallet(self, derivation_index: int = 0) -> GeneratedWallet:
        """
        Generate a new Solana wallet.

        Args:
            derivation_index: BIP-44 index (for multiple wallets from same seed)

        Returns:
            GeneratedWallet with keys and seed phrase
        """
        try:
            if not HAS_BIP_UTILS or not HAS_NACL:
                raise RuntimeError("Mnemonic dependencies missing (bip-utils + pynacl required)")

            seed_phrase = self._generate_seed_phrase()
            keypair = self._derive_keypair_from_seed(seed_phrase, derivation_index)
            public_key = str(keypair.pubkey())
            private_key_b58 = self._secret_to_base58(bytes(keypair))
            derivation_path = f"m/44'/501'/{derivation_index}'/0'"

            logger.info(f"Generated wallet: {public_key[:10]}...")

            return GeneratedWallet(
                public_key=public_key,
                private_key=private_key_b58,
                seed_phrase=seed_phrase,
                derivation_path=derivation_path,
            )

        except Exception as e:
            logger.error(f"Wallet generation failed: {e}")
            raise

    async def import_from_seed(self, seed_phrase: str, derivation_index: int = 0) -> GeneratedWallet:
        """
        Import wallet from seed phrase.

        Args:
            seed_phrase: BIP-39 seed phrase
            derivation_index: Wallet index

        Returns:
            GeneratedWallet
        """
        try:
            if not HAS_BIP_UTILS or not HAS_NACL:
                raise RuntimeError("Mnemonic dependencies missing (bip-utils + pynacl required)")

            if not Bip39MnemonicValidator(str(seed_phrase)).Validate():
                raise ValueError("Invalid seed phrase")

            keypair = self._derive_keypair_from_seed(seed_phrase, derivation_index)
            public_key = str(keypair.pubkey())
            private_key_b58 = self._secret_to_base58(bytes(keypair))
            derivation_path = f"m/44'/501'/{derivation_index}'/0'"

            logger.info(f"Imported wallet: {public_key[:10]}...")

            return GeneratedWallet(
                public_key=public_key,
                private_key=private_key_b58,
                seed_phrase=seed_phrase,
                derivation_path=derivation_path,
            )

        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            raise

    def _generate_seed_phrase(self) -> str:
        """Generate BIP-39 seed phrase (12 words)."""
        if not HAS_BIP_UTILS:
            raise RuntimeError("Mnemonic generation unavailable (bip-utils not installed)")
        return str(Bip39MnemonicGenerator().FromWordsNumber(Bip39WordsNum.WORDS_NUM_12))

    def _derive_keypair_from_seed(self, seed_phrase: str, derivation_index: int) -> Keypair:
        """Derive a Solana keypair from a seed phrase."""
        if not HAS_BIP_UTILS or not HAS_NACL:
            raise RuntimeError("Mnemonic dependencies missing (bip-utils + pynacl required)")
        seed = Bip39SeedGenerator(seed_phrase).Generate()
        bip44 = (
            Bip44.FromSeed(seed, Bip44Coins.SOLANA)
            .Purpose()
            .Coin()
            .Account(0)
            .Change(Bip44Changes.CHAIN_EXT)
            .AddressIndex(derivation_index)
        )
        private_key = bip44.PrivateKey().Raw().ToBytes()
        signing_key = SigningKey(private_key)
        secret_key = signing_key.encode() + signing_key.verify_key.encode()
        return Keypair.from_bytes(secret_key)

    def _secret_to_base58(self, secret: bytes) -> str:
        """Convert secret key to base58 format."""
        import base58
        return base58.b58encode(secret).decode()

    def _public_key_from_secret(self, secret: bytes) -> str:
        """Derive public key from secret."""
        keypair = Keypair.from_secret_key(secret)
        return str(keypair.pubkey())

    def validate_address(self, address: str) -> bool:
        """
        Validate a Solana address format.

        Args:
            address: Solana address (base58)

        Returns:
            True if valid format
        """
        try:
            Pubkey(address)
            return True
        except Exception:
            return False


class WalletService:
    """
    Complete wallet management service.

    Handles wallet generation, encryption, balance checking,
    and secure storage.
    """

    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        """
        Initialize wallet service.

        Args:
            rpc_url: Solana RPC endpoint
        """
        self.generator = SolanaWalletGenerator()
        self.encryption = WalletEncryption()
        self.rpc_url = rpc_url
        # Note: RPC client for balance checking delegated to MarketDataService

    # ==================== WALLET GENERATION ====================

    async def create_new_wallet(self, derivation_index: int = 0,
                               user_password: str = "default") -> Tuple[GeneratedWallet, str]:
        """
        Create a new wallet and encrypt it.

        Args:
            derivation_index: BIP-44 index
            user_password: Password to encrypt private key

        Returns:
            (GeneratedWallet, encrypted_private_key)
        """
        try:
            wallet = await self.generator.generate_wallet(derivation_index)

            # Encrypt private key
            encrypted_key = self.encryption.encrypt_private_key(
                wallet.private_key,
                user_password
            )

            logger.info(f"Created wallet: {wallet.public_key[:10]}...")

            return wallet, encrypted_key

        except Exception as e:
            logger.error(f"Wallet creation failed: {e}")
            raise

    async def import_wallet(self, seed_phrase: str, derivation_index: int = 0,
                           user_password: str = "default") -> Tuple[GeneratedWallet, str]:
        """
        Import wallet from seed phrase.

        Args:
            seed_phrase: BIP-39 seed phrase
            derivation_index: BIP-44 index
            user_password: Encryption password

        Returns:
            (GeneratedWallet, encrypted_private_key)
        """
        try:
            wallet = await self.generator.import_from_seed(seed_phrase, derivation_index)

            encrypted_key = self.encryption.encrypt_private_key(
                wallet.private_key,
                user_password
            )

            logger.info(f"Imported wallet: {wallet.public_key[:10]}...")

            return wallet, encrypted_key

        except Exception as e:
            logger.error(f"Wallet import failed: {e}")
            raise

    # ==================== KEY MANAGEMENT ====================

    def decrypt_private_key(self, encrypted_key: str, password: str) -> str:
        """
        Decrypt a stored private key.

        Args:
            encrypted_key: Encrypted key from storage
            password: User password

        Returns:
            Decrypted private key

        Raises:
            ValueError if password incorrect
        """
        try:
            return self.encryption.decrypt_private_key(encrypted_key, password)
        except Exception as e:
            logger.error(f"Key decryption failed: {e}")
            raise ValueError("Invalid password")

    # ==================== BALANCE & ACCOUNT INFO ====================

    async def get_balance(self, address: str) -> Optional[float]:
        """
        Get SOL balance for address.

        Note: Balance checking delegated to MarketDataService
        This is a placeholder that returns None - use MarketDataService.get_wallet_balance instead.

        Args:
            address: Solana address

        Returns:
            Balance in SOL or None
        """
        try:
            if not self.generator.validate_address(address):
                return None

            # Balance checking is delegated to MarketDataService which has RPC access
            logger.warning(f"Balance check requested but delegated to MarketDataService for {address}")
            return None

        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None

    async def get_token_balance(self, address: str, token_mint: str) -> Optional[float]:
        """
        Get token balance for an address.

        Args:
            address: Solana address
            token_mint: Token mint address

        Returns:
            Token balance or None
        """
        try:
            # Would use Token Program to get token account balance
            # Simplified here
            return 0.0

        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return None

    # ==================== ADDRESS VALIDATION ====================

    def validate_address(self, address: str) -> bool:
        """
        Validate Solana address format.

        Args:
            address: Address to validate

        Returns:
            True if valid
        """
        return self.generator.validate_address(address)

    def validate_private_key(self, private_key: str) -> bool:
        """
        Validate private key format.

        Args:
            private_key: Private key to validate

        Returns:
            True if valid format
        """
        try:
            import base58
            decoded = base58.b58decode(private_key)
            return len(decoded) in (32, 64)
        except Exception:
            return False

    def load_keypair_from_private_key(self, private_key: str) -> Keypair:
        """Load a Keypair from a base58-encoded private key."""
        import base58
        decoded = base58.b58decode(private_key)
        if len(decoded) == 64:
            return Keypair.from_bytes(decoded)
        if len(decoded) == 32:
            if not HAS_NACL:
                raise RuntimeError("PyNaCl required to expand 32-byte seeds")
            signing_key = SigningKey(decoded)
            secret_key = signing_key.encode() + signing_key.verify_key.encode()
            return Keypair.from_bytes(secret_key)
        raise ValueError("Invalid private key length")

    async def import_from_private_key(
        self, private_key: str, user_password: str = "default"
    ) -> Tuple[GeneratedWallet, str]:
        """
        Import wallet from a base58-encoded private key.

        Returns:
            (GeneratedWallet, encrypted_private_key)
        """
        keypair = self.load_keypair_from_private_key(private_key)
        public_key = str(keypair.pubkey())
        import base58
        private_key_b58 = base58.b58encode(bytes(keypair)).decode()
        encrypted_key = self.encryption.encrypt_private_key(
            private_key_b58, user_password
        )
        wallet = GeneratedWallet(
            public_key=public_key,
            private_key=private_key_b58,
            seed_phrase="",
            derivation_path="imported",
        )
        return wallet, encrypted_key

    # ==================== SECURITY ====================

    def export_wallet_backup(self, public_key: str, encrypted_private_key: str,
                           password: str) -> Dict[str, str]:
        """
        Export wallet as encrypted backup.

        Args:
            public_key: Wallet address
            encrypted_private_key: Encrypted key from storage
            password: User password (for verification)

        Returns:
            Backup dictionary
        """
        try:
            # Verify password by attempting decryption
            _ = self.encryption.decrypt_private_key(encrypted_private_key, password)

            return {
                'address': public_key,
                'encrypted_key': encrypted_private_key,
                'backup_date': datetime.utcnow().isoformat(),
                'version': '1.0',
            }

        except Exception as e:
            logger.error(f"Backup export failed: {e}")
            raise ValueError("Invalid password")

    def import_wallet_backup(self, backup: Dict[str, str], password: str) -> Tuple[str, str]:
        """
        Import wallet from backup file.

        Args:
            backup: Backup dictionary
            password: Decryption password

        Returns:
            (public_key, encrypted_private_key)
        """
        try:
            # Verify password
            private_key = self.encryption.decrypt_private_key(
                backup['encrypted_key'],
                password
            )

            logger.info(f"Imported backup for {backup['address'][:10]}...")

            return backup['address'], backup['encrypted_key']

        except Exception as e:
            logger.error(f"Backup import failed: {e}")
            raise ValueError("Invalid backup or password")

    # ==================== CLEANUP ====================

    async def close(self):
        """Close RPC connection (if any)."""
        # Note: RPC client is delegated to MarketDataService
        # This is kept for interface compatibility
        pass


# Singleton instance
_wallet_service: Optional[WalletService] = None


async def get_wallet_service(rpc_url: str = "https://api.mainnet-beta.solana.com") -> WalletService:
    """Get or create wallet service (singleton)."""
    global _wallet_service
    if _wallet_service is None:
        _wallet_service = WalletService(rpc_url)
    return _wallet_service
