import pandas as pd
import src.config as config
from .backtester import Backtester
from .strategies.hybrid_strategy import HybridStrategy

# CONFIG
DATA_FILE = config.get_analysis_filename()
SHARP_MOVE_THRESHOLD = 0.04

def preprocess_data(df, sharp_move_threshold=SHARP_MOVE_THRESHOLD):
    """Pre-processes the market data to add features required by the PredictionStrategy."""
    df = df.sort_values(["TargetTime", "Expiration", "Timestamp"]).reset_index(drop=True)

    # Minute index
    df["MinuteFromStart"] = (
        (df["Timestamp"] - df["TargetTime"]).dt.total_seconds() / 60
    ).astype(int)

    # Deltas
    df["UpMidDelta"] = df.groupby(["TargetTime", "Expiration"])["UpMid"].diff()
    df["DownMidDelta"] = df.groupby(["TargetTime", "Expiration"])["DownMid"].diff()

    # Liquidity imbalance
    df["BidLiquidityImbalance"] = (
        df["UpBidLiquidity"] - df["DownBidLiquidity"]
    )

    # Sharp information arrival
    df["SharpEvent"] = (
        (df["UpMidDelta"].abs() >= sharp_move_threshold) |
        (df["DownMidDelta"].abs() >= sharp_move_threshold)
    )

    # --- Signal Generation: Moved to PredictionStrategy ---
    # The strategy now calculates the signal internally.

    return df

if __name__ == "__main__":
    # Instantiate the strategy
    strategy = HybridStrategy()

    # Instantiate the backtester
    backtester = Backtester(initial_capital=config.INITIAL_CAPITAL)

    # Load data
    try:
        backtester.load_data(DATA_FILE)
    except FileNotFoundError as e:
        print(e)
        exit()

    # Pre-process the data
    backtester.market_data = preprocess_data(backtester.market_data)

    # Run the backtest
    backtester.run_strategy(strategy)

    # Generate and print the report
    backtester.generate_report()
