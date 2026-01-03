import os
import pandas as pd
from src.analysis.backtester import Backtester
from src.analysis.strategies.avg_arbitrage_strategy import AvgArbitrageStrategy
from src.config import ANALYSIS_DATE

def main():
    """
    Main function to run the backtester for the AvgArbitrageStrategy.
    """
    # Determine data file path
    if ANALYSIS_DATE == 0:
        data_dir = 'data'
        # Filter for market data files and get the latest one
        market_files = sorted([f for f in os.listdir(data_dir) if f.startswith('market_data_')])
        if not market_files:
            print("Error: No market_data files found in the data directory.")
            return
        latest_file = market_files[-1]
        filepath = os.path.join(data_dir, latest_file)
        print(f"Running backtest on the latest dataset: {latest_file}")
    else:
        filepath = f'data/{ANALYSIS_DATE}_market_data.csv'
        print(f"Running backtest on specified dataset: {filepath}")

    # Initialize strategy
    strategy = AvgArbitrageStrategy(
        margin=0.01,
        initial_trade_capital_percentage=0.05,
        max_capital_allocation_percentage=0.50
    )

    # Initialize backtester
    backtester = Backtester()

    # Load data
    try:
        backtester.load_data(filepath)
    except FileNotFoundError as e:
        print(f"Failed to load data: {e}")
        return

    # Run backtest
    backtester.run_strategy(strategy)

    # Generate and print the report
    backtester.generate_report()

if __name__ == "__main__":
    main()
