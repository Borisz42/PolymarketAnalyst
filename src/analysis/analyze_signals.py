import argparse
import pandas as pd
from src.analysis.hybrid_backtester import preprocess_data
import matplotlib.pyplot as plt
import seaborn as sns

SHARP_MOVE_THRESHOLD = 0.04

def analyze_signals(file_path):
    """
    Analyzes the market data to find correlations and distributions of signals.
    """
    print(f"Analyzing data from {file_path}...")
    try:
        df = pd.read_csv(file_path, parse_dates=['Timestamp', 'TargetTime', 'Expiration'])
    except FileNotFoundError:
        print(f"Data file not found at {file_path}")
        return

    # Preprocess the data to get the same features the strategy uses
    df = preprocess_data(df, sharp_move_threshold=SHARP_MOVE_THRESHOLD)

    # Identify large price movements (potential losses)
    df['LargePriceMove'] = (df['UpMid'].shift(-5) - df['UpMid']).abs() > SHARP_MOVE_THRESHOLD

    # Analyze the characteristics of the data points before large price movements
    analysis_df = df[df['LargePriceMove']].copy()

    print("--- Analysis of Signals Before Large Price Movements ---")
    print(analysis_df[['MinuteFromStart', 'UpMidDelta', 'DownMidDelta', 'BidLiquidityImbalance', 'SharpEvent']].describe())

    # Look for correlations
    correlation_matrix = df[['UpMidDelta', 'DownMidDelta', 'BidLiquidityImbalance', 'SharpEvent', 'LargePriceMove']].corr()
    print("\n--- Correlation Matrix ---")
    print(correlation_matrix)

    # Plot the correlation matrix
    plt.figure(figsize=(10, 8))
    sns.heatmap(correlation_matrix, annot=True, cmap='coolwarm', fmt=".2f")
    plt.title('Correlation Matrix of Signals and Large Price Movements')
    plt.savefig('signal_correlation_matrix.png')
    print("\nSaved correlation matrix plot to signal_correlation_matrix.png")

    # Plot the distribution of BidLiquidityImbalance
    plt.figure(figsize=(12, 6))

    # Cap the data for better visualization, excluding extreme outliers
    p05 = df['BidLiquidityImbalance'].quantile(0.05)
    p95 = df['BidLiquidityImbalance'].quantile(0.95)
    capped_imbalance = df['BidLiquidityImbalance'].clip(p05, p95)

    sns.histplot(capped_imbalance, bins=100, kde=True)
    plt.title('Distribution of Bid-Side Liquidity Imbalance (Capped at 5th and 95th percentiles)')
    plt.xlabel('Bid-Side Liquidity Imbalance')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.savefig('liquidity_imbalance_distribution.png')
    print("\nSaved liquidity imbalance distribution plot to liquidity_imbalance_distribution.png")

    print("\n--- BidLiquidityImbalance Absolute Value Quantiles ---")
    print(df['BidLiquidityImbalance'].abs().quantile([0.5, 0.75, 0.9, 0.95, 0.98, 0.99]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze market data signals.")
    parser.add_argument("data_file", nargs='?', default='data/market_data_20251230.csv',
                        type=str, help="Path to the market data CSV file.")
    args = parser.parse_args()
    analyze_signals(args.data_file)
