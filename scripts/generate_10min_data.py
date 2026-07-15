#!/usr/bin/env python3
"""
Generate a CSV file with only the LATEST BTC/EUR price at 10-minute intervals.
Keeps only the most recent data point - overwrites previous data.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime


def generate_10min_data():
    """
    Load all available data and keep only the latest price at 10-minute intervals.
    """
    data_dir = Path("data")
    
    # Load historical data
    hist_file = data_dir / "historical" / "btceur_bitstamp_1min_2012-2025.csv.gz"
    if hist_file.exists():
        df_hist = pd.read_csv(hist_file, compression='gzip')
    else:
        print(f"⚠️  Historical file not found at {hist_file}")
        df_hist = pd.DataFrame()
    
    # Load recent updates
    updates_file = data_dir / "updates" / "btceur_bitstamp_1min_latest.csv"
    if updates_file.exists():
        df_recent = pd.read_csv(updates_file)
    else:
        print(f"⚠️  Updates file not found at {updates_file}")
        df_recent = pd.DataFrame()
    
    # Combine datasets
    if not df_hist.empty and not df_recent.empty:
        df = pd.concat([df_hist, df_recent], ignore_index=True)
    elif not df_hist.empty:
        df = df_hist.copy()
    elif not df_recent.empty:
        df = df_recent.copy()
    else:
        print("❌ Error: No data files found!")
        return
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    
    # Sort by datetime to ensure proper grouping
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Round down to nearest 10-minute interval
    df['time_10min'] = df['datetime'].dt.floor('10min')
    
    # Group by 10-minute intervals and get the LAST (most recent) price
    df_10min = df.groupby('time_10min').agg({
        'close': 'last',  # Get the last close price in each 10-min window
        'timestamp': 'last'  # Get the corresponding timestamp
    }).reset_index()
    
    # Rename columns
    df_10min = df_10min.rename(columns={
        'time_10min': 'datetime',
        'close': 'price'
    })
    
    # Format datetime
    df_10min['datetime'] = df_10min['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # SELECT ONLY THE LAST ROW (latest data point)
    if len(df_10min) > 0:
        df_10min = df_10min.iloc[[-1]]  # Keep only the last row
    
    # Select and reorder columns
    output_df = df_10min[['datetime', 'price', 'timestamp']]
    
    # Save to CSV (overwrites previous data)
    output_file = data_dir / "updates" / "btceur_bitstamp_10min_latest.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_file, index=False)
    
    print("✅ Generated 10-minute data successfully!")
    print(f"📁 File: {output_file}")
    print(f"\n📊 Latest data:")
    print(output_df.to_string(index=False))


if __name__ == "__main__":
    generate_10min_data()
