import pandas as pd
import src.config as config
from .backtester import Backtester
from .strategies.prediction_strategy import PredictionStrategy
from .preprocessing import preprocess_base_features

# CONFIG
DATA_FILE = config.get_analysis_filename()

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
    backtester.market_data = preprocess_base_features(backtester.market_data)

    # Run the backtest
    backtester.run_strategy(strategy)

    # Generate and print the report
    backtester.generate_report()
