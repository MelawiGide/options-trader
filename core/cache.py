"""
Cache manager for API responses.

Caching is critical for:
1. Performance - avoid redundant API calls
2. Rate limiting - respect API limits
3. Cost reduction - minimize paid API usage
"""
import hashlib
import pickle
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
import logging

from diskcache import Cache

from config import paths

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Thread-safe disk-based cache with TTL support.

    Why diskcache over redis?
    - No external dependencies
    - Persistent across restarts
    - Perfect for single-user applications
    """

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or paths.cache_dir
        self.cache = Cache(directory=str(self.cache_dir))
        logger.info(f"Cache initialized at: {self.cache_dir}")

    def _generate_key(self, symbol: str, data_type: str, **kwargs) -> str:
        """
        Generate a unique cache key.

        Examples:
        - AAPL:quote:()
        - SPY:chain:(expiry='2024-02-23')
        - TSLA:iv:(period=30)
        """
        # Sort kwargs for consistent keys
        params = sorted(kwargs.items())
        key_string = f"{symbol}:{data_type}:{params}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, symbol: str, data_type: str, **kwargs) -> Optional[Any]:
        """
        Retrieve cached data if available and not expired.

        Returns None if cache miss or expired.
        """
        key = self._generate_key(symbol, data_type, **kwargs)

        try:
            cached_data = self.cache.get(key)
            if cached_data is None:
                logger.debug(f"Cache miss: {key[:8]}...")
                return None

            # Check if data has expired
            if datetime.now() > cached_data['expires']:
                logger.debug(f"Cache expired: {key[:8]}...")
                self.cache.delete(key)
                return None

            logger.debug(f"Cache hit: {key[:8]}...")
            return cached_data['data']

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, symbol: str, data_type: str, data: Any,
            ttl_seconds: int = 300, **kwargs) -> None:
        """
        Store data in cache with TTL.

        Args:
            symbol: Stock/option symbol
            data_type: Type of data (quote, chain, iv, etc.)
            data: The data to cache
            ttl_seconds: Time-to-live in seconds
            **kwargs: Additional parameters for key generation
        """
        key = self._generate_key(symbol, data_type, **kwargs)
        expires = datetime.now() + timedelta(seconds=ttl_seconds)

        try:
            self.cache.set(key, {
                'data': data,
                'expires': expires,
                'cached_at': datetime.now()
            })
            logger.debug(f"Cached: {key[:8]}... (TTL: {ttl_seconds}s)")

        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            'size': len(self.cache),
            'directory': str(self.cache_dir)
        }
