# Analysis & Backtesting Module

This module contains the tools for analyzing market data and backtesting trading strategies against historical data. The core of this module is a flexible backtesting engine that is decoupled from the trading strategies themselves.

## Backtesting Architecture

The backtesting engine is primarily driven by `backtester.py`. Its key responsibilities include:

-   **Data Loading**: Loads historical market data from the specified CSV file in the `data/` directory.
-   **Chronological Simulation**: Processes the data point by point, in chronological order, to simulate the progression of time.
-   **Strategy Integration**: For each data point, it calls the `decide()` method of the provided strategy instance to see if a trade should be executed.
-   **Trade Execution**: Simulates the buying of contracts, deducting the cost from the available capital.
-   **Slippage Simulation**: Optionally applies a delay to trade execution to simulate market slippage, providing a more realistic PnL calculation.
-   **Position Management**: Tracks all open positions and resolves them once their market expires.
-   **Reporting**: Generates a detailed report at the end of the simulation, including total PnL, ROI, max drawdown, and other key metrics.

## Included Strategies

The following strategies are included in the `src/analysis/strategies/` directory:

-   **`RebalancingStrategy`**: A sophisticated strategy that aims to accumulate paired positions (both UP and DOWN contracts) when profitable opportunities arise, while maintaining a balanced portfolio to hedge risk.
-   **`PredictionStrategy`**: A simpler, event-driven strategy that trades based on sharp price movements and liquidity imbalances, aiming to capitalize on short-term momentum.
-   **`HybridStrategy`**: A strategy that combines the `PredictionStrategy` and `RebalancingStrategy`. It uses prediction signals to initiate a trade and rebalancing logic to manage the position afterward.
-   **`MovingAverageStrategy`**: A classic momentum strategy that uses the crossover of two simple moving averages (SMAs) of the mid-price to generate buy signals. It's a good example of a stateful strategy.

## Implementing a Custom Strategy

The backtester is designed to be easily extensible. You can create your own trading strategy by following these steps:

1.  **Create a New File**: Add a new Python file to the `src/analysis/strategies/` directory (e.g., `my_strategy.py`).

2.  **Inherit from `Strategy`**: In your new file, import the base `Strategy` class and create a new class that inherits from it.

    ```python
    from .base_strategy import Strategy

    class MyStrategy(Strategy):
        def __init__(self):
            # Initialize any strategy-specific variables here
            super().__init__()

        def decide(self, data_point, capital):
            # Your trading logic goes here
            pass
    ```

3.  **Implement the `decide()` Method**: This is the core of your strategy. The backtester will call this method for each row of the market data.
    -   **`data_point`**: A pandas Series representing a single row of market data at a specific timestamp.
    -   **`capital`**: The current available capital.

    Your `decide()` method should return one of two things:
    -   `None`: If no action should be taken.
    -   A `tuple`: `(side, quantity, entry_price, score)` if you want to execute a trade.
        -   `side` (str): Either `'Up'` or `'Down'`.
        -   `quantity` (float): The number of shares to buy.
        -   `entry_price` (float): The price at which to buy the shares (e.g., `data_point['UpAsk']`).
        -   `score` (float): A numeric value representing the signal strength (e.g., the difference between two moving averages). This is not used by the backtester for any calculations but is recorded in the trade logs, making it invaluable for post-analysis and debugging.

4.  **Example Implementation**:

    Here is a more practical example of a simple moving average (SMA) crossover strategy. This strategy calculates two moving averages of the mid-price and buys "Up" when the short-term average crosses above the long-term average, signaling upward momentum.

    ```python
    # In src/analysis/strategies/moving_average_strategy.py
    import pandas as pd
    from .base_strategy import Strategy

    class MovingAverageStrategy(Strategy):
        def __init__(self, short_window=5, long_window=20):
            super().__init__()
            self.short_window = short_window
            self.long_window = long_window
            self.prices = []
            self.short_sma = []
            self.long_sma = []

        def decide(self, data_point, capital):
            self.prices.append(data_point['UpMid'])

            if len(self.prices) > self.long_window:
                # Calculate SMAs
                short_sma_val = pd.Series(self.prices[-self.short_window:]).mean()
                long_sma_val = pd.Series(self.prices[-self.long_window:]).mean()
                self.short_sma.append(short_sma_val)
                self.long_sma.append(long_sma_val)

                # Check for crossover signal
                if len(self.short_sma) > 1 and self.short_sma[-2] < self.long_sma[-2] and short_sma_val > long_sma_val:
                    quantity = 10.0
                    cost = quantity * data_point['UpAsk']
                    if capital >= cost:
                        return ('Up', quantity, data_point['UpAsk'], 1.0)
            return None
    ```

5.  **Run the Backtester**: To run your new strategy, create a new runner script in `src/analysis/` (e.g., `my_strategy_backtester.py`) by copying and modifying an existing one like `backtester.py`.

    ```python
    # In src/analysis/my_strategy_backtester.py
    if __name__ == "__main__":
        from .strategies.my_strategy import MyStrategy # Import your new strategy
        from .backtester import Backtester
        from ..config import INITIAL_CAPITAL, DATA_FILE

        backtester = Backtester(initial_capital=INITIAL_CAPITAL)
        try:
            backtester.load_data(DATA_FILE)
        except FileNotFoundError as e:
            print(e)
            exit()

        strategy = MyStrategy() # Instantiate your strategy
        backtester.run_strategy(strategy)
        backtester.generate_report()
    ```

### Note on Stateful Strategies

Some strategies, like the `MovingAverageStrategy` example above, need to maintain a state (e.g., a history of prices) across multiple calls to the `decide()` method. The backtester supports this naturally. Any instance variables you define in your strategy's `__init__` method will persist throughout the backtest of a single market.

**Important**: The backtester creates a new instance of the strategy for each market to prevent data leakage from one market to the next.

For more advanced state management, such as updating your portfolio based on trade confirmations, the backtester includes a powerful optional callback: the `update_portfolio` method.

-   **How it Works**: After a trade is successfully executed, the backtester checks if the strategy instance has a method named `update_portfolio`.
-   **Implementation**: If the method exists, the backtester will call it, passing a dictionary containing the details of the confirmed trade (e.g., `side`, `quantity`, `price`). This allows your strategy to update its internal state *after* a trade is confirmed.

```python
# In your strategy class
def update_portfolio(self, trade_confirmation):
    """
    Optional method. Called by the backtester after a trade is executed.
    'trade_confirmation' is a dict with trade details.
    """
    side = trade_confirmation['side']
    quantity = trade_confirmation['quantity']

    # Example: Update internal position tracking
    if side == 'Up':
        self.my_up_position += quantity
    else:
        self.my_down_position += quantity

    print(f"Portfolio updated: Just bought {quantity} {side} shares.")
```
