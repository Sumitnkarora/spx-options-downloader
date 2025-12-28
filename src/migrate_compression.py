#!/usr/bin/env python3
"""
Add compressed_file_path column to available_dates table.

This column stores the full path to the compressed .zst file.
"""

from database import ThetaDatabase
import sqlite3


def check_column_exists(cursor, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def migrate_compression_column(db: ThetaDatabase):
    """Add compressed_file_path column to available_dates table."""
    cursor = db.conn.cursor()

    print("Checking available_dates table schema...", flush=True)

    # Check if compressed_file_path column exists
    if not check_column_exists(cursor, "available_dates", "compressed_file_path"):
        print("Adding column: compressed_file_path...", flush=True)
        cursor.execute("ALTER TABLE available_dates ADD COLUMN compressed_file_path TEXT")
        db.conn.commit()
        print("Added compressed_file_path column to available_dates table", flush=True)
    else:
        print("Column compressed_file_path already exists, skipping", flush=True)

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
    print("Starting compression migration...", flush=True)

    # Connect to database
    print("Connecting to database...", flush=True)
    db = ThetaDatabase()
    db.connect()
    print("Database connected", flush=True)

    try:
        # Run migration
        migrate_compression_column(db)

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
