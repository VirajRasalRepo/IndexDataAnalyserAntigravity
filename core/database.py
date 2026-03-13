"""
Database module for Index Data Analyser.
Handles MySQL connections with connection pooling and proper resource management.
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from mysql.connector.cursor import MySQLCursor
from mysql.connector.pooling import PooledMySQLConnection

from .config import Config

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections with connection pooling."""

    _pool: Optional[pooling.MySQLConnectionPool] = None

    @classmethod
    def initialize_pool(cls, pool_name: str = "analyzer_pool", pool_size: int = 5) -> None:
        """
        Initialize the connection pool.

        Args:
            pool_name: Name of the connection pool
            pool_size: Number of connections in the pool
        """
        if cls._pool is not None:
            logger.warning("Connection pool already initialized")
            return

        try:
            cls._pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name=pool_name,
                pool_size=pool_size,
                pool_reset_session=True,
                **Config.get_db_config()
            )
            logger.info(f"Database connection pool initialized with {pool_size} connections")
        except MySQLError as err:
            logger.error(f"Failed to create connection pool: {err}")
            raise

    @classmethod
    def get_connection(cls) -> PooledMySQLConnection:
        """
        Get a connection from the pool.

        Returns:
            A pooled MySQL connection

        Raises:
            RuntimeError: If connection pool is not initialized
            MySQLError: If connection fails
        """
        if cls._pool is None:
            raise RuntimeError("Connection pool not initialized. Call initialize_pool() first.")

        try:
            connection = cls._pool.get_connection()
            return connection
        except MySQLError as err:
            logger.error(f"Failed to get connection from pool: {err}")
            raise

    @classmethod
    @contextmanager
    def get_cursor(cls, dictionary: bool = False) -> Generator[MySQLCursor, None, None]:
        """
        Context manager for database cursor with automatic connection handling.

        Args:
            dictionary: If True, returns results as dictionaries

        Yields:
            MySQL cursor

        Example:
            with DatabaseManager.get_cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                results = cursor.fetchall()
        """
        connection = None
        cursor = None

        try:
            connection = cls.get_connection()
            cursor = connection.cursor(dictionary=dictionary, buffered=True)
            yield cursor
            connection.commit()
        except MySQLError as err:
            if connection:
                connection.rollback()
            logger.error(f"Database operation failed: {err}")
            raise
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    @classmethod
    def close_pool(cls) -> None:
        """Close all connections in the pool."""
        if cls._pool is not None:
            # Connection pools don't have a direct close method
            # Connections are closed when they're returned to the pool
            cls._pool = None
            logger.info("Database connection pool closed")


def execute_query(query: str, params: tuple = None, fetch: bool = False) -> Optional[list]:
    """
    Execute a SQL query with parameters.

    Args:
        query: SQL query string
        params: Query parameters
        fetch: If True, fetch and return results

    Returns:
        Query results if fetch=True, None otherwise

    Raises:
        MySQLError: If query execution fails
    """
    with DatabaseManager.get_cursor() as cursor:
        cursor.execute(query, params or ())
        if fetch:
            return cursor.fetchall()
    return None


def execute_many(query: str, data: list) -> int:
    """
    Execute a query with multiple parameter sets (batch insert).

    Args:
        query: SQL query string
        data: List of parameter tuples

    Returns:
        Number of affected rows

    Raises:
        MySQLError: If query execution fails
    """
    with DatabaseManager.get_cursor() as cursor:
        cursor.executemany(query, data)
        return cursor.rowcount
