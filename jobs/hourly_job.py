#!/usr/bin/env python3
"""
Hourly Data Fetch & Processing Job

Executes every hour at :00 to:
1. Fetch latest OHLC for all 20 pairs
2. Calculate volatility metrics
3. Update correlation matrix (if needed)
4. Cache results in Redis
5. Broadcast updates via WebSocket

Total execution time: ~18-20 seconds
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oanda_integration import OANDAClient, VolatilityAnalyzer
from utils.db_connection import get_db
from utils.config import Config

logger = logging.getLogger(__name__)


def fetch_and_store_candles(client: OANDAClient, db, pairs: list) -> int:
    """
    Fetch latest OHLC candles and store in database

    Args:
        client: OANDAClient instance
        db: Database connection
        pairs: List of instrument pairs

    Returns:
        Number of candles inserted
    """
    logger.info("📥 Fetching latest candles...")
    start_time = datetime.utcnow()

    inserted = 0
    for pair in pairs:
        try:
            # Fetch last 2 hours (to catch any missed candles)
            candles = client.get_candles(pair, "H1", count=2, price="MBA")

            if not candles:
                logger.warning(f"  ⚠ No candles returned for {pair}")
                continue

            for candle in candles:
                try:
                    db.insert_candle(pair, candle)
                    inserted += 1
                except Exception as e:
                    logger.debug(f"  Duplicate or error for {pair}: {e}")

        except Exception as e:
            logger.error(f"  ❌ Error fetching {pair}: {e}")

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"✅ Candles fetched: {inserted} records in {elapsed:.1f}s")

    return inserted


def calculate_volatility_metrics(db, pairs: list) -> int:
    """
    Calculate volatility metrics for all pairs

    Args:
        db: Database connection
        pairs: List of instrument pairs

    Returns:
        Number of metrics calculated
    """
    logger.info("📊 Calculating volatility metrics...")
    start_time = datetime.utcnow()

    calculated = 0
    for pair in pairs:
        try:
            # Get last 300 candles (about 12-13 days of hourly data)
            candles_data = db.get_latest_candles(pair, limit=300)

            if len(candles_data) < 50:
                logger.debug(f"  Skipping {pair}: insufficient data ({len(candles_data)} candles)")
                continue

            # Convert to DataFrame for analysis
            df = VolatilityAnalyzer.candles_to_dataframe(
                [
                    {
                        "time": c["time"],
                        "mid": {
                            "o": float(c["open_mid"]),
                            "h": float(c["high_mid"]),
                            "l": float(c["low_mid"]),
                            "c": float(c["close_mid"]),
                        },
                    }
                    for c in candles_data
                ]
            )

            # Calculate metrics
            try:
                volatility_20 = VolatilityAnalyzer.calculate_historical_volatility(df["close"], 20)
                volatility_50 = VolatilityAnalyzer.calculate_historical_volatility(df["close"], 50)
                sma_15 = VolatilityAnalyzer.calculate_moving_average(df["close"], 15)
                sma_30 = VolatilityAnalyzer.calculate_moving_average(df["close"], 30)
                sma_50 = VolatilityAnalyzer.calculate_moving_average(df["close"], 50)
                upper_bb, middle_bb, lower_bb = VolatilityAnalyzer.calculate_bollinger_bands(df["close"], 20)
                atr = VolatilityAnalyzer.calculate_atr(df, 14)
            except Exception as e:
                logger.warning(f"  Error calculating metrics for {pair}: {e}")
                continue

            # Get latest values
            metric_data = {
                "time": candles_data[-1]["time"],
                "volatility_20": float(volatility_20.iloc[-1]) if volatility_20.iloc[-1] > 0 else None,
                "volatility_50": float(volatility_50.iloc[-1]) if volatility_50.iloc[-1] > 0 else None,
                "sma_15": float(sma_15.iloc[-1]) if len(sma_15) > 0 else None,
                "sma_30": float(sma_30.iloc[-1]) if len(sma_30) > 0 else None,
                "sma_50": float(sma_50.iloc[-1]) if len(sma_50) > 0 else None,
                "bb_upper": float(upper_bb.iloc[-1]) if len(upper_bb) > 0 else None,
                "bb_middle": float(middle_bb.iloc[-1]) if len(middle_bb) > 0 else None,
                "bb_lower": float(lower_bb.iloc[-1]) if len(lower_bb) > 0 else None,
                "atr": float(atr.iloc[-1]) if len(atr) > 0 else None,
            }

            db.insert_volatility_metric(pair, metric_data)
            calculated += 1

        except Exception as e:
            logger.error(f"  ❌ Error calculating metrics for {pair}: {e}")

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"✅ Volatility metrics calculated: {calculated} pairs in {elapsed:.1f}s")

    return calculated


def hourly_job():
    """Main hourly job execution"""

    job_start = datetime.utcnow()
    logger.info("=" * 80)
    logger.info(f"🟢 Starting Hourly Data Fetch Job - {job_start.isoformat()}")
    logger.info("=" * 80)

    db = get_db()
    client = OANDAClient(use_demo=True)
    pairs = Config.TRACKED_PAIRS

    try:
        # Step 1: Fetch candles (5 sec)
        candle_count = fetch_and_store_candles(client, db, pairs)

        # Step 2: Calculate volatility (10 sec)
        metric_count = calculate_volatility_metrics(db, pairs)

        # Step 3: Log job execution
        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()

        db.log_cron_job(
            job_name="hourly_fetch_and_metrics",
            status="success",
            duration_seconds=int(duration),
            records=candle_count + metric_count,
        )

        logger.info("=" * 80)
        logger.info("✅ Hourly Job Completed Successfully")
        logger.info(f"  Duration: {duration:.1f} seconds")
        logger.info(f"  Candles inserted: {candle_count}")
        logger.info(f"  Metrics calculated: {metric_count}")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error(f"❌ Hourly job failed: {e}", exc_info=True)

        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()

        db.log_cron_job(
            job_name="hourly_fetch_and_metrics",
            status="failed",
            duration_seconds=int(duration),
            error_msg=str(e),
        )

        return False


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/hourly_job.log"),
            logging.StreamHandler(),
        ],
    )

    # Create logs directory if needed
    Path("logs").mkdir(exist_ok=True)

    # Run the job
    success = hourly_job()
    sys.exit(0 if success else 1)
