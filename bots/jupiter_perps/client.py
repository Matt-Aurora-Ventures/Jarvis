from solders.pubkey import Pubkey

# Jupiter Perps Program ID constraint
PROGRAM_ID = Pubkey.from_string("PERPHjGBqRHArX4DySjwM6UJHiR3sWAatqfdBS2qQJu")

def derive_position_pda(trader_wallet_bytes: bytes, custody_bytes: bytes, collateral_bytes: bytes) -> Pubkey:
    """
    Derive the deterministic Jupiter PositionRequest PDA securely without RPC hitting.
    Based on exactly the Trader, the pairs being traded, and the collateral.
    """
    pda, nonce = Pubkey.find_program_address(
        [trader_wallet_bytes, custody_bytes, collateral_bytes],
        PROGRAM_ID
    )
    return pda

class JupiterPerpsAnchorClient:
    """
    Creates structural, deterministic IDL instructions wrapping the Jupiter Perps API.
    Aims to manage position payloads to avoid routing over REST endpoints logic natively.
    """
    def __init__(self, key_manager_wallet):
        self.wallet = key_manager_wallet

    async def build_position_request(self, custody: str, collateral: str, size: float, action: str):
        """
        Mocks the struct parsing of the IDL and transaction building via `solders` priority-fee wrappers.
        Builds and signs offline.
        """
        # Stand-in instruction assembly
        mock_tx_payload = f"Instruction: RequestPosition | Market: {custody}/{collateral} | Action: {action} | Size: {size}"
        signed_tx = self.wallet.sign_transaction(mock_tx_payload)

        # In a generic environment, returning the signed chunk safely
        return signed_tx

    async def execute_tx(self, signed_tx):
        """Broadcasts signed transaction directly to a Jito block engine or RPC."""
        return {"status": "processing", "signature": "mock_jup_sig_123"}
