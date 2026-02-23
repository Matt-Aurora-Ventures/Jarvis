from __future__ import annotations

import json

import base58
import pytest
from solders.keypair import Keypair

from core.jupiter_perps.signer import load_signer_keypair


def test_load_signer_from_b58(monkeypatch: pytest.MonkeyPatch) -> None:
    keypair = Keypair()
    encoded = base58.b58encode(bytes(keypair)).decode("utf-8")
    monkeypatch.setenv("PERPS_SIGNER_KEYPAIR_B58", encoded)
    monkeypatch.delenv("PERPS_SIGNER_KEYPAIR_PATH", raising=False)

    loaded = load_signer_keypair(str(keypair.pubkey()))
    assert bytes(loaded) == bytes(keypair)


def test_load_signer_from_json_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    keypair = Keypair()
    source = tmp_path / "kp.json"
    source.write_text(json.dumps(list(bytes(keypair))), encoding="utf-8")

    monkeypatch.setenv("PERPS_SIGNER_KEYPAIR_PATH", str(source))
    monkeypatch.delenv("PERPS_SIGNER_KEYPAIR_B58", raising=False)

    loaded = load_signer_keypair(str(keypair.pubkey()))
    assert bytes(loaded) == bytes(keypair)


def test_load_signer_mismatch_wallet_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    keypair = Keypair()
    encoded = base58.b58encode(bytes(keypair)).decode("utf-8")
    monkeypatch.setenv("PERPS_SIGNER_KEYPAIR_B58", encoded)
    monkeypatch.delenv("PERPS_SIGNER_KEYPAIR_PATH", raising=False)

    with pytest.raises(RuntimeError, match="does not match PERPS_WALLET_ADDRESS"):
        load_signer_keypair("11111111111111111111111111111111")
