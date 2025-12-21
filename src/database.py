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
