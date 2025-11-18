"""High-level Cache Manager for FX Data Pipeline

Manages caching of:
- Current prices (5 min TTL)
- Volatility metrics (1 hour TTL)
- Correlation matrix (1 day TTL)
- Best pairs (1 day TTL)
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

from cache.redis_client import get_redis
from utils.config import Config

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages all Redis caching operations"""

    # Cache key prefixes
    PREFIX_PRICE = "price"
    PREFIX_METRICS = "metrics"
    PREFIX_CORRELATION = "correlation"
    PREFIX_BEST_PAIRS = "best_pairs"
    PREFIX_SESSION = "session"

    def __init__(self):
        """Initialize cache manager"""
        self.redis = get_redis()

    # ========== PRICE CACHING ==========

    def cache_price(self, instrument: str, bid: float, ask: float, mid: float, time: str = None) -> bool:
        """
        Cache current price for a pair

        Args:
            instrument: Instrument name (e.g., EUR_USD)
            bid: Bid price
            ask: Ask price
            mid: Mid price
            time: Timestamp (optional)

        Returns:
            True if successful
        """
        try:
            key = f"{self.PREFIX_PRICE}:{instrument}"

            data = {
                "bid": str(bid),
                "ask": str(ask),
                "mid": str(mid),
                "time": time or datetime.utcnow().isoformat(),
            }

            self.redis.hset(key, data)
            self.redis.expire(key, Config.CACHE_TTL_PRICES)

            return True

        except Exception as e:
            logger.error(f"❌ Error caching price for {instrument}: {e}")
            return False

    def get_price(self, instrument: str) -> Optional[Dict]:
        """
        Get cached price for a pair

        Args:
            instrument: Instrument name

        Returns:
            Dictionary with bid, ask, mid, time
        """
        try:
            key = f"{self.PREFIX_PRICE}:{instrument}"
            return self.redis.hgetall(key) or None

        except Exception as e:
            logger.error(f"❌ Error getting cached price for {instrument}: {e}")
            return None

    def get_all_prices(self) -> Dict[str, Dict]:
        """Get all cached prices"""
        try:
            prices = {}

            for pair in Config.TRACKED_PAIRS:
                price = self.get_price(pair)
                if price:
                    prices[pair] = price

            return prices

        except Exception as e:
            logger.error(f"❌ Error getting all cached prices: {e}")
            return {}

    # ========== VOLATILITY METRICS CACHING ==========

    def cache_volatility_metrics(
        self,
        instrument: str,
        volatility_20: float = None,
        volatility_50: float = None,
        sma_15: float = None,
        sma_30: float = None,
        sma_50: float = None,
        bb_upper: float = None,
        bb_middle: float = None,
        bb_lower: float = None,
        atr: float = None,
    ) -> bool:
        """
        Cache volatility metrics for a pair

        Args:
            instrument: Instrument name
            volatility_20: 20-period historical volatility
            volatility_50: 50-period historical volatility
            sma_15: 15-period SMA
            sma_30: 30-period SMA
            sma_50: 50-period SMA
            bb_upper: Bollinger Band upper
            bb_middle: Bollinger Band middle
            bb_lower: Bollinger Band lower
            atr: Average True Range

        Returns:
            True if successful
        """
        try:
            key = f"{self.PREFIX_METRICS}:{instrument}"

            data = {
                "volatility_20": str(volatility_20) if volatility_20 else "N/A",
                "volatility_50": str(volatility_50) if volatility_50 else "N/A",
                "sma_15": str(sma_15) if sma_15 else "N/A",
                "sma_30": str(sma_30) if sma_30 else "N/A",
                "sma_50": str(sma_50) if sma_50 else "N/A",
                "bb_upper": str(bb_upper) if bb_upper else "N/A",
                "bb_middle": str(bb_middle) if bb_middle else "N/A",
                "bb_lower": str(bb_lower) if bb_lower else "N/A",
                "atr": str(atr) if atr else "N/A",
                "cached_at": datetime.utcnow().isoformat(),
            }

            self.redis.hset(key, data)
            self.redis.expire(key, Config.CACHE_TTL_METRICS)

            return True

        except Exception as e:
            logger.error(f"❌ Error caching volatility metrics for {instrument}: {e}")
            return False

    def get_volatility_metrics(self, instrument: str) -> Optional[Dict]:
        """
        Get cached volatility metrics for a pair

        Args:
            instrument: Instrument name

        Returns:
            Dictionary with volatility metrics
        """
        try:
            key = f"{self.PREFIX_METRICS}:{instrument}"
            return self.redis.hgetall(key) or None

        except Exception as e:
            logger.error(f"❌ Error getting cached metrics for {instrument}: {e}")
            return None

    def get_all_volatility_metrics(self) -> Dict[str, Dict]:
        """Get all cached volatility metrics"""
        try:
            metrics = {}

            for pair in Config.TRACKED_PAIRS:
                metric = self.get_volatility_metrics(pair)
                if metric:
                    metrics[pair] = metric

            return metrics

        except Exception as e:
            logger.error(f"❌ Error getting all cached metrics: {e}")
            return {}

    # ========== CORRELATION CACHING ==========

    def cache_correlation_matrix(self, correlation_data: Dict) -> bool:
        """
        Cache correlation matrix

        Args:
            correlation_data: Dictionary with pair correlations

        Returns:
            True if successful
        """
        try:
            key = f"{self.PREFIX_CORRELATION}:matrix"

            data = {
                "data": correlation_data,
                "cached_at": datetime.utcnow().isoformat(),
            }

            self.redis.set(key, data, ttl=Config.CACHE_TTL_CORRELATION)

            return True

        except Exception as e:
            logger.error(f"❌ Error caching correlation matrix: {e}")
            return False

    def get_correlation_matrix(self) -> Optional[Dict]:
        """Get cached correlation matrix"""
        try:
            key = f"{self.PREFIX_CORRELATION}:matrix"
            return self.redis.get(key)

        except Exception as e:
            logger.error(f"❌ Error getting cached correlation matrix: {e}")
            return None

    # ========== BEST PAIRS CACHING ==========

    def cache_best_pairs(self, best_pairs_list: List[Dict]) -> bool:
        """
        Cache best pairs recommendations

        Args:
            best_pairs_list: List of best pair recommendations

        Returns:
            True if successful
        """
        try:
            key = f"{self.PREFIX_BEST_PAIRS}:recommendations"

            data = {
                "pairs": best_pairs_list,
                "cached_at": datetime.utcnow().isoformat(),
                "count": len(best_pairs_list),
            }

            self.redis.set(key, data, ttl=Config.CACHE_TTL_CORRELATION)

            return True

        except Exception as e:
            logger.error(f"❌ Error caching best pairs: {e}")
            return False

    def get_best_pairs(self) -> Optional[List[Dict]]:
        """Get cached best pairs recommendations"""
        try:
            key = f"{self.PREFIX_BEST_PAIRS}:recommendations"
            data = self.redis.get(key)

            if data and isinstance(data, dict):
                return data.get("pairs", [])

            return None

        except Exception as e:
            logger.error(f"❌ Error getting cached best pairs: {e}")
            return None

    # ========== UTILITY METHODS ==========

    def cache_ready_check(self) -> bool:
        """Check if cache has essential data"""
        prices = self.get_all_prices()
        metrics = self.get_all_volatility_metrics()

        cache_ready = len(prices) > 0 and len(metrics) > 0

        if cache_ready:
            logger.info(f"✅ Cache ready: {len(prices)} prices, {len(metrics)} metrics")
        else:
            logger.warning(f"⚠️ Cache incomplete: {len(prices)} prices, {len(metrics)} metrics")

        return cache_ready

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        try:
            info = self.redis.info()

            stats = {
                "used_memory": info.get("used_memory_human", "N/A"),
                "used_memory_rss": info.get("used_memory_rss_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
                "expired_keys": info.get("expired_keys", 0),
                "evicted_keys": info.get("evicted_keys", 0),
            }

            return stats

        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {}

    def clear_cache(self) -> bool:
        """Clear all cached data"""
        try:
            self.redis.flush()
            logger.info("✅ Cache cleared")
            return True

        except Exception as e:
            logger.error(f"❌ Error clearing cache: {e}")
            return False


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get or create cache manager"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
