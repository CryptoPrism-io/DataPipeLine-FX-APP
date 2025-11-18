#!/usr/bin/env python3
"""
REST API Server for FX Data Pipeline

Provides endpoints for:
- Current prices and quotes
- Historical OHLC data
- Volatility metrics
- Correlation analysis
- Best pairs recommendations
- Market session information
- Cache health checks

Usage:
    python api/app.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from flask import Flask, jsonify, request
from flask_cors import CORS

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config
from cache.cache_manager import CacheManager
from cache.redis_client import get_redis
from utils.db_connection import DatabaseConnection

# Setup logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Initialize managers
cache_manager = CacheManager()
db = DatabaseConnection()

# ========== HEALTH & INFO ENDPOINTS ==========


@app.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint

    Returns:
        200: Service is healthy
        503: Service is unhealthy
    """
    try:
        # Check Redis connection
        redis_client = get_redis()
        redis_info = redis_client.info()

        # Check Database connection
        if not db.conn:
            db.connect()

        return jsonify(
            {
                "status": "healthy",
                "timestamp": datetime.utcnow().isoformat(),
                "services": {
                    "redis": "connected" if redis_info else "disconnected",
                    "database": "connected",
                    "api": "running",
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@app.route("/api/v1/info", methods=["GET"])
def api_info():
    """Get API information and configuration"""
    try:
        return jsonify(
            {
                "api_version": "1.0.0",
                "service": "FX Data Pipeline REST API",
                "tracked_pairs": Config.TRACKED_PAIRS,
                "pair_count": len(Config.TRACKED_PAIRS),
                "cache_ttls": {
                    "prices": f"{Config.CACHE_TTL_PRICES}s",
                    "metrics": f"{Config.CACHE_TTL_METRICS}s",
                    "correlation": f"{Config.CACHE_TTL_CORRELATION}s",
                },
                "data_retention": f"{Config.DATA_RETENTION_DAYS}d",
                "endpoints": {
                    "health": "/health",
                    "info": "/api/v1/info",
                    "prices": {
                        "current": "/api/v1/prices/current",
                        "all": "/api/v1/prices/all",
                    },
                    "candles": "/api/v1/candles/{instrument}",
                    "metrics": {
                        "volatility": "/api/v1/metrics/volatility",
                        "volatility_single": "/api/v1/metrics/volatility/{instrument}",
                    },
                    "correlation": {
                        "matrix": "/api/v1/correlation/matrix",
                        "pairs": "/api/v1/correlation/pairs",
                    },
                    "best_pairs": "/api/v1/best-pairs",
                    "sessions": "/api/v1/sessions",
                    "cache_stats": "/api/v1/cache/stats",
                },
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting API info: {e}")
        return jsonify({"error": str(e)}), 500


# ========== PRICE ENDPOINTS ==========


@app.route("/api/v1/prices/current", methods=["GET"])
def get_current_price():
    """
    Get current price for a specific instrument

    Query Parameters:
        instrument: Instrument name (e.g., EUR_USD) - REQUIRED

    Returns:
        200: Price data
        400: Missing instrument parameter
        404: Price not found in cache
        500: Server error
    """
    try:
        instrument = request.args.get("instrument", "").upper()

        if not instrument:
            return jsonify({"error": "Missing 'instrument' parameter"}), 400

        if instrument not in Config.TRACKED_PAIRS:
            return jsonify(
                {"error": f"Instrument {instrument} not in tracked pairs"}
            ), 400

        price = cache_manager.get_price(instrument)

        if not price:
            return (
                jsonify(
                    {
                        "error": f"No cached price for {instrument}",
                        "message": "Run cron job first to populate prices",
                    }
                ),
                404,
            )

        return jsonify({"instrument": instrument, "price": price}), 200

    except Exception as e:
        logger.error(f"❌ Error getting current price: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/prices/all", methods=["GET"])
def get_all_prices():
    """
    Get all cached prices for tracked pairs

    Returns:
        200: Dictionary of all prices
        500: Server error
    """
    try:
        prices = cache_manager.get_all_prices()

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "pair_count": len(prices),
                "prices": prices,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting all prices: {e}")
        return jsonify({"error": str(e)}), 500


# ========== HISTORICAL DATA ENDPOINTS ==========


@app.route("/api/v1/candles/<instrument>", methods=["GET"])
def get_historical_candles(instrument: str):
    """
    Get historical OHLC candles for an instrument

    Path Parameters:
        instrument: Instrument name (e.g., EUR_USD)

    Query Parameters:
        limit: Number of candles to return (default: 24, max: 500)
        granularity: Granularity filter (H1, D, etc.) (default: H1)
        start_time: Filter candles after this ISO timestamp (optional)
        end_time: Filter candles before this ISO timestamp (optional)

    Returns:
        200: List of candles
        400: Invalid parameters
        404: No data found
        500: Server error
    """
    try:
        instrument = instrument.upper()

        if instrument not in Config.TRACKED_PAIRS:
            return jsonify(
                {"error": f"Instrument {instrument} not in tracked pairs"}
            ), 400

        # Get query parameters
        limit = min(int(request.args.get("limit", 24)), 500)
        granularity = request.args.get("granularity", "H1").upper()
        start_time = request.args.get("start_time")
        end_time = request.args.get("end_time")

        if not db.conn:
            db.connect()

        with db.cursor(dict_cursor=True) as cursor:
            # Build query
            query = """
                SELECT instrument, time, granularity,
                       open_bid, high_bid, low_bid, close_bid,
                       open_ask, high_ask, low_ask, close_ask,
                       open_mid, high_mid, low_mid, close_mid,
                       volume, created_at
                FROM oanda_candles
                WHERE instrument = %s AND granularity = %s
            """
            params = [instrument, granularity]

            if start_time:
                query += " AND time >= %s"
                params.append(start_time)

            if end_time:
                query += " AND time <= %s"
                params.append(end_time)

            query += " ORDER BY time DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

        if not rows:
            return (
                jsonify(
                    {
                        "error": f"No candles found for {instrument}",
                        "message": "Run backfill script to populate historical data",
                    }
                ),
                404,
            )

        # Convert rows to list of dicts with proper formatting
        candles = []
        for row in reversed(rows):  # Reverse to get chronological order
            candles.append(
                {
                    "time": row["time"],
                    "granularity": row["granularity"],
                    "bid": {
                        "o": float(row["open_bid"]),
                        "h": float(row["high_bid"]),
                        "l": float(row["low_bid"]),
                        "c": float(row["close_bid"]),
                    },
                    "ask": {
                        "o": float(row["open_ask"]),
                        "h": float(row["high_ask"]),
                        "l": float(row["low_ask"]),
                        "c": float(row["close_ask"]),
                    },
                    "mid": {
                        "o": float(row["open_mid"]),
                        "h": float(row["high_mid"]),
                        "l": float(row["low_mid"]),
                        "c": float(row["close_mid"]),
                    },
                    "volume": row["volume"],
                }
            )

        return jsonify(
            {
                "instrument": instrument,
                "granularity": granularity,
                "count": len(candles),
                "candles": candles,
            }
        ), 200

    except ValueError as e:
        logger.warning(f"⚠️ Invalid parameter: {e}")
        return jsonify({"error": f"Invalid parameter: {e}"}), 400
    except Exception as e:
        logger.error(f"❌ Error getting candles: {e}")
        return jsonify({"error": str(e)}), 500


# ========== VOLATILITY METRICS ENDPOINTS ==========


@app.route("/api/v1/metrics/volatility", methods=["GET"])
def get_all_volatility_metrics():
    """
    Get volatility metrics for all tracked pairs

    Returns:
        200: Dictionary of volatility metrics
        500: Server error
    """
    try:
        metrics = cache_manager.get_all_volatility_metrics()

        if not metrics:
            return (
                jsonify(
                    {
                        "error": "No volatility metrics in cache",
                        "message": "Run hourly cron job first",
                    }
                ),
                404,
            )

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "pair_count": len(metrics),
                "metrics": metrics,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting volatility metrics: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/metrics/volatility/<instrument>", methods=["GET"])
def get_volatility_metrics(instrument: str):
    """
    Get volatility metrics for a specific instrument

    Path Parameters:
        instrument: Instrument name (e.g., EUR_USD)

    Returns:
        200: Volatility metrics
        400: Invalid instrument
        404: Metrics not found
        500: Server error
    """
    try:
        instrument = instrument.upper()

        if instrument not in Config.TRACKED_PAIRS:
            return jsonify(
                {"error": f"Instrument {instrument} not in tracked pairs"}
            ), 400

        metrics = cache_manager.get_volatility_metrics(instrument)

        if not metrics:
            return (
                jsonify(
                    {
                        "error": f"No metrics for {instrument}",
                        "message": "Run hourly cron job first",
                    }
                ),
                404,
            )

        return jsonify(
            {"instrument": instrument, "metrics": metrics}
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting volatility metrics: {e}")
        return jsonify({"error": str(e)}), 500


# ========== CORRELATION ENDPOINTS ==========


@app.route("/api/v1/correlation/matrix", methods=["GET"])
def get_correlation_matrix():
    """
    Get the correlation matrix for all tracked pairs

    Returns:
        200: Correlation matrix
        404: Matrix not found
        500: Server error
    """
    try:
        matrix = cache_manager.get_correlation_matrix()

        if not matrix:
            return (
                jsonify(
                    {
                        "error": "No correlation matrix in cache",
                        "message": "Run daily cron job first",
                    }
                ),
                404,
            )

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "pair_count": len(Config.TRACKED_PAIRS),
                "matrix": matrix,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting correlation matrix: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/v1/correlation/pairs", methods=["GET"])
def get_pair_correlation():
    """
    Get correlation between two specific pairs

    Query Parameters:
        pair1: First instrument (e.g., EUR_USD) - REQUIRED
        pair2: Second instrument (e.g., GBP_USD) - REQUIRED

    Returns:
        200: Correlation value
        400: Missing parameters
        404: Correlation not found
        500: Server error
    """
    try:
        pair1 = request.args.get("pair1", "").upper()
        pair2 = request.args.get("pair2", "").upper()

        if not pair1 or not pair2:
            return jsonify(
                {"error": "Missing 'pair1' or 'pair2' parameter"}
            ), 400

        if pair1 not in Config.TRACKED_PAIRS or pair2 not in Config.TRACKED_PAIRS:
            return jsonify(
                {"error": "One or both pairs not in tracked pairs"}
            ), 400

        matrix = cache_manager.get_correlation_matrix()

        if not matrix:
            return (
                jsonify(
                    {
                        "error": "No correlation matrix in cache",
                        "message": "Run daily cron job first",
                    }
                ),
                404,
            )

        # Extract correlation value
        correlation = None
        if pair1 in matrix and pair2 in matrix[pair1]:
            correlation = matrix[pair1][pair2]

        if correlation is None:
            return (
                jsonify(
                    {
                        "error": f"No correlation data for {pair1} and {pair2}",
                    }
                ),
                404,
            )

        return jsonify(
            {
                "pair1": pair1,
                "pair2": pair2,
                "correlation": float(correlation),
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting pair correlation: {e}")
        return jsonify({"error": str(e)}), 500


# ========== BEST PAIRS ENDPOINTS ==========


@app.route("/api/v1/best-pairs", methods=["GET"])
def get_best_pairs():
    """
    Get recommended best trading pairs

    Query Parameters:
        category: Filter by category (hedging, diversification, moderate, high_correlation)
                  (optional)

    Returns:
        200: List of best pairs
        404: Recommendations not found
        500: Server error
    """
    try:
        category = request.args.get("category", "").lower()

        best_pairs = cache_manager.get_best_pairs()

        if not best_pairs:
            return (
                jsonify(
                    {
                        "error": "No best pairs recommendations in cache",
                        "message": "Run daily cron job first",
                    }
                ),
                404,
            )

        # Filter by category if provided
        if category:
            best_pairs = [p for p in best_pairs if p.get("category") == category]

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "count": len(best_pairs),
                "pairs": best_pairs,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting best pairs: {e}")
        return jsonify({"error": str(e)}), 500


# ========== MARKET SESSIONS ENDPOINTS ==========


@app.route("/api/v1/sessions", methods=["GET"])
def get_market_sessions():
    """
    Get market session information

    Returns:
        200: List of market sessions
        500: Server error
    """
    try:
        if not db.conn:
            db.connect()

        with db.cursor(dict_cursor=True) as cursor:
            cursor.execute(
                """
                SELECT session_name, start_time, end_time, timezone, description
                FROM market_sessions
                ORDER BY start_time
            """
            )
            rows = cursor.fetchall()

        sessions = [
            {
                "name": row["session_name"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "timezone": row["timezone"],
                "description": row["description"],
            }
            for row in rows
        ]

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "count": len(sessions),
                "sessions": sessions,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting market sessions: {e}")
        return jsonify({"error": str(e)}), 500


# ========== CACHE MANAGEMENT ENDPOINTS ==========


@app.route("/api/v1/cache/stats", methods=["GET"])
def get_cache_stats():
    """
    Get cache statistics and health

    Returns:
        200: Cache statistics
        500: Server error
    """
    try:
        stats = cache_manager.get_cache_stats()

        return jsonify(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "cache": stats,
            }
        ), 200

    except Exception as e:
        logger.error(f"❌ Error getting cache stats: {e}")
        return jsonify({"error": str(e)}), 500


# ========== ERROR HANDLERS ==========


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify(
        {
            "error": "Endpoint not found",
            "message": "Check /api/v1/info for available endpoints",
        }
    ), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"❌ Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


def create_logs_directory():
    """Ensure logs directory exists"""
    log_dir = Path(Config.LOG_FILE).parent
    log_dir.mkdir(exist_ok=True)


if __name__ == "__main__":
    # Create logs directory
    create_logs_directory()

    logger.info("=" * 80)
    logger.info("🚀 Starting FX Data Pipeline REST API")
    logger.info("=" * 80)

    try:
        # Validate configuration
        Config.validate()

        # Connect to database
        db.connect()

        logger.info(f"✅ API Server initialized")
        logger.info(f"📍 Host: {Config.API_HOST}")
        logger.info(f"📍 Port: {Config.API_PORT}")
        logger.info(f"🔗 Base URL: http://{Config.API_HOST}:{Config.API_PORT}")
        logger.info(f"📊 Tracked pairs: {len(Config.TRACKED_PAIRS)}")
        logger.info(f"\n✅ Visit http://localhost:{Config.API_PORT}/api/v1/info for API documentation\n")

        # Run Flask app
        app.run(
            host=Config.API_HOST,
            port=Config.API_PORT,
            debug=Config.API_DEBUG,
            use_reloader=False,  # Disable reloader for better logging
        )

    except Exception as e:
        logger.error(f"❌ Failed to start API: {e}")
        sys.exit(1)
