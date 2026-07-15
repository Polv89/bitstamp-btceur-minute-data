#!/usr/bin/env python3
"""
Daily Price Updater Script

This script fetches BTC/EUR price data from Bitstamp API every 10 minutes
and saves it to a file containing only today's prices.

The file is updated every 10 minutes and resets at midnight UTC.

Usage:
    python -m scripts.daily_price_updater
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests


class BitstampPriceUpdater:
    """Manages daily BTC/EUR price updates from Bitstamp API."""

    API_URL = "https://www.bitstamp.net/api/v2/ticker/btceur/"
    OUTPUT_DIR = Path("data/daily")
    UPDATE_INTERVAL = 600  # 10 minutes in seconds

    def __init__(self):
        """Initialize the updater."""
        self.output_dir = self.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_date = None
        self.output_file = None

    def get_today_filename(self) -> Path:
        """Get the filename for today's date."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self.output_dir / f"btceur_prices_{today}.csv"

    def reset_for_new_day(self) -> bool:
        """Check if it's a new day and reset if necessary."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if today != self.current_date:
            self.current_date = today
            self.output_file = self.get_today_filename()
            # Create new file with header
            self._write_header()
            print(f"[{datetime.utcnow().isoformat()}] Starting new day: {today}")
            return True
        return False

    def _write_header(self):
        """Write CSV header to file."""
        with open(self.output_file, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "datetime", "bid", "ask", "last"]
            )
            writer.writeheader()

    def fetch_price_data(self) -> dict | None:
        """
        Fetch current BTC/EUR price data from Bitstamp API.

        Returns:
            Dictionary with price data or None if request fails.
        """
        try:
            response = requests.get(self.API_URL, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"[{datetime.utcnow().isoformat()}] Error fetching data: {e}")
            return None

    def save_price_data(self, data: dict):
        """
        Save price data to CSV file.

        Args:
            data: Dictionary containing price data from API.
        """
        if not data:
            return

        try:
            timestamp = int(data.get("timestamp", 0))
            dt = datetime.utcfromtimestamp(timestamp)

            row = {
                "timestamp": timestamp,
                "datetime": dt.isoformat(),
                "bid": data.get("bid", ""),
                "ask": data.get("ask", ""),
                "last": data.get("last", ""),
            }

            with open(self.output_file, "a", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["timestamp", "datetime", "bid", "ask", "last"]
                )
                writer.writerow(row)

            print(
                f"[{dt.isoformat()}] Saved - BID: {row['bid']}, "
                f"ASK: {row['ask']}, LAST: {row['last']}"
            )
        except Exception as e:
            print(f"[{datetime.utcnow().isoformat()}] Error saving data: {e}")

    def run(self, once: bool = False):
        """
        Run the price updater.

        Args:
            once: If True, fetch and save data only once then exit.
                 If False, run continuously with 10-minute intervals.
        """
        print("Starting BTC/EUR Daily Price Updater")
        print(f"Output directory: {self.output_dir.absolute()}")
        print(f"Update interval: {self.UPDATE_INTERVAL} seconds (10 minutes)")
        print(f"Running in {'once' if once else 'continuous'} mode")
        print()

        self.reset_for_new_day()

        try:
            while True:
                # Check if it's a new day
                self.reset_for_new_day()

                # Fetch and save data
                data = self.fetch_price_data()
                if data:
                    self.save_price_data(data)

                if once:
                    break

                # Wait for next update
                time.sleep(self.UPDATE_INTERVAL)

        except KeyboardInterrupt:
            print("\n[KeyboardInterrupt] Stopping price updater")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Update daily BTC/EUR prices from Bitstamp API"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fetch and save data once, then exit (for testing)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Update interval in seconds (default: 600 = 10 minutes)",
    )

    args = parser.parse_args()

    updater = BitstampPriceUpdater()
    updater.UPDATE_INTERVAL = args.interval

    updater.run(once=args.once)


if __name__ == "__main__":
    main()
