"""Redis Connection Manager & Helpers"""

import redis
import json
import logging
from typing import Any, Optional
from utils.config import Config

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis connection manager with connection pooling"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = None,
        password: str = None,
        decode_responses: bool = True,
    ):
        """
        Initialize Redis connection

        Args:
            host: Redis host (default: localhost)
            port: Redis port (default: 6379)
            db: Redis database number (default: 0)
            password: Redis password (default: None)
            decode_responses: Decode responses to strings (default: True)
        """
        self.host = host or Config.REDIS_HOST
        self.port = port or Config.REDIS_PORT
        self.db = db or Config.REDIS_DB
        self.password = password or Config.REDIS_PASSWORD

        try:
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=decode_responses,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )

            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Connected to Redis: {self.host}:{self.port}/{self.db}")

        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set a key-value pair in Redis

        Args:
            key: Redis key
            value: Value (will be JSON serialized if not string)
            ttl: Time to live in seconds (optional)

        Returns:
            True if successful
        """
        try:
            if not isinstance(value, str):
                value = json.dumps(value)

            if ttl:
                self.redis_client.setex(key, ttl, value)
            else:
                self.redis_client.set(key, value)

            return True

        except Exception as e:
            logger.error(f"❌ Error setting key {key}: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from Redis

        Args:
            key: Redis key

        Returns:
            Value (parsed from JSON if applicable)
        """
        try:
            value = self.redis_client.get(key)

            if value is None:
                return None

            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        except Exception as e:
            logger.error(f"❌ Error getting key {key}: {e}")
            return None

    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis

        Args:
            key: Redis key

        Returns:
            True if successful
        """
        try:
            self.redis_client.delete(key)
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"❌ Error checking key {key}: {e}")
            return False

    def hset(self, key: str, mapping: dict) -> bool:
        """
        Set multiple hash fields

        Args:
            key: Redis hash key
            mapping: Dictionary of field-value pairs

        Returns:
            True if successful
        """
        try:
            # Convert non-string values to JSON
            serialized_mapping = {}
            for field, value in mapping.items():
                if not isinstance(value, str):
                    serialized_mapping[field] = json.dumps(value)
                else:
                    serialized_mapping[field] = value

            self.redis_client.hset(key, mapping=serialized_mapping)
            return True

        except Exception as e:
            logger.error(f"❌ Error setting hash {key}: {e}")
            return False

    def hget(self, key: str, field: str) -> Optional[Any]:
        """
        Get a hash field

        Args:
            key: Redis hash key
            field: Field name

        Returns:
            Field value (parsed from JSON if applicable)
        """
        try:
            value = self.redis_client.hget(key, field)

            if value is None:
                return None

            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

        except Exception as e:
            logger.error(f"❌ Error getting hash field {key}:{field}: {e}")
            return None

    def hgetall(self, key: str) -> dict:
        """
        Get all hash fields

        Args:
            key: Redis hash key

        Returns:
            Dictionary of field-value pairs
        """
        try:
            data = self.redis_client.hgetall(key)

            # Try to parse values as JSON
            parsed_data = {}
            for field, value in data.items():
                try:
                    parsed_data[field] = json.loads(value)
                except json.JSONDecodeError:
                    parsed_data[field] = value

            return parsed_data

        except Exception as e:
            logger.error(f"❌ Error getting all hash fields for {key}: {e}")
            return {}

    def hdel(self, key: str, field: str) -> bool:
        """
        Delete a hash field

        Args:
            key: Redis hash key
            field: Field name

        Returns:
            True if successful
        """
        try:
            self.redis_client.hdel(key, field)
            return True

        except Exception as e:
            logger.error(f"❌ Error deleting hash field {key}:{field}: {e}")
            return False

    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment a value

        Args:
            key: Redis key
            amount: Amount to increment by

        Returns:
            New value
        """
        try:
            return self.redis_client.incrby(key, amount)

        except Exception as e:
            logger.error(f"❌ Error incrementing key {key}: {e}")
            return None

    def expire(self, key: str, ttl: int) -> bool:
        """
        Set expiration on a key

        Args:
            key: Redis key
            ttl: Time to live in seconds

        Returns:
            True if successful
        """
        try:
            self.redis_client.expire(key, ttl)
            return True

        except Exception as e:
            logger.error(f"❌ Error setting expiration for {key}: {e}")
            return False

    def ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key

        Args:
            key: Redis key

        Returns:
            Remaining seconds, -1 if no TTL, -2 if doesn't exist
        """
        try:
            return self.redis_client.ttl(key)

        except Exception as e:
            logger.error(f"❌ Error getting TTL for {key}: {e}")
            return None

    def flush(self) -> bool:
        """
        Flush all keys in current database

        Args:
            None

        Returns:
            True if successful
        """
        try:
            self.redis_client.flushdb()
            logger.info(f"✅ Flushed Redis database {self.db}")
            return True

        except Exception as e:
            logger.error(f"❌ Error flushing database: {e}")
            return False

    def info(self) -> dict:
        """Get Redis server info"""
        try:
            return self.redis_client.info()

        except Exception as e:
            logger.error(f"❌ Error getting Redis info: {e}")
            return {}

    def close(self):
        """Close Redis connection"""
        try:
            self.redis_client.close()
            logger.info("✅ Redis connection closed")

        except Exception as e:
            logger.error(f"❌ Error closing Redis connection: {e}")


# Global Redis instance
_redis_client = None


def get_redis() -> RedisClient:
    """Get or create Redis connection"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def close_redis():
    """Close global Redis connection"""
    global _redis_client
    if _redis_client:
        _redis_client.close()
        _redis_client = None
