import pandas as pd
import numpy as np

# =========================
# CONFIG
# =========================
CSV_PATH = "data/market_data_20251226.csv"

MIN_MINUTE = 2
MAX_MINUTE = 7
SHARP_MOVE_THRESHOLD = 0.04
MAX_ENTRY_PRICE = 0.85
POSITION_SIZE = 1.0  # $1 per trade

# =========================
# LOAD & PREPARE DATA
# =========================
df = pd.read_csv(
    CSV_PATH,
    parse_dates=["Timestamp", "TargetTime", "Expiration"]
)

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

# =========================
# DETERMINE MARKET WINNER
# =========================
def determine_winner(market_df):
    if market_df.empty:
        return None
    last = market_df.iloc[-1]

    if last["UpAsk"] == 0:
        return "Up"
    if last["DownAsk"] == 0:
        return "Down"
    if last["DownAsk"] > last["UpAsk"]:
        return "Down"
    return "Up"

results = {}
for group_keys, group_df in df.groupby(["TargetTime", "Expiration"]):
    results[group_keys] = determine_winner(group_df)

multi_index = pd.MultiIndex.from_tuples(results.keys(), names=["TargetTime", "Expiration"])
winners_series = pd.Series(list(results.values()), index=multi_index)
winners = winners_series.to_frame("Winner").reset_index()

df = df.merge(winners, on=["TargetTime", "Expiration"], how="left")

# =========================
# BACKTEST
# =========================
trades = []

for (target, expiry), market in df.groupby(["TargetTime", "Expiration"]):

    entered = False
    winner = market["Winner"].iloc[0]

    for _, row in market.iterrows():

        if entered:
            break

        minute = row["MinuteFromStart"]

        # --- Time filter
        if minute < MIN_MINUTE or minute > MAX_MINUTE:
            continue

        # --- Sharp event
        if not row["SharpEvent"]:
            continue

        # --- Direction
        side = None
        ask = None

        if row["UpMidDelta"] > 0:
            side = "Up"
            ask = row["UpAsk"]
            liquidity_ok = row["BidLiquidityImbalance"] < 0

        elif row["DownMidDelta"] > 0:
            side = "Down"
            ask = row["DownAsk"]
            liquidity_ok = row["BidLiquidityImbalance"] > 0

        else:
            continue

        # --- Liquidity confirmation
        if not liquidity_ok:
            continue

        # --- Price sanity
        if ask is None or ask > MAX_ENTRY_PRICE:
            continue

        # ===== ENTER TRADE =====
        entered = True

        pnl = (POSITION_SIZE - ask) if side == winner else -ask

        trades.append({
            "TargetTime": target,
            "Expiration": expiry,
            "Minute": minute,
            "Side": side,
            "EntryPrice": ask,
            "Winner": winner,
            "PnL": pnl
        })

        pnl = (POSITION_SIZE - ask) if side == winner else -ask

        trades.append({
            "TargetTime": target,
            "Expiration": expiry,
            "Minute": minute,
            "Side": side,
            "EntryPrice": ask,
            "Winner": winner,
            "PnL": pnl
        })

# =========================
# RESULTS
# =========================
trades_df = pd.DataFrame(trades)

if trades_df.empty:
    print("❌ No trades executed.")
    exit()

total_pnl = trades_df["PnL"].sum()
win_rate = (trades_df["PnL"] > 0).mean()
avg_win = trades_df.loc[trades_df["PnL"] > 0, "PnL"].mean()
avg_loss = trades_df.loc[trades_df["PnL"] < 0, "PnL"].mean()

# Equity curve & drawdown
trades_df["Equity"] = trades_df["PnL"].cumsum()
trades_df["Peak"] = trades_df["Equity"].cummax()
trades_df["Drawdown"] = trades_df["Equity"] - trades_df["Peak"]
max_dd = trades_df["Drawdown"].min()

print("\n========== BACKTEST RESULTS ==========")
print(f"Trades taken     : {len(trades_df)}")
print(f"Win rate         : {win_rate:.2%}")
print(f"Total PnL        : ${total_pnl:.2f}")
print(f"Average win      : ${avg_win:.2f}")
print(f"Average loss     : ${avg_loss:.2f}")
print(f"Profit factor    : {abs(avg_win / avg_loss):.2f}")
print(f"Max drawdown     : ${max_dd:.2f}")
print("=====================================\n")

print(trades_df.head())
