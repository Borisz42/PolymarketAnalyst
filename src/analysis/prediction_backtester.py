import pandas as pd
import src.config as config
from .backtester import Backtester
from .strategies.prediction_strategy import PredictionStrategy

# CONFIG
DATA_FILE = config.get_analysis_filename()
SHARP_MOVE_THRESHOLD = 0.04

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

    # --- Signal Generation ---
    def generate_signal(row):
        up_score = 0
        down_score = 0

        # Signal 1: Price Delta
        if row["UpMidDelta"] > 0:
            up_score += 1
        if row["DownMidDelta"] > 0:
            down_score += 1

        # Signal 2: Liquidity Imbalance
        if row["BidLiquidityImbalance"] > 0:
            up_score += 1
        elif row["BidLiquidityImbalance"] < 0:
            down_score += 1

        # Decision based on score
        if up_score >= 2:
            return "Up"
        elif down_score >= 2:
            return "Down"
        else:
            return "Hold"

    df["Signal"] = df.apply(generate_signal, axis=1)

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
