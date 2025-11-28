#!/usr/bin/env python3
"""
Backfill 1000 Hours of OHLC Data from OANDA

Fetches 1000 hours (~42 days) of hourly OHLC data for all 20 tracked pairs.
This provides enough data for meaningful correlation analysis.

Usage:
    python backfill_1000_hours.py
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from oanda_integration import OANDAClient, VolatilityAnalyzer
from utils.db_connection import get_db
from utils.config import Config

# Create logs directory first
Path("logs").mkdir(exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/backfill_1000h.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def backfill_1000_hours(hours: int = 1000):
    """Backfill N hours of OHLC data for all tracked pairs"""

    logger.info("=" * 80)
    logger.info("🟢 Starting OHLC Data Backfill")
    logger.info("=" * 80)
    logger.info(f"Start time: {datetime.utcnow().isoformat()}")
    logger.info(f"Pairs to fetch: {len(Config.TRACKED_PAIRS)}")
    approx_days = hours / 24.0
    logger.info(f"Candles per pair: {hours} (~{approx_days:.1f} days)")
    logger.info("=" * 80)

    db = get_db()
    client = OANDAClient(
        api_token=Config.OANDA_API_KEY,
        use_demo=(Config.OANDA_ENVIRONMENT == "demo")
    )

    pairs = Config.TRACKED_PAIRS
    total_candles = 0
    total_inserted = 0
    failed_pairs = []

    for idx, pair in enumerate(pairs, 1):
        logger.info(f"\n[{idx}/{len(pairs)}] Processing {pair}...")

        try:
            # Fetch configurable hourly candles
            logger.info(f"  Fetching {hours} hourly candles...")
            candles = client.get_candles(
                instrument=pair,
                granularity="H1",
                count=hours,
                price="MBA"
            )

            if not candles:
                logger.warning(f"  ⚠️  No data returned for {pair}")
                failed_pairs.append(pair)
                continue

            total_candles += len(candles)
            logger.info(f"  ✅ Fetched {len(candles)} candles")

            # Insert into database
            logger.info(f"  💾 Inserting into database...")
            inserted_count = 0

            for candle in candles:
                try:
                    db.insert_candle(pair, candle)
                    inserted_count += 1
                except Exception as e:
                    # Skip duplicate entries (already exist)
                    if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                        continue
                    logger.debug(f"    Skip: {e}")

            logger.info(f"  ✅ Inserted {inserted_count} new candles for {pair}")
            total_inserted += inserted_count

        except Exception as e:
            logger.error(f"  ❌ Error processing {pair}: {e}")
            failed_pairs.append(pair)
            continue

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 Backfill Summary")
    logger.info("=" * 80)
    logger.info(f"Total candles fetched: {total_candles:,}")
    logger.info(f"Total candles inserted: {total_inserted:,}")
    logger.info(f"Pairs successful: {len(pairs) - len(failed_pairs)}/{len(pairs)}")

    if failed_pairs:
        logger.warning(f"Failed pairs: {', '.join(failed_pairs)}")

    # Show database stats
    logger.info("\n📈 Database Record Counts:")
    try:
        with db.cursor() as cur:
            # Total candles
            cur.execute("SELECT COUNT(*) FROM oanda_candles")
            total_db_candles = cur.fetchone()[0]
            logger.info(f"  Total OHLC candles: {total_db_candles:,}")

            # Candles per pair
            cur.execute("""
                SELECT instrument, COUNT(*) as count
                FROM oanda_candles
                GROUP BY instrument
                ORDER BY instrument
            """)
            logger.info("\n  Candles per pair:")
            for row in cur.fetchall():
                logger.info(f"    {row[0]}: {row[1]:,} candles")

            # Date range
            cur.execute("""
                SELECT
                    MIN(time) as earliest,
                    MAX(time) as latest
                FROM oanda_candles
            """)
            earliest, latest = cur.fetchone()
            if earliest and latest:
                logger.info(f"\n  Date range: {earliest} to {latest}")

    except Exception as e:
        logger.warning(f"Could not fetch database stats: {e}")

    logger.info("\n" + "=" * 80)
    logger.info("✅ Backfill complete!")
    logger.info("=" * 80)
    logger.info("\nNext steps:")
    logger.info("1. Run correlation analysis: python jobs/daily_correlation_job.py")
    logger.info("2. Or wait for tonight's automated correlation job (midnight UTC)")
    logger.info("3. Check API: curl http://localhost:5000/api/v1/correlation/matrix")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill OHLC candles for tracked pairs")
    parser.add_argument("--hours", type=int, default=1000, help="Number of hours to backfill (per pair)")
    parser.add_argument("--days", type=int, default=None, help="Number of days to backfill (overrides hours)")
    args = parser.parse_args()

    target_hours = args.hours
    if args.days is not None:
        target_hours = args.days * 24

    try:
        backfill_1000_hours(hours=target_hours)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Backfill interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        sys.exit(1)
