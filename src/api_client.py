import requests
import csv
from typing import List, Tuple
from datetime import datetime
from io import StringIO


class ThetaDataAPI:
    def __init__(self, base_url: str = "http://localhost:25503"):
        """Initialize ThetaData API client."""
        self.base_url = base_url

    def _convert_date_to_api_format(self, date_str: str) -> str:
        """
        Convert date from YYYY-MM-DD to YYYYMMDD format for API calls.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Date in YYYYMMDD format
        """
        return date_str.replace("-", "")

    def _parse_csv_response(self, response_text: str) -> List[List[str]]:
        """
        Parse CSV response from ThetaData API.

        Args:
            response_text: Raw response text from API

        Returns:
            List of rows, where each row is a list of column values
        """
        if not response_text.strip():
            return []

        # Use CSV reader to properly handle quoted values
        csv_file = StringIO(response_text)
        reader = csv.reader(csv_file)

        # Skip header row and parse data rows
        data_rows = []
        next(reader, None)  # Skip header
        for row in reader:
            if row:  # Skip empty rows
                data_rows.append(row)

        return data_rows

    def get_expirations(self, symbol: str) -> List[Tuple[str, str]]:
        """
        Fetch all expiration dates for a given symbol.

        Args:
            symbol: Option symbol (SPX or SPXW)

        Returns:
            List of tuples (symbol, expiration) where expiration is in YYYY-MM-DD format
        """
        url = f"{self.base_url}/v3/option/list/expirations"
        params = {"symbol": symbol}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data_rows = self._parse_csv_response(response.text)
            expirations = []

            for row in data_rows:
                if len(row) >= 2:
                    sym = row[0].strip()
                    exp_date = row[1].strip()
                    expirations.append((sym, exp_date))

            return expirations

        except requests.exceptions.RequestException as e:
            print(f"Error fetching expirations for {symbol}: {e}")
            return []

    def get_strikes(self, symbol: str, expiration: str) -> List[Tuple[str, str, float]]:
        """
        Fetch all strike prices for a given symbol and expiration.

        Args:
            symbol: Option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format

        Returns:
            List of tuples (symbol, expiration, strike)
        """
        # Convert date from YYYY-MM-DD to YYYYMMDD for API call
        expiration_api_format = self._convert_date_to_api_format(expiration)

        url = f"{self.base_url}/v3/option/list/strikes"
        params = {
            "symbol": symbol,
            "expiration": expiration_api_format
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data_rows = self._parse_csv_response(response.text)
        strikes = []

        for row in data_rows:
            if len(row) >= 2:
                try:
                    strike_price = float(row[1].strip())
                    # Store with original YYYY-MM-DD format
                    strikes.append((symbol, expiration, strike_price))
                except ValueError:
                    print(f"Invalid strike value: {row[1]}")
                    continue

        return strikes

    def get_dates(self, symbol: str, expiration: str) -> List[Tuple[str, str, str]]:
        """
        Fetch all quote dates for a given symbol and expiration.

        Args:
            symbol: Option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format

        Returns:
            List of tuples (symbol, expiration, trade_date)
        """
        # Convert date from YYYY-MM-DD to YYYYMMDD for API call
        expiration_api_format = self._convert_date_to_api_format(expiration)

        url = f"{self.base_url}/v3/option/list/dates/quote"
        params = {
            "symbol": symbol,
            "expiration": expiration_api_format
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data_rows = self._parse_csv_response(response.text)
        dates = []

        for row in data_rows:
            if len(row) >= 1:
                date_value = row[0].strip()
                # Store with original YYYY-MM-DD format
                dates.append((symbol, expiration, date_value))

        return dates

    def get_greeks_history(self, symbol: str, expiration: str, trade_date: str, interval: str = "5s") -> str:
        """
        Fetch Greeks history data for a given symbol, expiration, and date.

        Args:
            symbol: Option symbol (SPX or SPXW)
            expiration: Expiration date in YYYY-MM-DD format
            trade_date: Quote date in YYYY-MM-DD format
            interval: Data interval (default: "5s", options: "1s", "5s", "10s", "15s", "30s", "1m", "5m", etc.)

        Returns:
            Raw CSV string containing Greeks data

        Raises:
            requests.exceptions.RequestException: On API errors
        """
        # Convert dates from YYYY-MM-DD to YYYYMMDD for API call
        expiration_api_format = self._convert_date_to_api_format(expiration)
        date_api_format = self._convert_date_to_api_format(trade_date)

        url = f"{self.base_url}/v3/option/history/greeks/all"
        params = {
            "symbol": symbol,
            "expiration": expiration_api_format,
            "date": date_api_format,
            "interval": interval
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.text
