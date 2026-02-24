class MockWeb3Client:
    """
    Mock EVM Client replacing the Solana paradigms.
    Uses standard `web3.py` structures minimally scoped for ERC-7621 interactions.
    """
    def __init__(self, key_manager_wallet):
        self.wallet = key_manager_wallet
        self.chain_id = 1 # Ethereum Mainnet
        self.gas_price = "20 gwei"

    def build_erc7621_mint(self, weights_payload: dict):
        """Builds a mock ABI transaction payload targeting the Alvara Factory proxy."""
        # Simulated payload builder converting Python dicts to Solidity calldata
        tx = f"Factory.mint({weights_payload})"
        signed = self.wallet.sign_transaction(tx)
        return signed

    def send_raw_transaction(self, signed_tx: str):
        # Mocks transmitting to EVM RPC
        return {"status": 1, "hash": "0xABC123"}
