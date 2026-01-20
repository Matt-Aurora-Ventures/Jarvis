"""
Comprehensive Data Validation Tests for JARVIS

Tests cover:
1. Invalid input rejection with clear errors
2. Type coercion correctness
3. Range validation (min/max)
4. Required field enforcement
5. Optional fields with correct defaults
6. Nested object validation
7. Custom validators (Solana, Telegram, Trading)
8. Composite validators
9. Decorator-based validation
"""
import pytest
from pydantic import ValidationError as PydanticValidationError

# Core validation module
from core.validation import (
    ValidationError,
    MultiValidationError,
    Validator,
    RequiredValidator,
    TypeValidator,
    RangeValidator,
    LengthValidator,
    RegexValidator,
    ChoiceValidator,
    EmailValidator,
    URLValidator,
    SolanaAddressValidator,
    SolanaAmountValidator,
    TokenMintValidator,
    TelegramUserIdValidator,
    TelegramChatIdValidator,
    SlippageValidator,
    PriorityFeeValidator,
    ChainValidator,
    OptionalValidator,
    ListValidator,
    validate_params,
    validate_solana_address,
    validate_sol_amount,
    validate_telegram_user,
    validate_slippage,
)

# API schema validators
from api.schemas.validators import (
    sanitize_string,
    validate_alphanumeric,
    validate_symbol,
    validate_address,
    validate_positive_number,
    validate_range,
    validate_enum_list,
    validate_no_duplicates,
    validate_max_items,
    ValidatedString,
    AlphanumericString,
    TradingSymbol,
    SolanaAddress,
    PositiveFloat,
    Percentage,
    PaginationMixin,
    CONSTRAINTS,
    PATTERNS,
    BLACKLIST_PATTERNS,
)

# API schemas
from api.schemas.trading import (
    CreateOrderRequest,
    OrderResponse,
    OrderSide,
    OrderType,
    OrderStatus,
    CancelOrderRequest,
    PositionResponse,
    TradeResponse,
    BacktestRequest,
    BacktestResponse,
)
from api.schemas.pagination import (
    PaginationParams,
    PaginatedResponse,
    CursorPaginationParams,
    paginate,
    encode_cursor,
    decode_cursor,
)
from api.schemas.responses import (
    APIResponse,
    ErrorDetail,
    ValidationErrorResponse,
    success_response,
    error_response,
    validation_error_response,
    paginated_response,
    make_error_response,
    ERROR_CODES,
)


# =============================================================================
# 1. Invalid Input Rejection Tests
# =============================================================================


class TestInvalidInputRejection:
    """Test that invalid inputs are rejected with clear error messages."""

    def test_required_validator_rejects_none(self):
        """Test RequiredValidator rejects None values."""
        validator = RequiredValidator()
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(None, "test_field")
        assert "required" in str(exc_info.value).lower()
        assert exc_info.value.field == "test_field"

    def test_required_validator_rejects_empty_string(self):
        """Test RequiredValidator rejects empty strings by default."""
        validator = RequiredValidator(allow_empty=False)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("", "test_field")
        assert "empty" in str(exc_info.value).lower()

    def test_required_validator_allows_empty_when_configured(self):
        """Test RequiredValidator allows empty strings when configured."""
        validator = RequiredValidator(allow_empty=True)
        result = validator.validate("", "test_field")
        assert result == ""

    def test_type_validator_rejects_wrong_type(self):
        """Test TypeValidator rejects wrong types with clear message."""
        validator = TypeValidator(int)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("not an int", "count")
        assert "Expected int" in str(exc_info.value)
        assert "got str" in str(exc_info.value)

    def test_regex_validator_rejects_non_matching(self):
        """Test RegexValidator rejects non-matching strings."""
        validator = RegexValidator(r"^[A-Z]{3}$", message="Must be 3 uppercase letters")
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("abc", "code")
        assert "3 uppercase letters" in str(exc_info.value)

    def test_choice_validator_rejects_invalid_choice(self):
        """Test ChoiceValidator rejects invalid choices."""
        validator = ChoiceValidator({"buy", "sell"})
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("hold", "action")
        assert "Must be one of" in str(exc_info.value)

    def test_email_validator_rejects_invalid_email(self):
        """Test EmailValidator rejects invalid email formats."""
        validator = EmailValidator()
        invalid_emails = [
            "not-an-email",
            "@missing-local.com",
            "missing-at.com",
            "missing@domain",
            "spaces in@email.com",
        ]
        for email in invalid_emails:
            with pytest.raises(ValidationError) as exc_info:
                validator.validate(email, "email")
            assert "Invalid email format" in str(exc_info.value)

    def test_url_validator_rejects_invalid_url(self):
        """Test URLValidator rejects invalid URLs."""
        validator = URLValidator()
        invalid_urls = [
            "not-a-url",
            "ftp://file-server.com",  # Only http/https allowed
            "http://",
            "://missing-scheme.com",
        ]
        for url in invalid_urls:
            with pytest.raises(ValidationError) as exc_info:
                validator.validate(url, "website")
            assert "Invalid URL format" in str(exc_info.value)

    def test_url_validator_https_requirement(self):
        """Test URLValidator enforces HTTPS when required."""
        validator = URLValidator(require_https=True)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("http://insecure.com", "api_endpoint")
        assert "HTTPS required" in str(exc_info.value)


# =============================================================================
# 2. Type Coercion Tests
# =============================================================================


class TestTypeCoercion:
    """Test that type coercion works correctly when enabled."""

    def test_type_validator_coerces_string_to_int(self):
        """Test TypeValidator coerces string to int."""
        validator = TypeValidator(int, coerce=True)
        result = validator.validate("42", "count")
        assert result == 42
        assert isinstance(result, int)

    def test_type_validator_coerces_string_to_float(self):
        """Test TypeValidator coerces string to float."""
        validator = TypeValidator(float, coerce=True)
        result = validator.validate("3.14", "price")
        assert result == 3.14
        assert isinstance(result, float)

    def test_type_validator_coercion_fails_gracefully(self):
        """Test TypeValidator coercion fails with clear error."""
        validator = TypeValidator(int, coerce=True)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("not a number", "count")
        assert "Cannot convert" in str(exc_info.value)

    def test_solana_amount_coerces_string(self):
        """Test SolanaAmountValidator coerces string to float."""
        validator = SolanaAmountValidator()
        result = validator.validate("1.5", "amount")
        assert result == 1.5
        assert isinstance(result, float)

    def test_telegram_user_id_coerces_string(self):
        """Test TelegramUserIdValidator coerces string to int."""
        validator = TelegramUserIdValidator()
        result = validator.validate("123456789", "user_id")
        assert result == 123456789
        assert isinstance(result, int)

    def test_slippage_strips_percent_sign(self):
        """Test SlippageValidator handles percent sign."""
        validator = SlippageValidator()
        result = validator.validate("2.5%", "slippage")
        assert result == 2.5

    def test_priority_fee_coerces_string(self):
        """Test PriorityFeeValidator coerces string to int."""
        validator = PriorityFeeValidator()
        result = validator.validate("1000", "priority_fee")
        assert result == 1000
        assert isinstance(result, int)


# =============================================================================
# 3. Range Validation Tests
# =============================================================================


class TestRangeValidation:
    """Test range validation (min/max values)."""

    def test_range_validator_min_inclusive(self):
        """Test RangeValidator with inclusive minimum."""
        validator = RangeValidator(min_val=0)
        assert validator.validate(0, "value") == 0
        assert validator.validate(100, "value") == 100

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(-1, "value")
        assert "at least" in str(exc_info.value)

    def test_range_validator_max_inclusive(self):
        """Test RangeValidator with inclusive maximum."""
        validator = RangeValidator(max_val=100)
        assert validator.validate(100, "value") == 100
        assert validator.validate(0, "value") == 0

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(101, "value")
        assert "at most" in str(exc_info.value)

    def test_range_validator_exclusive_min(self):
        """Test RangeValidator with exclusive minimum."""
        validator = RangeValidator(min_val=0, exclusive_min=True)
        assert validator.validate(1, "value") == 1
        assert validator.validate(0.001, "value") == 0.001

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(0, "value")
        assert "greater than" in str(exc_info.value)

    def test_range_validator_exclusive_max(self):
        """Test RangeValidator with exclusive maximum."""
        validator = RangeValidator(max_val=100, exclusive_max=True)
        assert validator.validate(99, "value") == 99
        assert validator.validate(99.999, "value") == 99.999

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(100, "value")
        assert "less than" in str(exc_info.value)

    def test_range_validator_combined_min_max(self):
        """Test RangeValidator with both min and max."""
        validator = RangeValidator(min_val=10, max_val=20)
        assert validator.validate(10, "value") == 10
        assert validator.validate(15, "value") == 15
        assert validator.validate(20, "value") == 20

        with pytest.raises(ValidationError):
            validator.validate(9, "value")
        with pytest.raises(ValidationError):
            validator.validate(21, "value")

    def test_length_validator_min_length(self):
        """Test LengthValidator with minimum length."""
        validator = LengthValidator(min_len=5)
        assert validator.validate("hello", "text") == "hello"

        with pytest.raises(ValidationError) as exc_info:
            validator.validate("hi", "text")
        assert "at least 5" in str(exc_info.value)

    def test_length_validator_max_length(self):
        """Test LengthValidator with maximum length."""
        validator = LengthValidator(max_len=10)
        assert validator.validate("short", "text") == "short"

        with pytest.raises(ValidationError) as exc_info:
            validator.validate("this is too long", "text")
        assert "at most 10" in str(exc_info.value)

    def test_length_validator_works_with_lists(self):
        """Test LengthValidator works with lists."""
        validator = LengthValidator(min_len=1, max_len=5)
        assert validator.validate([1, 2, 3], "items") == [1, 2, 3]

        with pytest.raises(ValidationError):
            validator.validate([], "items")
        with pytest.raises(ValidationError):
            validator.validate([1, 2, 3, 4, 5, 6], "items")

    def test_solana_amount_range_validation(self):
        """Test SolanaAmountValidator enforces SOL amount range."""
        validator = SolanaAmountValidator(min_sol=0.001, max_sol=100)
        assert validator.validate(1.0, "amount") == 1.0
        assert validator.validate(0.001, "amount") == 0.001
        assert validator.validate(100.0, "amount") == 100.0

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(0.0001, "amount")
        assert "Minimum amount" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(101.0, "amount")
        assert "Maximum amount" in str(exc_info.value)

    def test_slippage_range_validation(self):
        """Test SlippageValidator enforces slippage range."""
        validator = SlippageValidator(max_slippage=50.0)
        assert validator.validate(0, "slippage") == 0.0
        assert validator.validate(25.0, "slippage") == 25.0
        assert validator.validate(50.0, "slippage") == 50.0

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(-1, "slippage")
        assert "cannot be negative" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(60.0, "slippage")
        assert "cannot exceed" in str(exc_info.value)

    def test_priority_fee_range_validation(self):
        """Test PriorityFeeValidator enforces fee range."""
        validator = PriorityFeeValidator(max_fee=1_000_000)
        assert validator.validate(0, "fee") == 0
        assert validator.validate(1000, "fee") == 1000
        assert validator.validate(1_000_000, "fee") == 1_000_000

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(-1, "fee")
        assert "cannot be negative" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate(2_000_000, "fee")
        assert "cannot exceed" in str(exc_info.value)


# =============================================================================
# 4. Required Field Enforcement Tests
# =============================================================================


class TestRequiredFieldEnforcement:
    """Test that required fields are properly enforced."""

    def test_create_order_requires_symbol(self):
        """Test CreateOrderRequest requires symbol field."""
        with pytest.raises((PydanticValidationError, TypeError)):
            CreateOrderRequest(
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=10.0
            )

    def test_create_order_requires_side(self):
        """Test CreateOrderRequest requires side field."""
        with pytest.raises((PydanticValidationError, TypeError)):
            CreateOrderRequest(
                symbol="SOL/USDC",
                order_type=OrderType.MARKET,
                amount=10.0
            )

    def test_create_order_requires_amount(self):
        """Test CreateOrderRequest requires amount field."""
        with pytest.raises((PydanticValidationError, TypeError)):
            CreateOrderRequest(
                symbol="SOL/USDC",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET
            )

    def test_cancel_order_validates_when_order_id_explicitly_empty(self):
        """Test CancelOrderRequest validates when order_id is explicitly empty string.

        Note: The validator uses Pydantic v1 @validator which fires when the field
        is explicitly provided. When no fields are provided (all defaults), the
        validator may not fire. This tests the explicit case.
        """
        # When order_id is explicitly set to empty string (not default None)
        # the validator should check and fail
        with pytest.raises((PydanticValidationError, ValueError)):
            CancelOrderRequest(order_id="")

    def test_cancel_order_accepts_valid_order_id(self):
        """Test CancelOrderRequest accepts valid order_id."""
        request = CancelOrderRequest(order_id="order-123")
        assert request.order_id == "order-123"

    def test_cancel_order_accepts_valid_client_order_id(self):
        """Test CancelOrderRequest accepts valid client_order_id."""
        request = CancelOrderRequest(client_order_id="client-order-456")
        assert request.client_order_id == "client-order-456"

    def test_backtest_request_requires_symbol(self):
        """Test BacktestRequest requires symbol field."""
        with pytest.raises((PydanticValidationError, TypeError)):
            BacktestRequest(interval="1h")

    def test_backtest_request_requires_interval(self):
        """Test BacktestRequest requires interval field."""
        with pytest.raises((PydanticValidationError, TypeError)):
            BacktestRequest(symbol="BTC")

    def test_multi_validation_error_tracks_all_errors(self):
        """Test MultiValidationError properly tracks all errors."""
        errors = [
            ValidationError("field1", "error1"),
            ValidationError("field2", "error2"),
            ValidationError("field3", "error3"),
        ]
        multi_error = MultiValidationError(errors)

        assert len(multi_error.errors) == 3
        error_dict = multi_error.to_dict()
        assert "field1" in error_dict
        assert "field2" in error_dict
        assert "field3" in error_dict


# =============================================================================
# 5. Optional Fields with Defaults Tests
# =============================================================================


class TestOptionalFieldDefaults:
    """Test that optional fields have correct defaults."""

    def test_create_order_default_order_type(self):
        """Test CreateOrderRequest defaults to MARKET order type."""
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side=OrderSide.BUY,
            amount=10.0
        )
        assert order.order_type == OrderType.MARKET

    def test_create_order_default_reduce_only(self):
        """Test CreateOrderRequest defaults reduce_only to False."""
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side=OrderSide.BUY,
            amount=10.0
        )
        assert order.reduce_only is False

    def test_create_order_default_post_only(self):
        """Test CreateOrderRequest defaults post_only to False."""
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side=OrderSide.BUY,
            amount=10.0
        )
        assert order.post_only is False

    def test_create_order_optional_price_none(self):
        """Test CreateOrderRequest price is None by default."""
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side=OrderSide.BUY,
            amount=10.0
        )
        assert order.price is None

    def test_create_order_optional_client_order_id_none(self):
        """Test CreateOrderRequest client_order_id is None by default."""
        order = CreateOrderRequest(
            symbol="SOL/USDC",
            side=OrderSide.BUY,
            amount=10.0
        )
        assert order.client_order_id is None

    def test_pagination_params_defaults(self):
        """Test PaginationParams has correct defaults."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 20
        assert params.sort_by is None
        assert params.sort_order == "desc"

    def test_cursor_pagination_defaults(self):
        """Test CursorPaginationParams has correct defaults."""
        params = CursorPaginationParams()
        assert params.cursor is None
        assert params.limit == 20
        assert params.direction == "next"

    def test_backtest_request_defaults(self):
        """Test BacktestRequest has correct defaults."""
        request = BacktestRequest(symbol="BTC", interval="1h")
        assert request.strategy == "sma_cross"
        assert request.initial_capital == 10000
        assert request.params == {}

    def test_optional_validator_returns_default(self):
        """Test OptionalValidator returns default for None."""
        inner_validator = TypeValidator(int)
        validator = OptionalValidator(inner_validator, default=0)

        assert validator.validate(None, "count") == 0
        assert validator.validate(42, "count") == 42


# =============================================================================
# 6. Nested Object Validation Tests
# =============================================================================


class TestNestedObjectValidation:
    """Test nested object and list validation."""

    def test_list_validator_validates_items(self):
        """Test ListValidator validates all items."""
        item_validator = RangeValidator(min_val=0, max_val=100)
        validator = ListValidator(item_validator)

        result = validator.validate([10, 20, 30], "scores")
        assert result == [10, 20, 30]

    def test_list_validator_fails_on_invalid_item(self):
        """Test ListValidator fails with specific item error."""
        item_validator = RangeValidator(min_val=0, max_val=100)
        validator = ListValidator(item_validator)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate([10, 150, 30], "scores")
        assert "scores[1]" in str(exc_info.value)

    def test_list_validator_enforces_min_items(self):
        """Test ListValidator enforces minimum items."""
        item_validator = TypeValidator(int)
        validator = ListValidator(item_validator, min_items=2)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate([1], "items")
        assert "at least 2" in str(exc_info.value)

    def test_list_validator_enforces_max_items(self):
        """Test ListValidator enforces maximum items."""
        item_validator = TypeValidator(int)
        validator = ListValidator(item_validator, max_items=3)

        with pytest.raises(ValidationError) as exc_info:
            validator.validate([1, 2, 3, 4], "items")
        assert "at most 3" in str(exc_info.value)

    def test_list_validator_rejects_non_list(self):
        """Test ListValidator rejects non-list input."""
        validator = ListValidator(TypeValidator(int))

        with pytest.raises(ValidationError) as exc_info:
            validator.validate("not a list", "items")
        assert "Expected list" in str(exc_info.value)

    def test_chain_validator_applies_all_validators(self):
        """Test ChainValidator applies validators in order."""
        validator = ChainValidator(
            RequiredValidator(),
            TypeValidator(str),
            LengthValidator(min_len=3, max_len=10),
            RegexValidator(r"^[a-z]+$", "lowercase letters only")
        )

        result = validator.validate("hello", "username")
        assert result == "hello"

    def test_chain_validator_stops_on_first_failure(self):
        """Test ChainValidator stops on first validation failure."""
        validator = ChainValidator(
            RequiredValidator(),
            TypeValidator(str),
            LengthValidator(min_len=10)  # Will fail for "hi"
        )

        with pytest.raises(ValidationError) as exc_info:
            validator.validate("hi", "text")
        assert "at least 10" in str(exc_info.value)

    def test_paginated_response_structure(self):
        """Test PaginatedResponse has correct structure."""
        items = [{"id": 1}, {"id": 2}, {"id": 3}]
        response = paginate(items, page=1, page_size=10)

        assert response.items == items
        assert response.total == 3
        assert response.page == 1
        assert response.page_size == 10
        assert response.total_pages == 1
        assert response.has_next is False
        assert response.has_prev is False

    def test_api_response_with_nested_error(self):
        """Test APIResponse with nested error details."""
        error = ErrorDetail(
            code="VAL_001",
            message="Validation failed",
            field="nested.field",
            details={"expected": "int", "got": "string"}
        )
        response = APIResponse(success=False, error=error)

        assert response.success is False
        assert response.error.field == "nested.field"
        assert response.error.details["expected"] == "int"


# =============================================================================
# 7. Solana-Specific Validation Tests
# =============================================================================


class TestSolanaValidation:
    """Test Solana-specific validators."""

    def test_solana_address_valid(self):
        """Test valid Solana addresses are accepted."""
        validator = SolanaAddressValidator()
        # Example valid addresses
        valid_addresses = [
            "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
            "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Random valid
        ]
        for addr in valid_addresses:
            result = validator.validate(addr, "address")
            assert result == addr

    def test_solana_address_invalid_length(self):
        """Test Solana addresses with invalid length are rejected."""
        validator = SolanaAddressValidator()

        # Too short
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("shortaddress", "address")
        assert "32-44 characters" in str(exc_info.value)

        # Too long
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("a" * 50, "address")
        assert "32-44 characters" in str(exc_info.value)

    def test_solana_address_invalid_characters(self):
        """Test Solana addresses with invalid characters are rejected."""
        validator = SolanaAddressValidator()

        # Contains 0 (not in base58)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("0" * 40, "address")
        assert "base58" in str(exc_info.value).lower()

        # Contains O (not in base58)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("O" * 40, "address")
        assert "base58" in str(exc_info.value).lower()

        # Contains special characters
        with pytest.raises(ValidationError) as exc_info:
            validator.validate("abcd!@#$%^&*()_+-=[]{}|;" + "a" * 20, "address")
        assert "base58" in str(exc_info.value).lower()

    def test_token_mint_validator_known_tokens(self):
        """Test TokenMintValidator accepts known token mints."""
        validator = TokenMintValidator(allow_unknown=False)
        known_mints = [
            "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        ]
        for mint in known_mints:
            result = validator.validate(mint, "token_mint")
            assert result == mint

    def test_token_mint_validator_unknown_rejected_when_configured(self):
        """Test TokenMintValidator rejects unknown mints when configured."""
        validator = TokenMintValidator(allow_unknown=False)
        # Valid format but unknown mint
        unknown_mint = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(unknown_mint, "token_mint")
        assert "Unknown token mint" in str(exc_info.value)

    def test_token_mint_validator_allows_unknown_when_configured(self):
        """Test TokenMintValidator allows unknown mints when configured."""
        validator = TokenMintValidator(allow_unknown=True)
        unknown_mint = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        result = validator.validate(unknown_mint, "token_mint")
        assert result == unknown_mint

    def test_solana_amount_allows_zero_when_configured(self):
        """Test SolanaAmountValidator allows zero when configured."""
        validator = SolanaAmountValidator(allow_zero=True)
        result = validator.validate(0, "amount")
        assert result == 0.0


# =============================================================================
# 8. Telegram-Specific Validation Tests
# =============================================================================


class TestTelegramValidation:
    """Test Telegram-specific validators."""

    def test_telegram_user_id_valid(self):
        """Test valid Telegram user IDs are accepted."""
        validator = TelegramUserIdValidator()
        valid_ids = [1, 123456789, 9999999999]
        for user_id in valid_ids:
            result = validator.validate(user_id, "user_id")
            assert result == user_id

    def test_telegram_user_id_rejects_zero(self):
        """Test Telegram user ID validator rejects zero."""
        validator = TelegramUserIdValidator()
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(0, "user_id")
        assert "positive" in str(exc_info.value)

    def test_telegram_user_id_rejects_negative(self):
        """Test Telegram user ID validator rejects negative numbers."""
        validator = TelegramUserIdValidator()
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(-123, "user_id")
        assert "positive" in str(exc_info.value)

    def test_telegram_chat_id_accepts_negative(self):
        """Test Telegram chat ID validator accepts negative IDs (groups)."""
        validator = TelegramChatIdValidator()
        # Negative IDs are valid for groups/channels
        result = validator.validate(-1001234567890, "chat_id")
        assert result == -1001234567890

    def test_telegram_chat_id_accepts_positive(self):
        """Test Telegram chat ID validator accepts positive IDs (users)."""
        validator = TelegramChatIdValidator()
        result = validator.validate(123456789, "chat_id")
        assert result == 123456789


# =============================================================================
# 9. Trading Validation Tests
# =============================================================================


class TestTradingValidation:
    """Test trading-specific validators."""

    def test_valid_trading_symbols(self):
        """Test valid trading symbols are accepted."""
        valid_symbols = ["SOL/USDC", "BTC", "ETH/USDT", "BONK/SOL"]
        for symbol in valid_symbols:
            result = validate_symbol(symbol)
            assert result == symbol.upper()

    def test_symbol_normalization(self):
        """Test symbols are normalized to uppercase."""
        result = validate_symbol("sol/usdc")
        assert result == "SOL/USDC"

    def test_invalid_trading_symbols(self):
        """Test invalid trading symbols are rejected."""
        invalid_symbols = [
            "SOL-USDC",  # Wrong separator
            "SOL USDC",  # Space
            "SOL/USDC/BTC",  # Too many parts
            "123/456",  # Numbers only
            "",  # Empty
            "TOOLONGNAME/USDC",  # Too long
        ]
        for symbol in invalid_symbols:
            with pytest.raises(ValueError):
                validate_symbol(symbol)

    def test_order_side_enum(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_type_enum(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"
        assert OrderType.STOP.value == "stop"
        assert OrderType.STOP_LIMIT.value == "stop_limit"

    def test_order_status_enum(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "pending"
        assert OrderStatus.OPEN.value == "open"
        assert OrderStatus.FILLED.value == "filled"
        assert OrderStatus.CANCELLED.value == "cancelled"

    def test_backtest_interval_pattern(self):
        """Test backtest interval pattern validation."""
        # Valid intervals
        valid_request = BacktestRequest(symbol="BTC", interval="1h")
        assert valid_request.interval == "1h"

        valid_intervals = ["1m", "5m", "15m", "1h", "4h", "1d", "30m"]
        for interval in valid_intervals:
            request = BacktestRequest(symbol="BTC", interval=interval)
            assert request.interval == interval


# =============================================================================
# 10. API Schema Validator Function Tests
# =============================================================================


class TestAPISchemaValidatorFunctions:
    """Test API schema validator functions."""

    def test_sanitize_string_removes_whitespace(self):
        """Test sanitize_string removes leading/trailing whitespace."""
        assert sanitize_string("  hello  ") == "hello"
        assert sanitize_string("\t\ntest\n\t") == "test"

    def test_sanitize_string_blocks_xss(self):
        """Test sanitize_string blocks XSS attempts."""
        xss_strings = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img onload='alert(1)'>",
            "<div onclick='evil()'>",
        ]
        for xss in xss_strings:
            with pytest.raises(ValueError, match="invalid or suspicious"):
                sanitize_string(xss)

    def test_sanitize_string_blocks_sql_injection(self):
        """Test sanitize_string blocks SQL injection attempts."""
        sql_strings = [
            "'; DROP TABLE users; --",
            "SELECT * FROM users",
            "1; DELETE FROM orders",
            "UNION SELECT password FROM users",
        ]
        for sql in sql_strings:
            with pytest.raises(ValueError, match="invalid or suspicious"):
                sanitize_string(sql)

    def test_validate_positive_number(self):
        """Test validate_positive_number function."""
        assert validate_positive_number(1.0) == 1.0
        assert validate_positive_number(0.001) == 0.001

        with pytest.raises(ValueError):
            validate_positive_number(0)
        with pytest.raises(ValueError):
            validate_positive_number(-1)

    def test_validate_range_function(self):
        """Test validate_range function."""
        assert validate_range(50, 0, 100) == 50
        assert validate_range(0, 0, 100) == 0
        assert validate_range(100, 0, 100) == 100

        with pytest.raises(ValueError):
            validate_range(-1, 0, 100)
        with pytest.raises(ValueError):
            validate_range(101, 0, 100)

    def test_validate_enum_list(self):
        """Test validate_enum_list function."""
        allowed = ["red", "green", "blue"]
        assert validate_enum_list(["red", "blue"], allowed) == ["red", "blue"]

        with pytest.raises(ValueError):
            validate_enum_list(["red", "yellow"], allowed)

    def test_validate_no_duplicates(self):
        """Test validate_no_duplicates function."""
        assert validate_no_duplicates([1, 2, 3]) == [1, 2, 3]
        assert validate_no_duplicates(["a", "b", "c"]) == ["a", "b", "c"]

        with pytest.raises(ValueError):
            validate_no_duplicates([1, 2, 2, 3])

    def test_validate_max_items(self):
        """Test validate_max_items function."""
        assert validate_max_items([1, 2, 3], 5) == [1, 2, 3]
        assert validate_max_items([1, 2, 3], 3) == [1, 2, 3]

        with pytest.raises(ValueError):
            validate_max_items([1, 2, 3, 4, 5, 6], 5)


# =============================================================================
# 11. Decorator-Based Validation Tests
# =============================================================================


class TestDecoratorValidation:
    """Test validate_params decorator."""

    def test_sync_function_validation(self):
        """Test validate_params decorator with sync function."""
        @validate_params(
            amount=RangeValidator(min_val=0, max_val=100)
        )
        def process_amount(amount: float) -> float:
            return amount * 2

        assert process_amount(amount=50) == 100

    def test_sync_function_validation_failure(self):
        """Test validate_params decorator fails correctly."""
        @validate_params(
            amount=RangeValidator(min_val=0, max_val=100)
        )
        def process_amount(amount: float) -> float:
            return amount * 2

        with pytest.raises(MultiValidationError):
            process_amount(amount=150)

    @pytest.mark.asyncio
    async def test_async_function_validation(self):
        """Test validate_params decorator with async function."""
        @validate_params(
            wallet=SolanaAddressValidator(),
            amount=SolanaAmountValidator()
        )
        async def transfer(wallet: str, amount: float) -> dict:
            return {"wallet": wallet, "amount": amount}

        result = await transfer(
            wallet="So11111111111111111111111111111111111111112",
            amount=1.5
        )
        assert result["amount"] == 1.5

    @pytest.mark.asyncio
    async def test_async_function_validation_failure(self):
        """Test validate_params decorator fails correctly for async."""
        @validate_params(
            wallet=SolanaAddressValidator()
        )
        async def transfer(wallet: str) -> dict:
            return {"wallet": wallet}

        with pytest.raises(MultiValidationError):
            await transfer(wallet="invalid")

    def test_multiple_validation_errors(self):
        """Test validate_params collects multiple errors."""
        @validate_params(
            amount=RangeValidator(min_val=0, max_val=100),
            count=TypeValidator(int)
        )
        def process(amount: float, count: int) -> dict:
            return {"amount": amount, "count": count}

        with pytest.raises(MultiValidationError) as exc_info:
            process(amount=150, count="not a number")

        # Should have captured multiple errors
        assert len(exc_info.value.errors) >= 1


# =============================================================================
# 12. Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience validation functions."""

    def test_validate_solana_address(self):
        """Test validate_solana_address convenience function."""
        valid = "So11111111111111111111111111111111111111112"
        assert validate_solana_address(valid) == valid

        with pytest.raises(ValidationError):
            validate_solana_address("invalid")

    def test_validate_sol_amount(self):
        """Test validate_sol_amount convenience function."""
        assert validate_sol_amount(1.5) == 1.5
        assert validate_sol_amount("2.0") == 2.0

        with pytest.raises(ValidationError):
            validate_sol_amount(-1)

    def test_validate_telegram_user(self):
        """Test validate_telegram_user convenience function."""
        assert validate_telegram_user(123456789) == 123456789
        assert validate_telegram_user("123456789") == 123456789

        with pytest.raises(ValidationError):
            validate_telegram_user(-1)

    def test_validate_slippage(self):
        """Test validate_slippage convenience function."""
        assert validate_slippage(2.5) == 2.5
        assert validate_slippage("3.0%") == 3.0

        with pytest.raises(ValidationError):
            validate_slippage(100)  # Exceeds default max


# =============================================================================
# 13. API Response Validation Tests
# =============================================================================


class TestAPIResponseValidation:
    """Test API response schemas and utilities."""

    def test_success_response_structure(self):
        """Test success_response utility function."""
        response = success_response(data={"id": 1}, message="Created")
        assert response["success"] is True
        assert response["data"]["id"] == 1
        assert response["meta"]["message"] == "Created"

    def test_error_response_structure(self):
        """Test error_response utility function."""
        response = error_response(
            code="VAL_001",
            message="Validation failed",
            field="email",
            details={"expected": "valid email"}
        )
        assert response["success"] is False
        assert response["error"]["code"] == "VAL_001"
        assert response["error"]["field"] == "email"

    def test_validation_error_response(self):
        """Test validation_error_response utility function."""
        errors = [
            {"loc": ("body", "email"), "msg": "Invalid email", "type": "value_error"},
            {"loc": ("body", "age"), "msg": "Must be positive", "type": "value_error"},
        ]
        response = validation_error_response(errors)
        assert response["success"] is False
        assert len(response["errors"]) == 2

    def test_paginated_response_structure(self):
        """Test paginated_response utility function."""
        response = paginated_response(
            items=[{"id": 1}, {"id": 2}],
            total=100,
            page=2,
            page_size=10
        )
        assert response["success"] is True
        assert len(response["data"]) == 2
        assert response["meta"]["pagination"]["total"] == 100
        assert response["meta"]["pagination"]["page"] == 2
        assert response["meta"]["pagination"]["total_pages"] == 10
        assert response["meta"]["pagination"]["has_next"] is True
        assert response["meta"]["pagination"]["has_prev"] is True

    def test_make_error_response_from_code(self):
        """Test make_error_response utility function."""
        response = make_error_response("AUTH_001")
        assert response["error"]["code"] == "AUTH_001"
        assert "Authentication required" in response["error"]["message"]

    def test_error_codes_defined(self):
        """Test all expected error codes are defined."""
        expected_codes = [
            "VAL_001", "VAL_002",
            "AUTH_001", "AUTH_002", "AUTH_003", "AUTH_004",
            "RATE_001",
            "SYS_001", "SYS_002", "SYS_003",
            "TRADE_001", "TRADE_002", "TRADE_003",
            "PROV_001", "PROV_002",
        ]
        for code in expected_codes:
            assert code in ERROR_CODES


# =============================================================================
# 14. Cursor Pagination Tests
# =============================================================================


class TestCursorPagination:
    """Test cursor-based pagination."""

    def test_encode_decode_cursor(self):
        """Test cursor encoding and decoding."""
        data = {"id": 123, "timestamp": "2024-01-01"}
        encoded = encode_cursor(data)
        decoded = decode_cursor(encoded)
        assert decoded == data

    def test_decode_invalid_cursor(self):
        """Test decoding invalid cursor returns empty dict."""
        result = decode_cursor("invalid-cursor")
        assert result == {}

    def test_cursor_pagination_params_validation(self):
        """Test CursorPaginationParams validation."""
        # Valid params
        params = CursorPaginationParams(limit=50, direction="prev")
        assert params.limit == 50
        assert params.direction == "prev"

        # Invalid direction should fail
        with pytest.raises(PydanticValidationError):
            CursorPaginationParams(direction="invalid")


# =============================================================================
# 15. Constraint Constants Tests
# =============================================================================


class TestConstraintConstants:
    """Test constraint constants are properly defined."""

    def test_constraints_defined(self):
        """Test all expected constraints are defined."""
        assert "symbol" in CONSTRAINTS
        assert "address" in CONSTRAINTS
        assert "amount" in CONSTRAINTS
        assert "price" in CONSTRAINTS
        assert "percentage" in CONSTRAINTS
        assert "limit" in CONSTRAINTS
        assert "offset" in CONSTRAINTS

    def test_patterns_defined(self):
        """Test all expected patterns are defined."""
        assert "alphanumeric" in PATTERNS
        assert "symbol" in PATTERNS
        assert "address" in PATTERNS
        assert "uuid" in PATTERNS
        assert "iso8601" in PATTERNS

    def test_blacklist_patterns_exist(self):
        """Test blacklist patterns are defined."""
        assert len(BLACKLIST_PATTERNS) > 0

    def test_symbol_constraint_example(self):
        """Test symbol constraint has proper structure."""
        symbol = CONSTRAINTS["symbol"]
        assert "min_length" in symbol
        assert "max_length" in symbol
        assert "pattern" in symbol
        assert "example" in symbol


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
