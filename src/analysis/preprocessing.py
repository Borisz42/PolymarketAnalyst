import pandas as pd

SHARP_MOVE_THRESHOLD = 0.04

def preprocess_data(df, sharp_move_threshold=SHARP_MOVE_THRESHOLD):
    """Pre-processes the market data to add features required by various strategies."""
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

    # --- Moving Averages ---
    for window in [5, 10]:
        df[f"UpAsk_MA_{window}"] = df.groupby(["TargetTime", "Expiration"])["UpAsk"].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )
        df[f"DownAsk_MA_{window}"] = df.groupby(["TargetTime", "Expiration"])["DownAsk"].transform(
            lambda x: x.rolling(window, min_periods=1).mean()
        )

    # --- Volatility (using Mid prices) ---
    df["UpMid_Volatility"] = df.groupby(["TargetTime", "Expiration"])["UpMid"].transform(
        lambda x: x.rolling(10, min_periods=1).std()
    )
    df["DownMid_Volatility"] = df.groupby(["TargetTime", "Expiration"])["DownMid"].transform(
        lambda x: x.rolling(10, min_periods=1).std()
    )

    # --- Spread ---
    df["Up_Spread"] = df["UpAsk"] - df["UpBid"]
    df["Down_Spread"] = df["DownAsk"] - df["DownBid"]

    # --- Crossover Signals ---
    # Shift the moving average columns to get the previous value for comparison
    df['UpAsk_MA_5_prev'] = df.groupby(['TargetTime', 'Expiration'])['UpAsk_MA_5'].shift(1)
    df['UpAsk_MA_10_prev'] = df.groupby(['TargetTime', 'Expiration'])['UpAsk_MA_10'].shift(1)
    df['DownAsk_MA_5_prev'] = df.groupby(['TargetTime', 'Expiration'])['DownAsk_MA_5'].shift(1)
    df['DownAsk_MA_10_prev'] = df.groupby(['TargetTime', 'Expiration'])['DownAsk_MA_10'].shift(1)

    # Bullish Crossover: 5-period MA crosses above 10-period MA
    df['Up_MA_Crossover'] = (
        (df['UpAsk_MA_5'] > df['UpAsk_MA_10']) &
        (df['UpAsk_MA_5_prev'] <= df['UpAsk_MA_10_prev'])
    )

    # Crossover Signal for Down market: 5-period MA crosses above 10-period MA
    df['Down_MA_Crossover'] = (
        (df['DownAsk_MA_5'] > df['DownAsk_MA_10']) &
        (df['DownAsk_MA_5_prev'] <= df['DownAsk_MA_10_prev'])
    )

    # Clean up temporary columns
    df.drop(columns=['UpAsk_MA_5_prev', 'UpAsk_MA_10_prev', 'DownAsk_MA_5_prev', 'DownAsk_MA_10_prev'], inplace=True)

    return df
