"""
Database connection pooling for SQLite.

Provides a simple connection pool to reduce overhead of opening/closing
database connections frequently.
"""

import sqlite3
import threading
from typing import Dict, Optional
from queue import Queue, Empty
from contextlib import contextmanager


class ConnectionPool:
    """Thread-safe connection pool for SQLite databases."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        """
        Initialize connection pool.
        
        Args:
            db_path: Path to SQLite database
            pool_size: Maximum number of connections to maintain
        """
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._created_connections = 0
        
        # Pre-create connections
        for _ in range(pool_size):
            self._pool.put(self._create_connection())
            
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        self._created_connections += 1
        return conn
        
    @contextmanager
    def get_connection(self):
        """
        Get a connection from the pool.
        
        Yields:
            sqlite3.Connection: Database connection
        """
        conn = None
        try:
            # Try to get from pool with timeout
            try:
                conn = self._pool.get(timeout=5.0)
            except Empty:
                # Pool exhausted, create temporary connection
                conn = self._create_connection()
                
            yield conn
            
        finally:
            if conn:
                try:
                    # Return to pool if space available
                    self._pool.put_nowait(conn)
                except:
                    # Pool full, close the connection
                    conn.close()
                    
    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break


class ConnectionPoolManager:
    """Singleton manager for database connection pools."""
    
    _instance: Optional['ConnectionPoolManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._pools: Dict[str, ConnectionPool] = {}
        return cls._instance
        
    def get_pool(self, db_path: str, pool_size: int = 5) -> ConnectionPool:
        """
        Get or create a connection pool for a database.
        
        Args:
            db_path: Path to database
            pool_size: Size of connection pool
            
        Returns:
            ConnectionPool for the database
        """
        if db_path not in self._pools:
            with self._lock:
                if db_path not in self._pools:
                    self._pools[db_path] = ConnectionPool(db_path, pool_size)
        return self._pools[db_path]
        
    def close_all_pools(self):
        """Close all connection pools."""
        with self._lock:
            for pool in self._pools.values():
                pool.close_all()
            self._pools.clear()
