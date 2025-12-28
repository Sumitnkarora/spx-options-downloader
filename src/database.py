import sqlite3
import os
from datetime import datetime
from typing import List, Tuple


class ThetaDatabase:
    def __init__(self, db_path: str = "database/theta_options.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self._ensure_database_directory()
        self.conn = None

    def _ensure_database_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

    def connect(self):
        """Connect to the SQLite database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        return self.conn

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

    def create_tables(self):
        """Create the expirations and strikes tables."""
        cursor = self.conn.cursor()

        # Create expirations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expirations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                expiration DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, expiration)
            )
        """)

        # Create strikes table with foreign key reference
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strikes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                expiration DATE NOT NULL,
                strike REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (symbol, expiration) REFERENCES expirations(symbol, expiration),
                UNIQUE(symbol, expiration, strike)
            )
        """)

        # Create available_dates table with foreign key reference
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS available_dates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                expiration DATE NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (symbol, expiration) REFERENCES expirations(symbol, expiration),
                UNIQUE(symbol, expiration, date)
            )
        """)

        self.conn.commit()
        print("Database tables created successfully")

    def insert_expiration(self, symbol: str, expiration: str):
        """
        Insert an expiration date for a symbol.

        Args:
            symbol: The option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO expirations (symbol, expiration) VALUES (?, ?)",
                (symbol, expiration)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting expiration {symbol} {expiration}: {e}")
            return None

    def insert_strike(self, symbol: str, expiration: str, strike: float):
        """
        Insert a strike price for a symbol and expiration.

        Args:
            symbol: The option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format
            strike: Strike price
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO strikes (symbol, expiration, strike) VALUES (?, ?, ?)",
                (symbol, expiration, strike)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting strike {symbol} {expiration} {strike}: {e}")
            return None

    def get_expiration_count(self) -> int:
        """Get total count of expirations."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM expirations")
        return cursor.fetchone()[0]

    def get_strike_count(self) -> int:
        """Get total count of strikes."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM strikes")
        return cursor.fetchone()[0]

    def get_all_expirations(self) -> List[Tuple[str, str]]:
        """Get all expirations from the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT symbol, expiration FROM expirations ORDER BY symbol, expiration")
        return cursor.fetchall()

    def insert_date(self, symbol: str, expiration: str, date: str):
        """
        Insert a quote date for a symbol and expiration.

        Args:
            symbol: The option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format
            date: Quote date in YYYY-MM-DD format
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO available_dates (symbol, expiration, date) VALUES (?, ?, ?)",
                (symbol, expiration, date)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting date {symbol} {expiration} {date}: {e}")
            return None

    def get_date_count(self) -> int:
        """Get total count of available dates."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM available_dates")
        return cursor.fetchone()[0]

    def set_busy_timeout(self, timeout_ms: int = 30000):
        """
        Set SQLite busy timeout for handling concurrent access.

        Args:
            timeout_ms: Timeout in milliseconds (default: 30 seconds)
        """
        self.conn.execute(f"PRAGMA busy_timeout = {timeout_ms}")

    def claim_next_row(self, max_retries: int = 3) -> Tuple[int, str, str, str]:
        """
        Atomically claim next pending row for processing.

        Args:
            max_retries: Maximum number of retries allowed

        Returns:
            Tuple of (row_id, symbol, expiration, date) or None if no rows available
        """
        cursor = self.conn.cursor()
        try:
            # Begin immediate transaction to acquire write lock
            self.conn.execute("BEGIN IMMEDIATE")

            # Find next available row (latest first)
            cursor.execute("""
                SELECT id, symbol, expiration, date
                FROM available_dates
                WHERE status = 'pending' AND retry_count < ?
                ORDER BY expiration DESC, date DESC
                LIMIT 1
            """, (max_retries,))

            row = cursor.fetchone()
            if not row:
                self.conn.rollback()
                return None

            row_id, symbol, expiration, date = row

            # Claim the row
            cursor.execute("""
                UPDATE available_dates
                SET status = 'in_progress',
                    started_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (row_id,))

            self.conn.commit()
            return (row_id, symbol, expiration, date)

        except sqlite3.Error as e:
            self.conn.rollback()
            raise

    def mark_completed(self, row_id: int):
        """
        Mark a row as successfully completed.

        Args:
            row_id: The row ID to mark as completed
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE available_dates
            SET status = 'completed',
                completed_at = CURRENT_TIMESTAMP,
                error_message = NULL
            WHERE id = ?
        """, (row_id,))
        self.conn.commit()

    def mark_failed(self, row_id: int, error_msg: str, max_retries: int = 3):
        """
        Mark a row as failed and increment retry count.

        Args:
            row_id: The row ID to mark as failed
            error_msg: Error message to store
            max_retries: Maximum retries before marking permanently failed

        Returns:
            The new status ('pending' if will retry, 'failed' if giving up)
        """
        cursor = self.conn.cursor()

        # Get current retry count
        cursor.execute("SELECT retry_count FROM available_dates WHERE id = ?", (row_id,))
        result = cursor.fetchone()
        if not result:
            return None

        retry_count = result[0]
        new_retry_count = retry_count + 1
        new_status = 'failed' if new_retry_count >= max_retries else 'pending'

        cursor.execute("""
            UPDATE available_dates
            SET status = ?,
                retry_count = ?,
                error_message = ?,
                completed_at = CASE WHEN ? = 'failed' THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE id = ?
        """, (new_status, new_retry_count, error_msg, new_status, row_id))

        self.conn.commit()
        return new_status

    def reset_stuck_rows(self, timeout_minutes: int = 30) -> int:
        """
        Reset rows stuck in 'in_progress' state back to pending.

        Args:
            timeout_minutes: How long a row can be in_progress before considered stuck

        Returns:
            Number of rows reset
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE available_dates
            SET status = 'pending',
                error_message = 'Reset from stuck in_progress state'
            WHERE status = 'in_progress'
            AND started_at < datetime('now', '-' || ? || ' minutes')
        """, (timeout_minutes,))

        reset_count = cursor.rowcount
        self.conn.commit()

        return reset_count

    def get_download_stats(self) -> dict:
        """
        Get download statistics by status.

        Returns:
            Dictionary with counts for each status
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                COALESCE(status, 'pending') as status,
                COUNT(*) as count
            FROM available_dates
            GROUP BY status
        """)

        stats = {}
        for status, count in cursor.fetchall():
            stats[status] = count

        # Get total
        cursor.execute("SELECT COUNT(*) FROM available_dates")
        stats['total'] = cursor.fetchone()[0]

        return stats

    def update_compressed_file_path(self, row_id: int, file_path: str):
        """
        Store the compressed file path for a row.

        Args:
            row_id: The row ID to update
            file_path: Full path to the compressed .zst file
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE available_dates
            SET compressed_file_path = ?
            WHERE id = ?
        """, (file_path, row_id))
        self.conn.commit()
