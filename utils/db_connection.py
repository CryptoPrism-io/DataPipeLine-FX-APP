"""PostgreSQL Database Connection Manager"""

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from contextlib import contextmanager
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """PostgreSQL connection manager with connection pooling"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
    ):
        """
        Initialize database connection

        Args:
            host: PostgreSQL host (default: localhost)
            port: PostgreSQL port (default: 5432)
            database: Database name (default: fx_trading_data)
            user: Database user (default: postgres)
            password: Database password (default: empty)
        """
        self.host = host or os.getenv("DB_HOST", "localhost")
        self.port = port or int(os.getenv("DB_PORT", "5432"))
        self.database = database or os.getenv("DB_NAME", "fx_trading_data")
        self.user = user or os.getenv("DB_USER", "postgres")
        self.password = password or os.getenv("DB_PASSWORD", "")

        self.conn = None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            logger.info(f"✅ Connected to PostgreSQL: {self.user}@{self.host}:{self.port}/{self.database}")
            return self.conn
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("✅ Database connection closed")

    @contextmanager
    def cursor(self, dict_cursor=False):
        """Context manager for database cursor"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"❌ Database error: {e}")
            raise
        finally:
            cursor.close()

    def insert_candle(self, instrument: str, candle_data: dict, asset_class: str = None):
        """Insert OHLC candle into database (asset-class aware, with fallback for legacy schema)"""
        asset_cls = asset_class or "UNKNOWN"
        complete = bool(candle_data.get("complete", True))

        params = (
            instrument,
            asset_cls,
            candle_data["time"],
            candle_data.get("granularity", "H1"),
            candle_data["bid"]["o"],
            candle_data["bid"]["h"],
            candle_data["bid"]["l"],
            candle_data["bid"]["c"],
            candle_data["ask"]["o"],
            candle_data["ask"]["h"],
            candle_data["ask"]["l"],
            candle_data["ask"]["c"],
            candle_data["mid"]["o"],
            candle_data["mid"]["h"],
            candle_data["mid"]["l"],
            candle_data["mid"]["c"],
            candle_data.get("volume", 0),
            complete,
        )

        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO oanda_candles
                    (instrument, asset_class, time, granularity,
                     open_bid, high_bid, low_bid, close_bid,
                     open_ask, high_ask, low_ask, close_ask,
                     open_mid, high_mid, low_mid, close_mid,
                     volume, complete)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instrument, time, granularity) DO UPDATE SET
                        asset_class = EXCLUDED.asset_class,
                        complete = EXCLUDED.complete,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    params,
                )
        except Exception as e:
            # Fallback for legacy schema without asset_class/complete
            if "asset_class" in str(e) or "complete" in str(e):
                with self.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO oanda_candles
                        (instrument, time, granularity, open_bid, high_bid, low_bid, close_bid,
                         open_ask, high_ask, low_ask, close_ask, open_mid, high_mid, low_mid, close_mid, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (instrument, time, granularity) DO UPDATE SET
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        params[0:16] + (params[16],),
                    )
            else:
                raise

    def insert_volatility_metric(self, instrument: str, metric_data: dict, asset_class: str = None):
        """Insert volatility metrics into database (asset-class aware, with legacy fallback)"""
        asset_cls = asset_class or "UNKNOWN"
        params = (
            instrument,
            asset_cls,
            metric_data.get("time"),
            metric_data.get("volatility_20"),
            metric_data.get("volatility_50"),
            metric_data.get("sma_15"),
            metric_data.get("sma_30"),
            metric_data.get("sma_50"),
            metric_data.get("bb_upper"),
            metric_data.get("bb_middle"),
            metric_data.get("bb_lower"),
            metric_data.get("atr"),
        )

        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO volatility_metrics
                    (instrument, asset_class, time, volatility_20, volatility_50, sma_15, sma_30, sma_50,
                     bb_upper, bb_middle, bb_lower, atr)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (instrument, time) DO UPDATE SET
                        asset_class = EXCLUDED.asset_class,
                        volatility_20 = EXCLUDED.volatility_20,
                        volatility_50 = EXCLUDED.volatility_50,
                        sma_15 = EXCLUDED.sma_15,
                        sma_30 = EXCLUDED.sma_30,
                        sma_50 = EXCLUDED.sma_50,
                        bb_upper = EXCLUDED.bb_upper,
                        bb_middle = EXCLUDED.bb_middle,
                        bb_lower = EXCLUDED.bb_lower,
                        atr = EXCLUDED.atr,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    params,
                )
        except Exception as e:
            if "asset_class" in str(e):
                with self.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO volatility_metrics
                        (instrument, time, volatility_20, volatility_50, sma_15, sma_30, sma_50,
                         bb_upper, bb_middle, bb_lower, atr)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (instrument, time) DO UPDATE SET
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (params[0], params[2], params[3], params[4], params[5], params[6], params[7], params[8], params[9], params[10], params[11]),
                    )
            else:
                raise

    def upsert_instrument(self, name: str, asset_class: str = None, display_name: str = None):
        """Register instrument with asset class (best effort; skips if table absent)"""
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO instruments (name, asset_class, display_name)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        asset_class = COALESCE(EXCLUDED.asset_class, instruments.asset_class),
                        display_name = COALESCE(EXCLUDED.display_name, instruments.display_name),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (name, asset_class, display_name),
                )
        except Exception as e:
            if "instruments" in str(e):
                logger.debug("Instruments table not present; skipping upsert")
            else:
                raise

    def insert_correlation(self, pair1: str, pair2: str, correlation: float, time: datetime):
        """Insert correlation data into database"""
        # Ensure pair1 < pair2 for consistency
        if pair1 > pair2:
            pair1, pair2 = pair2, pair1

        with self.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO correlation_matrix
                (pair1, pair2, time, correlation, window_size)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pair1, pair2, time) DO UPDATE SET
                    correlation = EXCLUDED.correlation,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (pair1, pair2, time, correlation, 100),
            )

    def insert_best_pairs(self, time: datetime, best_pairs_list: list):
        """Insert best pairs tracker data"""
        with self.cursor() as cursor:
            for rank, (pair1, pair2, corr, category, reason) in enumerate(best_pairs_list, 1):
                if pair1 > pair2:
                    pair1, pair2 = pair2, pair1

                cursor.execute(
                    """
                    INSERT INTO best_pairs_tracker
                    (time, pair1, pair2, correlation, category, reason, rank)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (pair1, pair2, time) DO UPDATE SET
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (time, pair1, pair2, corr, category, reason, rank),
                )

    def insert_real_time_price(self, instrument: str, bid: float, ask: float, mid: float):
        """Insert real-time price to audit log"""
        with self.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO real_time_prices_audit
                (instrument, bid, ask, mid, timestamp)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (instrument, bid, ask, mid),
            )

    def log_cron_job(self, job_name: str, status: str, duration_seconds: int = None, error_msg: str = None, records: int = None):
        """Log cron job execution"""
        with self.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO cron_job_log
                (job_name, start_time, end_time, status, duration_seconds, error_message, records_processed)
                VALUES (%s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s, %s, %s)
                """,
                (job_name, status, duration_seconds, error_msg, records),
            )

    def get_latest_candles(self, instrument: str, limit: int = 300) -> list:
        """Get latest candles for an instrument"""
        with self.cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT * FROM oanda_candles
                WHERE instrument = %s
                ORDER BY time DESC
                LIMIT %s
                """,
                (instrument, limit),
            )
            return list(reversed(cursor.fetchall()))

    def get_all_instruments(self) -> list:
        """Get all unique instruments in database"""
        with self.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT instrument FROM oanda_candles
                ORDER BY instrument
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_candle_count(self) -> dict:
        """Get count of candles per instrument"""
        with self.cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT instrument, COUNT(*) as count
                FROM oanda_candles
                GROUP BY instrument
                ORDER BY instrument
                """
            )
            return {row["instrument"]: row["count"] for row in cursor.fetchall()}

    def delete_old_candles(self, days: int = 365) -> int:
        """Delete candles older than specified days"""
        with self.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM oanda_candles
                WHERE time < CURRENT_TIMESTAMP - INTERVAL '%s days'
                """,
                (days,),
            )
            return cursor.rowcount

    def delete_old_prices(self, hours: int = 24) -> int:
        """Delete real-time prices older than specified hours"""
        with self.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM real_time_prices_audit
                WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '%s hours'
                """,
                (hours,),
            )
            return cursor.rowcount


# Global connection instance
_db_connection = None


def get_db() -> DatabaseConnection:
    """Get or create database connection"""
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
        _db_connection.connect()
    return _db_connection


def close_db():
    """Close global database connection"""
    global _db_connection
    if _db_connection:
        _db_connection.disconnect()
        _db_connection = None
