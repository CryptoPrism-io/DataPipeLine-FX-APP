"""Redis Pub/Sub Manager for WebSocket Broadcasting

Channels:
- price_updates: Real-time price changes
- volatility_alerts: Volatility spike notifications
- correlation_alerts: High correlation warnings
- data_ready: New data available notification
"""

import json
import logging
from typing import Callable, List
from threading import Thread

from cache.redis_client import get_redis

logger = logging.getLogger(__name__)


class PubSubManager:
    """Manages Redis Pub/Sub for WebSocket broadcasting"""

    # Channel names
    CHANNEL_PRICES = "price_updates"
    CHANNEL_VOLATILITY_ALERTS = "volatility_alerts"
    CHANNEL_CORRELATION_ALERTS = "correlation_alerts"
    CHANNEL_DATA_READY = "data_ready"

    def __init__(self):
        """Initialize Pub/Sub manager"""
        self.redis = get_redis()
        self.pubsub = None
        self.subscribers = {}
        self.listening = False

    def publish_price_update(self, instrument: str, price_data: dict) -> bool:
        """
        Publish price update to subscribers

        Args:
            instrument: Instrument name
            price_data: Dictionary with bid, ask, mid, time

        Returns:
            True if successful
        """
        try:
            message = {
                "instrument": instrument,
                "bid": str(price_data.get("bid")),
                "ask": str(price_data.get("ask")),
                "mid": str(price_data.get("mid")),
                "time": price_data.get("time"),
            }

            self.redis.redis_client.publish(self.CHANNEL_PRICES, json.dumps(message))

            return True

        except Exception as e:
            logger.error(f"❌ Error publishing price update for {instrument}: {e}")
            return False

    def publish_volatility_alert(
        self,
        instrument: str,
        volatility: float,
        threshold: float,
        severity: str = "WARNING",
    ) -> bool:
        """
        Publish volatility alert

        Args:
            instrument: Instrument name
            volatility: Current volatility value
            threshold: Alert threshold
            severity: Alert severity (WARNING, CRITICAL)

        Returns:
            True if successful
        """
        try:
            message = {
                "instrument": instrument,
                "volatility": float(volatility),
                "threshold": float(threshold),
                "severity": severity,
                "timestamp": str(__import__("datetime").datetime.utcnow().isoformat()),
            }

            self.redis.redis_client.publish(self.CHANNEL_VOLATILITY_ALERTS, json.dumps(message))

            return True

        except Exception as e:
            logger.error(f"❌ Error publishing volatility alert for {instrument}: {e}")
            return False

    def publish_correlation_alert(
        self,
        pair1: str,
        pair2: str,
        correlation: float,
        threshold: float,
        severity: str = "WARNING",
    ) -> bool:
        """
        Publish correlation alert

        Args:
            pair1: First pair
            pair2: Second pair
            correlation: Correlation value
            threshold: Alert threshold
            severity: Alert severity (WARNING, CRITICAL)

        Returns:
            True if successful
        """
        try:
            message = {
                "pair1": pair1,
                "pair2": pair2,
                "correlation": float(correlation),
                "threshold": float(threshold),
                "severity": severity,
                "timestamp": str(__import__("datetime").datetime.utcnow().isoformat()),
            }

            self.redis.redis_client.publish(self.CHANNEL_CORRELATION_ALERTS, json.dumps(message))

            return True

        except Exception as e:
            logger.error(f"❌ Error publishing correlation alert: {e}")
            return False

    def publish_data_ready(self, data_type: str, count: int = 0) -> bool:
        """
        Publish notification that new data is ready

        Args:
            data_type: Type of data (candles, metrics, correlation)
            count: Number of records updated

        Returns:
            True if successful
        """
        try:
            message = {
                "data_type": data_type,
                "count": count,
                "timestamp": str(__import__("datetime").datetime.utcnow().isoformat()),
            }

            self.redis.redis_client.publish(self.CHANNEL_DATA_READY, json.dumps(message))

            return True

        except Exception as e:
            logger.error(f"❌ Error publishing data_ready notification: {e}")
            return False

    def subscribe(
        self,
        channels: List[str],
        callback: Callable,
    ):
        """
        Subscribe to channels and listen for messages

        Args:
            channels: List of channel names to subscribe to
            callback: Callback function for received messages
                     Function signature: callback(channel, message)
        """
        try:
            self.pubsub = self.redis.redis_client.pubsub()

            # Subscribe to channels
            self.pubsub.subscribe(channels)
            logger.info(f"✅ Subscribed to channels: {', '.join(channels)}")

            # Listen for messages
            self.listening = True

            for message in self.pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        callback(message["channel"], data)

                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Invalid JSON in message: {message['data']}")

                    except Exception as e:
                        logger.error(f"❌ Error in callback: {e}")

                elif message["type"] == "subscribe":
                    logger.info(f"📡 Subscribed to {message['channel']}")

        except Exception as e:
            logger.error(f"❌ Error subscribing to channels: {e}")
            self.listening = False

    def start_listener_thread(
        self,
        channels: List[str],
        callback: Callable,
    ) -> Thread:
        """
        Start listener in background thread

        Args:
            channels: List of channels to subscribe to
            callback: Message callback function

        Returns:
            Thread object
        """
        thread = Thread(
            target=self.subscribe,
            args=(channels, callback),
            daemon=True,
            name="Redis-Listener",
        )
        thread.start()
        return thread

    def unsubscribe(self, channels: List[str] = None):
        """
        Unsubscribe from channels

        Args:
            channels: List of channels to unsubscribe from (all if None)
        """
        try:
            if self.pubsub:
                if channels:
                    self.pubsub.unsubscribe(channels)
                    logger.info(f"Unsubscribed from channels: {', '.join(channels)}")
                else:
                    self.pubsub.unsubscribe()
                    logger.info("Unsubscribed from all channels")

        except Exception as e:
            logger.error(f"❌ Error unsubscribing: {e}")

    def close(self):
        """Close Pub/Sub connection"""
        try:
            if self.pubsub:
                self.pubsub.close()
                self.listening = False
                logger.info("✅ Pub/Sub connection closed")

        except Exception as e:
            logger.error(f"❌ Error closing Pub/Sub: {e}")


# Global Pub/Sub manager instance
_pubsub_manager = None


def get_pubsub_manager() -> PubSubManager:
    """Get or create Pub/Sub manager"""
    global _pubsub_manager
    if _pubsub_manager is None:
        _pubsub_manager = PubSubManager()
    return _pubsub_manager


# Example usage/testing
if __name__ == "__main__":
    import time

    logging.basicConfig(level=logging.INFO)

    # Create manager
    pubsub = get_pubsub_manager()

    # Example callback
    def message_handler(channel: str, message: dict):
        logger.info(f"📬 Message on {channel}: {message}")

    # Start listening in background
    thread = pubsub.start_listener_thread(
        [
            PubSubManager.CHANNEL_PRICES,
            PubSubManager.CHANNEL_VOLATILITY_ALERTS,
            PubSubManager.CHANNEL_CORRELATION_ALERTS,
        ],
        message_handler,
    )

    logger.info("Listener thread started. Publishing test messages...\n")

    # Publish test messages
    time.sleep(1)
    pubsub.publish_price_update("EUR_USD", {"bid": 1.08945, "ask": 1.08950, "mid": 1.089475, "time": "2024-11-18T15:45:00Z"})

    time.sleep(1)
    pubsub.publish_volatility_alert("EUR_USD", 0.0185, 0.02, "WARNING")

    time.sleep(1)
    pubsub.publish_correlation_alert("EUR_USD", "GBP_USD", 0.82, 0.70, "CRITICAL")

    time.sleep(1)
    pubsub.publish_data_ready("candles", 20)

    time.sleep(2)

    logger.info("\nClosing listener...")
    pubsub.close()
