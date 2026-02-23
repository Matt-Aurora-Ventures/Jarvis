"""
Trading Constants and Configuration

Contains all constants, token lists, and configuration values.
"""

import os
from pathlib import Path

from .types import RiskLevel


# ==========================================================================
# STATE FILE PATHS
# ==========================================================================

# Import state paths if available
try:
    from core.state_paths import STATE_PATHS
    _STATE_PATHS_AVAILABLE = True
except ImportError:
    _STATE_PATHS_AVAILABLE = False
    STATE_PATHS = None

_ROOT = Path(__file__).resolve().parents[3]
_TRADER_STATE_DIR = _ROOT / "data" / "trader"

POSITIONS_FILE = _TRADER_STATE_DIR / "positions.json"
HISTORY_FILE = _TRADER_STATE_DIR / "trade_history.json"
DAILY_VOLUME_FILE = _TRADER_STATE_DIR / "daily_volume.json"
AUDIT_LOG_FILE = STATE_PATHS.audit_log if _STATE_PATHS_AVAILABLE else _ROOT / "data" / "logs" / "audit.jsonl"

# Legacy primary paths (read-only fallback)
_LEGACY_TRADING_DIR = Path.home() / ".lifeos" / "trading"
LEGACY_POSITIONS_FILE = STATE_PATHS.positions if _STATE_PATHS_AVAILABLE else _LEGACY_TRADING_DIR / "positions.json"
LEGACY_HISTORY_FILE = _LEGACY_TRADING_DIR / "trade_history.json"


# ==========================================================================
# SPENDING CAPS - Protect treasury from runaway losses
# ==========================================================================

MAX_TRADE_USD = 100.0      # Maximum single trade size
MAX_DAILY_USD = 500.0      # Maximum daily trading volume
MAX_POSITION_PCT = 0.20    # Max 20% of portfolio in single position
MAX_ALLOCATION_PER_TOKEN = None  # DISABLED: No maximum per-token allocation
ALLOW_STACKING = True  # ENABLED: Allow multiple positions in the same token


# ==========================================================================
# TP/SL CONFIGURATION BY SENTIMENT GRADE
# ==========================================================================

TP_SL_CONFIG = {
    'A+': {'take_profit': 0.30, 'stop_loss': 0.08},  # 30% TP, 8% SL - highest conviction
    'A': {'take_profit': 0.30, 'stop_loss': 0.08},   # 30% TP, 8% SL
    'A-': {'take_profit': 0.25, 'stop_loss': 0.10},
    'B+': {'take_profit': 0.20, 'stop_loss': 0.10},  # 20% TP, 10% SL
    'B': {'take_profit': 0.18, 'stop_loss': 0.12},   # 18% TP, 12% SL
    'B-': {'take_profit': 0.15, 'stop_loss': 0.12},
    'C+': {'take_profit': 0.12, 'stop_loss': 0.15},
    'C': {'take_profit': 0.10, 'stop_loss': 0.15},   # 10% TP, 15% SL - lower conviction
    'C-': {'take_profit': 0.08, 'stop_loss': 0.15},
    'D': {'take_profit': 0.05, 'stop_loss': 0.20},   # Very risky
    'F': {'take_profit': 0.05, 'stop_loss': 0.20},   # DO NOT TRADE
}

# Grade emoji mappings for UI
GRADE_EMOJI = {
    'A+': '', 'A': '', 'A-': '',
    'B+': '', 'B': '', 'B-': '',
    'C+': '', 'C': '', 'C-': '',
    'D': '', 'F': ''
}


# ==========================================================================
# ADMIN CONFIGURATION
# ==========================================================================

# Prefer env-driven admin IDs; fallback is the current primary admin (post account migration).
ADMIN_USER_ID = int(os.environ.get("JARVIS_ADMIN_USER_ID", "8527368699"))


# ==========================================================================
# POSITION SIZING BY RISK LEVEL
# ==========================================================================

POSITION_SIZE = {
    RiskLevel.CONSERVATIVE: 0.01,   # 1%
    RiskLevel.MODERATE: 0.02,       # 2%
    RiskLevel.AGGRESSIVE: 0.05,     # 5%
    RiskLevel.DEGEN: 0.10,          # 10%
}


# ==========================================================================
# TOKEN SAFETY SYSTEM - HARDCODED REMEDIATIONS FROM PERFORMANCE AUDIT
# ==========================================================================

# ESTABLISHED TOKENS - Vetted, liquid, safe to trade with normal position sizes
ESTABLISHED_TOKENS = {
    # Major Solana tokens
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
    "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
    "So11111111111111111111111111111111111111112": "SOL",
    "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So": "MSOL",
    "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj": "STSOL",
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": "WIF",
    "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof": "RNDR",
    "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3": "PYTH",
    "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ": "W",
    "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4": "JTO",

    # WRAPPED MAJOR TOKENS - Cross-chain bridged assets (Portal/Wormhole)
    "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": "WETH",
    "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh": "WBTC",
    "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E": "WBTC_SOL",
    "FYfQ9uaRaYvRiaEGUmct45F9WKam3BYXArTrotnTNFXF": "WADA",
    "A9mUU4qviSctJVPJdBJWkb28deg915LYJKrzQ19ji3FM": "WDOT",
    "CWE8jPTUYhdCTZYWPTe1o5DFqfdjzWKc9WKz6PBjkgy8": "WAVAX",
    "9bzWNhJcgbVnUPV1T1QMMLj9a4PEcXXPKzPNxMcGUP8n": "WMATIC",
    "CDJWUqTcYTVAKXAVXoQZFes5JUFc7owSeq7eMQcDSbo5": "WLINK",
    "4wjPQJ6PrkC4dHhYghwJzGBVP78DkBzA2U3kHoFNBuhj": "WUNI",
    "AUrMpCDYYcPuHhyNX8gEEqbmDPFUpBpHrNW3vPeCFn5Z": "WAAVE",
    "EchesyfXePKdLtoiZSL8pBe8Myagyy8ZRqsACNCFGnvp": "WFIL",
    "7i5KKsX2weiTkry7jA4ZwSuXGhs5eJBEjY8vVxR4pfRx": "GMT",
    "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R": "RAY",
    "AFbX8oGjGpmVFywbVouvhQSRmiW2aR1mohfahi4Y2AdB": "GST",
    "BRjpCHtyQLNCo8gqRUr8jtdAj5AjPYQaoqbvcZiHok1k": "devUSDC",
    "Saber2gLauYim4Mvftnrasomsv6NvAuncvMEZwcLpD1": "SBR",
    "GENEtH5amGSi8kHAtQoezp1XEXwZJ8vcuePYnXdKrMYz": "GENE",
    "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE": "ORCA",
    "MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey": "MNDE",
    "kinXdEcpDQeHPEuQnqmUgtYykqKGVFq6CeVX5iAHJq6": "KIN",

    # TOP 30 BY MARKET CAP (Solana ecosystem)
    "SHDWyBxihqiCj6YekG2GUr7wqKLeLAMK1gHZck9pL6y": "SHDW",
    "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA": "BLZE",
    "TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6": "TNSR",
    "HxhWkVpk5NS4Ltg5nij2G671CKXFRKM5AGKUWZK3Q8KV": "HAWK",
    "mb1eu7TzEc71KxDpsmsKoucSSuuoGLv1drys1oP2jh6": "MOBILE",
    "iotEVVZLEywoTn1QdwNPddxPWszn3zFhEot3MfL9fns": "IOT",
    "HNTkznmTnk98R9RnFMn6Y7Sbkg6bz5D7WTxo1sXX9G4F": "HNT",

    # Tokenized equities (XStocks) - backed by real assets
    "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W": "SPYx",
    "XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB": "TSLAX",
    "Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh": "NVDAX",
    "Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re": "GLDx",
    "XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc": "TQQQx",
    "XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp": "AAPLx",
    "XsMGMDhxqnWAqtF4xk2Z5i4wJBhZnJ4Wk6c8XJNhE3J": "GOOGLx",
    "XsMSFTs3E5UT7cRUhP7sQDh9KRo6LGp5TE8yPkMiL5F": "MSFTx",
}


# HIGH RISK TOKEN PATTERNS - Require extra scrutiny and smaller positions
HIGH_RISK_PATTERNS = [
    "pump",     # pump.fun tokens - high risk, small positions only
]


# BLOCKED TOKENS - Never trade these (stablecoins only)
BLOCKED_TOKENS = {
    # USD-pegged stablecoins
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "USDC",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "USDT",
    "BRjpCHtyQLNCo8gqRUr8jtdAj5AjPYQaoqbvcZiHok1k": "devUSDC",
    # Other stablecoins
    "USDH1SM1ojwWUga67PGrgFWUHibbjqMvuMaDkRJTgkX": "USDH",
    "7kbnvuGBxxj8AG9qp8Scn56muWGaRaFqxg1FsRp3PaFT": "UXD",
    "Dn4noZ5jgGfkntzcQSUZ8czkreiZ1ForXYoV2H8Dm7S1": "USDCet",
}

BLOCKED_SYMBOLS = {"USDC", "USDT", "USDH", "UXD", "BUSD", "DAI", "TUSD", "FRAX", "USDD", "devUSDC"}


# MINIMUM REQUIREMENTS FOR HIGH-RISK TOKENS
MIN_LIQUIDITY_USD = 5000       # $5k minimum liquidity for any trade
MIN_VOLUME_24H_USD = 2500      # $2.5k minimum daily volume
MIN_TOKEN_AGE_HOURS = 1        # At least 1 hour old (not instant rugs)
MAX_HIGH_RISK_POSITION_PCT = 0.15  # Max 15% of normal position for high-risk
MAX_UNVETTED_POSITION_PCT = 0.25   # Max 25% of normal position for unvetted
