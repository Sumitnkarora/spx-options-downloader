#!/usr/bin/env python3
"""
Retry downloading quote dates for specific symbol/expiration combinations that failed previously.

Edit the FAILED_EXPIRATIONS list below to include the combinations you want to retry.
"""

from database import ThetaDatabase
from api_client import ThetaDataAPI
from datetime import datetime


# Edit this list with the symbol/expiration combinations you want to retry
FAILED_EXPIRATIONS = [
    ("SPXW", "2019-07-08"),
    ("SPXW", "2019-07-10"),
    ("SPXW", "2019-07-24"),
    ("SPXW", "2019-07-26"),
    ("SPXW", "2019-08-21"),
    ("SPXW", "2019-10-11"),
    ("SPXW", "2019-10-14"),
    ("SPXW", "2019-11-06"),
    ("SPXW", "2019-11-08"),
    ("SPXW", "2019-12-04"),
    ("SPXW", "2019-12-06"),
    ("SPXW", "2019-12-30"),
    ("SPXW", "2019-12-31"),
    ("SPXW", "2020-01-22"),
    ("SPXW", "2020-01-24"),
    ("SPXW", "2020-01-31"),
    ("SPXW", "2020-02-03"),
    ("SPXW", "2020-02-14"),
    ("SPXW", "2020-02-18"),
    ("SPXW", "2020-02-28"),
    ("SPXW", "2020-03-02"),
    ("SPXW", "2020-03-18"),
    ("SPXW", "2020-03-20"),
    ("SPXW", "2020-04-01"),
    ("SPX", "2012-06-16"),
    ("SPXW", "2024-06-04"),
    ("SPXW", "2024-06-05"),
]


def log_error(error_message: str, log_file: str = "errors.log"):
    """Log error message to errors.log file with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {error_message}\n")


def main():
    print("Starting retry failed dates downloader...", flush=True)

    # Initialize database
    print("Connecting to database...", flush=True)
    db = ThetaDatabase()
    db.connect()
    db.create_tables()
    print("Database connected", flush=True)

    # Initialize API client
    print("Initializing API client...", flush=True)
    api = ThetaDataAPI()

    try:
        if not FAILED_EXPIRATIONS:
            print("No expirations to retry. Edit FAILED_EXPIRATIONS list in the script.", flush=True)
            return

        print(f"Found {len(FAILED_EXPIRATIONS)} expirations to retry", flush=True)

        # Process each expiration
        for idx, (symbol, expiration) in enumerate(FAILED_EXPIRATIONS, 1):
            print(f"\n[{idx}/{len(FAILED_EXPIRATIONS)}] Processing: {symbol} {expiration}")

            try:
                # Fetch dates for this expiration
                dates = api.get_dates(symbol, expiration)

                if dates:
                    print(f"  Found {len(dates)} dates")
                    for date_sym, date_exp, date_value in dates:
                        print(f"    Inserting date: {date_value}")
                        db.insert_date(date_sym, date_exp, date_value)
                else:
                    print(f"  No dates found")
            except Exception as e:
                error_msg = f"Error processing {symbol} {expiration}: {e}"
                print(f"  {error_msg}")
                log_error(error_msg)

        print(f"\nDone! Total dates in database: {db.get_date_count()}")
        print(f"Database: {db.db_path}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        print(f"Partial progress - Dates in database: {db.get_date_count()}")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
