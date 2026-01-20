"""
Scam Detector Tests

Tests for the anti-scam detection system that:
- Detects pump-and-dump patterns
- Identifies suspicious trades
- Monitors for honeypots
- Tracks known scams
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


class TestScamDetector:
    """Tests for the scam detector."""

    @pytest.fixture
    def detector(self, tmp_path):
        """Create a scam detector instance."""
        from core.security.scam_detector import ScamDetector
        return ScamDetector(cache_dir=tmp_path)

    def test_initialization(self, tmp_path):
        """Test scam detector initializes correctly."""
        from core.security.scam_detector import ScamDetector
        detector = ScamDetector(cache_dir=tmp_path)
        assert detector is not None

    def test_detect_pump_and_dump_pattern(self, detector):
        """Test detecting pump-and-dump price pattern."""
        price_history = [
            {"timestamp": "2024-01-01T00:00:00Z", "price": 1.0},
            {"timestamp": "2024-01-01T00:05:00Z", "price": 1.5},
            {"timestamp": "2024-01-01T00:10:00Z", "price": 3.0},  # Pump
            {"timestamp": "2024-01-01T00:15:00Z", "price": 5.0},  # Peak
            {"timestamp": "2024-01-01T00:20:00Z", "price": 2.0},  # Dump
            {"timestamp": "2024-01-01T00:25:00Z", "price": 0.5},  # Crash
        ]

        result = detector.detect_pump_and_dump(
            token_address="TestToken123",
            price_history=price_history
        )

        assert result["is_pump_and_dump"] is True
        assert result["confidence"] > 0.7
        assert "price_spike" in result["indicators"] or result["pump_detected"] is True

    def test_detect_normal_price_movement(self, detector):
        """Test that normal price movements are not flagged."""
        price_history = [
            {"timestamp": "2024-01-01T00:00:00Z", "price": 1.0},
            {"timestamp": "2024-01-01T01:00:00Z", "price": 1.02},
            {"timestamp": "2024-01-01T02:00:00Z", "price": 0.98},
            {"timestamp": "2024-01-01T03:00:00Z", "price": 1.05},
            {"timestamp": "2024-01-01T04:00:00Z", "price": 1.03},
        ]

        result = detector.detect_pump_and_dump(
            token_address="StableToken123",
            price_history=price_history
        )

        assert result["is_pump_and_dump"] is False

    def test_identify_suspicious_trade(self, detector):
        """Test identifying suspicious trading patterns."""
        trade_data = {
            "token_address": "SuspiciousToken123",
            "trade_size_usd": 50000,
            "price_impact_pct": 15,  # High price impact
            "buyer_address": "BuyerWallet123",
            "seller_address": "SellerWallet456",
        }

        # Mock historical data showing buyer/seller relationship
        with patch.object(detector, '_get_wallet_history') as mock_history:
            mock_history.return_value = {
                "shared_transactions": 50,  # Many shared transactions
                "avg_trade_interval_seconds": 60,  # Rapid trading
            }

            result = detector.identify_suspicious_trade(trade_data)

            assert result["is_suspicious"] is True
            assert len(result["reasons"]) > 0

    def test_detect_wash_trading(self, detector):
        """Test detecting wash trading patterns."""
        trades = [
            {"buyer": "Wallet1", "seller": "Wallet2", "amount": 1000, "timestamp": "2024-01-01T00:00:00Z"},
            {"buyer": "Wallet2", "seller": "Wallet1", "amount": 1000, "timestamp": "2024-01-01T00:05:00Z"},
            {"buyer": "Wallet1", "seller": "Wallet2", "amount": 1000, "timestamp": "2024-01-01T00:10:00Z"},
            {"buyer": "Wallet2", "seller": "Wallet1", "amount": 1000, "timestamp": "2024-01-01T00:15:00Z"},
        ]

        result = detector.detect_wash_trading(
            token_address="WashTradeToken123",
            recent_trades=trades
        )

        assert result["wash_trading_detected"] is True
        assert result["wash_trading_score"] > 0.7

    def test_detect_honeypot(self, detector):
        """Test detecting honeypot tokens."""
        with patch.object(detector, '_simulate_sell') as mock_sell:
            # Simulate sell always fails
            mock_sell.return_value = {
                "can_sell": False,
                "error": "Transfer blocked",
                "tax_on_sell": 99,  # 99% sell tax
            }

            result = detector.detect_honeypot("HoneypotToken123")

            assert result["is_honeypot"] is True
            assert "sell_blocked" in result["reasons"] or result["sell_tax_pct"] > 50

    def test_detect_not_honeypot(self, detector):
        """Test that legitimate tokens are not flagged as honeypots."""
        with patch.object(detector, '_simulate_sell') as mock_sell:
            mock_sell.return_value = {
                "can_sell": True,
                "tax_on_sell": 1,  # Normal 1% tax
            }

            result = detector.detect_honeypot("LegitToken123")

            assert result["is_honeypot"] is False

    def test_check_known_scam_database(self, detector):
        """Test checking against known scam database."""
        # Add a known scam
        detector.report_scam(
            token_address="KnownScamToken123",
            scam_type="rugpull",
            evidence={"link": "https://example.com/scam-report"}
        )

        result = detector.check_known_scam("KnownScamToken123")

        assert result["is_known_scam"] is True
        assert result["scam_type"] == "rugpull"

    def test_check_unknown_token(self, detector):
        """Test checking an unknown token."""
        result = detector.check_known_scam("UnknownToken123")

        assert result["is_known_scam"] is False

    def test_track_wallet_reputation(self, detector):
        """Test wallet reputation tracking."""
        # Report wallet involvement in scam
        detector.report_scam_wallet(
            wallet_address="ScamWallet123",
            role="creator",
            associated_token="RugpullToken123"
        )

        result = detector.check_wallet_reputation("ScamWallet123")

        assert result["reputation_score"] < 1.0  # Reduced from perfect
        assert result["scam_associations"] >= 1
        assert result["is_known_scammer"] is True

    def test_comprehensive_token_scan(self, detector):
        """Test comprehensive token security scan."""
        with patch.multiple(detector,
                          detect_pump_and_dump=MagicMock(return_value={"is_pump_and_dump": False}),
                          detect_honeypot=MagicMock(return_value={"is_honeypot": False}),
                          check_known_scam=MagicMock(return_value={"is_known_scam": False}),
                          detect_wash_trading=MagicMock(return_value={"wash_trading_detected": False})):

            result = detector.comprehensive_scan("TokenAddress123")

            assert "overall_risk_score" in result
            assert "pump_dump_risk" in result
            assert "honeypot_risk" in result
            assert "scam_database_match" in result
            assert "recommendation" in result


class TestScamDetectorRealTimeMonitoring:
    """Tests for real-time scam monitoring."""

    @pytest.fixture
    def detector(self, tmp_path):
        from core.security.scam_detector import ScamDetector
        return ScamDetector(cache_dir=tmp_path)

    def test_add_to_watchlist(self, detector):
        """Test adding token to watchlist."""
        result = detector.add_to_watchlist(
            token_address="WatchToken123",
            alert_threshold=0.7,
            callback_url="https://example.com/alert"
        )

        assert result["success"] is True
        assert detector.is_watchlisted("WatchToken123")

    def test_remove_from_watchlist(self, detector):
        """Test removing token from watchlist."""
        detector.add_to_watchlist("WatchToken123", 0.7)
        detector.remove_from_watchlist("WatchToken123")

        assert not detector.is_watchlisted("WatchToken123")

    def test_alert_generation(self, detector):
        """Test alert generation when threshold exceeded."""
        detector.add_to_watchlist("AlertToken123", alert_threshold=0.5)

        with patch.object(detector, 'comprehensive_scan') as mock_scan:
            mock_scan.return_value = {"overall_risk_score": 0.8}

            alerts = detector.check_watchlist()

            assert len(alerts) >= 1
            assert alerts[0]["token_address"] == "AlertToken123"


class TestScamDetectorPatternAnalysis:
    """Tests for advanced pattern analysis."""

    @pytest.fixture
    def detector(self, tmp_path):
        from core.security.scam_detector import ScamDetector
        return ScamDetector(cache_dir=tmp_path)

    def test_detect_coordinated_buying(self, detector):
        """Test detecting coordinated buying patterns."""
        buy_events = [
            {"wallet": "W1", "amount": 1000, "timestamp": "2024-01-01T00:00:00Z"},
            {"wallet": "W2", "amount": 1000, "timestamp": "2024-01-01T00:00:01Z"},
            {"wallet": "W3", "amount": 1000, "timestamp": "2024-01-01T00:00:02Z"},
            {"wallet": "W4", "amount": 1000, "timestamp": "2024-01-01T00:00:03Z"},
            {"wallet": "W5", "amount": 1000, "timestamp": "2024-01-01T00:00:04Z"},
        ]

        result = detector.detect_coordinated_activity(
            token_address="CoordToken123",
            events=buy_events
        )

        assert result["coordinated_activity_detected"] is True
        assert result["confidence"] > 0.5

    def test_detect_insider_trading(self, detector):
        """Test detecting potential insider trading."""
        # Large buys before announcement
        pre_announcement_trades = [
            {"wallet": "InsiderWallet", "amount": 100000, "timestamp": "2024-01-01T00:00:00Z"},
        ]
        announcement_time = "2024-01-01T01:00:00Z"
        price_before = 1.0
        price_after = 5.0

        result = detector.detect_insider_trading(
            token_address="InsiderToken123",
            trades=pre_announcement_trades,
            announcement_time=announcement_time,
            price_before=price_before,
            price_after=price_after
        )

        assert result["insider_trading_suspected"] is True
        assert "InsiderWallet" in result["suspect_wallets"]

    def test_detect_bot_activity(self, detector):
        """Test detecting bot-like trading activity."""
        trades = [
            {"timestamp": "2024-01-01T00:00:00.000Z", "amount": 100},
            {"timestamp": "2024-01-01T00:00:00.100Z", "amount": 100},  # 100ms apart
            {"timestamp": "2024-01-01T00:00:00.200Z", "amount": 100},
            {"timestamp": "2024-01-01T00:00:00.300Z", "amount": 100},
            {"timestamp": "2024-01-01T00:00:00.400Z", "amount": 100},
        ]

        result = detector.detect_bot_activity(
            token_address="BotToken123",
            trades=trades
        )

        assert result["bot_activity_detected"] is True
        assert result["bot_confidence"] > 0.7
