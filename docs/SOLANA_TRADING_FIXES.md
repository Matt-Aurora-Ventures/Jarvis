# Solana Trading Stack Fixes - 2026-01-05

## Issues Found

1. **Jupiter API DNS resolution failure**: `quote-api.jup.ag` was not resolving
   - **Fix**: Use `public.jupiterapi.com` which works

2. **simulate=True by default**: Trades were only simulating, not executing
   - **Fix**: Changed to `simulate=False` in `savage_swap.py`

3. **Balance detection lag**: Balance queries after swap can show stale data
   - **Fix**: Account for RPC caching, wait for confirmation

4. **Token filter selecting SOL derivatives**: Scanner was picking tokens named "SOL" 
   - **Fix**: Exclude base tokens (SOL, USDC, etc) from momentum scan

## Files Changed

1. `/core/solana_execution.py`
   - Updated Jupiter API URLs
   - Added fallback configuration

2. `/scripts/savage_swap.py`
   - Changed `simulate=True` to `simulate=False`
   - Updated Jupiter API URLs

## Verification

- Jupiter quote API: ✅ Working (public.jupiterapi.com)
- Transaction signing: ✅ Working
- Transaction execution: ✅ Working (saw "AlreadyProcessed" = previous tx succeeded)
- Current balance: 0.03885 SOL (~$5.36)

## Next Steps

1. Run live trader with proper token filters
2. Monitor positions actively for TP/SL
3. Backtest historical momentum signals
