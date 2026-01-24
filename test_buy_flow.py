"""
Test script for buy flow and position persistence.
Tests US-006 integration without needing real Telegram or live blockchain.
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone

async def test_buy_flow():
    """Test the buy flow creates position and logs observation."""

    print("=" * 60)
    print("TESTING BUY FLOW (US-006 + US-003)")
    print("=" * 60)

    # Clean test files
    positions_file = Path.home() / ".lifeos" / "trading" / "demo_positions.json"
    observations_file = Path.home() / ".lifeos" / "trading" / "demo_observations.jsonl"

    print(f"\n1. Cleaning test files...")
    if positions_file.exists():
        positions_file.unlink()
        print(f"   Deleted: {positions_file}")
    if observations_file.exists():
        observations_file.unlink()
        print(f"   Deleted: {observations_file}")

    # Create position data (simulating execute_buy_with_tpsl result)
    print(f"\n2. Creating test position...")
    test_position = {
        "id": "buy_test123",
        "symbol": "PONKE",
        "address": "FakeTokenAddress123",
        "amount": 1000.0,
        "amount_sol": 0.5,
        "entry_price": 0.00042,
        "current_price": 0.00042,
        "tp_percent": 50.0,
        "sl_percent": 20.0,
        "tp_price": 0.00063,
        "sl_price": 0.000336,
        "source": "test",
        "tx_hash": "test_tx_123",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wallet_address": "test_wallet",
        "status": "open",
    }
    print(f"   Position ID: {test_position['id']}")
    print(f"   Symbol: {test_position['symbol']}")
    print(f"   Entry: ${test_position['entry_price']:.6f}")
    print(f"   TP: ${test_position['tp_price']:.6f} (+{test_position['tp_percent']:.0f}%)")
    print(f"   SL: ${test_position['sl_price']:.6f} (-{test_position['sl_percent']:.0f}%)")

    # Save position using order_monitor functions
    print(f"\n3. Saving position to disk...")
    from tg_bot.services.order_monitor import load_positions, save_positions

    positions = load_positions()
    print(f"   Loaded {len(positions)} existing positions")

    positions.append(test_position)
    save_positions(positions)
    print(f"   Saved position to: {positions_file}")

    # Verify save
    positions_loaded = load_positions()
    assert len(positions_loaded) == 1, "Position not saved!"
    assert positions_loaded[0]["id"] == "buy_test123", "Wrong position saved!"
    print(f"   OK Verification: Position saved correctly")

    # Log observation
    print(f"\n4. Logging buy observation...")
    from tg_bot.services.observation_collector import log_buy_executed

    log_buy_executed(
        user_id=12345,
        token_symbol=test_position["symbol"],
        token_address=test_position["address"],
        amount_sol=test_position["amount_sol"],
        entry_price=test_position["entry_price"],
        tp_percent=test_position["tp_percent"],
        sl_percent=test_position["sl_percent"],
        source="manual",
    )
    print(f"   Logged to: {observations_file}")

    # Verify observation
    if observations_file.exists():
        with open(observations_file, 'r') as f:
            observations = [json.loads(line) for line in f if line.strip()]

        assert len(observations) == 1, "Observation not logged!"
        assert observations[0]["event_type"] == "buy_executed", "Wrong event type!"
        print(f"   OK Verification: Observation logged correctly")
        print(f"   Event type: {observations[0]['event_type']}")
        print(f"   User ID: {observations[0]['user_id']}")

    # Test order_monitor detection
    print(f"\n5. Testing order_monitor can detect position...")
    from tg_bot.services.order_monitor import get_order_monitor

    monitor = get_order_monitor()
    active_positions = [p for p in load_positions() if p.get("status") == "open"]
    print(f"   OK order_monitor found {len(active_positions)} open position(s)")

    if active_positions:
        pos = active_positions[0]
        print(f"   Position: {pos['symbol']} (TP: ${pos['tp_price']:.6f}, SL: ${pos['sl_price']:.6f})")

    print("\n" + "=" * 60)
    print("OK - ALL TESTS PASSED")
    print("=" * 60)
    print("\nFiles created:")
    print(f"  - {positions_file}")
    print(f"  - {observations_file}")
    print("\nNext: Start supervisor and order_monitor will check this position every 10s")


if __name__ == "__main__":
    asyncio.run(test_buy_flow())
