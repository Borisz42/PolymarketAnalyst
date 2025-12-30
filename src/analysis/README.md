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
    -   A `tuple`: `(side, quantity, price, score)` if you want to execute a trade.
        -   `side` (str): Either `'Up'` or `'Down'`.
        -   `quantity` (float): The number of shares to buy.
        -   `price` (float): The price at which to buy the shares (e.g., `data_point['UpAsk']`).
        -   `score` (float): A score representing the signal strength (can be 0 if not used).

4.  **Example Implementation**:

    ```python
    # In src/analysis/strategies/my_strategy.py
    from .base_strategy import Strategy

    class MyStrategy(Strategy):
        def __init__(self):
            super().__init__()

        def decide(self, market_data_point, current_capital):
            # A simple strategy: buy 10 UP shares if the ask price is below $0.50
            if market_data_point['UpAsk'] < 0.50:
                quantity_to_buy = 10.0
                cost = quantity_to_buy * market_data_point['UpAsk']
                if current_capital >= cost:
                    return ('Up', quantity_to_buy, market_data_point['UpAsk'], 1.0)
            return None
    ```

5.  **Run the Backtester**: To run the backtester with your new strategy, use the `hybrid_backtester.py` script, which is designed to run any strategy. You will need to modify it to import and instantiate your strategy.

    ```bash
    python -m src.analysis.hybrid_backtester my_strategy <path_to_data_file>
    ```
