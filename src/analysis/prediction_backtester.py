import pandas as pd
import src.config as config
from .backtester import Backtester
from .strategies.prediction_strategy import PredictionStrategy

# CONFIG
DATA_FILE = config.get_analysis_filename()
SHARP_MOVE_THRESHOLD = 0.08

def preprocess_data(df):
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
        (df["UpMidDelta"].abs() >= SHARP_MOVE_THRESHOLD) |
        (df["DownMidDelta"].abs() >= SHARP_MOVE_THRESHOLD)
    )

    # --- Signal Generation: Moved to PredictionStrategy ---
    # The strategy now calculates the signal internally.

    return df

if __name__ == "__main__":
    # Instantiate the strategy
    strategy = PredictionStrategy()

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
