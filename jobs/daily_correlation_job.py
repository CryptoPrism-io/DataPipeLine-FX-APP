#!/usr/bin/env python3
"""
Daily Correlation Analysis Job

Executes daily at midnight UTC (00:00) to:
1. Calculate correlation matrix for all 20 pairs
2. Identify best uncorrelated pairs (correlation < 0.7)
3. Store results in database
4. Update Redis cache
5. Log execution

Total execution time: ~25-30 seconds

Formula:
- Fetch last 100 hourly candles per pair (~4 days)
- Calculate correlation matrix (20x20)
- Rank pairs by correlation strength
- Identify best pairs for diversification
"""

import sys
import logging
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from oanda_integration import VolatilityAnalyzer  # noqa: F401 - imported for side-effects/config
from utils.config import Config
from utils.db_connection import get_db

logger = logging.getLogger(__name__)


def calculate_correlation_matrix(db, pairs: list, window_size: int = 100) -> Optional[pd.DataFrame]:
    """
    Calculate correlation matrix for all pairs.

    Returns:
        Correlation matrix as a DataFrame or None if calculation fails.
    """
    logger.info(f"Calculating correlation matrix ({window_size}-period window)...")
    start_time = datetime.utcnow()

    price_data: Dict[str, List[float]] = {}
    min_series_length: Optional[int] = None

    for pair in pairs:
        try:
            candles = db.get_latest_candles(pair, limit=window_size)

            if not candles:
                logger.warning(f"  Skipping {pair}: no candles available")
                continue

            # Require at least 2 points to compute correlation; otherwise skip.
            if len(candles) < 2:
                logger.warning(f"  Skipping {pair}: insufficient data ({len(candles)} candles)")
                continue

            prices = [float(c["close_mid"]) for c in candles if "close_mid" in c]
            if not prices:
                logger.warning(f"  Skipping {pair}: no closing prices found")
                continue

            capped_len = min(window_size, len(prices))
            price_data[pair] = prices[-capped_len:]
            min_series_length = capped_len if min_series_length is None else min(min_series_length, capped_len)

        except Exception as e:
            logger.error(f"  Error fetching data for {pair}: {e}")

    logger.info(f"  Using {len(price_data)} pairs for correlation calculation")

    if len(price_data) < 2 or not min_series_length:
        logger.warning("  Not enough pairs for correlation matrix")
        return None

    # Align all price series to the same length to avoid pandas length errors
    lengths = {len(series) for series in price_data.values()}
    if len(lengths) > 1:
        target_length = min_series_length
        for pair, series in price_data.items():
            if len(series) != target_length:
                logger.debug(f"  Aligning {pair} series from {len(series)} to {target_length} samples")
                price_data[pair] = series[-target_length:]

    try:
        df_prices = pd.DataFrame(price_data)
        correlation_matrix = df_prices.corr()

        if correlation_matrix.empty:
            logger.warning("  Correlation matrix is empty after calculation")
            return None

        logger.info(f"Correlation matrix calculated in {(datetime.utcnow() - start_time).total_seconds():.1f}s")
        return correlation_matrix
    except Exception as e:
        logger.error(f"  Error calculating correlation: {e}")
        return None


def store_correlation_matrix(db, correlation_matrix: pd.DataFrame, current_time: datetime) -> int:
    """
    Store correlation matrix in database.

    Args:
        db: Database connection
        correlation_matrix: Pandas correlation matrix
        current_time: Timestamp for the calculation
    """
    logger.info("Storing correlations in database...")
    start_time = datetime.utcnow()

    inserted = 0
    for pair1 in correlation_matrix.columns:
        for pair2 in correlation_matrix.columns:
            if pair1 >= pair2:  # Avoid duplicates and self-correlation
                continue

            corr_value = correlation_matrix.loc[pair1, pair2]

            try:
                db.insert_correlation(pair1, pair2, float(corr_value), current_time)
                inserted += 1
            except Exception as e:
                logger.debug(f"  Error inserting correlation for {pair1}-{pair2}: {e}")

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"Stored {inserted} correlation pairs in {elapsed:.1f}s")

    return inserted


def identify_best_pairs(correlation_matrix: pd.DataFrame, threshold: float = 0.7) -> list:
    """
    Identify best pairs based on correlation threshold.

    Categorizes pairs as:
    - Uncorrelated: |correlation| < 0.4 (good for diversification)
    - Moderately correlated: 0.4 <= |correlation| < 0.7
    - Highly correlated: |correlation| >= 0.7 (avoid together)
    - Negatively correlated: correlation < -0.4 (excellent for hedging)
    """
    logger.info(f"Identifying best pairs (threshold: {threshold})...")
    start_time = datetime.utcnow()

    best_pairs = []

    for pair1, pair2 in combinations(correlation_matrix.columns, 2):
        corr_value = correlation_matrix.loc[pair1, pair2]

        if corr_value < -0.4:
            category = "negatively_correlated"
            reason = "Excellent for hedging - negative correlation"
            rank_score = -corr_value
        elif corr_value < 0.4:
            category = "uncorrelated"
            reason = "Good for diversification - low correlation"
            rank_score = -abs(corr_value)
        elif corr_value < threshold:
            category = "moderately_correlated"
            reason = f"Moderate correlation: {corr_value:.3f}"
            rank_score = -corr_value
        else:
            category = "highly_correlated"
            reason = f"High correlation: {corr_value:.3f} - avoid together"
            rank_score = corr_value
            continue  # Skip highly correlated pairs

        best_pairs.append((pair1, pair2, float(corr_value), category, reason, rank_score))

    best_pairs.sort(key=lambda x: x[5], reverse=True)
    best_pairs = [(p1, p2, c, cat, r) for p1, p2, c, cat, r, _ in best_pairs]

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"Identified {len(best_pairs)} best pairs in {elapsed:.1f}s")

    for category in ["negatively_correlated", "uncorrelated", "moderately_correlated"]:
        count = sum(1 for p in best_pairs if p[3] == category)
        if count > 0:
            logger.info(f"  {category}: {count} pairs")

    return best_pairs


def store_best_pairs(db, best_pairs: list, current_time: datetime) -> None:
    """Store best pairs in database."""
    logger.info("Storing best pairs rankings...")
    start_time = datetime.utcnow()

    try:
        db.insert_best_pairs(current_time, best_pairs)
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Stored {len(best_pairs)} best pair recommendations in {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"Error storing best pairs: {e}")


def daily_correlation_job() -> bool:
    """Main daily correlation job execution."""

    job_start = datetime.utcnow()
    current_time = job_start.replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info("=" * 80)
    logger.info(f"Starting Daily Correlation Analysis Job - {job_start.isoformat()}")
    logger.info("=" * 80)

    db = get_db()
    pairs = Config.TRACKED_PAIRS

    try:
        correlation_matrix = calculate_correlation_matrix(db, pairs, window_size=Config.CORRELATION_WINDOW_SIZE)

        if correlation_matrix is None or correlation_matrix.empty:
            raise ValueError("Failed to calculate correlation matrix")

        correlation_count = store_correlation_matrix(db, correlation_matrix, current_time)
        best_pairs = identify_best_pairs(correlation_matrix, threshold=Config.CORRELATION_THRESHOLD)
        store_best_pairs(db, best_pairs, current_time)

        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()

        db.log_cron_job(
            job_name="daily_correlation_analysis",
            status="success",
            duration_seconds=int(duration),
            records=correlation_count + len(best_pairs),
        )

        logger.info("=" * 80)
        logger.info("Daily Correlation Job Completed Successfully")
        logger.info(f"  Duration: {duration:.1f} seconds")
        logger.info(f"  Correlations stored: {correlation_count}")
        logger.info(f"  Best pairs identified: {len(best_pairs)}")
        logger.info("=" * 80)

        logger.info("\nTop 5 Best Pairs for Diversification:")
        for idx, (p1, p2, corr, category, reason) in enumerate(best_pairs[:5], 1):
            logger.info(f"  {idx}. {p1} vs {p2}: {corr:+.3f} ({category}) - {reason}")

        return True

    except Exception as e:
        logger.error(f"Daily correlation job failed: {e}", exc_info=True)

        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()

        db.log_cron_job(
            job_name="daily_correlation_analysis",
            status="failed",
            duration_seconds=int(duration),
            error_msg=str(e),
        )

        return False


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/daily_correlation_job.log"),
            logging.StreamHandler(),
        ],
    )

    success = daily_correlation_job()
    sys.exit(0 if success else 1)
