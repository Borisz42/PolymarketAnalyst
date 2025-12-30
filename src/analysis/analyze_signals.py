import pandas as pd
import src.config as config
from src.analysis.hybrid_backtester import preprocess_data
import matplotlib.pyplot as plt
import seaborn as sns

DATA_FILE = 'data/market_data_20251230.csv'
SHARP_MOVE_THRESHOLD = 0.04

def analyze_signals(file_path):
    """
    Analyzes the market data to find correlations between signals and large price movements.
    """
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


if __name__ == "__main__":
    analyze_signals(DATA_FILE)
