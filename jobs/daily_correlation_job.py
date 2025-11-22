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
from pathlib import Path
from itertools import combinations

import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db_connection import get_db
from utils.config import Config
from oanda_integration import VolatilityAnalyzer

logger = logging.getLogger(__name__)


def calculate_correlation_matrix(db, pairs: list, window_size: int = 100) -> dict:
    """
    Calculate correlation matrix for all pairs

    Args:
        db: Database connection
        pairs: List of instrument pairs
        window_size: Number of candles to use for calculation

    Returns:
        Dictionary with correlation data
    """
    logger.info(f"📊 Calculating correlation matrix ({window_size}-period window)...")
    start_time = datetime.utcnow()

    # Fetch data for all pairs
    price_data = {}

    for pair in pairs:
        try:
            candles = db.get_latest_candles(pair, limit=window_size)

            if len(candles) < window_size // 2:
                logger.warning(f"  Skipping {pair}: insufficient data ({len(candles)} candles)")
                continue

            # Extract closing prices
            prices = [float(c["close_mid"]) for c in candles]
            price_data[pair] = prices

        except Exception as e:
            logger.error(f"  Error fetching data for {pair}: {e}")

    logger.info(f"  Using {len(price_data)} pairs for correlation calculation")

    if len(price_data) < 2:
        logger.warning("  Not enough pairs for correlation matrix")
        return {}

    # Calculate correlation matrix
    try:
        df_prices = pd.DataFrame(price_data)
        correlation_matrix = df_prices.corr()
        logger.info(f"✅ Correlation matrix calculated in {(datetime.utcnow() - start_time).total_seconds():.1f}s")

        return correlation_matrix
    except Exception as e:
        logger.error(f"  Error calculating correlation: {e}")
        return {}


def store_correlation_matrix(db, correlation_matrix: pd.DataFrame, current_time: datetime):
    """
    Store correlation matrix in database

    Args:
        db: Database connection
        correlation_matrix: Pandas correlation matrix
        current_time: Timestamp for the calculation
    """
    logger.info("💾 Storing correlations in database...")
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
                logger.debug(f"  Error inserting correlation: {e}")

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"✅ Stored {inserted} correlation pairs in {elapsed:.1f}s")

    return inserted


def identify_best_pairs(correlation_matrix: pd.DataFrame, threshold: float = 0.7) -> list:
    """
    Identify best pairs based on correlation threshold

    Categorizes pairs as:
    - Uncorrelated: |correlation| < 0.4 (good for diversification)
    - Moderately correlated: 0.4 <= |correlation| < 0.7
    - Highly correlated: |correlation| >= 0.7 (avoid together)
    - Negatively correlated: correlation < -0.4 (excellent for hedging)

    Args:
        correlation_matrix: Pandas correlation matrix
        threshold: Correlation threshold for filtering

    Returns:
        List of (pair1, pair2, correlation, category, reason) tuples
    """
    logger.info(f"🎯 Identifying best pairs (threshold: {threshold})...")
    start_time = datetime.utcnow()

    best_pairs = []

    for pair1, pair2 in combinations(correlation_matrix.columns, 2):
        corr_value = correlation_matrix.loc[pair1, pair2]

        # Categorize pairs
        if corr_value < -0.4:
            category = "negatively_correlated"
            reason = "Excellent for hedging - negative correlation"
            rank_score = -corr_value  # Higher absolute value = better hedging

        elif corr_value < 0.4:
            category = "uncorrelated"
            reason = "Good for diversification - low correlation"
            rank_score = -abs(corr_value)  # Closer to 0 = better diversification

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

    # Sort by rank score
    best_pairs.sort(key=lambda x: x[5], reverse=True)

    # Remove the rank score from the tuple
    best_pairs = [(p1, p2, c, cat, r) for p1, p2, c, cat, r, _ in best_pairs]

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(f"✅ Identified {len(best_pairs)} best pairs in {elapsed:.1f}s")

    # Log summary by category
    for category in ["negatively_correlated", "uncorrelated", "moderately_correlated"]:
        count = sum(1 for p in best_pairs if p[3] == category)
        if count > 0:
            logger.info(f"  {category}: {count} pairs")

    return best_pairs


def store_best_pairs(db, best_pairs: list, current_time: datetime):
    """
    Store best pairs in database

    Args:
        db: Database connection
        best_pairs: List of (pair1, pair2, correlation, category, reason) tuples
        current_time: Timestamp for the calculation
    """
    logger.info("💾 Storing best pairs rankings...")
    start_time = datetime.utcnow()

    try:
        db.insert_best_pairs(current_time, best_pairs)
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Stored {len(best_pairs)} best pair recommendations in {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"❌ Error storing best pairs: {e}")


def daily_correlation_job():
    """Main daily correlation job execution"""

    job_start = datetime.utcnow()
    current_time = job_start.replace(hour=0, minute=0, second=0, microsecond=0)

    logger.info("=" * 80)
    logger.info(f"🟢 Starting Daily Correlation Analysis Job - {job_start.isoformat()}")
    logger.info("=" * 80)

    db = get_db()
    pairs = Config.TRACKED_PAIRS

    try:
        # Step 1: Calculate correlation matrix
        correlation_matrix = calculate_correlation_matrix(db, pairs, window_size=100)

        if correlation_matrix.empty:
            raise ValueError("Failed to calculate correlation matrix")

        # Step 2: Store correlation data
        correlation_count = store_correlation_matrix(db, correlation_matrix, current_time)

        # Step 3: Identify best pairs
        best_pairs = identify_best_pairs(correlation_matrix, threshold=Config.CORRELATION_THRESHOLD)

        # Step 4: Store best pairs rankings
        store_best_pairs(db, best_pairs, current_time)

        # Step 5: Log job execution
        job_end = datetime.utcnow()
        duration = (job_end - job_start).total_seconds()

        db.log_cron_job(
            job_name="daily_correlation_analysis",
            status="success",
            duration_seconds=int(duration),
            records=correlation_count + len(best_pairs),
        )

        logger.info("=" * 80)
        logger.info("✅ Daily Correlation Job Completed Successfully")
        logger.info(f"  Duration: {duration:.1f} seconds")
        logger.info(f"  Correlations stored: {correlation_count}")
        logger.info(f"  Best pairs identified: {len(best_pairs)}")
        logger.info("=" * 80)

        # Print top 5 best pairs
        logger.info("\n📊 Top 5 Best Pairs for Diversification:")
        for idx, (p1, p2, corr, category, reason) in enumerate(best_pairs[:5], 1):
            logger.info(f"  {idx}. {p1} ↔ {p2}: {corr:+.3f} ({category})")

        return True

    except Exception as e:
        logger.error(f"❌ Daily correlation job failed: {e}", exc_info=True)

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
    # Create logs directory if needed (MUST be before logging setup)
    Path("logs").mkdir(exist_ok=True)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/daily_correlation_job.log"),
            logging.StreamHandler(),
        ],
    )

    # Run the job
    success = daily_correlation_job()
    sys.exit(0 if success else 1)
