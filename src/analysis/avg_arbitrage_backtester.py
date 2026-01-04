from src.analysis.backtester import Backtester
from src.analysis.strategies.avg_arbitrage_strategy import AvgArbitrageStrategy
import src.config as config

def main():
    """
    Main function to run the backtester for the AvgArbitrageStrategy.
    """
    # Initialize strategy
    strategy = AvgArbitrageStrategy(
        margin=0.025,
        initial_trade_capital_percentage=0.08,
        max_capital_allocation_percentage=0.70
    )

    # Initialize backtester
    backtester = Backtester()

    # Load data using the centralized config function
    try:
        data_file = config.get_analysis_filename()
        print(f"Running backtest on dataset: {data_file}")
        backtester.load_data(data_file)
    except FileNotFoundError as e:
        print(f"Failed to load data: {e}")
        return

    # Run backtest
    backtester.run_strategy(strategy)

    # Generate and print the report
    backtester.generate_report()

if __name__ == "__main__":
    main()
