import pandas as pd
import numpy as np
import os
from src.config import get_analysis_filename

def analyze_market_data(filename):
    """
    Analyzes market data from a CSV file, providing summary statistics,
    and resolution analysis.
    """
    if not os.path.exists(filename):
        print(f"Error: The file {filename} was not found.")
        return

    print(f"Analyzing market data from: {filename}\n")

    try:
        # Load the data using pandas
        df = pd.read_csv(filename)
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    # --- Overall Statistics ---
    total_rows = len(df)
    unique_markets = df['Expiration'].nunique()

    print("--- Overall Summary ---")
    print(f"Total data points (rows): {total_rows}")
    print(f"Number of unique markets found: {unique_markets}")
    print("-" * 25)

    # --- Resolution Analysis ---
    if unique_markets > 0:
        resolved_up = 0
        resolved_down = 0
        resolved_up_markets = []
        resolved_down_markets = []

        # Group by market expiration to identify individual markets
        market_groups = df.groupby('Expiration')

        for name, group in market_groups:
            # Get the last available data point for the market
            last_record = group.sort_values(by='Timestamp').iloc[-1]
            
            up_price = last_record['UpAsk']
            down_price = last_record['DownAsk']

            # Determine resolution based on the final prices using the new logic
            if up_price == 0:
                resolved_up += 1
                resolved_up_markets.append(name)
            elif down_price == 0:
                resolved_down += 1
                resolved_down_markets.append(name)
            elif down_price > up_price:
                resolved_down += 1
                resolved_down_markets.append(name)
            else:  # up_price >= down_price (and neither is 0)
                resolved_up += 1
                resolved_up_markets.append(name)

        print("--- Market Resolution Summary ---")
        print(f"Markets likely resolved 'Up': {resolved_up}")
        print(f"Markets likely resolved 'Down': {resolved_down}")
        if resolved_up_markets:
            print("\nResolved 'Up' Markets:")
            for market in resolved_up_markets:
                print(f"  - {market}")
        if resolved_down_markets:
            print("\nResolved 'Down' Markets:")
            for market in resolved_down_markets:
                print(f"  - {market}")

        print("-" * 25)


    # --- Price & Liquidity Analysis ---
    metrics = {
        'UpAsk': ['min', 'max', 'mean', 'std'],
        'DownAsk': ['min', 'max', 'mean', 'std'],
        'UpBid': ['min', 'max', 'mean', 'std'],
        'DownBid': ['min', 'max', 'mean', 'std'],
        'UpAskLiquidity': ['min', 'max', 'mean', 'std'],
        'DownAskLiquidity': ['min', 'max', 'mean', 'std'],
    }
    
    # Add a column for the sum of 'UpAsk' and 'DownAsk'
    df['AskSum'] = df['UpAsk'] + df['DownAsk']
    metrics['AskSum'] = ['min', 'max', 'mean', 'std']


    print("--- Detailed Metrics ---")
    
    # Calculate and print statistics for each specified column
    for col, stats in metrics.items():
        if col in df.columns:
            print(f"\nStatistics for '{col}':")
            try:
                # Using .agg() to compute all stats at once
                result = df[col].agg(stats)
                for stat_name, value in result.items():
                    print(f"  - {stat_name.capitalize()}: {value:.4f}")
            except Exception as e:
                print(f"Could not compute statistics for '{col}': {e}")
        else:
            print(f"\nColumn '{col}' not found in the data.")
            
    print("\n" + "-" * 25)
    print("Analysis complete.")


if __name__ == "__main__":
    # Use the centralized config to get the correct analysis file
    analysis_file = get_analysis_filename()
    analyze_market_data(analysis_file)