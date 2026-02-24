import os
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from core.backtest.data_ingestion.coingecko import CoinGeckoFetcher

@pytest.fixture
def mock_coingecko_response():
    return {
        "prices": [
            [1672531200000, 16500.5],
            [1672617600000, 16600.2]
        ],
        "total_volumes": [
            [1672531200000, 12000000000.0],
            [1672617600000, 13000000000.0]
        ],
        "market_caps": [
            [1672531200000, 318000000000.0],
            [1672617600000, 320000000000.0]
        ]
    }

class TestCoinGeckoFetcher:

    def setup_method(self):
        # Use a temporary test cache directory
        self.fetcher = CoinGeckoFetcher(cache_dir="test_data_cache")

    def teardown_method(self):
        # Cleanup
        if os.path.exists("test_data_cache"):
            for f in os.listdir("test_data_cache"):
                os.remove(os.path.join("test_data_cache", f))
            os.rmdir("test_data_cache")

    @patch("core.backtest.data_ingestion.coingecko.requests.get")
    def test_fetch_success(self, mock_get, mock_coingecko_response):
        """Test successful fetch and parsing of CoinGecko data."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_coingecko_response
        mock_get.return_value = mock_resp

        df = self.fetcher.fetch_historical_data("bitcoin", 2, "usd", use_cache=False)

        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

        # Check columns
        assert list(df.columns) == ["timestamp", "price", "volume", "market_cap"]

        # Check correct parsing of data
        assert df.iloc[0]["price"] == 16500.5
        assert df.iloc[1]["volume"] == 13000000000.0

    @patch("core.backtest.data_ingestion.coingecko.requests.get")
    def test_cache_logic(self, mock_get, mock_coingecko_response):
        """Test that data is cached and then loaded from cache."""
        mock_resp =Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_coingecko_response
        mock_get.return_value = mock_resp

        # First fetch (should hit API and write to cache)
        df1 = self.fetcher.fetch_historical_data("solana", 1, "usd", use_cache=True)
        assert mock_get.call_count == 1
        assert df1 is not None

        # Change the mock to simulate failure to prove it loads from cache
        mock_get.return_value.status_code = 500

        # Second fetch (should hit cache)
        df2 = self.fetcher.fetch_historical_data("solana", 1, "usd", use_cache=True)

        # Call count should remain 1 because it loaded from cache
        assert mock_get.call_count == 1
        assert df2 is not None
        assert len(df1) == len(df2)
        assert df1.iloc[0]['price'] == df2.iloc[0]['price']

    @patch("core.backtest.data_ingestion.coingecko.time.sleep")
    @patch("core.backtest.data_ingestion.coingecko.requests.get")
    def test_rate_limit_retry(self, mock_get, mock_sleep, mock_coingecko_response):
        """Test that it retries upon 429 status code."""
        # Setup consecutive mock responses: 429, then 200
        mock_429 = Mock()
        mock_429.status_code = 429

        mock_200 = Mock()
        mock_200.status_code = 200
        mock_200.json.return_value = mock_coingecko_response

        mock_get.side_effect = [mock_429, mock_200]

        df = self.fetcher.fetch_historical_data("ethereum", 1, use_cache=False)

        assert mock_get.call_count == 2
        assert mock_sleep.call_count == 1
        assert df is not None
        assert len(df) == 2
