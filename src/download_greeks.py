#!/usr/bin/env python3
"""
Download Greeks history data for all symbol/expiration/date combinations.

This script downloads 5-second interval Greeks data from ThetaData API.
Run multiple instances in separate terminals for parallel processing.
"""

from database import ThetaDatabase
from api_client import ThetaDataAPI
from datetime import datetime
import os
import signal
import sys


def log_error(error_message: str, log_file: str = "errors.log"):
    """Log error message to errors.log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {error_message}\n")


def get_file_path(symbol: str, expiration: str, date: str) -> str:
    """
    Generate file path for Greeks data with monthly organization.

    Args:
        symbol: Option symbol (SPX or SPXW)
        expiration: Expiration date in YYYY-MM-DD format
        date: Quote date in YYYY-MM-DD format

    Returns:
        File path: data/{symbol}/{year}/{month}/{symbol}_{expiration}_{date}_5s.csv
    """
    # Extract year and month from quote date
    year = date[:4]
    month = date[5:7]

    # Convert dates to YYYYMMDD format for filename
    exp_formatted = expiration.replace("-", "")
    date_formatted = date.replace("-", "")

    # Build path
    base_dir = "/Volumes/X9/data"
    symbol_dir = os.path.join(base_dir, symbol)
    year_dir = os.path.join(symbol_dir, year)
    month_dir = os.path.join(year_dir, month)
    filename = f"{symbol}_{exp_formatted}_{date_formatted}_5s.csv"

    # Create directory if needed (thread-safe)
    os.makedirs(month_dir, exist_ok=True)

    return os.path.join(month_dir, filename)


class GreeksDownloader:
    """Simple downloader for Greeks history data."""

    def __init__(self, max_retries: int = 3):
        """
        Initialize downloader.

        Args:
            max_retries: Maximum retry attempts per download (default: 3)
        """
        self.max_retries = max_retries
        self.db = None
        self.api = None
        self.interrupted = False
        self.completed_count = 0
        self.failed_count = 0

    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\nShutdown requested by user...", flush=True)
        print("Finishing current download...", flush=True)
        self.interrupted = True

    def run(self):
        """Main download loop."""
        print("Starting Greeks downloader...", flush=True)

        # Initialize database
        print("Connecting to database...", flush=True)
        self.db = ThetaDatabase()
        self.db.connect()
        self.db.create_tables()
        self.db.set_busy_timeout(30000)  # 30 second timeout for concurrent access
        print("Database connected", flush=True)

        # Reset stuck rows from previous runs
        stuck_count = self.db.reset_stuck_rows(timeout_minutes=30)
        if stuck_count > 0:
            print(f"Reset {stuck_count} stuck rows from previous run", flush=True)

        # Initialize API client
        print("Initializing API client...", flush=True)
        self.api = ThetaDataAPI()

        # Get initial statistics
        stats = self.db.get_download_stats()
        pending = stats.get('pending', 0)
        completed = stats.get('completed', 0)
        failed = stats.get('failed', 0)
        total = stats.get('total', 0)

        print(f"\nStatus: Pending: {pending:,} | Completed: {completed:,} | Failed: {failed:,} | Total: {total:,}", flush=True)
        print("Starting download process...\n", flush=True)

        # Setup signal handler for Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)

        # Main download loop
        rows_processed = 0
        try:
            while not self.interrupted:
                # Claim next row
                row = self.db.claim_next_row(max_retries=self.max_retries)

                if not row:
                    # No more rows available
                    print("\nNo more pending rows available", flush=True)
                    break

                row_id, symbol, expiration, date = row
                rows_processed += 1

                print(f"[{rows_processed}] Processing: {symbol} {expiration} {date}", flush=True)

                try:
                    # Download Greeks data
                    csv_data = self.api.get_greeks_history(symbol, expiration, date)

                    # Generate file path
                    file_path = get_file_path(symbol, expiration, date)

                    # Write to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(csv_data)

                    file_size = os.path.getsize(file_path)
                    print(f"  Saved: {file_path} ({file_size:,} bytes)", flush=True)

                    # Mark as completed
                    self.db.mark_completed(row_id)
                    self.completed_count += 1

                except Exception as e:
                    error_msg = f"Error downloading {symbol} {expiration} {date}: {e}"
                    print(f"  {error_msg}", flush=True)
                    log_error(error_msg)

                    # Mark as failed (with retry logic)
                    status = self.db.mark_failed(row_id, str(e), self.max_retries)

                    if status == 'failed':
                        self.failed_count += 1
                        print(f"  Row permanently failed after {self.max_retries} attempts", flush=True)
                    else:
                        print(f"  Row will be retried later", flush=True)

            # Final statistics
            print(f"\nDownload session summary:", flush=True)
            print(f"  Rows processed this session: {rows_processed:,}", flush=True)
            print(f"  Completed: {self.completed_count:,}", flush=True)
            print(f"  Failed: {self.failed_count:,}", flush=True)

            # Get final database statistics
            final_stats = self.db.get_download_stats()
            print(f"\nFinal database status:", flush=True)
            print(f"  Pending: {final_stats.get('pending', 0):,}", flush=True)
            print(f"  Completed: {final_stats.get('completed', 0):,}", flush=True)
            print(f"  Failed: {final_stats.get('failed', 0):,}", flush=True)
            print(f"  Total: {final_stats.get('total', 0):,}", flush=True)

            if self.interrupted:
                print("\nInterrupted by user", flush=True)
            else:
                print("\nAll pending rows processed!", flush=True)

            print(f"Database: {self.db.db_path}", flush=True)

        except Exception as e:
            print(f"\nUnexpected error: {e}", flush=True)
            import traceback
            traceback.print_exc()

        finally:
            if self.db:
                self.db.close()


def main():
    """Main entry point."""
    downloader = GreeksDownloader(max_retries=3)
    downloader.run()


if __name__ == "__main__":
    main()
