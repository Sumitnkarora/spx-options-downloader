#!/usr/bin/env python3
"""
Rename 'date' column to 'trade_date' in available_dates table.

The 'date' keyword is reserved in SQL, so renaming to 'trade_date' avoids
potential conflicts and improves code clarity.
"""

from database import ThetaDatabase
import sqlite3


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_rename_date_column(db: ThetaDatabase):
    """Rename 'date' column to 'trade_date' in available_dates table."""
    cursor = db.conn.cursor()

    print("Checking available_dates table schema...", flush=True)

    # Check current state
    has_date = check_column_exists(cursor, "available_dates", "date")
    has_trade_date = check_column_exists(cursor, "available_dates", "trade_date")

    if has_trade_date and not has_date:
        print("Column 'trade_date' already exists and 'date' is gone - migration already complete", flush=True)
        return

    if not has_date:
        print("ERROR: Column 'date' does not exist! Cannot proceed with migration.", flush=True)
        return

    if has_trade_date:
        print("WARNING: Both 'date' and 'trade_date' columns exist. Manual intervention needed.", flush=True)
        return

    # Perform migration using SQLite's RENAME COLUMN (requires SQLite 3.25.0+)
    print("Renaming column 'date' to 'trade_date'...", flush=True)

    try:
        # Try the simple rename first (SQLite 3.25.0+)
        cursor.execute("ALTER TABLE available_dates RENAME COLUMN date TO trade_date")
        db.conn.commit()
        print("Successfully renamed column using ALTER TABLE RENAME COLUMN", flush=True)
    except sqlite3.OperationalError as e:
        # If RENAME COLUMN not supported, use the traditional approach
        print(f"RENAME COLUMN not supported, using table recreation method: {e}", flush=True)

        # Get current table schema
        cursor.execute("PRAGMA table_info(available_dates)")
        columns = cursor.fetchall()

        # Build new table schema with renamed column
        print("Creating new table with renamed column...", flush=True)
        cursor.execute("""
            CREATE TABLE available_dates_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                expiration DATE NOT NULL,
                trade_date DATE NOT NULL,
                status TEXT DEFAULT 'pending',
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                error_message TEXT,
                compressed_file_path TEXT,
                UNIQUE(symbol, expiration, trade_date),
                FOREIGN KEY (symbol, expiration) REFERENCES expirations(symbol, expiration)
            )
        """)

        # Copy data from old table to new table
        print("Copying data to new table...", flush=True)
        cursor.execute("""
            INSERT INTO available_dates_new
                (id, symbol, expiration, trade_date, status, started_at, completed_at,
                 retry_count, error_message, compressed_file_path)
            SELECT
                id, symbol, expiration, date, status, started_at, completed_at,
                retry_count, error_message, compressed_file_path
            FROM available_dates
        """)

        # Drop old table
        print("Dropping old table...", flush=True)
        cursor.execute("DROP TABLE available_dates")

        # Rename new table
        print("Renaming new table...", flush=True)
        cursor.execute("ALTER TABLE available_dates_new RENAME TO available_dates")

        db.conn.commit()
        print("Successfully renamed column using table recreation method", flush=True)

    # Verify the change
    if check_column_exists(cursor, "available_dates", "trade_date"):
        print("✓ Column 'trade_date' now exists", flush=True)

    if not check_column_exists(cursor, "available_dates", "date"):
        print("✓ Column 'date' has been removed", flush=True)

    # Show statistics
    print("\nCurrent status breakdown:", flush=True)
    cursor.execute("""
        SELECT
            COALESCE(status, 'pending') as status,
            COUNT(*) as count
        FROM available_dates
        GROUP BY status
        ORDER BY
            CASE status
                WHEN 'completed' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'pending' THEN 3
                WHEN 'failed' THEN 4
                ELSE 5
            END
    """)

    for status, count in cursor.fetchall():
        print(f"  {status}: {count:,}", flush=True)

    # Total count
    cursor.execute("SELECT COUNT(*) FROM available_dates")
    total = cursor.fetchone()[0]
    print(f"  Total: {total:,}", flush=True)


def main():
    print("Starting trade_date migration...", flush=True)

    # Connect to database
    print("Connecting to database...", flush=True)
    db = ThetaDatabase()
    db.connect()
    print("Database connected", flush=True)

    try:
        # Run migration
        migrate_rename_date_column(db)

        print("\nMigration completed successfully!", flush=True)
        print(f"Database: {db.db_path}", flush=True)

    except Exception as e:
        print(f"\nError during migration: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
