import pandas as pd

SHARP_MOVE_THRESHOLD = 0.04

def preprocess_base_features(df, sharp_move_threshold=SHARP_MOVE_THRESHOLD):
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

    return df

def preprocess_moving_average_features(df):
    """Pre-processes the market data to add features required by the MovingAverageStrategy."""
    df = df.set_index('Timestamp')

    # --- Moving Averages ---
    for window in ['5s', '10s']:
        df[f"UpAsk_MA_{window}"] = df.groupby(["TargetTime", "Expiration"])["UpAsk"].transform(
            lambda x: x.rolling(window).mean()
        )
        df[f"DownAsk_MA_{window}"] = df.groupby(["TargetTime", "Expiration"])["DownAsk"].transform(
            lambda x: x.rolling(window).mean()
        )

    # --- Volatility (using Mid prices) ---
    df["UpMid_Volatility"] = df.groupby(["TargetTime", "Expiration"])["UpMid"].transform(
        lambda x: x.rolling('10s').std()
    )
    df["DownMid_Volatility"] = df.groupby(["TargetTime", "Expiration"])["DownMid"].transform(
        lambda x: x.rolling('10s').std()
    )

    # --- Spread ---
    df["Up_Spread"] = df["UpAsk"] - df["UpBid"]
    df["Down_Spread"] = df["DownAsk"] - df["DownBid"]

    # --- Crossover Signals ---
    # Shift the moving average columns to get the previous value for comparison
    df['UpAsk_MA_5s_prev'] = df.groupby(['TargetTime', 'Expiration'])['UpAsk_MA_5s'].shift(1)
    df['UpAsk_MA_10s_prev'] = df.groupby(['TargetTime', 'Expiration'])['UpAsk_MA_10s'].shift(1)
    df['DownAsk_MA_5s_prev'] = df.groupby(['TargetTime', 'Expiration'])['DownAsk_MA_5s'].shift(1)
    df['DownAsk_MA_10s_prev'] = df.groupby(['TargetTime', 'Expiration'])['DownAsk_MA_10s'].shift(1)

    # Bullish Crossover: 5-period MA crosses above 10-period MA
    df['Up_MA_Crossover'] = (
        (df['UpAsk_MA_5s'] > df['UpAsk_MA_10s']) &
        (df['UpAsk_MA_5s_prev'] <= df['UpAsk_MA_10s_prev'])
    )

    # Crossover Signal for Down market: 5-period MA crosses above 10-period MA
    df['Down_MA_Crossover'] = (
        (df['DownAsk_MA_5s'] > df['DownAsk_MA_10s']) &
        (df['DownAsk_MA_5s_prev'] <= df['DownAsk_MA_10s_prev'])
    )

    # Clean up temporary columns
    df.drop(columns=['UpAsk_MA_5s_prev', 'UpAsk_MA_10s_prev', 'DownAsk_MA_5s_prev', 'DownAsk_MA_10s_prev'], inplace=True)

    return df.reset_index()
