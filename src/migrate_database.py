#!/usr/bin/env python3
"""
Migrate the available_dates table to add columns for download tracking.

Adds 5 new columns:
- status: pending, in_progress, completed, failed
- started_at: timestamp when download started
- completed_at: timestamp when download finished
- retry_count: number of retry attempts (0-3)
- error_message: last error message for debugging
"""

from database import ThetaDatabase
import sqlite3


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_available_dates(db: ThetaDatabase):
    """Add download tracking columns to available_dates table."""
    cursor = db.conn.cursor()

    print("Checking available_dates table schema...", flush=True)

    # Check which columns need to be added
    columns_to_add = [
        ("status", "TEXT DEFAULT 'pending'"),
        ("started_at", "TIMESTAMP"),
        ("completed_at", "TIMESTAMP"),
        ("retry_count", "INTEGER DEFAULT 0"),
        ("error_message", "TEXT")
    ]

    columns_added = 0

    for column_name, column_def in columns_to_add:
        if not check_column_exists(cursor, "available_dates", column_name):
            print(f"Adding column: {column_name}...", flush=True)
            cursor.execute(f"ALTER TABLE available_dates ADD COLUMN {column_name} {column_def}")
            columns_added += 1
        else:
            print(f"Column {column_name} already exists, skipping", flush=True)

    if columns_added > 0:
        db.conn.commit()
        print(f"\nAdded {columns_added} new columns to available_dates table", flush=True)
    else:
        print("\nAll columns already exist, no migration needed", flush=True)

    # Reset any stuck rows from previous runs
    print("\nChecking for stuck rows (in_progress for more than 30 minutes)...", flush=True)
    cursor.execute("""
        SELECT COUNT(*) FROM available_dates
        WHERE status = 'in_progress'
        AND started_at < datetime('now', '-30 minutes')
    """)
    stuck_count = cursor.fetchone()[0]

    if stuck_count > 0:
        print(f"Found {stuck_count} stuck rows, resetting to pending...", flush=True)
        cursor.execute("""
            UPDATE available_dates
            SET status = 'pending',
                error_message = 'Reset from stuck in_progress state'
            WHERE status = 'in_progress'
            AND started_at < datetime('now', '-30 minutes')
        """)
        db.conn.commit()
        print(f"Reset {stuck_count} stuck rows to pending", flush=True)
    else:
        print("No stuck rows found", flush=True)

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
    print("Starting database migration...", flush=True)

    # Connect to database
    print("Connecting to database...", flush=True)
    db = ThetaDatabase()
    db.connect()
    print("Database connected", flush=True)

    try:
        # Ensure tables exist
        db.create_tables()

        # Run migration
        migrate_available_dates(db)

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
