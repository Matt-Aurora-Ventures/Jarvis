import os
import json
import time
import requests
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any

class CoinGeckoFetcher:
    """
    Data ingestion wrapper for CoinGecko API.
    Handles rate limiting, caching, and pandas DataFrame conversion.
    """

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # Default sleep for rate limit
        self.rate_limit_sleep = 60
        self.max_retries = 3

    def _get_cache_path(self, coin_id: str, vs_currency: str, days: int) -> Path:
        """Generate a standardized cache path."""
        return self.cache_dir / f"{coin_id}_{vs_currency}_{days}d.parquet"

    def fetch_historical_data(self, coin_id: str, days: int, vs_currency: str = "usd", use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetch historical price, total_volume, and market_cap data.
        Returns a Pandas DataFrame aligned by timestamp.
        """
        cache_path = self._get_cache_path(coin_id, vs_currency, days)

        # Check Local Cache
        if use_cache and cache_path.exists():
            try:
                return pd.read_parquet(cache_path)
            except Exception as e:
                print(f"[CoinGeckoFetcher] Failed to read cache {cache_path}: {e}")

        # Fetch from API
        url = f"{self.BASE_URL}/coins/{coin_id}/market_chart"
        params: Dict[str, Any] = {
            "vs_currency": vs_currency,
            "days": str(days)
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    df = self._parse_market_chart(data)

                    if use_cache and df is not None and not df.empty:
                        df.to_parquet(cache_path, index=False)

                    return df

                elif response.status_code == 429:
                    print(f"[CoinGeckoFetcher] Rate limited. Sleeping for {self.rate_limit_sleep}s (Attempt {attempt+1}/{self.max_retries})")
                    time.sleep(self.rate_limit_sleep)

                else:
                    print(f"[CoinGeckoFetcher] API returned status {response.status_code}: {response.text}")
                    break

            except requests.RequestException as e:
                print(f"[CoinGeckoFetcher] Request failed: {e}")

        return None

    def _parse_market_chart(self, data: dict) -> Optional[pd.DataFrame]:
        """
        Convert CoinGecko market_chart JSON response into a normalized DataFrame.
        """
        if not data or 'prices' not in data:
            return None

        # Parse arrays
        prices = pd.DataFrame(data.get('prices', []), columns=['timestamp', 'price'])
        volumes = pd.DataFrame(data.get('total_volumes', []), columns=['timestamp', 'volume'])
        market_caps = pd.DataFrame(data.get('market_caps', []), columns=['timestamp', 'market_cap'])

        # Convert timestamp to datetime and set as index to allow merging
        for df in [prices, volumes, market_caps]:
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)

        # Merge all into one df
        merged_df = pd.concat([prices, volumes, market_caps], axis=1)

        # Keep timestamp as a column and drop index
        merged_df.reset_index(inplace=True)
        return merged_df
