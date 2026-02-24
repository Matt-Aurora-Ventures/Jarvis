class KeyManager:
    """Mock abstract class for managing isolated keys away from environment vars"""
    def __init__(self):
        pass

    def create_wallet(self, name: str):
        return MockWallet(name)

    def load_wallet(self, name: str):
        return MockWallet(name)

class MockWallet:
    def __init__(self, name: str):
        self.name = name
        self.bytes = b"mock_wallet_address_1234"

    def sign_transaction(self, tx):
        return f"SIGNED_TX_{tx}"
