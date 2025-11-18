#!/usr/bin/env python3
"""
WebSocket Server for FX Data Pipeline

Provides real-time price streaming and alerts to multiple clients using:
- Flask-SocketIO for WebSocket connections
- Redis Pub/Sub for event broadcasting
- Room-based subscriptions for flexible client management
- Event-driven architecture for alerts and notifications

Architecture:
┌─────────────────────────────────────────────────────────────┐
│                  Flask-SocketIO Server                       │
│              (api/websocket_server.py)                       │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Client 1 (subscribe: EUR_USD, GBP_USD)                     │
│       │                                                       │
│  Client 2 (subscribe: EUR_USD)                              │
│       │                                                       │
│  Client 3 (subscribe: all 20 pairs)                         │
│       └─────────────────┬───────────────────┘              │
│                         │                                    │
│                   Room Management                            │
│                   (pair subscriptions)                       │
│                         │                                    │
│                   ┌─────▼──────┐                            │
│                   │ Redis Pub/Sub│                           │
│                   │  Listener    │                           │
│                   └─────┬──────┘                            │
│                         │                                    │
│            Broadcasts from cron jobs:                       │
│            - price_updates                                  │
│            - volatility_alerts                              │
│            - correlation_alerts                             │
│            - data_ready                                     │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Usage:
    python api/websocket_server.py

Client Usage (JavaScript):
    const socket = io('http://localhost:5001');
    socket.on('connect', () => {
        socket.emit('subscribe', ['EUR_USD', 'GBP_USD']);
    });
    socket.on('price_update', (data) => {
        console.log(data);
    });
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread
from typing import Dict, List, Set

from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
from flask_cors import CORS

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config import Config
from cache.cache_manager import CacheManager
from cache.pubsub import PubSubListener
from utils.db_connection import DatabaseConnection

# Setup logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(Config.LOG_FILE.replace("api.log", "websocket.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

# Enable CORS
CORS(app, resources={"*": {"origins": "*"}})

# Initialize SocketIO
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=Config.WEBSOCKET_PING_TIMEOUT,
    ping_interval=Config.WEBSOCKET_PING_INTERVAL,
    max_http_buffer_size=1e6,  # 1MB max message size
)

# Initialize managers
cache_manager = CacheManager()
db = DatabaseConnection()

# Track client subscriptions
# Format: {sid: {'subscribed_pairs': set(), 'subscribed_all': bool}}
client_subscriptions: Dict[str, Dict] = {}

# Track active connections
active_connections = 0
max_connections = Config.WEBSOCKET_MAX_CLIENTS


# ========== CONNECTION HANDLERS ==========


@socketio.on("connect")
def handle_connect(auth):
    """Handle client connection"""
    global active_connections

    client_id = request.sid if hasattr(request, "sid") else "unknown"
    active_connections += 1

    logger.info(
        f"✅ Client connected: {client_id} "
        f"(Active: {active_connections}/{max_connections})"
    )

    # Initialize subscription tracking for this client
    client_subscriptions[client_id] = {"subscribed_pairs": set(), "subscribed_all": False}

    # Send welcome message
    emit(
        "connection_established",
        {
            "message": "Connected to FX Data Pipeline WebSocket Server",
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id,
            "tracked_pairs": Config.TRACKED_PAIRS,
            "pair_count": len(Config.TRACKED_PAIRS),
            "max_clients": max_connections,
            "active_clients": active_connections,
        },
    )

    logger.debug(f"📡 Sent welcome message to {client_id}")


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    global active_connections

    client_id = request.sid if hasattr(request, "sid") else "unknown"
    active_connections = max(0, active_connections - 1)

    # Clean up subscriptions
    if client_id in client_subscriptions:
        subscribed_pairs = client_subscriptions[client_id].get("subscribed_pairs", set())
        del client_subscriptions[client_id]
        logger.info(
            f"🔴 Client disconnected: {client_id} "
            f"(was subscribed to {len(subscribed_pairs)} pairs, "
            f"Active: {active_connections}/{max_connections})"
        )
    else:
        logger.info(f"🔴 Client disconnected: {client_id}")


# ========== SUBSCRIPTION HANDLERS ==========


@socketio.on("subscribe")
def handle_subscribe(data):
    """
    Subscribe to price updates for specific pairs

    Client sends:
    {
        'pairs': ['EUR_USD', 'GBP_USD']  or
        'pairs': '*'  (all 20 pairs)
    }
    """
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    try:
        pairs = data.get("pairs", [])

        # Handle subscribe to all pairs
        if pairs == "*":
            logger.info(f"👤 Client {client_id} subscribed to ALL 20 pairs")
            client_subscriptions[client_id]["subscribed_all"] = True
            client_subscriptions[client_id]["subscribed_pairs"] = set(Config.TRACKED_PAIRS)

            # Join rooms for all pairs
            for pair in Config.TRACKED_PAIRS:
                join_room(f"price_{pair}")

            emit(
                "subscription_confirmed",
                {
                    "pairs": Config.TRACKED_PAIRS,
                    "pair_count": len(Config.TRACKED_PAIRS),
                    "subscribed_to_all": True,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        # Handle subscribe to specific pairs
        elif isinstance(pairs, list) and pairs:
            # Validate pairs
            invalid_pairs = [p for p in pairs if p not in Config.TRACKED_PAIRS]

            if invalid_pairs:
                emit(
                    "subscription_error",
                    {
                        "error": f"Invalid pairs: {invalid_pairs}",
                        "valid_pairs": Config.TRACKED_PAIRS,
                    },
                )
                return

            # Subscribe to each pair
            client_subscriptions[client_id]["subscribed_pairs"].update(pairs)

            for pair in pairs:
                join_room(f"price_{pair}")
                logger.debug(f"👤 Client {client_id} joined room: price_{pair}")

            emit(
                "subscription_confirmed",
                {
                    "pairs": list(pairs),
                    "pair_count": len(pairs),
                    "subscribed_to_all": False,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(f"👤 Client {client_id} subscribed to {len(pairs)} pairs")

        else:
            emit(
                "subscription_error",
                {
                    "error": "Invalid subscription request",
                    "message": "Expected pairs as list or '*' for all",
                },
            )

    except Exception as e:
        logger.error(f"❌ Subscription error for {client_id}: {e}")
        emit("subscription_error", {"error": str(e)})


@socketio.on("unsubscribe")
def handle_unsubscribe(data):
    """
    Unsubscribe from price updates for specific pairs

    Client sends:
    {
        'pairs': ['EUR_USD', 'GBP_USD']  or
        'pairs': '*'  (all pairs)
    }
    """
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    try:
        pairs = data.get("pairs", [])

        # Handle unsubscribe from all
        if pairs == "*":
            # Leave all rooms
            for pair in Config.TRACKED_PAIRS:
                leave_room(f"price_{pair}")

            client_subscriptions[client_id]["subscribed_all"] = False
            client_subscriptions[client_id]["subscribed_pairs"].clear()

            emit(
                "unsubscription_confirmed",
                {
                    "pairs": Config.TRACKED_PAIRS,
                    "message": "Unsubscribed from all pairs",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(f"👤 Client {client_id} unsubscribed from ALL pairs")

        # Handle unsubscribe from specific pairs
        elif isinstance(pairs, list) and pairs:
            for pair in pairs:
                if pair in Config.TRACKED_PAIRS:
                    leave_room(f"price_{pair}")
                    client_subscriptions[client_id]["subscribed_pairs"].discard(pair)
                    logger.debug(f"👤 Client {client_id} left room: price_{pair}")

            emit(
                "unsubscription_confirmed",
                {
                    "pairs": list(pairs),
                    "message": f"Unsubscribed from {len(pairs)} pairs",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            logger.info(f"👤 Client {client_id} unsubscribed from {len(pairs)} pairs")

    except Exception as e:
        logger.error(f"❌ Unsubscription error for {client_id}: {e}")
        emit("unsubscription_error", {"error": str(e)})


@socketio.on("get_subscriptions")
def handle_get_subscriptions():
    """Get current client subscriptions"""
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    if client_id in client_subscriptions:
        subs = client_subscriptions[client_id]
        emit(
            "subscriptions_info",
            {
                "subscribed_pairs": list(subs.get("subscribed_pairs", [])),
                "pair_count": len(subs.get("subscribed_pairs", set())),
                "subscribed_to_all": subs.get("subscribed_all", False),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )


# ========== PRICE UPDATE HANDLERS ==========


@socketio.on("request_price")
def handle_request_price(data):
    """
    Request current price for a specific pair

    Client sends:
    {
        'instrument': 'EUR_USD'
    }
    """
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    try:
        instrument = data.get("instrument", "").upper()

        if not instrument or instrument not in Config.TRACKED_PAIRS:
            emit(
                "price_error",
                {"error": f"Invalid instrument: {instrument}"},
            )
            return

        # Get price from cache
        price = cache_manager.get_price(instrument)

        if price:
            emit(
                "price_response",
                {
                    "instrument": instrument,
                    "price": price,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        else:
            emit(
                "price_error",
                {
                    "error": f"No cached price for {instrument}",
                    "message": "Run hourly cron job to populate prices",
                },
            )

    except Exception as e:
        logger.error(f"❌ Error requesting price for {client_id}: {e}")
        emit("price_error", {"error": str(e)})


@socketio.on("request_all_prices")
def handle_request_all_prices():
    """Request all current prices"""
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    try:
        prices = cache_manager.get_all_prices()

        if prices:
            emit(
                "all_prices_response",
                {
                    "prices": prices,
                    "pair_count": len(prices),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        else:
            emit(
                "price_error",
                {
                    "error": "No cached prices available",
                    "message": "Run hourly cron job to populate prices",
                },
            )

    except Exception as e:
        logger.error(f"❌ Error requesting all prices for {client_id}: {e}")
        emit("price_error", {"error": str(e)})


# ========== STATUS & INFO HANDLERS ==========


@socketio.on("get_server_stats")
def handle_get_server_stats():
    """Get server statistics"""
    client_id = request.sid if hasattr(request, "sid") else "unknown"

    try:
        # Get cache stats
        cache_stats = cache_manager.get_cache_stats()

        # Count subscriptions
        total_subscriptions = sum(
            len(subs.get("subscribed_pairs", set())) for subs in client_subscriptions.values()
        )

        emit(
            "server_stats",
            {
                "timestamp": datetime.utcnow().isoformat(),
                "active_clients": active_connections,
                "max_clients": max_connections,
                "total_subscriptions": total_subscriptions,
                "average_subs_per_client": (
                    total_subscriptions / max(1, active_connections)
                ),
                "tracked_pairs": len(Config.TRACKED_PAIRS),
                "cache": cache_stats.get("cache", {}),
            },
        )

    except Exception as e:
        logger.error(f"❌ Error getting server stats for {client_id}: {e}")
        emit("server_error", {"error": str(e)})


@socketio.on("ping")
def handle_ping():
    """Handle client ping"""
    emit("pong", {"timestamp": datetime.utcnow().isoformat()})


# ========== BROADCAST HANDLERS (from cron jobs) ==========


def broadcast_price_update(instrument: str, price_data: dict):
    """
    Broadcast price update to subscribed clients

    Called from cron jobs when new price is available
    """
    try:
        socketio.emit(
            "price_update",
            {
                "instrument": instrument,
                "price": price_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"price_{instrument}",
        )

        logger.debug(f"📤 Broadcasted price update for {instrument}")

    except Exception as e:
        logger.error(f"❌ Error broadcasting price update: {e}")


def broadcast_volatility_alert(
    instrument: str, volatility: float, threshold: float, severity: str = "warning"
):
    """
    Broadcast volatility alert to subscribed clients

    Severity levels: info, warning, critical
    """
    try:
        socketio.emit(
            "volatility_alert",
            {
                "instrument": instrument,
                "volatility": volatility,
                "threshold": threshold,
                "severity": severity,
                "message": f"Volatility ({volatility}) exceeded threshold ({threshold})",
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"price_{instrument}",
        )

        logger.info(
            f"🚨 Broadcasted {severity} volatility alert for {instrument}: {volatility}"
        )

    except Exception as e:
        logger.error(f"❌ Error broadcasting volatility alert: {e}")


def broadcast_correlation_alert(
    pair1: str, pair2: str, correlation: float, threshold: float, severity: str = "info"
):
    """
    Broadcast correlation alert to subscribed clients

    Severity levels: info, warning, critical
    """
    try:
        socketio.emit(
            "correlation_alert",
            {
                "pair1": pair1,
                "pair2": pair2,
                "correlation": correlation,
                "threshold": threshold,
                "severity": severity,
                "message": f"Correlation between {pair1} and {pair2} changed to {correlation}",
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"price_{pair1}",
        )

        # Also emit to pair2 subscribers
        socketio.emit(
            "correlation_alert",
            {
                "pair1": pair1,
                "pair2": pair2,
                "correlation": correlation,
                "threshold": threshold,
                "severity": severity,
                "message": f"Correlation between {pair1} and {pair2} changed to {correlation}",
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"price_{pair2}",
        )

        logger.info(f"🔗 Broadcasted correlation alert: {pair1}-{pair2} = {correlation}")

    except Exception as e:
        logger.error(f"❌ Error broadcasting correlation alert: {e}")


def broadcast_data_ready(data_type: str, count: int):
    """
    Broadcast data ready notification to all clients

    Data types: prices, metrics, correlations, candles
    """
    try:
        socketio.emit(
            "data_ready",
            {
                "data_type": data_type,
                "count": count,
                "message": f"{data_type} data updated ({count} records)",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"📊 Broadcasted data_ready: {data_type} ({count} records)")

    except Exception as e:
        logger.error(f"❌ Error broadcasting data ready: {e}")


# ========== REDIS PUB/SUB LISTENER ==========


def start_pubsub_listener():
    """Start Redis Pub/Sub listener in background thread"""

    def listen():
        try:
            pubsub = PubSubListener()

            logger.info("📡 Starting Redis Pub/Sub listener...")

            def on_price_update(data):
                """Handle price update from Redis"""
                try:
                    instrument = data.get("instrument")
                    price = data.get("price")
                    if instrument and price:
                        broadcast_price_update(instrument, price)
                except Exception as e:
                    logger.error(f"❌ Error handling price update: {e}")

            def on_volatility_alert(data):
                """Handle volatility alert from Redis"""
                try:
                    instrument = data.get("instrument")
                    volatility = data.get("volatility")
                    threshold = data.get("threshold")
                    severity = data.get("severity", "warning")
                    if instrument and volatility is not None:
                        broadcast_volatility_alert(instrument, volatility, threshold, severity)
                except Exception as e:
                    logger.error(f"❌ Error handling volatility alert: {e}")

            def on_correlation_alert(data):
                """Handle correlation alert from Redis"""
                try:
                    pair1 = data.get("pair1")
                    pair2 = data.get("pair2")
                    correlation = data.get("correlation")
                    threshold = data.get("threshold")
                    severity = data.get("severity", "info")
                    if pair1 and pair2 and correlation is not None:
                        broadcast_correlation_alert(
                            pair1, pair2, correlation, threshold, severity
                        )
                except Exception as e:
                    logger.error(f"❌ Error handling correlation alert: {e}")

            def on_data_ready(data):
                """Handle data ready notification from Redis"""
                try:
                    data_type = data.get("data_type")
                    count = data.get("count")
                    if data_type and count is not None:
                        broadcast_data_ready(data_type, count)
                except Exception as e:
                    logger.error(f"❌ Error handling data ready: {e}")

            # Register callbacks
            callbacks = {
                "price_updates": on_price_update,
                "volatility_alerts": on_volatility_alert,
                "correlation_alerts": on_correlation_alert,
                "data_ready": on_data_ready,
            }

            # Start listening (blocking)
            pubsub.subscribe(list(callbacks.keys()), callbacks)

        except Exception as e:
            logger.error(f"❌ Pub/Sub listener error: {e}")
            raise

    # Start in background thread
    listener_thread = Thread(target=listen, daemon=True)
    listener_thread.start()
    logger.info("✅ Redis Pub/Sub listener thread started")


# ========== HELPER ENDPOINT ==========


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    from flask import jsonify

    return jsonify(
        {
            "status": "healthy",
            "service": "WebSocket Server",
            "timestamp": datetime.utcnow().isoformat(),
            "active_clients": active_connections,
            "max_clients": max_connections,
        }
    ), 200


# ========== MAIN ==========


def create_logs_directory():
    """Ensure logs directory exists"""
    log_dir = Path(Config.LOG_FILE).parent
    log_dir.mkdir(exist_ok=True)


if __name__ == "__main__":
    # Create logs directory
    create_logs_directory()

    logger.info("=" * 80)
    logger.info("🚀 Starting FX Data Pipeline WebSocket Server")
    logger.info("=" * 80)

    try:
        # Validate configuration
        Config.validate()

        # Connect to database
        db.connect()

        logger.info(f"✅ WebSocket Server initialized")
        logger.info(f"📍 Host: {Config.WEBSOCKET_HOST}")
        logger.info(f"📍 Port: {Config.WEBSOCKET_PORT}")
        logger.info(f"🔗 WebSocket URL: ws://{Config.WEBSOCKET_HOST}:{Config.WEBSOCKET_PORT}")
        logger.info(f"📊 Tracked pairs: {len(Config.TRACKED_PAIRS)}")
        logger.info(f"👥 Max clients: {max_connections}")
        logger.info(f"⏱️  Ping interval: {Config.WEBSOCKET_PING_INTERVAL}s")
        logger.info(f"⏱️  Ping timeout: {Config.WEBSOCKET_PING_TIMEOUT}s")

        # Start Redis Pub/Sub listener in background
        start_pubsub_listener()

        logger.info("\n✅ WebSocket Server ready for connections\n")

        # Run SocketIO app
        socketio.run(
            app,
            host=Config.WEBSOCKET_HOST,
            port=Config.WEBSOCKET_PORT,
            debug=Config.API_DEBUG,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )

    except Exception as e:
        logger.error(f"❌ Failed to start WebSocket server: {e}")
        sys.exit(1)
