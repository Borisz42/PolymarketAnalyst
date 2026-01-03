import os
import pandas as pd
from src.analysis.backtester import Backtester
from src.analysis.strategies.avg_arbitrage_strategy import AvgArbitrageStrategy
from src.config import ANALYSIS_DATE

def main():
    """
    Main function to run the backtester for the AvgArbitrageStrategy.
    """
    # Load data
    if ANALYSIS_DATE == 0:
        # get the latest file from the data directory
        data_dir = 'data'
        files = os.listdir(data_dir)
        files.sort()
        latest_file = files[-1]
        filepath = os.path.join(data_dir, latest_file)
    else:
        filepath = f'data/{ANALYSIS_DATE}_market_data.csv'

    market_data = pd.read_csv(filepath)

    # Initialize strategy
    strategy = AvgArbitrageStrategy(
        margin=0.01,
        initial_trade_capital_percentage=0.05,
        max_capital_allocation_percentage=0.50
    )

    # Initialize backtester
    backtester = Backtester(market_data, strategy)

    # Run backtest
    backtester.run()

if __name__ == "__main__":
    main()
