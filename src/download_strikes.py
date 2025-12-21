#!/usr/bin/env python3
"""
Download strikes for all expirations in the database from ThetaData.
"""

from database import ThetaDatabase
from api_client import ThetaDataAPI


def main():
    print("Starting strikes downloader...", flush=True)

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

            # Fetch strikes for this expiration
            strikes = api.get_strikes(symbol, expiration)

            if strikes:
                print(f"  Found {len(strikes)} strikes")
                for strike_sym, strike_exp, strike_price in strikes:
                    print(f"    Inserting strike: {strike_price}")
                    db.insert_strike(strike_sym, strike_exp, strike_price)
            else:
                print(f"  No strikes found")

        print(f"\nDone! Total strikes in database: {db.get_strike_count()}")
        print(f"Database: {db.db_path}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        print(f"Partial progress - Strikes in database: {db.get_strike_count()}")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
