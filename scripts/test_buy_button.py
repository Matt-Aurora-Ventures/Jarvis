"""Test buy button execution."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Load env
env_path = Path(__file__).resolve().parents[1] / "tg_bot" / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"'))


async def test():
    from bots.buy_tracker.ape_buttons import parse_ape_callback, execute_ape_trade
    
    # Test callback format from sentiment report
    test_cb = 'ape:5:m:t:BONK:DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263'
    parsed = parse_ape_callback(test_cb)
    print('Parsed:', parsed)
    
    if parsed:
        result = await execute_ape_trade(
            callback_data=test_cb,
            entry_price=0.0,
            treasury_balance_sol=0.093,
            user_id=8527130908
        )
        print('Success:', result.success)
        print('Error:', result.error if result.error else 'None')
        if result.trade_setup:
            print('Setup:', result.trade_setup)
        if result.tx_signature:
            print('TX:', result.tx_signature)


if __name__ == "__main__":
    asyncio.run(test())
