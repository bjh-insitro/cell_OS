"""
Tests for connection pooling and caching.
"""

import pytest
import tempfile
import os
import time
from cell_os.database.connection_pool import ConnectionPool, ConnectionPoolManager
from cell_os.database.cache import LRUCache, cached_query


class TestConnectionPool:
    
    def setup_method(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        
    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            
    def test_pool_creation(self):
        """Test creating a connection pool."""
        pool = ConnectionPool(self.temp_db.name, pool_size=3)
        assert pool.pool_size == 3
        assert pool._created_connections == 3
        pool.close_all()
        
    def test_get_connection(self):
        """Test getting connections from pool."""
        pool = ConnectionPool(self.temp_db.name, pool_size=2)
        
        with pool.get_connection() as conn:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER)")
            
        # Connection should be returned to pool
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            assert len(tables) == 1
            
        pool.close_all()
        
    def test_pool_exhaustion(self):
        """Test behavior when pool is exhausted."""
        pool = ConnectionPool(self.temp_db.name, pool_size=1)
        
        # This should work even though pool size is 1
        # (creates temporary connection)
        with pool.get_connection() as conn1:
            with pool.get_connection() as conn2:
                assert conn1 is not None
                assert conn2 is not None
                
        pool.close_all()


class TestConnectionPoolManager:
    
    def test_singleton(self):
        """Test that ConnectionPoolManager is a singleton."""
        manager1 = ConnectionPoolManager()
        manager2 = ConnectionPoolManager()
        assert manager1 is manager2
        
    def test_get_pool(self):
        """Test getting pools for different databases."""
        manager = ConnectionPoolManager()
        
        temp1 = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp1.close()
        temp2.close()
        
        try:
            pool1 = manager.get_pool(temp1.name)
            pool2 = manager.get_pool(temp2.name)
            
            # Should be different pools
            assert pool1 is not pool2
            
            # Getting same path should return same pool
            pool1_again = manager.get_pool(temp1.name)
            assert pool1 is pool1_again
            
        finally:
            manager.close_all_pools()
            os.unlink(temp1.name)
            os.unlink(temp2.name)


class TestLRUCache:
    
    def test_basic_operations(self):
        """Test basic cache get/set."""
        cache = LRUCache(max_size=3, default_ttl=0)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None
        
    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = LRUCache(max_size=2, default_ttl=0)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"
        
    def test_ttl_expiration(self):
        """Test TTL-based expiration."""
        cache = LRUCache(max_size=10, default_ttl=0.1)  # 100ms TTL
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        time.sleep(0.15)  # Wait for expiration
        assert cache.get("key1") is None
        
    def test_cache_stats(self):
        """Test cache statistics."""
        cache = LRUCache(max_size=10, default_ttl=0)
        
        cache.set("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5
        
    def test_invalidate(self):
        """Test cache invalidation."""
        cache = LRUCache(max_size=10, default_ttl=0)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        cache.invalidate("key1")
        assert cache.get("key1") is None


class TestCachedQueryDecorator:
    
    def test_cached_query(self):
        """Test @cached_query decorator."""
        call_count = [0]
        
        class MockRepo:
            @cached_query(ttl=60)
            def get_data(self, key: str):
                call_count[0] += 1
                return f"data_{key}"
        
        repo = MockRepo()
        
        # First call - cache miss
        result1 = repo.get_data("test")
        assert result1 == "data_test"
        assert call_count[0] == 1
        
        # Second call - cache hit
        result2 = repo.get_data("test")
        assert result2 == "data_test"
        assert call_count[0] == 1  # Should not increment
        
    def test_cache_invalidation(self):
        """Test cache invalidation in decorator."""
        call_count = [0]
        
        class MockRepo:
            @cached_query(ttl=60)
            def get_data(self, key: str):
                call_count[0] += 1
                return f"data_{key}"
        
        repo = MockRepo()
        
        repo.get_data("test")
        assert call_count[0] == 1
        
        # Clear cache
        repo.get_data.clear_cache()
        
        repo.get_data("test")
        assert call_count[0] == 2  # Should call again
