#!/usr/bin/env python3
"""
Download quote dates for all expirations in the database from ThetaData.
"""

from database import ThetaDatabase
from api_client import ThetaDataAPI


def main():
    print("Starting dates downloader...", flush=True)

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
        # Get all expirations from database
        print("Fetching expirations from database...", flush=True)
        expirations = db.get_all_expirations()
        print(f"DEBUG: Got {len(expirations) if expirations else 0} expirations", flush=True)

        if not expirations:
            print("No expirations found in database. Run download_expirations.py first.", flush=True)
            return

        print(f"Found {len(expirations)} expirations in database", flush=True)

        # Process each expiration
        for idx, (symbol, expiration) in enumerate(expirations, 1):
            print(f"\n[{idx}/{len(expirations)}] Processing: {symbol} {expiration}")

            # Fetch dates for this expiration
            dates = api.get_dates(symbol, expiration)

            if dates:
                print(f"  Found {len(dates)} dates")
                for date_sym, date_exp, date_value in dates:
                    print(f"    Inserting date: {date_value}")
                    db.insert_date(date_sym, date_exp, date_value)
            else:
                print(f"  No dates found")

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
