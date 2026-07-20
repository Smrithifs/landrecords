"""
Cache service for managing Redis-based caching.
Handles caching of scraped data and session data.
"""

from typing import Optional, Any, Dict
import json
import asyncio


class CacheService:
    """Service for Redis-based caching."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize cache service.
        
        Args:
            config: Configuration dictionary containing Redis settings
        """
        self.config = config
        self.redis_host = config.get('redis_host', 'localhost')
        self.redis_port = config.get('redis_port', 6379)
        self.redis_db = config.get('redis_db', 0)
        self.redis_password = config.get('redis_password', None)
        self.default_ttl = config.get('default_ttl', 3600)
        self.redis_client = None
    
    async def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            import redis.asyncio as redis
            self.redis_client = await redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True
            )
            await self.redis_client.ping()
        except ImportError:
            print("Redis library not installed. Install with: pip install redis")
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
    
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis_client:
            return None
        
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Error getting from cache: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            print(f"Error setting cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Error deleting from cache: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            return await self.redis_client.exists(key) > 0
        except Exception as e:
            print(f"Error checking cache existence: {e}")
            return False
    
    async def get_or_set(self, key: str, value_func, ttl: Optional[int] = None) -> Any:
        """
        Get value from cache or set using provided function.
        
        Args:
            key: Cache key
            value_func: Async function to generate value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or newly generated value
        """
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        new_value = await value_func()
        await self.set(key, new_value, ttl)
        return new_value
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "scrape:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.redis_client:
            return 0
        
        try:
            keys = []
            async for key in self.redis_client.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Error clearing pattern: {e}")
            return 0
