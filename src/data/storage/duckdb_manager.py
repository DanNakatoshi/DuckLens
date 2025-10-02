"""DuckDB database manager for local data storage."""

from contextlib import contextmanager
from datetime import datetime
from typing import Generator

import duckdb
from loguru import logger

from src.config.settings import settings
from src.models.schemas import StockPrice
from src.utils.exceptions import DatabaseError


class DuckDBManager:
    """Manager for DuckDB operations."""

    def __init__(self, db_path: str | None = None) -> None:
        """Initialize database manager."""
        self.db_path = db_path or settings.duckdb_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema."""
        try:
            with self.get_connection() as conn:
                # Create stock_prices table
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stock_prices (
                        symbol VARCHAR NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        open DECIMAL(18, 4) NOT NULL,
                        high DECIMAL(18, 4) NOT NULL,
                        low DECIMAL(18, 4) NOT NULL,
                        close DECIMAL(18, 4) NOT NULL,
                        volume BIGINT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (symbol, timestamp)
                    )
                """
                )

                # Create index for faster queries
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_stock_prices_symbol_timestamp
                    ON stock_prices(symbol, timestamp DESC)
                """
                )

                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {e}") from e

    @contextmanager
    def get_connection(self) -> Generator[duckdb.DuckDBPyConnection, None, None]:
        """Get database connection context manager."""
        conn = None
        try:
            conn = duckdb.connect(self.db_path)
            yield conn
        except Exception as e:
            raise DatabaseError(f"Database connection error: {e}") from e
        finally:
            if conn:
                conn.close()

    def insert_stock_prices(self, prices: list[StockPrice]) -> int:
        """Insert stock prices, skipping duplicates."""
        if not prices:
            return 0

        try:
            with self.get_connection() as conn:
                # Get count before insert
                before_count = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]

                # Batch insert using executemany
                conn.executemany(
                    """
                    INSERT INTO stock_prices (symbol, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (symbol, timestamp) DO NOTHING
                """,
                    [
                        (
                            p.symbol,
                            p.timestamp,
                            float(p.open),
                            float(p.high),
                            float(p.low),
                            float(p.close),
                            p.volume,
                        )
                        for p in prices
                    ],
                )

                # Get count after insert
                after_count = conn.execute("SELECT COUNT(*) FROM stock_prices").fetchone()[0]

                inserted_count = after_count - before_count
                logger.info(f"Inserted {inserted_count} new stock prices out of {len(prices)}")
                return inserted_count
        except Exception as e:
            raise DatabaseError(f"Failed to insert stock prices: {e}") from e

    def get_stock_prices(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[StockPrice]:
        """Retrieve stock prices with optional filters."""
        try:
            with self.get_connection() as conn:
                query = "SELECT symbol, timestamp, open, high, low, close, volume FROM stock_prices WHERE symbol = ?"
                params = [symbol]

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC"

                if limit:
                    query += f" LIMIT {limit}"

                result = conn.execute(query, params).fetchall()

                return [
                    StockPrice(
                        symbol=row[0],
                        timestamp=row[1],
                        open=row[2],
                        high=row[3],
                        low=row[4],
                        close=row[5],
                        volume=row[6],
                    )
                    for row in result
                ]
        except Exception as e:
            raise DatabaseError(f"Failed to retrieve stock prices: {e}") from e

    def get_latest_timestamp(self, symbol: str) -> datetime | None:
        """Get the latest timestamp for a symbol."""
        try:
            with self.get_connection() as conn:
                result = conn.execute(
                    "SELECT MAX(timestamp) FROM stock_prices WHERE symbol = ?",
                    [symbol],
                ).fetchone()
                return result[0] if result and result[0] else None
        except Exception as e:
            raise DatabaseError(f"Failed to get latest timestamp: {e}") from e

    def get_symbols(self) -> list[str]:
        """Get list of all symbols in database."""
        try:
            with self.get_connection() as conn:
                result = conn.execute(
                    "SELECT DISTINCT symbol FROM stock_prices ORDER BY symbol"
                ).fetchall()
                return [row[0] for row in result]
        except Exception as e:
            raise DatabaseError(f"Failed to get symbols: {e}") from e
