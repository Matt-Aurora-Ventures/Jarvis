#!/usr/bin/env python3
"""Check if we should trade OIL token."""

import requests
import json

def check_oil_trade():
    # OIL token address from wallet
    oil_mint = "4oP9Fx9ZfMhG8KwRfhBjNTvRvjZjLWuGtRRZCsRqrJn"

    print('🛢️ OIL TOKEN TRADING ANALYSIS')
    print('='*50)

    try:
        # Get OIL token data from DexScreener
        response = requests.get(f'https://api.dexscreener.com/latest/dex/tokens/{oil_mint}', timeout=10)

        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])

            if pairs:
                pair = pairs[0]
                symbol = pair.get('baseToken', {}).get('symbol', 'OIL')
                price = float(pair.get('priceUsd', 0) or 0)
                liq = float(pair.get('liquidity', {}).get('usd', 0) or 0)
                vol_24h = float(pair.get('volume', {}).get('h24', 0) or 0)
                price_change_24h = float(pair.get('priceChange', {}).get('h24', 0) or 0)

                print(f'Symbol: {symbol}')
                print(f'Current Price: ${price:.8f}')
                print(f'Liquidity: ${liq:,.0f}')
                print(f'24h Volume: ${vol_24h:,.0f}')
                print(f'24h Change: {price_change_24h:+.1f}%')

                # Current position
                current_holding = 42264.1077
                current_value = current_holding * price
                print(f'\n📊 CURRENT POSITION:')
                print(f'Holding: {current_holding:,.4f} OIL')
                print(f'Current Value: ${current_value:.2f}')

                # Trading decision logic
                should_trade = False
                action = ""
                reason = ""

                if price_change_24h > 25 and vol_24h > 50000:
                    should_trade = True
                    action = "BUY MORE"
                    reason = f"Strong upward momentum (+{price_change_24h:.1f}%) with high volume"
                elif price_change_24h < -40:
                    should_trade = True
                    action = "BUY DIP"
                    reason = f"Significant dip ({price_change_24h:.1f}%) - potential recovery"
                elif price_change_24h > 10 and vol_24h > 10000:
                    should_trade = True
                    action = "MONITOR"
                    reason = f"Moderate momentum (+{price_change_24h:.1f}%) with decent volume"
                else:
                    reason = f"Market conditions neutral ({price_change_24h:+.1f}% change, ${vol_24h:,.0f} volume)"

                print(f'\n💡 DECISION: {"✅ " + action if should_trade else "❌ HOLD"}')
                print(f'Reason: {reason}')

                if should_trade and action in ["BUY MORE", "BUY DIP"]:
                    # Calculate position size (use 20% of available capital)
                    available_capital = 15.30  # From wallet status
                    position_size = available_capital * 0.20
                    oil_quantity = position_size / price if price > 0 else 0

                    print(f'\n🎯 TRADE PROPOSAL:')
                    print(f'Action: {action}')
                    print(f'Amount: ${position_size:.2f} (${oil_quantity:.0f} OIL)')
                    print(f'Expected Entry: ${price:.8f}')

                    return {
                        'should_trade': True,
                        'action': action,
                        'amount_usd': position_size,
                        'quantity': oil_quantity,
                        'price': price,
                        'reason': reason
                    }

            else:
                print('No trading pairs found for OIL')
        else:
            print(f'DexScreener API error: {response.status_code}')

    except Exception as e:
        print(f'Error checking OIL: {e}')

    return {'should_trade': False, 'reason': 'Unable to get market data'}

if __name__ == "__main__":
    result = check_oil_trade()

    if result['should_trade']:
        print(f'\n🚀 EXECUTING {result["action"]} TRADE...')
        # Here we would call the trading function
        print(f'Amount: ${result["amount_usd"]:.2f}')
        print(f'Quantity: {result["quantity"]:.0f} OIL')
        print('Trade execution would happen here...')
    else:
        print(f'\n⏸️  HOLDING: {result["reason"]}')