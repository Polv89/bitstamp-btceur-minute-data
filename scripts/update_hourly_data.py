import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List
import pandas as pd
import requests

# Configuration
CURRENCY_PAIRS = ["btceur", "btcusd"]
HOURLY_PATHS = {
    "btceur": "data/updates/btceur_bitstamp_hourly_latest.csv",
    "btcusd": "data/updates/btcusd_bitstamp_hourly_latest.csv",
}
COMBINED_PATH = "data/updates/btc_combined_hourly_latest.csv"
DAYS_TO_KEEP = 7  # Keep last 7 days of hourly data
COLUMN_NAMES = ["timestamp", "open", "high", "low", "close", "volume"]

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
logger.addHandler(console_handler)


def fetch_bitstamp_hourly_data(
    currency_pair: str,
    start_timestamp: int,
    end_timestamp: int,
    step: int = 3600,  # 1 hour in seconds
    limit: int = 1000,
) -> List[dict]:
    """Fetch OHLC data from Bitstamp API."""
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
        logger.error(f"Error fetching hourly data for {currency_pair}: {e}")
        return []


def ensure_hourly_seed_files() -> None:
    """Create seed files for both pairs if they don't exist."""
    seed_timestamp = int((datetime.now(timezone.utc) - timedelta(days=DAYS_TO_KEEP)).timestamp())
    header = "timestamp,open,high,low,close,volume\n"
    for pair in CURRENCY_PAIRS:
        path = HOURLY_PATHS[pair]
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(header)
            logger.info(f"Created seed file {path}")


def get_missing_intervals(df: pd.DataFrame) -> tuple or None:
    """Check if data needs to be updated."""
    if len(df) == 0:
        start = int((datetime.now(timezone.utc) - timedelta(days=DAYS_TO_KEEP)).timestamp())
        end = int(datetime.now(timezone.utc).timestamp()) - 3600
        return start, end
    
    last_timestamp = int(df["timestamp"].max())
    current_timestamp = int(datetime.now(timezone.utc).timestamp()) - 3600
    
    if last_timestamp >= current_timestamp:
        logger.info(f"Hourly data already up to date (last: {last_timestamp}, current: {current_timestamp})")
        return None
    
    return last_timestamp + 3600, current_timestamp


def fetch_and_append_hourly_data(
    currency_pair: str,
    missing_interval: tuple,
    existing_df: pd.DataFrame,
) -> pd.DataFrame:
    """Fetch missing hourly data and append to existing DataFrame."""
    all_new_data = []
    start_timestamp, end_timestamp = missing_interval
    logger.info(f"[{currency_pair}] Fetching hourly data from {start_timestamp} to {end_timestamp}")

    while start_timestamp < end_timestamp:
        remaining_hours = (end_timestamp - start_timestamp) // 3600
        limit = min(1000, max(1, remaining_hours))
        window_end = min(start_timestamp + ((limit - 1) * 3600), end_timestamp)

        logger.info(f"[{currency_pair}] Fetching {limit} hours from {start_timestamp} to {window_end}")
        new_data = fetch_bitstamp_data(currency_pair, start_timestamp, window_end, step=3600, limit=limit)

        if new_data:
            df_new = pd.DataFrame(new_data)
            df_new["timestamp"] = pd.to_numeric(df_new["timestamp"], errors="coerce")
            df_new.columns = COLUMN_NAMES
            all_new_data.append(df_new)
            last_ts = int(df_new["timestamp"].max())
            start_timestamp = last_ts + 3600
        else:
            logger.warning(f"[{currency_pair}] No data for interval {start_timestamp}-{window_end}")
            start_timestamp = window_end + 3600

    if all_new_data:
        updated_df = pd.concat([existing_df] + all_new_data, ignore_index=True)
        updated_df.drop_duplicates(subset="timestamp", inplace=True)
        updated_df.sort_values("timestamp", ascending=True, inplace=True)
        
        # Keep only last 7 days
        cutoff_timestamp = int((datetime.now(timezone.utc) - timedelta(days=DAYS_TO_KEEP)).timestamp())
        updated_df = updated_df[updated_df["timestamp"] >= cutoff_timestamp]
        
        logger.info(f"[{currency_pair}] Total hourly records: {len(updated_df)}")
        return updated_df
    else:
        logger.info(f"[{currency_pair}] No new hourly data found")
        return existing_df


def fetch_bitstamp_data(currency_pair, start, end, step, limit):
    """Wrapper for API call."""
    url = f"https://www.bitstamp.net/api/v2/ohlc/{currency_pair}/"
    params = {"step": step, "start": start, "end": end, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return response.json().get("data", {}).get("ohlc", [])
    except Exception as e:
        logger.error(f"Error: {e}")
        return []


def process_hourly_pair(pair: str) -> pd.DataFrame:
    """Full pipeline for one currency pair (hourly)."""
    path = HOURLY_PATHS[pair]
    
    # Load existing data
    df = pd.read_csv(path)
    logger.info(f"[{pair}] Loaded {len(df)} existing hourly records")
    
    # Check missing intervals
    missing = get_missing_intervals(df)
    if not missing:
        logger.info(f"[{pair}] No missing hourly data to fetch")
    else:
        df = fetch_and_append_hourly_data(pair, missing, df)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        df.to_csv(path, index=False)
        logger.info(f"[{pair}] Saved {len(df)} hourly records to {path}")
    
    return df


def create_combined_file(btceur_df: pd.DataFrame, btcusd_df: pd.DataFrame) -> None:
    """Create a combined compact CSV for both pairs (last 24 hours)."""
    # Keep only last 24 hours
    cutoff = int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp())
    
    btceur_24h = btceur_df[btceur_df["timestamp"] >= cutoff].copy()
    btcusd_24h = btcusd_df[btcusd_df["timestamp"] >= cutoff].copy()
    
    # Merge on timestamp
    merged = btceur_24h.merge(
        btcusd_24h,
        on="timestamp",
        suffixes=("_eur", "_usd"),
        how="outer"
    )
    merged.sort_values("timestamp", inplace=True)
    
    # Format: timestamp, eur_close, usd_close (minimal format)
    output = merged[["timestamp", "close_eur", "close_usd"]].copy()
    output.columns = ["timestamp", "btc_eur", "btc_usd"]
    
    # Convert timestamp to readable format
    output["datetime"] = pd.to_datetime(output["timestamp"], unit="s", utc=True).dt.strftime("%Y-%m-%d %H:%M")
    output = output[["datetime", "btc_eur", "btc_usd"]]
    
    os.makedirs(os.path.dirname(COMBINED_PATH), exist_ok=True)
    output.to_csv(COMBINED_PATH, index=False)
    logger.info(f"Saved {len(output)} combined records to {COMBINED_PATH} ({len(open(COMBINED_PATH).read())} bytes)")


if __name__ == "__main__":
    ensure_hourly_seed_files()
    
    # Process both pairs
    dfs = {}
    for pair in CURRENCY_PAIRS:
        dfs[pair] = process_hourly_pair(pair)
    
    # Create combined file
    create_combined_file(dfs["btceur"], dfs["btcusd"])
    
    logger.info("✅ Hourly data update complete!")
