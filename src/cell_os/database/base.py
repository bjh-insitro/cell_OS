"""
Base repository class for database operations.
"""
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from abc import ABC, abstractmethod
from .connection_pool import ConnectionPoolManager


class BaseRepository(ABC):
    """Base repository with common CRUD operations."""
    
    def __init__(self, db_path: str, use_pooling: bool = True):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database
            use_pooling: Whether to use connection pooling (default: True)
        """
        self.db_path = db_path
        self.use_pooling = use_pooling
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        if use_pooling:
            self._pool_manager = ConnectionPoolManager()
            self._pool = self._pool_manager.get_pool(db_path)
        
        self._init_schema()
    
    @abstractmethod
    def _init_schema(self):
        """Initialize database schema. Must be implemented by subclasses."""
        pass
    
    def _get_raw_connection(self) -> sqlite3.Connection:
        """
        Get a raw database connection (not from pool).
        Use this for schema initialization and other setup tasks.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection (from pool if enabled)."""
        if self.use_pooling:
            # Return context manager for pooled connection
            return self._pool.get_connection()
        else:
            # Direct connection
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
    
    def _execute(self, query: str, params: Tuple = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor."""
        if self.use_pooling:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor
        else:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor
            finally:
                conn.close()
    
    def _fetch_one(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and fetch one result as dict."""
        if self.use_pooling:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
        else:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                row = cursor.fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
    
    def _fetch_all(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and fetch all results as list of dicts."""
        if self.use_pooling:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
    
    def _insert(self, table: str, data: Dict[str, Any]) -> int:
        """Insert a row and return last row id."""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor = self._execute(query, tuple(data.values()))
        return cursor.lastrowid
    
    def _update(self, table: str, data: Dict[str, Any], where: str, where_params: Tuple = ()) -> int:
        """Update rows and return number of affected rows."""
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {where}"
        cursor = self._execute(query, tuple(data.values()) + where_params)
        return cursor.rowcount
    
    def _delete(self, table: str, where: str, where_params: Tuple = ()) -> int:
        """Delete rows and return number of affected rows."""
        query = f"DELETE FROM {table} WHERE {where}"
        cursor = self._execute(query, where_params)
        return cursor.rowcount
