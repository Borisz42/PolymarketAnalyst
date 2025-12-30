import src.config as config
from .backtester import Backtester
from .strategies.moving_average_strategy import MovingAverageStrategy
from .preprocessing import preprocess_data

if __name__ == "__main__":
    # Instantiate the strategy with fine-tuned parameters
    strategy = MovingAverageStrategy(
        volatility_threshold=0.005,
        spread_threshold=0.04,
        imbalance_threshold=150
    )

    # Instantiate the backtester
    backtester = Backtester(initial_capital=config.INITIAL_CAPITAL)

    # Load data
    try:
        backtester.load_data(config.get_analysis_filename())
    except FileNotFoundError as e:
        print(e)
        exit()

    # Pre-process the data
    backtester.market_data = preprocess_data(backtester.market_data)

    # Run the backtest
    backtester.run_strategy(strategy)

    # Generate and print the report
    backtester.generate_report()
