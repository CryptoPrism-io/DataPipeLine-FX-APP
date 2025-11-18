#!/usr/bin/env python3
"""
APScheduler Setup - Manages all background jobs

Scheduled Jobs:
1. Hourly Data Fetch (every hour at :00)
   - Fetch OHLC candles
   - Calculate volatility metrics
   - Cache results

2. Daily Correlation Analysis (daily at 00:00 UTC)
   - Calculate correlation matrix
   - Identify best pairs
   - Store rankings

Usage:
    python jobs/scheduler.py
"""

import sys
import logging
import signal
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config
from hourly_job import hourly_job
from daily_correlation_job import daily_correlation_job

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/scheduler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Create scheduler instance
scheduler = BackgroundScheduler(daemon=False)


def job_listener(event):
    """Listen to job execution events"""
    if event.exception:
        logger.error(f"❌ Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"✅ Job {event.job_id} completed successfully")


def register_jobs():
    """Register all background jobs"""

    logger.info("📋 Registering background jobs...")

    # Hourly Data Fetch Job
    if Config.HOURLY_JOB_ENABLED:
        try:
            scheduler.add_job(
                hourly_job,
                trigger=CronTrigger(hour="*", minute=0),  # Every hour at :00
                id="hourly_fetch_and_metrics",
                name="Hourly OHLC Fetch & Volatility Calculation",
                max_instances=1,  # Prevent concurrent execution
                misfire_grace_time=60,  # Allow 60s grace period
            )
            logger.info("  ✓ Hourly fetch job registered")
        except Exception as e:
            logger.error(f"  ❌ Failed to register hourly job: {e}")

    # Daily Correlation Job
    if Config.DAILY_JOB_ENABLED:
        try:
            scheduler.add_job(
                daily_correlation_job,
                trigger=CronTrigger(hour=Config.DAILY_JOB_HOUR, minute=Config.DAILY_JOB_MINUTE),  # 00:00 UTC
                id="daily_correlation_analysis",
                name="Daily Correlation Matrix & Best Pairs Analysis",
                max_instances=1,
                misfire_grace_time=300,  # Allow 5m grace period
            )
            logger.info("  ✓ Daily correlation job registered")
        except Exception as e:
            logger.error(f"  ❌ Failed to register daily job: {e}")

    # Add event listener
    scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

    logger.info("✅ All jobs registered")


def start_scheduler():
    """Start the scheduler"""

    logger.info("=" * 80)
    logger.info("🟢 Starting APScheduler")
    logger.info("=" * 80)

    try:
        register_jobs()

        scheduler.start()

        logger.info("\n✅ Scheduler started successfully")
        logger.info("\n📅 Scheduled Jobs:")
        for job in scheduler.get_jobs():
            logger.info(f"  - {job.name} ({job.id})")
            logger.info(f"    Trigger: {job.trigger}")
            logger.info(f"    Max instances: {job.max_instances}")

        logger.info("\n⏰ Next job executions:")
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                logger.info(f"  - {job.name}: {next_run.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        logger.info("\n🔄 Scheduler is running. Press Ctrl+C to stop.\n")

    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")
        raise


def stop_scheduler():
    """Stop the scheduler gracefully"""

    logger.info("\n" + "=" * 80)
    logger.info("🛑 Stopping scheduler...")
    logger.info("=" * 80)

    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("✅ Scheduler stopped")


def signal_handler(sig, frame):
    """Handle Ctrl+C signal"""
    logger.info("\nReceived shutdown signal")
    stop_scheduler()
    sys.exit(0)


if __name__ == "__main__":
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        start_scheduler()

        # Keep the scheduler running
        scheduler.print_jobs()
        import time

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        stop_scheduler()
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")
        stop_scheduler()
        sys.exit(1)
