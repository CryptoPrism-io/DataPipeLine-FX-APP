#!/usr/bin/env python3
"""
OANDA v20 Integration Module
Based on: https://github.com/oanda/v20-python-samples

Provides utilities for:
- Account management
- Instrument discovery
- Candlestick data fetching
- Real-time price streaming
- Volatility calculation
- Correlation analysis
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OANDAClient:
    """OANDA v20 REST API Client"""

    def __init__(self, api_token: str, account_id: str = None, use_demo: bool = True):
        """
        Initialize OANDA client

        Args:
            api_token: OANDA API token
            account_id: Account ID (if None, fetches the first account)
            use_demo: Use demo account (True) or live (False)
        """
        self.api_token = api_token
        self.account_id = account_id
        self.base_url = "https://api-fxpractice.oanda.com" if use_demo else "https://api-fxtrade.oanda.com"

        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "AcceptDatetimeFormat": "UNIX"
        }

    def get_accounts(self) -> Dict:
        """Get list of accounts"""
        try:
            response = requests.get(
                f"{self.base_url}/v3/accounts",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            accounts = response.json()['accounts']
            logger.info(f"Found {len(accounts)} account(s)")

            # Set first account as default if not specified
            if not self.account_id and accounts:
                self.account_id = accounts[0]['id']
                logger.info(f"Using account: {self.account_id}")

            return response.json()
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            raise

    def get_account_details(self) -> Dict:
        """Get details of current account"""
        try:
            response = requests.get(
                f"{self.base_url}/v3/accounts/{self.account_id}",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            account = response.json()['account']
            logger.info(f"Account Balance: {account['balance']} {account['currency']}")

            return response.json()
        except Exception as e:
            logger.error(f"Error fetching account details: {e}")
            raise

    def get_instruments(self) -> List[Dict]:
        """Get list of available instruments"""
        try:
            response = requests.get(
                f"{self.base_url}/v3/accounts/{self.account_id}/instruments",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()

            instruments = response.json()['instruments']
            logger.info(f"Found {len(instruments)} instruments")

            return instruments
        except Exception as e:
            logger.error(f"Error fetching instruments: {e}")
            raise

    def get_candles(
        self,
        instrument: str,
        granularity: str = "H1",
        count: int = 300,
        price: str = "MBA"
    ) -> List[Dict]:
        """
        Fetch candlestick data

        Args:
            instrument: Instrument name (e.g., "EUR_USD")
            granularity: Time granularity (M1, M5, H1, D, etc.)
            count: Number of candles to fetch
            price: Price type (MBA, M, BA)

        Returns:
            List of candle data
        """
        try:
            params = {
                "count": min(count, 5000),  # Max 5000
                "granularity": granularity,
                "price": price
            }

            response = requests.get(
                f"{self.base_url}/v3/instruments/{instrument}/candles",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            candles = response.json()['candles']
            logger.info(f"Fetched {len(candles)} candles for {instrument} ({granularity})")

            return candles
        except Exception as e:
            logger.error(f"Error fetching candles for {instrument}: {e}")
            raise

    def get_current_prices(self, instruments: List[str]) -> Dict:
        """
        Get current market prices

        Args:
            instruments: List of instrument names

        Returns:
            Current pricing data
        """
        try:
            params = {
                "instruments": ",".join(instruments)
            }

            response = requests.get(
                f"{self.base_url}/v3/accounts/{self.account_id}/pricing",
                headers=self.headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()

            return response.json()
        except Exception as e:
            logger.error(f"Error fetching current prices: {e}")
            raise

    def stream_prices(self, instruments: List[str]):
        """
        Stream real-time prices

        Args:
            instruments: List of instrument names

        Yields:
            Price updates
        """
        try:
            params = {
                "instruments": ",".join(instruments)
            }

            response = requests.get(
                f"{self.base_url}/v3/accounts/{self.account_id}/pricing/stream",
                headers=self.headers,
                params=params,
                stream=True,
                timeout=None
            )
            response.raise_for_status()

            logger.info(f"Started streaming prices for: {', '.join(instruments)}")

            for line in response.iter_lines():
                if line:
                    yield json.loads(line)
        except Exception as e:
            logger.error(f"Error streaming prices: {e}")
            raise


class VolatilityAnalyzer:
    """Calculate volatility metrics from OHLC data"""

    @staticmethod
    def candles_to_dataframe(candles: List[Dict], price_type: str = "mid") -> pd.DataFrame:
        """Convert candles to pandas DataFrame"""
        data = []
        for candle in candles:
            price_data = candle[price_type]
            data.append({
                'time': pd.to_datetime(candle['time']),
                'open': float(price_data['o']),
                'high': float(price_data['h']),
                'low': float(price_data['l']),
                'close': float(price_data['c']),
                'volume': candle.get('volume', 0)
            })

        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        return df

    @staticmethod
    def calculate_historical_volatility(
        prices: pd.Series,
        period: int = 20,
        annualization_factor: float = 252
    ) -> pd.Series:
        """
        Calculate historical volatility

        Args:
            prices: Price series
            period: Lookback period
            annualization_factor: 252 for daily, 252*24 for hourly, etc.

        Returns:
            Volatility series
        """
        returns = np.log(prices / prices.shift(1))
        volatility = returns.rolling(window=period).std() * np.sqrt(annualization_factor)
        return volatility

    @staticmethod
    def calculate_moving_average(prices: pd.Series, period: int) -> pd.Series:
        """Calculate simple moving average"""
        return prices.rolling(window=period).mean()

    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        num_std: float = 2
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands

        Returns:
            (upper_band, middle_band, lower_band)
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
        return upper, middle, lower

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        atr = df['tr'].rolling(window=period).mean()
        return atr


class CorrelationAnalyzer:
    """Calculate correlation metrics between instruments"""

    @staticmethod
    def calculate_correlation_matrix(
        price_data: Dict[str, List[float]],
        window: int = None
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix

        Args:
            price_data: Dict with instrument names as keys, price lists as values
            window: Rolling window size (None for full period)

        Returns:
            Correlation matrix
        """
        df = pd.DataFrame(price_data)

        if window:
            correlation = df.rolling(window=window).corr()
            # Get the final correlation matrix
            return correlation.iloc[-1]
        else:
            return df.corr()

    @staticmethod
    def get_best_pairs(correlation_matrix: pd.DataFrame, threshold: float = 0.7) -> List[Tuple]:
        """
        Find best uncorrelated pairs

        Args:
            correlation_matrix: Correlation matrix
            threshold: Correlation threshold (pairs below this are considered uncorrelated)

        Returns:
            List of (pair1, pair2, correlation) tuples
        """
        pairs = []

        for i in range(len(correlation_matrix.columns)):
            for j in range(i + 1, len(correlation_matrix.columns)):
                pair1 = correlation_matrix.columns[i]
                pair2 = correlation_matrix.columns[j]
                corr = correlation_matrix.iloc[i, j]

                if abs(corr) < threshold:
                    pairs.append((pair1, pair2, corr))

        return sorted(pairs, key=lambda x: abs(x[2]))


class DataPipeline:
    """Full data pipeline for OANDA data"""

    def __init__(self, api_token: str, account_id: str = None, output_dir: str = "oanda_data"):
        self.client = OANDAClient(api_token, account_id)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def fetch_and_save_account_data(self):
        """Fetch and save account information"""
        logger.info("Fetching account data...")

        accounts = self.client.get_accounts()
        with open(self.output_dir / "accounts.json", "w") as f:
            json.dump(accounts, f, indent=2)

        account_details = self.client.get_account_details()
        with open(self.output_dir / "account_details.json", "w") as f:
            json.dump(account_details, f, indent=2)

    def fetch_and_save_instruments(self):
        """Fetch and save available instruments"""
        logger.info("Fetching instruments...")

        instruments = self.client.get_instruments()

        # Filter major pairs
        major_pairs = [
            "EUR_USD", "GBP_USD", "USD_JPY", "USD_CAD", "AUD_USD",
            "USD_CHF", "NZD_USD", "EUR_GBP", "EUR_JPY", "GBP_JPY"
        ]

        available_pairs = [
            i['name'] for i in instruments if i['name'] in major_pairs
        ]

        data = {
            "all_instruments": len(instruments),
            "major_pairs_available": available_pairs,
            "instruments_details": instruments
        }

        with open(self.output_dir / "instruments.json", "w") as f:
            json.dump(data, f, indent=2)

        return available_pairs

    def fetch_and_save_candles(self, pairs: List[str], granularities: List[str] = ["H1", "D"]):
        """Fetch and save candlestick data"""
        logger.info(f"Fetching candles for {len(pairs)} pairs...")

        all_candles = {}

        for pair in pairs:
            logger.info(f"  Fetching {pair}...")
            all_candles[pair] = {}

            for granularity in granularities:
                try:
                    candles = self.client.get_candles(pair, granularity, count=300)
                    all_candles[pair][granularity] = candles

                    # Save individual file
                    filename = self.output_dir / f"candles_{pair}_{granularity}.json"
                    with open(filename, "w") as f:
                        json.dump({"instrument": pair, "granularity": granularity, "candles": candles}, f, indent=2)
                except Exception as e:
                    logger.warning(f"    Failed to fetch {pair} {granularity}: {e}")

        # Save all candles
        with open(self.output_dir / "candles_all.json", "w") as f:
            json.dump(all_candles, f, indent=2)

    def calculate_volatility_metrics(self, pairs: List[str]):
        """Calculate volatility metrics from candle data"""
        logger.info("Calculating volatility metrics...")

        volatility_data = {}

        for pair in pairs:
            try:
                # Load candle data
                with open(self.output_dir / f"candles_{pair}_H1.json") as f:
                    data = json.load(f)
                    candles = data['candles']

                # Convert to DataFrame
                df = VolatilityAnalyzer.candles_to_dataframe(candles)

                # Calculate metrics
                volatility_data[pair] = {
                    "historical_volatility_20": df['close'].apply(
                        lambda x: x if pd.isna(x) else x
                    ),  # Placeholder
                    "sma_50": VolatilityAnalyzer.calculate_moving_average(df['close'], 50).dropna().tolist(),
                    "atr": VolatilityAnalyzer.calculate_atr(df).dropna().tolist()
                }

                logger.info(f"  ✓ Calculated metrics for {pair}")
            except Exception as e:
                logger.warning(f"  Failed to calculate metrics for {pair}: {e}")

        with open(self.output_dir / "volatility_metrics.json", "w") as f:
            # Convert to serializable format
            serializable_data = {}
            for pair, metrics in volatility_data.items():
                serializable_data[pair] = {
                    k: [float(v) for v in vs] if isinstance(vs, list) else float(vs)
                    for k, vs in metrics.items()
                }
            json.dump(serializable_data, f, indent=2)

    def calculate_correlation_matrix(self, pairs: List[str]):
        """Calculate correlation matrix between pairs"""
        logger.info("Calculating correlation matrix...")

        price_data = {}

        for pair in pairs:
            try:
                with open(self.output_dir / f"candles_{pair}_H1.json") as f:
                    data = json.load(f)
                    candles = data['candles']

                df = VolatilityAnalyzer.candles_to_dataframe(candles)
                price_data[pair] = df['close'].dropna().tolist()
            except Exception as e:
                logger.warning(f"  Failed to load data for {pair}: {e}")

        if len(price_data) > 1:
            # Calculate correlation
            df_prices = pd.DataFrame(price_data)
            correlation = df_prices.corr()

            # Find uncorrelated pairs
            best_pairs = CorrelationAnalyzer.get_best_pairs(correlation, threshold=0.7)

            result = {
                "correlation_matrix": correlation.to_dict(),
                "best_uncorrelated_pairs": [
                    {"pair1": p1, "pair2": p2, "correlation": float(corr)}
                    for p1, p2, corr in best_pairs
                ]
            }

            with open(self.output_dir / "correlation_matrix.json", "w") as f:
                json.dump(result, f, indent=2)

            logger.info(f"  Found {len(best_pairs)} uncorrelated pairs")


def main():
    """Main execution"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python oanda_integration.py <API_TOKEN> [ACCOUNT_ID]")
        sys.exit(1)

    api_token = sys.argv[1]
    account_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Create pipeline
    pipeline = DataPipeline(api_token, account_id)

    try:
        # Fetch account data
        pipeline.fetch_and_save_account_data()

        # Fetch instruments and get major pairs
        pairs = pipeline.fetch_and_save_instruments()

        # Fetch candlestick data
        if pairs:
            pipeline.fetch_and_save_candles(pairs, ["H1", "D"])

            # Calculate metrics
            pipeline.calculate_volatility_metrics(pairs)
            pipeline.calculate_correlation_matrix(pairs)

        logger.info("✅ Pipeline complete!")
        logger.info(f"Data saved to: {pipeline.output_dir}")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
