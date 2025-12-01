"""
Query result caching for database repositories.

Provides LRU cache with TTL for expensive database queries.
"""

import time
import threading
from typing import Any, Optional, Callable, Dict, Tuple
from functools import wraps
from collections import OrderedDict


class CacheEntry:
    """Cache entry with value and expiration time."""
    
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.time() + ttl if ttl > 0 else float('inf')
        
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expires_at


class LRUCache:
    """Thread-safe LRU cache with TTL support."""
    
    def __init__(self, max_size: int = 100, default_ttl: float = 300):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default time-to-live in seconds (0 = no expiration)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
                
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
                
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.value
            
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                
            ttl = ttl if ttl is not None else self.default_ttl
            self._cache[key] = CacheEntry(value, ttl)
            self._cache.move_to_end(key)
            
            # Evict oldest if over capacity
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
                
    def invalidate(self, key: str):
        """Remove entry from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                
    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = self._hits / total if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate
            }


def cached_query(ttl: float = 300, key_func: Optional[Callable] = None):
    """
    Decorator for caching query results.
    
    Args:
        ttl: Time-to-live in seconds
        key_func: Function to generate cache key from args/kwargs
                 (default: uses function name and str(args))
    
    Example:
        @cached_query(ttl=60)
        def get_cell_line(self, cell_line_id: str):
            # Expensive query
            return result
    """
    def decorator(func: Callable) -> Callable:
        cache = LRUCache(max_size=100, default_ttl=ttl)
        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                
            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                return result
                
            # Cache miss - execute query
            result = func(self, *args, **kwargs)
            
            # Cache result
            cache.set(cache_key, result, ttl)
            
            return result
            
        # Attach cache management methods
        wrapper.cache = cache
        wrapper.invalidate_cache = lambda key: cache.invalidate(key)
        wrapper.clear_cache = cache.clear
        wrapper.get_cache_stats = cache.get_stats
        
        return wrapper
    return decorator
