import logging
import os
from datetime import datetime, timezone
from typing import List, Tuple

import pandas as pd
import requests

# Configuration
CURRENCY_PAIRS = ["btceur", "btcusd"]  # entrambi i pair
DAILY_MINUTE_PATHS = {
    "btceur": "data/updates/btceur_bitstamp_1min_latest.csv",
    "btcusd": "data/updates/btcusd_bitstamp_1min_latest.csv",
}
DAILY_OHLC_PATHS = {
    "btceur": "data/updates/btceur_bitstamp_daily.csv",
    "btcusd": "data/updates/btcusd_bitstamp_daily.csv",
}
COLUMN_NAMES = ["timestamp", "open", "high", "low", "close", "volume"]

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)


def fetch_bitstamp_data(
    currency_pair: str,
    start_timestamp: int,
    end_timestamp: int,
    step: int = 60,
    limit: int = 1000,
) -> List[dict]:
    url = f"https://www.bitstamp.net/api/v2/ohlc/{currency_pair}/"
    params = {
        "step": step,
        "start": start_timestamp,
        "end": end_timestamp,
        "limit": limit,
    }
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json().get("data", {}).get("ohlc", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching data for {currency_pair}: {e}")
        return []


def ensure_seed_files() -> None:
    """Create seed files for both pairs if they don't exist."""
    seed_timestamp = 1293840000  # 2011-01-01
    seed_line = f"{seed_timestamp},0.0,0.0,0.0,0.0,0.0\n"
    header = "timestamp,open,high,low,close,volume\n"
    for pair in CURRENCY_PAIRS:
        path = DAILY_MINUTE_PATHS[pair]
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(header + seed_line)
            logger.info(f"Created seed file {path}")


def check_missing_intervals(df: pd.DataFrame) -> Tuple[int, int]:
    last_timestamp = int(df["timestamp"].max())
    current_timestamp = int(
        datetime.now(timezone.utc).replace(second=0, microsecond=0).timestamp()
    ) - 60
    if last_timestamp >= current_timestamp:
        logger.info(
            f"Data already up to date (last_timestamp: {last_timestamp}, current_timestamp: {current_timestamp})"
        )
        return None
    return last_timestamp + 60, current_timestamp


def fetch_and_append_missing_data(
    currency_pair: str,
    missing_interval: Tuple[int, int],
    existing_df: pd.DataFrame,
) -> pd.DataFrame:
    all_new_data = []
    start_timestamp, end_timestamp = missing_interval
    logger.info(f"[{currency_pair}] Missing data: from {start_timestamp} to {end_timestamp}")

    while start_timestamp < end_timestamp:
        remaining_minutes = (end_timestamp - start_timestamp) // 60
        limit = min(1000, remaining_minutes)
        if limit <= 0:
            break
        window_end = min(start_timestamp + ((limit - 1) * 60), end_timestamp)

        logger.info(f"[{currency_pair}] Fetching {limit} rows from {start_timestamp} to {window_end}")
        new_data = fetch_bitstamp_data(currency_pair, start_timestamp, window_end, limit=limit)

        if new_data:
            df_new = pd.DataFrame(new_data)
            df_new["timestamp"] = pd.to_numeric(df_new["timestamp"], errors="coerce")
            df_new.columns = COLUMN_NAMES
            all_new_data.append(df_new)
            last_ts = int(df_new["timestamp"].max())
            start_timestamp = last_ts + 60
        else:
            logger.warning(f"[{currency_pair}] No data for interval {start_timestamp}-{window_end}")
            start_timestamp = window_end + 60
            continue

    if all_new_data:
        updated_df = pd.concat([existing_df] + all_new_data, ignore_index=True)
        updated_df.drop_duplicates(subset="timestamp", inplace=True)
        updated_df.sort_values("timestamp", ascending=True, inplace=True)
        logger.info(f"[{currency_pair}] Total records after update: {len(updated_df)}")
        return updated_df
    else:
        logger.info(f"[{currency_pair}] No new data found")
        return existing_df


def resample_to_daily(minute_df: pd.DataFrame) -> pd.DataFrame:
    """Convert minute data to daily OHLCV, forcing numeric conversion to avoid string concatenation."""
    df = minute_df.copy()
    # Force numeric, coerce errors to NaN
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.set_index("datetime")
    daily = df.resample("1D").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna()
    daily.reset_index(inplace=True)
    daily["volume"] = daily["volume"].round(8)  # pulizia
    return daily


def process_pair(pair: str) -> None:
    """Full pipeline for one currency pair."""
    minute_path = DAILY_MINUTE_PATHS[pair]
    daily_path = DAILY_OHLC_PATHS[pair]

    # Load existing minute data
    df = pd.read_csv(minute_path)
    logger.info(f"[{pair}] Loaded {len(df)} existing minute records")

    # Check missing intervals
    missing = check_missing_intervals(df)
    if not missing:
        logger.info(f"[{pair}] No missing data to fetch")
    else:
        df = fetch_and_append_missing_data(pair, missing, df)
        # Validate and save updated minute data
        os.makedirs(os.path.dirname(minute_path), exist_ok=True)
        df.to_csv(minute_path, index=False)
        logger.info(f"[{pair}] Saved {len(df)} minute records to {minute_path}")

    # Generate daily OHLCV
    daily_df = resample_to_daily(df)
    daily_df.to_csv(daily_path, index=False)
    logger.info(f"[{pair}] Saved {len(daily_df)} daily records to {daily_path}")


if __name__ == "__main__":
    ensure_seed_files()
    for pair in CURRENCY_PAIRS:
        process_pair(pair)
