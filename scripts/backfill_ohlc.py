#!/usr/bin/env python3
"""
Backfill OHLC Data from OANDA

Fetches 1 year of hourly OHLC data for top 20 pairs and stores in PostgreSQL.
Run this once to populate historical data.

Usage:
    python scripts/backfill_ohlc.py
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/backfill.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def backfill_ohlc_data():
    """Backfill 1 year of OHLC data for all tracked pairs"""

    logger.info("=" * 80)
    logger.info("🟢 Starting OHLC Data Backfill")
    logger.info("=" * 80)

    db = get_db()
    client = OANDAClient(api_token=Config.OANDA_API_KEY, use_demo=(Config.OANDA_ENVIRONMENT == "demo"))

    pairs = Config.TRACKED_PAIRS
    total_records = 0
    failed_pairs = []

    for idx, pair in enumerate(pairs, 1):
        logger.info(f"\n[{idx}/{len(pairs)}] Fetching {pair}...")

        try:
            # Fetch last year of hourly candles (365 days × 24 hours = 8760 hours)
            # OANDA returns max 5000 candles per request, so we need to be smart
            # For hourly data: 5000 candles = ~208 days

            # Fetch in chunks: 200 days at a time
            days_chunks = [200, 165]  # Total 365 days
            all_candles = []

            for chunk_idx, days in enumerate(days_chunks):
                logger.info(f"  Fetching chunk {chunk_idx + 1}: last {days} days...")

                # Calculate from_date
                to_date = datetime.utcnow()
                if chunk_idx > 0:
                    # Subtract already fetched days
                    to_date = to_date - timedelta(days=sum(days_chunks[:chunk_idx]))

                from_date = to_date - timedelta(days=days)

                logger.info(f"    Date range: {from_date.date()} to {to_date.date()}")

                # Fetch candles for this period
                # Note: OANDA API doesn't have date range params, so we fetch by count
                # 200 days × 24 hours = 4800 candles (fits in 5000 limit)
                candles = client.get_candles(
                    instrument=pair,
                    granularity="H1",
                    count=min(4800, days * 24),
                    price="MBA",
                )

                if candles:
                    all_candles.extend(candles)
                    logger.info(f"    ✓ Fetched {len(candles)} candles")
                else:
                    logger.warning(f"    ⚠ No candles returned for {pair}")

                # Limit to 1-year of unique data
                if len(all_candles) > 8760:
                    all_candles = all_candles[-8760:]

            if not all_candles:
                logger.warning(f"  ❌ No data fetched for {pair}")
                failed_pairs.append(pair)
                continue

            # Sort by time (oldest first)
            all_candles.sort(key=lambda x: x["time"])

            # Insert into database
            logger.info(f"  Inserting {len(all_candles)} candles into database...")

            inserted_count = 0
            for candle in all_candles:
                try:
                    db.insert_candle(pair, candle)
                    inserted_count += 1
                except Exception as e:
                    logger.warning(f"    Failed to insert candle: {e}")

            logger.info(f"  ✅ Inserted {inserted_count} candles for {pair}")
            total_records += inserted_count

        except Exception as e:
            logger.error(f"  ❌ Error processing {pair}: {e}")
            failed_pairs.append(pair)
            continue

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 Backfill Summary")
    logger.info("=" * 80)
    logger.info(f"Total records inserted: {total_records:,}")
    logger.info(f"Pairs successful: {len(pairs) - len(failed_pairs)}/{len(pairs)}")

    if failed_pairs:
        logger.warning(f"Failed pairs: {', '.join(failed_pairs)}")

    # Show record count by pair
    logger.info("\n📈 Records per pair:")
    counts = db.get_candle_count()
    for pair in sorted(Config.TRACKED_PAIRS):
        count = counts.get(pair, 0)
        logger.info(f"  {pair}: {count:,} records")

    logger.info("\n✅ OHLC backfill complete!")


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    Path("logs").mkdir(exist_ok=True)

    try:
        backfill_ohlc_data()
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        sys.exit(1)
