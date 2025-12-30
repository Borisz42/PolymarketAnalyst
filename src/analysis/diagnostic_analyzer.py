import os
import sys
import pandas as pd

# Add the root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.analysis.backtester import Backtester
from src.analysis.strategies.hybrid_strategy import HybridStrategy
from src.analysis.hybrid_backtester import preprocess_data
import src.config as config

def analyze_worst_trades():
    """
    Analyzes the worst trades from a backtest of the HybridStrategy.
    """
    # --- 1. Setup and run the backtest ---

    config.ANALYSIS_DATE = 20251230
    data_file = config.get_analysis_filename()

    strategy = HybridStrategy()
    backtester = Backtester(initial_capital=config.INITIAL_CAPITAL)

    try:
        backtester.load_data(data_file)
    except FileNotFoundError as e:
        print(e)
        return

    backtester.market_data = preprocess_data(backtester.market_data)
    backtester.run_strategy(strategy)

    # --- 2. Analyze the transactions ---

    transactions_df = pd.DataFrame(backtester.transactions)

    if transactions_df.empty:
        print("No transactions were made during the backtest.")
        return

    resolutions_df = transactions_df[transactions_df['Type'] == 'Resolution'].copy()

    if resolutions_df.empty:
        print("No markets were resolved during the backtest.")
        return

    market_pnl = resolutions_df.groupby('MarketID')['PnL'].sum().sort_values()

    print("--- Market PnL Summary ---")
    print(market_pnl)
    print("--------------------------\\n")

    # --- 3. Focus on the worst trades ---

    worst_markets = market_pnl.head(3)

    print("--- Analysis of Top 3 Worst Markets ---")
    for market_id, pnl in worst_markets.items():
        print(f"\\nAnalyzing Market: {market_id}, PnL: ${pnl:.2f}")

        market_buy_trades = transactions_df[
            (transactions_df['MarketID'] == market_id) &
            (transactions_df['Type'] == 'Buy')
        ]

        if market_buy_trades.empty:
            print("  No buy trades found for this market.")
            continue

        first_trade_timestamp = market_buy_trades['Timestamp'].min()

        print(f"  First trade in this market at: {first_trade_timestamp}")
        print(f"  All buy trades for this market:\\n{market_buy_trades[['Timestamp', 'Side', 'Quantity', 'EntryPrice']]}")

        # Correctly get the preprocessed data for this market
        market_specific_data = backtester.market_data[
            (backtester.market_data['TargetTime'] == market_id[0]) &
            (backtester.market_data['Expiration'] == market_id[1])
        ]

        time_window_start = first_trade_timestamp - pd.Timedelta(minutes=1)

        pre_trade_data = market_specific_data[
            (market_specific_data['Timestamp'] >= time_window_start) &
            (market_specific_data['Timestamp'] <= first_trade_timestamp)
        ].copy()

        print(f"\\n  Market data leading up to the first trade (-1 min):\\n")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 1000)
        print(pre_trade_data[[
            'Timestamp', 'UpMid', 'DownMid', 'UpMidDelta', 'DownMidDelta',
            'BidLiquidityImbalance', 'SharpEvent'
        ]])
        print("-" * 50)


if __name__ == "__main__":
    analyze_worst_trades()
