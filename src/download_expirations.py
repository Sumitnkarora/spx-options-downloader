#!/usr/bin/env python3
"""
Download expirations for SPX and SPXW symbols from ThetaData.
"""

from database import ThetaDatabase
from api_client import ThetaDataAPI


def main():
    print("Starting expirations downloader...")

    # Initialize database
    db = ThetaDatabase()
    db.connect()
    db.create_tables()

    # Initialize API client
    api = ThetaDataAPI()

    # Symbols to download
    symbols = ["SPX", "SPXW"]

    try:
        for symbol in symbols:
            print(f"\nProcessing {symbol}...")

            # Fetch expirations
            expirations = api.get_expirations(symbol)

            if not expirations:
                print(f"No expirations found for {symbol}")
                continue

            print(f"Found {len(expirations)} expirations for {symbol}")

            # Insert each expiration
            for sym, expiration in expirations:
                print(f"Inserting expiration: {sym} {expiration}")
                db.insert_expiration(sym, expiration)

        print(f"\nDone! Total expirations in database: {db.get_expiration_count()}")
        print(f"Database: {db.db_path}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
