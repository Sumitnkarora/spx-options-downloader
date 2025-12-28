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
import configparser
import zstandard as zstd


def log_error(error_message: str, log_file: str = "errors.log"):
    """Log error message to errors.log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {error_message}\n")


def get_file_path(symbol: str, expiration: str, trade_date: str, base_dir: str, interval: str) -> str:
    """
    Generate file path for Greeks data with monthly organization.

    Args:
        symbol: Option symbol (SPX or SPXW)
        expiration: Expiration date in YYYY-MM-DD format
        trade_date: Quote date in YYYY-MM-DD format
        base_dir: Base directory path for data storage
        interval: Data interval (e.g., "5s", "1m")

    Returns:
        File path: {base_dir}/{symbol}/{year}/{month}/{symbol}_{expiration}_{trade_date}_{interval}.csv
    """
    # Extract year and month from quote date
    year = trade_date[:4]
    month = trade_date[5:7]

    # Convert dates to YYYYMMDD format for filename
    exp_formatted = expiration.replace("-", "")
    date_formatted = trade_date.replace("-", "")

    # Build path
    symbol_dir = os.path.join(base_dir, symbol)
    year_dir = os.path.join(symbol_dir, year)
    month_dir = os.path.join(year_dir, month)
    filename = f"{symbol}_{exp_formatted}_{date_formatted}_{interval}.csv"

    # Create directory if needed (thread-safe)
    os.makedirs(month_dir, exist_ok=True)

    return os.path.join(month_dir, filename)


class GreeksDownloader:
    """Simple downloader for Greeks history data."""

    def __init__(self, base_dir: str = "/Volumes/X9/data", interval: str = "5s", max_retries: int = 3):
        """
        Initialize downloader.

        Args:
            base_dir: Base directory path for data storage (default: /Volumes/X9/data)
            interval: Data interval (default: 5s)
            max_retries: Maximum retry attempts per download (default: 3)
        """
        self.base_dir = base_dir
        self.interval = interval
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

                row_id, symbol, expiration, trade_date = row
                rows_processed += 1

                print(f"[{rows_processed}] Processing: {symbol} {expiration} {trade_date}", flush=True)

                try:
                    # Download Greeks data
                    csv_data = self.api.get_greeks_history(symbol, expiration, trade_date, self.interval)

                    # Generate file path
                    file_path = get_file_path(symbol, expiration, trade_date, self.base_dir, self.interval)

                    # Write CSV to file (temporary)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(csv_data)

                    csv_size = os.path.getsize(file_path)
                    print(f"  Saved CSV: {file_path} ({csv_size:,} bytes)", flush=True)

                    # Compress the file with zstd level 10
                    compressed_path = file_path + ".zst"
                    print(f"  Compressing...", flush=True)

                    cctx = zstd.ZstdCompressor(level=10)
                    with open(file_path, 'rb') as input_file:
                        with open(compressed_path, 'wb') as compressed_file:
                            cctx.copy_stream(input_file, compressed_file)

                    compressed_size = os.path.getsize(compressed_path)
                    compression_ratio = csv_size / compressed_size if compressed_size > 0 else 0
                    print(f"  Compressed: {compressed_path} ({compressed_size:,} bytes, {compression_ratio:.1f}x)", flush=True)

                    # Delete original CSV file
                    os.remove(file_path)
                    print(f"  Deleted original CSV", flush=True)

                    # Store compressed file path in database
                    self.db.update_compressed_file_path(row_id, compressed_path)

                    # Mark as completed
                    self.db.mark_completed(row_id)
                    self.completed_count += 1

                except Exception as e:
                    error_msg = f"Error downloading {symbol} {expiration} {trade_date}: {e}"
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


def load_config(config_path: str = "config.ini"):
    """
    Load configuration from config file.

    Args:
        config_path: Path to config file (default: config.ini)

    Returns:
        Dictionary with configuration settings
    """
    config = configparser.ConfigParser()

    # Default values
    defaults = {
        'base_dir': '/Volumes/X9/data',
        'interval': '5s',
        'max_retries': 3
    }

    # Try to read config file
    if os.path.exists(config_path):
        config.read(config_path)
        if 'download' in config:
            base_dir = config.get('download', 'base_dir', fallback=defaults['base_dir'])
            interval = config.get('download', 'interval', fallback=defaults['interval'])
            max_retries = config.getint('download', 'max_retries', fallback=defaults['max_retries'])
        else:
            print(f"Warning: No [download] section in {config_path}, using defaults", flush=True)
            base_dir = defaults['base_dir']
            interval = defaults['interval']
            max_retries = defaults['max_retries']
    else:
        print(f"Warning: Config file {config_path} not found, using defaults", flush=True)
        base_dir = defaults['base_dir']
        interval = defaults['interval']
        max_retries = defaults['max_retries']

    return {
        'base_dir': base_dir,
        'interval': interval,
        'max_retries': max_retries
    }


def main():
    """Main entry point."""
    # Load configuration from config.ini
    config = load_config("config.ini")

    print(f"Configuration (from config.ini):", flush=True)
    print(f"  Base directory: {config['base_dir']}", flush=True)
    print(f"  Interval: {config['interval']}", flush=True)
    print(f"  Max retries: {config['max_retries']}", flush=True)
    print("", flush=True)

    downloader = GreeksDownloader(
        base_dir=config['base_dir'],
        interval=config['interval'],
        max_retries=config['max_retries']
    )
    downloader.run()


if __name__ == "__main__":
    main()
