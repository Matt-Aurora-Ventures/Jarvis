# Phase 4, Task 6: Error Handling Enhancement - COMPLETE

**Date**: 2026-01-26
**Duration**: 25 minutes
**Status**: ✅ COMPLETE

---

## Summary

Enhanced error handling with user-friendly error classes, helpful hints, and proper exception formatting for Telegram display.

---

## What Was Built

### 1. Error Class Hierarchy

**Location**: [tg_bot/handlers/demo/demo_trading.py:27-60](tg_bot/handlers/demo/demo_trading.py#L27-L60)

```python
class TradingError(Exception):
    """Base exception for user-friendly trading errors."""

    def __init__(self, message: str, hint: Optional[str] = None):
        self.message = message
        self.hint = hint
        super().__init__(message)

    def format_telegram(self) -> str:
        """Format error for Telegram display."""
        msg = f"❌ {self.message}"
        if self.hint:
            msg += f"\n\n💡 Hint: {self.hint}"
        return msg

class BagsAPIError(TradingError):
    """bags.fm API error with user-friendly messaging."""

class TPSLValidationError(TradingError):
    """TP/SL validation error with helpful hints."""

class InsufficientBalanceError(TradingError):
    """Insufficient balance for trade."""
```

**Benefits**:
- **User-friendly messages**: No raw exceptions shown to users
- **Actionable hints**: Guide users to fix issues
- **Telegram formatting**: `.format_telegram()` method for consistent display
- **Type safety**: Specific exceptions for different error scenarios

---

### 2. Enhanced TP/SL Validation Errors

**Location**: [tg_bot/handlers/demo/demo_trading.py:382-433](tg_bot/handlers/demo/demo_trading.py#L382-L433)

**Before**:
```python
raise ValueError("❌ Take-profit must be positive, got 500%")
```

**After**:
```python
raise TPSLValidationError(
    f"Take-profit seems unrealistic: {tp_percent}%",
    hint="Maximum recommended TP is 200%. For aggressive targets, try 100-200%"
)
```

**Error Scenarios Enhanced**:

| Scenario | Message | Hint |
|----------|---------|------|
| TP/SL missing | "Take-profit and stop-loss are required for all trades" | Example: tp_percent=50.0, sl_percent=20.0 |
| TP negative/zero | "Take-profit must be positive, got X%" | Try tp_percent=50.0 for a 50% profit target |
| SL negative/zero | "Stop-loss must be positive, got X%" | Try sl_percent=20.0 to risk 20% max loss |
| SL >= 100% | "Stop-loss cannot be >= 100% (would exceed investment)" | Maximum stop-loss is 99%. Typical range: 10-50% |
| TP >= 500% | "Take-profit seems unrealistic: X%" | Maximum recommended TP is 200% |
| TP < 5% | "Take-profit too low: X%" | Minimum recommended: 5% to cover trading fees |
| SL < 5% | "Stop-loss too low: X%" | Minimum recommended: 5% to allow natural price movement |

---

### 3. bags.fm API Error Handling

**Location**: [tg_bot/handlers/demo/demo_trading.py:317-351](tg_bot/handlers/demo/demo_trading.py#L317-L351)

**Added HTTP Status Code Detection**:

```python
try:
    import httpx
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 401 or status == 403:
            raise BagsAPIError(
                "bags.fm API authentication failed",
                hint="API key may be invalid or expired. Check BAGS_API_KEY and BAGS_PARTNER_KEY in settings"
            )
        elif status >= 500:
            logger.warning(f"bags.fm server error {status}, falling back to Jupiter: {exc}")
            # Continue to Jupiter fallback
        elif status == 429:
            logger.warning(f"bags.fm rate limit exceeded, falling back to Jupiter")
            # Continue to Jupiter fallback
except ImportError:
    pass  # httpx not available, continue with fallback
```

**Error Handling**:
- **401/403 (Auth)**: Immediate error, no fallback (config issue)
- **429 (Rate Limit)**: Warning logged, Jupiter fallback
- **500+ (Server Error)**: Warning logged, Jupiter fallback
- **Other errors**: Generic handling, Jupiter fallback

---

### 4. Jupiter Fallback Error Enhancement

**Location**: [tg_bot/handlers/demo/demo_trading.py:353-413](tg_bot/handlers/demo/demo_trading.py#L353-L413)

**Improved Error Messages**:

**Scenario 1: Wallet Not Configured**
```python
raise BagsAPIError(
    "Trade execution failed - wallet not configured",
    hint="Both bags.fm and Jupiter fallback require wallet setup. Contact admin."
)
```

**Scenario 2: Quote Failed**
```python
raise BagsAPIError(
    "Trade execution failed - unable to get price quote",
    hint=f"Both bags.fm and Jupiter could not provide a quote. Original error: {last_error or 'Unknown'}"
)
```

**Scenario 3: All Platforms Failed**
```python
raise BagsAPIError(
    "Trade execution failed on all platforms",
    hint=f"bags.fm error: {last_error or 'Unknown'}. Jupiter error: {jup_error or 'Unknown'}. Try again later or contact support."
)
```

**Scenario 4: Unexpected Error**
```python
logger.error(f"Unexpected error during swap execution: {exc}")
raise BagsAPIError(
    "Trade execution failed due to unexpected error",
    hint="An unexpected error occurred. Please try again or contact support if the issue persists."
)
```

---

### 5. Telegram Callback Error Handling

**Location**: [tg_bot/handlers/demo/callbacks/buy.py:217-236](tg_bot/handlers/demo/callbacks/buy.py#L217-L236)

**Before**:
```python
except ValueError as e:
    logger.warning(f"TP/SL validation failed: {e}")
    return DemoMenuBuilder.error_message(str(e))
except Exception as e:
    logger.error(f"Buy execution failed: {e}")
    return DemoMenuBuilder.error_message(f"Buy failed: {str(e)[:100]}")
```

**After**:
```python
except Exception as e:
    # Check for our custom user-friendly errors
    if isinstance(e, (ctx.TPSLValidationError, ctx.BagsAPIError, ctx.TradingError)):
        logger.warning(f"Trading error: {e.message}")
        return DemoMenuBuilder.error_message(e.format_telegram())
    elif isinstance(e, ValueError):
        # Legacy validation errors
        logger.warning(f"Validation error: {e}")
        return DemoMenuBuilder.error_message(f"❌ {str(e)}")
    else:
        # Unexpected error
        logger.error(f"Buy execution failed unexpectedly: {e}", exc_info=True)
        return DemoMenuBuilder.error_message(
            "❌ Trade execution failed\n\n"
            f"💡 Hint: {str(e)[:100] if str(e) else 'Unknown error'}. "
            "Please try again or contact support if the issue persists."
        )
```

**Benefits**:
- Properly formats custom error classes with `.format_telegram()`
- Logs technical details for debugging (with `exc_info=True`)
- Shows user-friendly messages in Telegram
- Provides actionable hints for resolution

---

### 6. Updated Integration Tests

**Location**: [tests/integration/test_bags_tpsl_flow.py](tests/integration/test_bags_tpsl_flow.py)

**Changed**: All validation tests now expect `TPSLValidationError` instead of `ValueError`

**Before**:
```python
with pytest.raises(ValueError, match="mandatory"):
    _validate_tpsl_required(None, 20.0)
```

**After**:
```python
with pytest.raises(TPSLValidationError, match="required"):
    _validate_tpsl_required(None, 20.0)
```

**Test Results**: ✅ All 13/13 tests passing

---

## Files Modified

1. **`tg_bot/handlers/demo/demo_trading.py`**:
   - Added error classes (lines 27-60)
   - Enhanced TP/SL validation (lines 382-433)
   - Enhanced bags.fm error handling (lines 317-351)
   - Enhanced Jupiter fallback errors (lines 353-413)

2. **`tg_bot/handlers/demo/callbacks/buy.py`**:
   - Updated exception handling (lines 217-236)
   - Added `.format_telegram()` usage

3. **`tests/integration/test_bags_tpsl_flow.py`**:
   - Imported `TPSLValidationError`
   - Updated all validation test assertions

---

## Error Message Examples

### Example 1: Missing TP/SL

**User sees**:
```
❌ Take-profit and stop-loss are required for all trades

💡 Hint: Example: tp_percent=50.0 (50% profit target), sl_percent=20.0 (20% max loss)
```

### Example 2: Invalid API Key

**User sees**:
```
❌ bags.fm API authentication failed

💡 Hint: API key may be invalid or expired. Check BAGS_API_KEY and BAGS_PARTNER_KEY in settings
```

**Admin sees (logs)**:
```
[WARNING] bags.fm API authentication failed
[INFO] ⚙️ Attempting Jupiter fallback for trade execution
```

### Example 3: Unrealistic TP

**User sees**:
```
❌ Take-profit seems unrealistic: 500%

💡 Hint: Maximum recommended TP is 200%. For aggressive targets, try 100-200%
```

### Example 4: Both Platforms Failed

**User sees**:
```
❌ Trade execution failed on all platforms

💡 Hint: bags.fm error: Server error 503. Jupiter error: Quote timeout. Try again later or contact support.
```

---

## Benefits of Enhanced Error Handling

### For Users

1. **Clear error messages**: No technical jargon
2. **Actionable hints**: Know what to do next
3. **Consistent formatting**: All errors follow same pattern
4. **Recovery guidance**: Hints suggest fixes

### For Developers

1. **Detailed logging**: Technical details in logs
2. **Exception hierarchy**: Easy to catch specific errors
3. **Debugging info**: `exc_info=True` preserves stack traces
4. **Separation of concerns**: User messages != log messages

### For Support

1. **Self-service resolution**: Users can fix issues themselves
2. **Reduced support burden**: Clear hints reduce questions
3. **Better bug reports**: Users describe exact error seen
4. **Log correlation**: User message + technical logs = full picture

---

## Success Criteria

- [x] User-friendly error classes created (TradingError, BagsAPIError, TPSLValidationError)
- [x] All TP/SL validation errors provide helpful hints
- [x] HTTP error codes properly detected and handled
- [x] Telegram formatting method (`.format_telegram()`)
- [x] Callback handler updated to use custom exceptions
- [x] Integration tests updated and passing (13/13)
- [x] Technical details logged for debugging
- [x] User messages are actionable

**All criteria met** ✅

---

## Comparison: Before vs After

### Before (Technical Errors)

```
ValueError: Stop-loss cannot be >= 100%, got 150%
```

### After (User-Friendly)

```
❌ Stop-loss cannot be >= 100% (would exceed your investment), got 150%

💡 Hint: Maximum stop-loss is 99%. Typical range: 10-50%
```

---

### Before (Generic API Error)

```
HTTP 401 Unauthorized
```

### After (Actionable Error)

```
❌ bags.fm API authentication failed

💡 Hint: API key may be invalid or expired. Check BAGS_API_KEY and BAGS_PARTNER_KEY in settings
```

---

## Next Steps (Future Enhancements)

1. **Error Analytics**: Track which errors occur most frequently
2. **Custom Error Codes**: Assign unique codes for support ticket correlation
3. **Retry Suggestions**: "This error is transient, retry in X seconds"
4. **i18n Support**: Translate errors to multiple languages
5. **Error Recovery**: Auto-retry with different parameters

---

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5
**Status**: Task 6 COMPLETE ✅
**Next**: Task 7 (Documentation)
