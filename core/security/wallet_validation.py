"""Wallet address validation utilities."""
import re
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ChainType(str, Enum):
    SOLANA = "solana"
    ETHEREUM = "ethereum"
    BITCOIN = "bitcoin"
    UNKNOWN = "unknown"


@dataclass
class ValidationResult:
    valid: bool
    chain: ChainType
    message: str
    checksum_valid: Optional[bool] = None


def validate_solana_address(address: str) -> ValidationResult:
    """Validate a Solana wallet address."""
    try:
        import base58
        
        if not address or not isinstance(address, str):
            return ValidationResult(False, ChainType.SOLANA, "Address is empty or invalid type")
        
        address = address.strip()
        
        if not re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
            return ValidationResult(False, ChainType.SOLANA, "Invalid character set or length")
        
        try:
            decoded = base58.b58decode(address)
        except Exception as e:
            return ValidationResult(False, ChainType.SOLANA, f"Base58 decode failed: {e}")
        
        if len(decoded) != 32:
            return ValidationResult(False, ChainType.SOLANA, f"Invalid length: {len(decoded)} bytes (expected 32)")
        
        return ValidationResult(True, ChainType.SOLANA, "Valid Solana address")
    
    except ImportError:
        if re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
            return ValidationResult(True, ChainType.SOLANA, "Likely valid (base58 not available for full validation)")
        return ValidationResult(False, ChainType.SOLANA, "Invalid format")


def validate_ethereum_address(address: str) -> ValidationResult:
    """Validate an Ethereum wallet address."""
    if not address or not isinstance(address, str):
        return ValidationResult(False, ChainType.ETHEREUM, "Address is empty or invalid type")
    
    address = address.strip()
    
    if not address.startswith('0x'):
        return ValidationResult(False, ChainType.ETHEREUM, "Must start with 0x")
    
    if len(address) != 42:
        return ValidationResult(False, ChainType.ETHEREUM, f"Invalid length: {len(address)} (expected 42)")
    
    if not re.match(r'^0x[0-9a-fA-F]{40}$', address):
        return ValidationResult(False, ChainType.ETHEREUM, "Invalid hex characters")
    
    checksum_valid = None
    if address != address.lower() and address != address.upper():
        checksum_valid = _verify_eth_checksum(address)
        if not checksum_valid:
            return ValidationResult(False, ChainType.ETHEREUM, "Invalid checksum", checksum_valid=False)
    
    return ValidationResult(True, ChainType.ETHEREUM, "Valid Ethereum address", checksum_valid=checksum_valid)


def _verify_eth_checksum(address: str) -> bool:
    """Verify Ethereum address checksum (EIP-55)."""
    try:
        import hashlib
        address_lower = address[2:].lower()
        hash_hex = hashlib.sha3_256(address_lower.encode()).hexdigest()
        
        for i, char in enumerate(address_lower):
            if char.isalpha():
                expected_case = char.upper() if int(hash_hex[i], 16) >= 8 else char.lower()
                if address[i + 2] != expected_case:
                    return False
        return True
    except Exception:
        return True


def validate_bitcoin_address(address: str) -> ValidationResult:
    """Validate a Bitcoin wallet address (basic validation)."""
    if not address or not isinstance(address, str):
        return ValidationResult(False, ChainType.BITCOIN, "Address is empty or invalid type")
    
    address = address.strip()
    
    if address.startswith('1') or address.startswith('3'):
        if not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
            return ValidationResult(False, ChainType.BITCOIN, "Invalid P2PKH/P2SH address format")
        return ValidationResult(True, ChainType.BITCOIN, "Valid Bitcoin address (P2PKH/P2SH)")
    
    if address.startswith('bc1'):
        if not re.match(r'^bc1[a-zA-HJ-NP-Z0-9]{39,59}$', address):
            return ValidationResult(False, ChainType.BITCOIN, "Invalid Bech32 address format")
        return ValidationResult(True, ChainType.BITCOIN, "Valid Bitcoin address (Bech32)")
    
    return ValidationResult(False, ChainType.BITCOIN, "Unknown Bitcoin address format")


def detect_chain(address: str) -> ChainType:
    """Detect which blockchain an address belongs to."""
    if not address:
        return ChainType.UNKNOWN
    
    address = address.strip()
    
    if address.startswith('0x') and len(address) == 42:
        return ChainType.ETHEREUM
    
    if address.startswith(('1', '3', 'bc1')):
        return ChainType.BITCOIN
    
    if re.match(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$', address):
        return ChainType.SOLANA
    
    return ChainType.UNKNOWN


def validate_address(address: str, chain: ChainType = None) -> ValidationResult:
    """Validate an address, auto-detecting chain if not specified."""
    if chain is None:
        chain = detect_chain(address)
    
    validators = {
        ChainType.SOLANA: validate_solana_address,
        ChainType.ETHEREUM: validate_ethereum_address,
        ChainType.BITCOIN: validate_bitcoin_address,
    }
    
    validator = validators.get(chain)
    if validator:
        return validator(address)
    
    return ValidationResult(False, ChainType.UNKNOWN, "Unable to determine chain type")
