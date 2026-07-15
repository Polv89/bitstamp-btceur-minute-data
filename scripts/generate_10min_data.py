#!/usr/bin/env python3
"""
Generate a CSV file with only the LATEST BTC/EUR price at 10-minute intervals.
Keeps only the most recent data point - overwrites previous data.
"""

import pandas as pd
from pathlib import Path


def generate_10min_data():
    """
    Load the latest BTC/EUR data and extract only the latest price.
    """
    data_dir = Path("data")
    
    # Load recent updates (compressed file with 1-minute data)
    updates_file = data_dir / "updates" / "btceur_bitstamp_1min_latest.csv.gz"
    
    if not updates_file.exists():
        print(f"❌ File not found: {updates_file}")
        return
    
    # Read the compressed CSV
    df = pd.read_csv(updates_file, compression='gzip')
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Group by 10-minute intervals and get the LAST price in each interval
    df['time_10min'] = df['datetime'].dt.floor('10min')
    df_10min = df.groupby('time_10min').agg({
        'close': 'last',
        'timestamp': 'last'
    }).reset_index()
    
    # Rename columns
    df_10min = df_10min.rename(columns={
        'time_10min': 'datetime',
        'close': 'price'
    })
    
    # Format datetime
    df_10min['datetime'] = df_10min['datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Keep ONLY the LAST row (latest data point)
    if len(df_10min) > 0:
        df_10min = df_10min.iloc[[-1]]
    
    # Select and reorder columns
    output_df = df_10min[['datetime', 'price', 'timestamp']]
    
    # Save to CSV (overwrites previous data)
    output_file = data_dir / "updates" / "btceur_bitstamp_10min_latest.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_file, index=False)
    
    print("✅ Generated 10-minute data successfully!")
    print(f"📁 File: {output_file}")
    print(f"\n📊 Latest BTC/EUR price:")
    print(output_df.to_string(index=False))


if __name__ == "__main__":
    generate_10min_data()
