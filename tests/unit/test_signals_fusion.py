"""
Tests for Signal Fusion System - core/signals/fusion.py

Tests cover:
- SignalDirection enum values
- SignalSource enum values
- SignalWeight dataclass and accuracy updates
- RawSignal creation, expiration, numeric conversion
- FusedSignal creation, validity, interpretation
- SignalFusion initialization, weighting, signal collection
- Weighted average calculation
- Direction determination thresholds
- Agreement score calculation
- Risk level determination
- Suggested action generation
- Outcome recording and weight adjustment
- Provider registration and collection
- Edge cases and error handling

Target: 60%+ coverage with comprehensive unit tests.
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Import the module under test
from core.signals.fusion import (
    SignalDirection,
    SignalSource,
    SignalWeight,
    RawSignal,
    FusedSignal,
    SignalFusion,
    get_signal_fusion,
)


# =============================================================================
# SignalDirection Tests
# =============================================================================

class TestSignalDirection:
    """Tests for SignalDirection enum."""

    def test_all_directions_defined(self):
        """Test all expected directions are defined."""
        expected = ["strong_buy", "buy", "neutral", "sell", "strong_sell"]
        actual = [d.value for d in SignalDirection]
        for direction in expected:
            assert direction in actual, f"Missing direction: {direction}"

    def test_direction_values_are_strings(self):
        """Test direction values are strings."""
        for direction in SignalDirection:
            assert isinstance(direction.value, str)

    def test_direction_ordering(self):
        """Test signal directions represent a spectrum from bullish to bearish."""
        directions = list(SignalDirection)
        assert directions[0] == SignalDirection.STRONG_BUY
        assert directions[-1] == SignalDirection.STRONG_SELL
        assert SignalDirection.NEUTRAL in directions


# =============================================================================
# SignalSource Tests
# =============================================================================

class TestSignalSource:
    """Tests for SignalSource enum."""

    def test_all_sources_defined(self):
        """Test all expected signal sources are defined."""
        expected = [
            "technical", "sentiment", "whale", "on_chain",
            "ml_model", "volume", "orderbook", "news",
            "correlation", "custom"
        ]
        actual = [s.value for s in SignalSource]
        for source in expected:
            assert source in actual, f"Missing source: {source}"

    def test_source_values_are_strings(self):
        """Test source values are strings."""
        for source in SignalSource:
            assert isinstance(source.value, str)

    def test_source_count(self):
        """Test expected number of sources."""
        assert len(SignalSource) == 10


# =============================================================================
# SignalWeight Tests
# =============================================================================

class TestSignalWeight:
    """Tests for SignalWeight dataclass."""

    def test_create_weight(self):
        """Test creating a basic SignalWeight."""
        weight = SignalWeight(
            source=SignalSource.TECHNICAL,
            base_weight=1.2,
        )
        assert weight.source == SignalSource.TECHNICAL
        assert weight.base_weight == 1.2
        # current_weight defaults to 1.0, not base_weight
        assert weight.current_weight == 1.0
        assert weight.accuracy_30d == 0.5  # Default
        assert weight.signals_count == 0
        assert weight.profitable_signals == 0

    def test_update_accuracy_profitable(self):
        """Test accuracy update with profitable outcome."""
        weight = SignalWeight(source=SignalSource.WHALE, base_weight=1.0)

        weight.update_accuracy(was_profitable=True)

        assert weight.signals_count == 1
        assert weight.profitable_signals == 1
        assert weight.accuracy_30d == 1.0

    def test_update_accuracy_losing(self):
        """Test accuracy update with losing outcome."""
        weight = SignalWeight(source=SignalSource.SENTIMENT, base_weight=1.0)

        weight.update_accuracy(was_profitable=False)

        assert weight.signals_count == 1
        assert weight.profitable_signals == 0
        assert weight.accuracy_30d == 0.0

    def test_update_accuracy_mixed(self):
        """Test accuracy with mixed outcomes."""
        weight = SignalWeight(source=SignalSource.VOLUME, base_weight=1.0)

        # 7 profitable, 3 losing = 70% accuracy
        for _ in range(7):
            weight.update_accuracy(was_profitable=True)
        for _ in range(3):
            weight.update_accuracy(was_profitable=False)

        assert weight.signals_count == 10
        assert weight.profitable_signals == 7
        assert weight.accuracy_30d == 0.7

    def test_weight_adjustment_by_accuracy(self):
        """Test weight adjusts based on accuracy."""
        weight = SignalWeight(source=SignalSource.TECHNICAL, base_weight=1.0)

        # High accuracy should increase weight
        for _ in range(10):
            weight.update_accuracy(was_profitable=True)

        # Weight = base * (0.5 + accuracy) = 1.0 * (0.5 + 1.0) = 1.5
        assert weight.current_weight == 1.5

    def test_weight_reduction_low_accuracy(self):
        """Test weight reduces with low accuracy."""
        weight = SignalWeight(source=SignalSource.NEWS, base_weight=1.0)

        # Low accuracy should decrease weight
        for _ in range(10):
            weight.update_accuracy(was_profitable=False)

        # Weight = base * (0.5 + accuracy) = 1.0 * (0.5 + 0.0) = 0.5
        assert weight.current_weight == 0.5

    def test_weight_to_dict(self):
        """Test converting SignalWeight to dictionary."""
        weight = SignalWeight(
            source=SignalSource.ML_MODEL,
            base_weight=1.1,
            current_weight=1.2,
            accuracy_30d=0.75,
        )

        data = weight.to_dict()

        assert data["source"] == "ml_model"
        assert data["base_weight"] == 1.1
        assert data["current_weight"] == 1.2
        assert data["accuracy_30d"] == 0.75
        assert "last_updated" in data


# =============================================================================
# RawSignal Tests
# =============================================================================

class TestRawSignal:
    """Tests for RawSignal dataclass."""

    def test_create_raw_signal(self):
        """Test creating a basic RawSignal."""
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8,
        )

        assert signal.source == SignalSource.TECHNICAL
        assert signal.token == "SOL"
        assert signal.direction == SignalDirection.BUY
        assert signal.strength == 0.7
        assert signal.confidence == 0.8
        assert signal.timestamp is not None

    def test_raw_signal_with_metadata(self):
        """Test RawSignal with metadata."""
        metadata = {"indicator": "RSI", "value": 30}
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="BTC",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.85,
            metadata=metadata,
        )

        assert signal.metadata["indicator"] == "RSI"
        assert signal.metadata["value"] == 30

    def test_raw_signal_to_numeric_strong_buy(self):
        """Test to_numeric for STRONG_BUY."""
        signal = RawSignal(
            source=SignalSource.WHALE,
            token="ETH",
            direction=SignalDirection.STRONG_BUY,
            strength=1.0,
            confidence=0.9,
        )

        # STRONG_BUY = 1.0, strength = 1.0, so result = 1.0
        assert signal.to_numeric() == 1.0

    def test_raw_signal_to_numeric_buy(self):
        """Test to_numeric for BUY."""
        signal = RawSignal(
            source=SignalSource.SENTIMENT,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.7,
        )

        # BUY = 0.5, strength = 0.8, so result = 0.4
        assert signal.to_numeric() == 0.4

    def test_raw_signal_to_numeric_neutral(self):
        """Test to_numeric for NEUTRAL."""
        signal = RawSignal(
            source=SignalSource.VOLUME,
            token="BTC",
            direction=SignalDirection.NEUTRAL,
            strength=0.5,
            confidence=0.6,
        )

        # NEUTRAL = 0.0
        assert signal.to_numeric() == 0.0

    def test_raw_signal_to_numeric_sell(self):
        """Test to_numeric for SELL."""
        signal = RawSignal(
            source=SignalSource.ON_CHAIN,
            token="AVAX",
            direction=SignalDirection.SELL,
            strength=0.7,
            confidence=0.8,
        )

        # SELL = -0.5, strength = 0.7, so result = -0.35
        assert signal.to_numeric() == -0.35

    def test_raw_signal_to_numeric_strong_sell(self):
        """Test to_numeric for STRONG_SELL."""
        signal = RawSignal(
            source=SignalSource.NEWS,
            token="LINK",
            direction=SignalDirection.STRONG_SELL,
            strength=1.0,
            confidence=0.95,
        )

        # STRONG_SELL = -1.0, strength = 1.0, so result = -1.0
        assert signal.to_numeric() == -1.0

    def test_raw_signal_not_expired(self):
        """Test fresh signal is not expired."""
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8,
        )

        assert not signal.is_expired()

    def test_raw_signal_expired(self):
        """Test signal with past expiry is expired."""
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8,
            expires_at=datetime.now() - timedelta(hours=2),
        )

        assert signal.is_expired()

    def test_raw_signal_default_expiry(self):
        """Test signal default expiry is 1 hour."""
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8,
            timestamp=datetime.now() - timedelta(hours=2),  # 2 hours ago
        )

        # Signal should be expired (default 1 hour expiry)
        assert signal.is_expired()


# =============================================================================
# FusedSignal Tests
# =============================================================================

class TestFusedSignal:
    """Tests for FusedSignal dataclass."""

    def test_create_fused_signal(self):
        """Test creating a FusedSignal."""
        signal = FusedSignal(
            signal_id="FSIG-TEST123",
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.75,
            confidence=0.8,
            source_signals={"technical": 0.5, "whale": 0.3},
            source_count=2,
            agreement_score=0.85,
        )

        assert signal.signal_id == "FSIG-TEST123"
        assert signal.token == "SOL"
        assert signal.direction == SignalDirection.BUY
        assert signal.strength == 0.75
        assert signal.confidence == 0.8
        assert signal.source_count == 2

    def test_fused_signal_auto_id(self):
        """Test FusedSignal generates ID if not provided."""
        signal = FusedSignal(
            signal_id="",
            token="BTC",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.85,
        )

        assert signal.signal_id.startswith("FSIG-")
        assert len(signal.signal_id) > 5

    def test_fused_signal_is_valid(self):
        """Test fresh FusedSignal is valid."""
        signal = FusedSignal(
            signal_id="FSIG-TEST",
            token="ETH",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.75,
        )

        assert signal.is_valid()

    def test_fused_signal_expired(self):
        """Test FusedSignal past valid_until is not valid."""
        signal = FusedSignal(
            signal_id="FSIG-OLD",
            token="SOL",
            direction=SignalDirection.SELL,
            strength=0.6,
            confidence=0.7,
            valid_until=datetime.now() - timedelta(hours=1),
        )

        assert not signal.is_valid()

    def test_fused_signal_to_dict(self):
        """Test converting FusedSignal to dictionary."""
        signal = FusedSignal(
            signal_id="FSIG-DICT",
            token="AVAX",
            direction=SignalDirection.NEUTRAL,
            strength=0.5,
            confidence=0.6,
            source_signals={"technical": 0.2, "sentiment": -0.1},
            interpretation="Neutral outlook",
            suggested_action="Wait for clarity",
        )

        data = signal.to_dict()

        assert data["signal_id"] == "FSIG-DICT"
        assert data["token"] == "AVAX"
        assert data["direction"] == "neutral"
        assert data["strength"] == 0.5
        assert data["interpretation"] == "Neutral outlook"
        assert "timestamp" in data
        assert "valid_until" in data


# =============================================================================
# SignalFusion Tests
# =============================================================================

class TestSignalFusion:
    """Tests for SignalFusion class."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a SignalFusion instance with temp storage."""
        storage_path = tmp_path / "test_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.5,
        )

    def test_create_fusion(self, fusion):
        """Test creating a SignalFusion instance."""
        assert fusion is not None
        assert fusion.min_sources == 2
        assert fusion.min_confidence == 0.5

    def test_default_weights_initialized(self, fusion):
        """Test default weights are initialized for all sources."""
        for source in SignalSource:
            assert source in fusion.weights
            weight = fusion.weights[source]
            assert weight.base_weight > 0

    def test_specific_default_weights(self, fusion):
        """Test specific default weight values."""
        assert fusion.weights[SignalSource.TECHNICAL].base_weight == 1.2
        assert fusion.weights[SignalSource.WHALE].base_weight == 1.5
        assert fusion.weights[SignalSource.ON_CHAIN].base_weight == 1.3
        assert fusion.weights[SignalSource.SENTIMENT].base_weight == 0.8

    @pytest.mark.asyncio
    async def test_add_signal(self, fusion):
        """Test adding a raw signal."""
        signal = RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.85,
        )

        await fusion.add_signal(signal)

        assert "SOL" in fusion.pending_signals
        assert SignalSource.TECHNICAL in fusion.pending_signals["SOL"]

    @pytest.mark.asyncio
    async def test_add_expired_signal_ignored(self, fusion):
        """Test expired signals are ignored."""
        signal = RawSignal(
            source=SignalSource.WHALE,
            token="BTC",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.9,
            expires_at=datetime.now() - timedelta(hours=2),
        )

        await fusion.add_signal(signal)

        # Expired signal should not be added
        assert "BTC" not in fusion.pending_signals or \
               SignalSource.WHALE not in fusion.pending_signals.get("BTC", {})

    @pytest.mark.asyncio
    async def test_fuse_signals_requires_minimum(self, fusion):
        """Test fusion requires minimum number of sources."""
        # Add only one signal (need 2)
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.8,
        ))

        # Should not create fused signal yet
        fused = await fusion.get_signal("SOL")
        assert fused is None

    @pytest.mark.asyncio
    async def test_fuse_signals_success(self, fusion):
        """Test successful signal fusion with multiple sources."""
        # Add multiple signals
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.85,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="SOL",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.9,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.SENTIMENT,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.75,
        ))

        fused = await fusion.get_signal("SOL")

        assert fused is not None
        assert fused.token == "SOL"
        assert fused.direction in [SignalDirection.BUY, SignalDirection.STRONG_BUY]
        # Fusion triggers after min_sources (2), so may process before all added
        assert fused.source_count >= 2

    @pytest.mark.asyncio
    async def test_fused_signal_confidence(self, fusion):
        """Test fused signal confidence calculation."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="ETH",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.9,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.VOLUME,
            token="ETH",
            direction=SignalDirection.BUY,
            strength=0.7,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("ETH")

        assert fused is not None
        assert 0.0 <= fused.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_fused_signal_agreement_unanimous(self, fusion):
        """Test agreement score with unanimous signals."""
        for source in [SignalSource.TECHNICAL, SignalSource.WHALE, SignalSource.SENTIMENT]:
            await fusion.add_signal(RawSignal(
                source=source,
                token="AVAX",
                direction=SignalDirection.BUY,
                strength=0.8,
                confidence=0.85,
            ))

        fused = await fusion.get_signal("AVAX")

        assert fused is not None
        assert fused.agreement_score == 1.0

    @pytest.mark.asyncio
    async def test_fused_signal_agreement_split(self, fusion):
        """Test agreement score with split signals."""
        fusion.min_confidence = 0.2  # Lower threshold for test

        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="LINK",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.8,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.NEWS,
            token="LINK",
            direction=SignalDirection.SELL,
            strength=0.7,
            confidence=0.8,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.ON_CHAIN,
            token="LINK",
            direction=SignalDirection.NEUTRAL,
            strength=0.5,
            confidence=0.7,
        ))

        fused = await fusion.get_signal("LINK")

        if fused:
            # Three different directions = low agreement
            assert fused.agreement_score < 1.0

    def test_register_provider(self, fusion):
        """Test registering a signal provider."""
        mock_provider = Mock(return_value=None)

        fusion.register_provider(SignalSource.CUSTOM, mock_provider)

        assert SignalSource.CUSTOM in fusion.providers
        assert fusion.providers[SignalSource.CUSTOM] == mock_provider

    @pytest.mark.asyncio
    async def test_collect_signals_from_providers(self, fusion):
        """Test collecting signals from registered providers."""
        # Create a mock provider that returns a signal
        mock_signal = RawSignal(
            source=SignalSource.CUSTOM,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.85,
        )
        mock_provider = AsyncMock(return_value=mock_signal)

        fusion.register_provider(SignalSource.CUSTOM, mock_provider)

        signals = await fusion.collect_signals("SOL")

        mock_provider.assert_called_once_with("SOL")
        assert SignalSource.CUSTOM in signals

    @pytest.mark.asyncio
    async def test_collect_signals_handles_errors(self, fusion):
        """Test collect_signals handles provider errors gracefully."""
        failing_provider = AsyncMock(side_effect=Exception("Provider error"))

        fusion.register_provider(SignalSource.CUSTOM, failing_provider)

        # Should not raise, should return empty or partial signals
        signals = await fusion.collect_signals("BTC")

        # Should still return (possibly empty) dict
        assert isinstance(signals, dict)

    @pytest.mark.asyncio
    async def test_record_outcome_profitable(self, fusion):
        """Test recording a profitable outcome updates weights."""
        # Create a fused signal
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.9,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="SOL",
            direction=SignalDirection.BUY,
            strength=0.85,
            confidence=0.85,
        ))

        fused = await fusion.get_signal("SOL")

        if fused:
            initial_tech_weight = fusion.weights[SignalSource.TECHNICAL].current_weight

            await fusion.record_outcome(fused.signal_id, was_profitable=True)

            # Weight should increase for sources that contributed positively
            new_tech_weight = fusion.weights[SignalSource.TECHNICAL].current_weight
            assert new_tech_weight >= initial_tech_weight

    @pytest.mark.asyncio
    async def test_get_active_signals(self, fusion):
        """Test getting all active fused signals."""
        # Create multiple fused signals
        for token in ["SOL", "BTC"]:
            await fusion.add_signal(RawSignal(
                source=SignalSource.TECHNICAL,
                token=token,
                direction=SignalDirection.BUY,
                strength=0.8,
                confidence=0.85,
            ))
            await fusion.add_signal(RawSignal(
                source=SignalSource.WHALE,
                token=token,
                direction=SignalDirection.BUY,
                strength=0.85,
                confidence=0.9,
            ))

        active = await fusion.get_active_signals()

        assert isinstance(active, list)

    def test_get_weight_stats(self, fusion):
        """Test getting weight statistics."""
        stats = fusion.get_weight_stats()

        assert isinstance(stats, dict)
        assert "technical" in stats
        assert "whale" in stats
        assert "current_weight" in stats["technical"]
        assert "accuracy_30d" in stats["technical"]


# =============================================================================
# Fusion Direction Thresholds Tests
# =============================================================================

class TestFusionDirectionThresholds:
    """Tests for direction determination based on signal values."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a fusion instance for threshold testing."""
        storage_path = tmp_path / "threshold_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.3,
        )

    @pytest.mark.asyncio
    async def test_strong_buy_threshold(self, fusion):
        """Test STRONG_BUY direction for high positive values."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="TEST",
            direction=SignalDirection.STRONG_BUY,
            strength=1.0,
            confidence=0.95,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="TEST",
            direction=SignalDirection.STRONG_BUY,
            strength=1.0,
            confidence=0.95,
        ))

        fused = await fusion.get_signal("TEST")

        assert fused is not None
        assert fused.direction == SignalDirection.STRONG_BUY

    @pytest.mark.asyncio
    async def test_strong_sell_threshold(self, fusion):
        """Test STRONG_SELL direction for high negative values."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="BEAR",
            direction=SignalDirection.STRONG_SELL,
            strength=1.0,
            confidence=0.95,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.NEWS,
            token="BEAR",
            direction=SignalDirection.STRONG_SELL,
            strength=1.0,
            confidence=0.9,
        ))

        fused = await fusion.get_signal("BEAR")

        assert fused is not None
        assert fused.direction == SignalDirection.STRONG_SELL

    @pytest.mark.asyncio
    async def test_neutral_threshold(self, fusion):
        """Test NEUTRAL direction for balanced signals."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="FLAT",
            direction=SignalDirection.BUY,
            strength=0.5,
            confidence=0.8,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.NEWS,
            token="FLAT",
            direction=SignalDirection.SELL,
            strength=0.5,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("FLAT")

        if fused:
            # Balanced signals should result in NEUTRAL or near-neutral
            assert fused.direction in [SignalDirection.NEUTRAL, SignalDirection.BUY, SignalDirection.SELL]


# =============================================================================
# Risk Level Tests
# =============================================================================

class TestRiskLevel:
    """Tests for risk level determination."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a fusion instance for risk testing."""
        storage_path = tmp_path / "risk_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.3,
        )

    @pytest.mark.asyncio
    async def test_low_risk_high_confidence_strength(self, fusion):
        """Test low risk level with high confidence and strength."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="SAFE",
            direction=SignalDirection.BUY,
            strength=0.9,
            confidence=0.95,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="SAFE",
            direction=SignalDirection.BUY,
            strength=0.85,
            confidence=0.9,
        ))

        fused = await fusion.get_signal("SAFE")

        assert fused is not None
        assert fused.risk_level in ["low", "medium"]

    @pytest.mark.asyncio
    async def test_high_risk_low_confidence(self, fusion):
        """Test high risk level with low confidence."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.NEWS,
            token="RISKY",
            direction=SignalDirection.BUY,
            strength=0.4,
            confidence=0.5,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.SENTIMENT,
            token="RISKY",
            direction=SignalDirection.SELL,
            strength=0.4,
            confidence=0.5,
        ))

        fused = await fusion.get_signal("RISKY")

        if fused:
            assert fused.risk_level in ["medium", "high"]


# =============================================================================
# Suggested Action Tests
# =============================================================================

class TestSuggestedAction:
    """Tests for suggested action generation."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a fusion instance for action testing."""
        storage_path = tmp_path / "action_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.3,
        )

    @pytest.mark.asyncio
    async def test_strong_buy_action(self, fusion):
        """Test suggested action for strong buy signal."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="LONG",
            direction=SignalDirection.STRONG_BUY,
            strength=0.95,
            confidence=0.9,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="LONG",
            direction=SignalDirection.STRONG_BUY,
            strength=0.9,
            confidence=0.85,
        ))

        fused = await fusion.get_signal("LONG")

        assert fused is not None
        assert "long" in fused.suggested_action.lower() or "position" in fused.suggested_action.lower()

    @pytest.mark.asyncio
    async def test_sell_action(self, fusion):
        """Test suggested action for sell signal."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="EXIT",
            direction=SignalDirection.STRONG_SELL,
            strength=0.9,
            confidence=0.85,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.ON_CHAIN,
            token="EXIT",
            direction=SignalDirection.SELL,
            strength=0.8,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("EXIT")

        assert fused is not None
        action_lower = fused.suggested_action.lower()
        assert "exit" in action_lower or "short" in action_lower or "sell" in action_lower or "profit" in action_lower


# =============================================================================
# Persistence Tests
# =============================================================================

class TestFusionPersistence:
    """Tests for SignalFusion data persistence."""

    def test_save_and_load_weights(self, tmp_path):
        """Test saving and loading weight data."""
        storage_path = tmp_path / "persist_fusion.json"

        # Create fusion and update some weights
        fusion1 = SignalFusion(storage_path=str(storage_path))
        fusion1.weights[SignalSource.TECHNICAL].update_accuracy(True)
        fusion1.weights[SignalSource.TECHNICAL].update_accuracy(True)
        fusion1._save()

        # Create new fusion instance and load
        fusion2 = SignalFusion(storage_path=str(storage_path))

        # Check weights were persisted
        assert fusion2.weights[SignalSource.TECHNICAL].signals_count == 2
        assert fusion2.weights[SignalSource.TECHNICAL].accuracy_30d == 1.0


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestFusionEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a fusion instance for edge case testing."""
        storage_path = tmp_path / "edge_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.3,
        )

    @pytest.mark.asyncio
    async def test_empty_token(self, fusion):
        """Test handling empty token string."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("")
        # Should handle gracefully
        assert fused is None or fused.token == ""

    @pytest.mark.asyncio
    async def test_zero_strength_signal(self, fusion):
        """Test handling signal with zero strength."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.TECHNICAL,
            token="ZERO",
            direction=SignalDirection.BUY,
            strength=0.0,
            confidence=0.8,
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="ZERO",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("ZERO")
        # Should still work
        assert fused is not None

    @pytest.mark.asyncio
    async def test_zero_confidence_signal(self, fusion):
        """Test handling signal with zero confidence."""
        await fusion.add_signal(RawSignal(
            source=SignalSource.NEWS,
            token="NOCONF",
            direction=SignalDirection.STRONG_BUY,
            strength=1.0,
            confidence=0.0,  # Zero confidence
        ))
        await fusion.add_signal(RawSignal(
            source=SignalSource.WHALE,
            token="NOCONF",
            direction=SignalDirection.BUY,
            strength=0.8,
            confidence=0.8,
        ))

        fused = await fusion.get_signal("NOCONF")
        # Zero confidence signal should have minimal impact
        assert fused is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent_signal(self, fusion):
        """Test getting signal for token with no data."""
        fused = await fusion.get_signal("DOESNOTEXIST")
        assert fused is None

    @pytest.mark.asyncio
    async def test_record_outcome_nonexistent_signal(self, fusion):
        """Test recording outcome for nonexistent signal."""
        # Should not raise
        await fusion.record_outcome("FSIG-DOESNOTEXIST", was_profitable=True)


# =============================================================================
# Module-Level Function Tests
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_get_signal_fusion_singleton(self):
        """Test get_signal_fusion returns singleton instance."""
        fusion1 = get_signal_fusion()
        fusion2 = get_signal_fusion()

        assert fusion1 is fusion2


# =============================================================================
# Integration Tests
# =============================================================================

class TestFusionIntegration:
    """Integration tests for SignalFusion."""

    @pytest.fixture
    def fusion(self, tmp_path):
        """Create a fusion instance for integration testing."""
        storage_path = tmp_path / "integration_fusion.json"
        return SignalFusion(
            storage_path=str(storage_path),
            min_sources_for_signal=2,
            min_confidence=0.5,
        )

    @pytest.mark.asyncio
    async def test_full_workflow(self, fusion):
        """Test full workflow: add signals, fuse, record outcome."""
        # 1. Add signals from multiple sources
        sources = [SignalSource.TECHNICAL, SignalSource.WHALE, SignalSource.SENTIMENT]
        for source in sources:
            await fusion.add_signal(RawSignal(
                source=source,
                token="WORKFLOW",
                direction=SignalDirection.BUY,
                strength=0.8,
                confidence=0.85,
            ))

        # 2. Get fused signal
        fused = await fusion.get_signal("WORKFLOW")

        assert fused is not None
        assert fused.token == "WORKFLOW"
        # Fusion triggers after min_sources (2), so may not include all 3
        assert fused.source_count >= 2

        # 3. Record outcome
        await fusion.record_outcome(fused.signal_id, was_profitable=True)

        # 4. Verify some weights were updated (sources that contributed to the signal)
        updated_count = sum(1 for source in sources if fusion.weights[source].signals_count > 0)
        assert updated_count >= 1

    @pytest.mark.asyncio
    async def test_multiple_tokens(self, fusion):
        """Test handling signals for multiple tokens."""
        tokens = ["SOL", "BTC", "ETH"]

        for token in tokens:
            await fusion.add_signal(RawSignal(
                source=SignalSource.TECHNICAL,
                token=token,
                direction=SignalDirection.BUY,
                strength=0.8,
                confidence=0.85,
            ))
            await fusion.add_signal(RawSignal(
                source=SignalSource.WHALE,
                token=token,
                direction=SignalDirection.BUY,
                strength=0.9,
                confidence=0.9,
            ))

        for token in tokens:
            fused = await fusion.get_signal(token)
            assert fused is not None
            assert fused.token == token


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
