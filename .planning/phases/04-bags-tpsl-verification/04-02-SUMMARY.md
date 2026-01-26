# Phase 4, Task 2: TP/SL Enforcement Audit - CRITICAL GAPS FOUND

**Date**: 2026-01-26
**Duration**: 30 minutes
**Status**: ❌ MAJOR ISSUES IDENTIFIED - REQUIRES IMMEDIATE FIXES

---

## Executive Summary

Audit revealed **CRITICAL gaps** in TP/SL enforcement:
1. ❌ **Unused enforcement function**: `execute_buy_with_tpsl()` exists but is NOT used in production code paths
2. ❌ **Hardcoded defaults**: Actual buy flow uses hardcoded 50%/20% TP/SL with no user customization
3. ❌ **No validation**: No checks to prevent invalid TP/SL values (0, negative, excessive)
4. ❌ **Bypass possible**: Users cannot customize TP/SL - stuck with defaults

**Impact**: While TP/SL IS applied to all trades, the enforcement is weak and inflexible.

---

## Findings

### 1. execute_buy_with_tpsl() Function Exists But Is Unused ❌

**Location**: [tg_bot/handlers/demo/demo_trading.py:347-354](tg_bot/handlers/demo/demo_trading.py#L347-L354)

**Function Signature**:
```python
async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float = 50.0,   # ❌ Optional with default
    sl_percent: float = 20.0,   # ❌ Optional with default
    slippage_bps: Optional[int] = None,
) -> Dict[str, Any]:
```

**Issues**:
- Parameters have defaults, making them effectively optional
- No validation of tp_percent/sl_percent values
- **MOST CRITICAL**: Function is NEVER called in production code!

**Evidence**: Searched entire `tg_bot/` directory:
```bash
grep -rn "await execute_buy_with_tpsl" tg_bot/ --include="*.py"
```
**Result**: Only found in docstring examples, not in actual execution paths.

---

### 2. Actual Buy Flow Bypasses execute_buy_with_tpsl() ❌

**Location**: [tg_bot/handlers/demo/callbacks/buy.py:122-230](tg_bot/handlers/demo/callbacks/buy.py#L122-L230)

**Actual Code Path**:
```python
async def handle_buy(...):
    # ...
    elif data.startswith("demo:execute_buy:"):
        # Execute via Bags.fm API with Jupiter fallback
        swap = await ctx.execute_swap_with_fallback(  # ❌ Direct swap, not execute_buy_with_tpsl
            from_token="So11111111111111111111111111111111111111112",
            to_token=token_addr,
            amount=amount,
            wallet_address=wallet_address,
            slippage_bps=slippage_bps,
        )

        if swap.get("success"):
            # ❌ Hardcoded TP/SL - no user input
            default_tp_pct = 50.0
            default_sl_pct = 20.0

            new_position = {
                "symbol": token_symbol,
                "address": token_addr,
                "amount": tokens_received,
                "entry_price": token_price,
                "tp_percent": default_tp_pct,  # ❌ Always 50%
                "sl_percent": default_sl_pct,  # ❌ Always 20%
                "tp_price": token_price * (1 + default_tp_pct / 100),
                "sl_price": token_price * (1 - default_sl_pct / 100),
                # ...
            }
```

**Problems**:
1. Calls low-level `execute_swap_with_fallback()` instead of `execute_buy_with_tpsl()`
2. Hardcodes TP/SL values (50% / 20%)
3. No user interface to customize TP/SL
4. No validation that values are reasonable

---

### 3. No TP/SL Validation Anywhere ❌

**Missing Validations**:
- ✗ Check that TP > 0
- ✗ Check that SL > 0
- ✗ Check that SL < 100% (would mean total loss + more)
- ✗ Check that TP is reasonable (e.g., < 500%)
- ✗ Prevent None or null values
- ✗ Prevent negative values

**Risk**: If someone modifies the hardcoded defaults to invalid values (e.g., 0, -10, 500), the system would accept them.

---

### 4. No User Customization ❌

**Current UX**: Users cannot set their own TP/SL targets.

**Missing Features**:
- No UI to input custom TP percentage
- No UI to input custom SL percentage
- No way to set different TP/SL for different tokens
- No way to adjust TP/SL after position is opened

**Example**: User wants conservative 20% TP with 10% SL → IMPOSSIBLE

---

## Entry Point Audit

### Checked Entry Points:

1. **Telegram /demo command** ✅ (uses callbacks)
   - Flows through `handle_buy()` callback
   - ❌ Bypasses `execute_buy_with_tpsl()`

2. **Quick buy buttons** ✅ (uses callbacks)
   - Same path as above
   - ❌ Same issue

3. **Custom amount input** ✅ (uses callbacks)
   - Same path as above
   - ❌ Same issue

4. **API endpoints** ⚠️ (not checked yet)
   - TODO: Check `api/fastapi_app.py`
   - Could be another entry point

5. **Treasury trading** ⚠️ (separate system)
   - TODO: Check `bots/treasury/trading.py`
   - May have different TP/SL rules

---

## Positive Findings ✅

Despite the gaps, some good aspects exist:

1. ✅ **TP/SL is always set**: Every position gets TP/SL (hardcoded 50%/20%)
2. ✅ **Monitoring exists**: `demo_orders.py` has background monitoring
3. ✅ **Exit triggers work**: `_check_demo_exit_triggers()` correctly checks TP/SL
4. ✅ **Enforcement function designed**: `execute_buy_with_tpsl()` has good design, just not wired up

**Net Assessment**: TP/SL EXISTS but is WEAK (no validation, no customization).

---

## Required Fixes

### Fix 1: Wire execute_buy_with_tpsl() Into Production Path (CRITICAL)

**Change**: Modify `handle_buy()` in [callbacks/buy.py](tg_bot/handlers/demo/callbacks/buy.py)

**Before**:
```python
swap = await ctx.execute_swap_with_fallback(...)
# Manual position creation with hardcoded TP/SL
```

**After**:
```python
result = await ctx.execute_buy_with_tpsl(
    token_address=token_addr,
    amount_sol=amount,
    wallet_address=wallet_address,
    tp_percent=tp_percent,  # From user input or defaults
    sl_percent=sl_percent,
    slippage_bps=slippage_bps,
)
```

**Impact**: Centralized TP/SL enforcement through designed function.

---

### Fix 2: Add TP/SL Validation Function (HIGH PRIORITY)

**Create**: `demo_trading.py::_validate_tpsl_required()`

```python
def _validate_tpsl_required(tp_percent: Optional[float], sl_percent: Optional[float]):
    """Ensure TP/SL are provided and valid."""
    if tp_percent is None or sl_percent is None:
        raise ValueError(
            "Take-profit and stop-loss are mandatory. "
            "Example: tp_percent=50.0 (50% profit target), sl_percent=20.0 (20% max loss)"
        )
    if tp_percent <= 0:
        raise ValueError(f"Take-profit must be positive, got {tp_percent}%")
    if sl_percent <= 0:
        raise ValueError(f"Stop-loss must be positive, got {sl_percent}%")
    if sl_percent >= 100:
        raise ValueError(f"Stop-loss cannot be >= 100% (would exceed investment), got {sl_percent}%")
    if tp_percent >= 500:
        raise ValueError(f"Take-profit seems unrealistic: {tp_percent}%. Max recommended: 200%")
    if tp_percent < 5:
        raise ValueError(f"Take-profit too low: {tp_percent}%. Minimum: 5%")
    if sl_percent < 5:
        raise ValueError(f"Stop-loss too low: {sl_percent}%. Minimum: 5%")
```

**Call at start of `execute_buy_with_tpsl()`**:
```python
async def execute_buy_with_tpsl(...):
    _validate_tpsl_required(tp_percent, sl_percent)
    # ... rest of implementation
```

---

### Fix 3: Add User TP/SL Customization UI (MEDIUM PRIORITY)

**Flow**:
1. User clicks "Buy"
2. Bot shows amount selection
3. **NEW**: Bot shows TP/SL configuration
4. User selects from presets or enters custom
5. Bot executes with custom TP/SL

**Presets UI**:
```python
keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Conservative (TP:20% SL:10%)", callback_data="demo:tpsl:20:10")],
    [InlineKeyboardButton("Balanced (TP:50% SL:20%)", callback_data="demo:tpsl:50:20")],
    [InlineKeyboardButton("Aggressive (TP:100% SL:30%)", callback_data="demo:tpsl:100:30")],
    [InlineKeyboardButton("Custom", callback_data="demo:tpsl:custom")],
])
```

---

### Fix 4: Make TP/SL Required Parameters (HIGH PRIORITY)

**Change**: Remove defaults from `execute_buy_with_tpsl()` signature

**Before**:
```python
async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float = 50.0,   # ❌ Has default
    sl_percent: float = 20.0,   # ❌ Has default
    slippage_bps: Optional[int] = None,
)
```

**After**:
```python
async def execute_buy_with_tpsl(
    token_address: str,
    amount_sol: float,
    wallet_address: str,
    tp_percent: float,   # ✅ Required
    sl_percent: float,   # ✅ Required
    slippage_bps: Optional[int] = None,
)
```

**Impact**: Forces all callers to explicitly provide TP/SL values.

---

## Audit of Other Entry Points (TODO)

### API Endpoints
**File**: `api/fastapi_app.py`
**Status**: ⏭️ Not yet audited
**Action**: Check if API exposes trade endpoints and if they enforce TP/SL

### Treasury Trading
**File**: `bots/treasury/trading.py`
**Status**: ⏭️ Not yet audited
**Action**: Document treasury TP/SL rules (may be different from demo bot)

---

## Timeline for Fixes

**Fix 1 (Wire function)**: 1 hour
**Fix 2 (Validation)**: 1 hour
**Fix 3 (UI customization)**: 3-4 hours
**Fix 4 (Remove defaults)**: 30 minutes

**Total**: 5.5-6.5 hours

**Priority Order**:
1. Fix 2 (Validation) - Prevents bad values
2. Fix 1 (Wire function) - Uses designed path
3. Fix 4 (Required params) - Enforces explicitness
4. Fix 3 (UI) - User experience improvement

---

## Risk Assessment

### Current Risk: MEDIUM-HIGH

**Why Medium-High (not CRITICAL)**:
- ✅ TP/SL IS being set (hardcoded)
- ✅ Monitoring IS running
- ✅ Exits ARE triggered

**But**:
- ❌ No flexibility for users
- ❌ No validation against bad values
- ❌ Enforcement function exists but unused
- ❌ Easy to accidentally bypass

**If Defaults Changed to 0**: Would be CRITICAL (no risk management).

---

## Recommendations

### Immediate (This Phase)
1. ✅ Implement Fix 2 (Validation function)
2. ✅ Implement Fix 1 (Wire execute_buy_with_tpsl)
3. ✅ Implement Fix 4 (Remove defaults)
4. ✅ Add integration tests

### Next Phase (Phase 5 or 6)
5. ⏭️ Implement Fix 3 (UI customization)
6. ⏭️ Allow TP/SL adjustment after position opened
7. ⏭️ Per-token TP/SL profiles
8. ⏭️ Auto-calculate TP/SL based on AI sentiment

---

## Next Steps

⏭️ **Proceed to implement fixes** in this order:
1. Write `_validate_tpsl_required()` function
2. Update `execute_buy_with_tpsl()` signature (remove defaults)
3. Add validation call at function start
4. Update `handle_buy()` to call `execute_buy_with_tpsl()`
5. Add tests for validation edge cases
6. Move to Task 3 (Verify TP/SL monitoring active)

---

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5
**Status**: Task 2 AUDIT COMPLETE - FIXES REQUIRED
**Next**: Implement fixes, then Task 3 (Monitoring Verification)
