import os
import sys
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.analysis.backtester import Backtester
from src.analysis.strategies.hybrid_strategy import HybridStrategy
from src.analysis.strategies.optimized_hybrid_strategy import OptimizedHybridStrategy
from src.analysis.hybrid_backtester import preprocess_data
import src.config as config

def run_and_summarize_strategy(strategy, data_file):
    """Runs a backtest for a given strategy and returns a summary of its performance."""

    backtester = Backtester(initial_capital=config.INITIAL_CAPITAL)

    try:
        backtester.load_data(data_file)
    except FileNotFoundError:
        return None

    backtester.market_data = preprocess_data(backtester.market_data)
    backtester.run_strategy(strategy)

    # --- Performance Metrics ---
    total_pnl = backtester.capital - backtester.initial_capital
    roi = (total_pnl / backtester.initial_capital) * 100 if backtester.initial_capital > 0 else 0
    max_drawdown = backtester._calculate_max_drawdown() * 100

    transactions_df = pd.DataFrame(backtester.transactions)
    if transactions_df.empty:
        return {
            "Total PnL": total_pnl, "ROI (%)": roi, "Max Drawdown (%)": max_drawdown,
            "Win Rate (%)": 0, "Profit Factor": 0, "Total Trades": 0
        }

    buy_trades = transactions_df[transactions_df['Type'] == 'Buy']
    resolutions = transactions_df[transactions_df['Type'] == 'Resolution']

    wins = resolutions[resolutions['PnL'] > 0]
    losses = resolutions[resolutions['PnL'] <= 0]

    win_rate = (len(wins) / len(resolutions)) * 100 if not resolutions.empty else 0

    total_profit = wins['PnL'].sum()
    total_loss = abs(losses['PnL'].sum())
    profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

    return {
        "Total PnL": f"${total_pnl:.2f}",
        "ROI (%)": f"{roi:.2f}",
        "Max Drawdown (%)": f"{max_drawdown:.2f}",
        "Win Rate (%)": f"{win_rate:.2f}",
        "Profit Factor": f"{profit_factor:.2f}",
        "Total Trades": len(buy_trades)
    }

def main():
    """Main function to run the comparison."""

    dates = [20251230] # Running one date at a time
    all_results = []

    for date in dates:
        config.ANALYSIS_DATE = date
        data_file = config.get_analysis_filename()

        print(f"--- Running backtests for {date} ---")

        original_strategy = HybridStrategy()
        optimized_strategy = OptimizedHybridStrategy()

        original_summary = run_and_summarize_strategy(original_strategy, data_file)
        if original_summary:
            original_summary['Strategy'] = 'Original Hybrid'
            original_summary['Date'] = date
            all_results.append(original_summary)

        optimized_summary = run_and_summarize_strategy(optimized_strategy, data_file)
        if optimized_summary:
            optimized_summary['Strategy'] = 'Optimized Hybrid'
            optimized_summary['Date'] = date
            all_results.append(optimized_summary)

    if all_results:
        results_df = pd.DataFrame(all_results)
        results_df = results_df.set_index(['Date', 'Strategy'])
        print("\\n--- Performance Comparison ---")
        print(results_df)
        print("--------------------------------\\n")

if __name__ == "__main__":
    main()
