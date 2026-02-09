import base58
import pytest

from solders.keypair import Keypair  # type: ignore

from tg_bot.handlers.demo.callbacks.wallet import _export_private_key_from_wallet


class _FakeSecureWallet:
    def __init__(self):
        self.last_address = None

    def get_private_key(self, address=None):
        self.last_address = address
        return "FAKE_PRIVATE_KEY_B58"

    def get_address(self):
        return "FAKE_ADDRESS"


class _FakeKeypairWallet:
    def __init__(self, keypair: Keypair | None):
        self._keypair = keypair

    @property
    def keypair(self):
        return self._keypair


def test_export_private_key_prefers_wallet_method():
    wallet = _FakeSecureWallet()
    private_key, address = _export_private_key_from_wallet(wallet, expected_address="ADDR123")
    assert private_key == "FAKE_PRIVATE_KEY_B58"
    assert address == "ADDR123"
    assert wallet.last_address == "ADDR123"


def test_export_private_key_keypair_roundtrip():
    keypair = Keypair()
    wallet = _FakeKeypairWallet(keypair)
    private_key, address = _export_private_key_from_wallet(wallet)

    assert address == str(keypair.pubkey())
    assert base58.b58decode(private_key) == bytes(keypair)


def test_export_private_key_keypair_missing_raises():
    wallet = _FakeKeypairWallet(None)
    with pytest.raises(ValueError):
        _export_private_key_from_wallet(wallet)


def test_export_private_key_unsupported_wallet_raises():
    with pytest.raises(ValueError):
        _export_private_key_from_wallet(object())

