# Polymarket BTC Monitor

A Python-based tool to monitor **Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets**. It features real-time data logging, an interactive analysis dashboard, and a modular backtesting framework for developing and evaluating trading strategies.

## Features

-   **Data Collection**:
    -   **High-Frequency Logging**: Utilizes a multi-threaded architecture to fetch and log market data with high frequency.
    -   **Automated Market Detection**: Automatically finds the active 15-minute BTC market.
    -   **CSV Storage**: Stores historical data in date-stamped CSV files in the `data/` directory.

-   **Interactive Dashboard**:
    -   **Live Auto-Refresh**: Automatically updates to display the latest data.
    -   **Advanced Visualization**: Charts for probability trends, market transitions, and liquidity.
    -   **Interactive Controls**: Manual refresh, auto-refresh toggle, and zoom controls.

-   **Backtester**:
    -   **Modular Strategies**: Decouples the backtesting engine from trading strategies, allowing for easy testing of different algorithms.
    -   **Slippage Simulation**: Simulates slippage by using the price from a few seconds after the trade decision.
    -   **Comprehensive Reporting**: Provides detailed reports including PnL, ROI, max drawdown, and trade statistics.

## Architecture

The project is organized into the following structure. For more detailed information on each module, please refer to the `README.md` file within the respective directory.

```
.
├── AGENTS.md
├── README.md
├── data/
│   └── market_data_20251226.csv
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── analysis/
│   │   ├── README.md
│   │   ├── __init__.py
│   │   ├── analyze_prices.py
│   │   ├── avg_arbitrage_backtester.py
│   │   ├── backtester.py
│   │   ├── hybrid_backtester.py
│   │   ├── moving_average_backtester.py
│   │   ├── prediction_backtester.py
│   │   ├── preprocessing.py
│   │   ├── reverse_engineer.py
│   │   ├── signal_accuracy_checker.py
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── avg_arbitrage_strategy.py
│   │       ├── base_strategy.py
│   │       ├── hybrid_strategy.py
│   │       ├── moving_average_strategy.py
│   │       ├── prediction_strategy.py
│   │       └── rebalancing_strategy.py
│   ├── config.py
│   ├── dashboard/
│   │   ├── README.md
│   │   ├── __init__.py
│   │   └── dashboard.py
│   └── data_collection/
│       ├── README.md
│       ├── __init__.py
│       ├── data_logger.py
│       ├── fetch_current_polymarket.py
│       ├── find_new_market.py
│       └── get_current_markets.py
└── tests/
    ├── data/
    │   └── test_market_data.csv
    └── test_backtester.py
```

-   `src/`: Contains the core application logic.
    -   `data_collection/`: Scripts for fetching and logging market data. ([Detailed Documentation](src/data_collection/README.md))
    -   `analysis/`: Tools for backtesting trading strategies and analyzing market data. ([Detailed Documentation](src/analysis/README.md))
    -   `dashboard/`: The Streamlit-based interactive dashboard. ([Detailed Documentation](src/dashboard/README.md))
-   `data/`: Stores historical market data in CSV format.
-   `tests/`: Contains unit tests for the backtester and other critical components.

## Installation

1.  **Clone the repository and navigate to the project directory.**
2.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Configuration

Adjust strategy and analysis parameters in `src/config.py`:

```python
# Set to 0 to use today's date for analysis, or a yyyymmdd integer (e.g., 20231225) for a specific day.
ANALYSIS_DATE = 0
INITIAL_CAPITAL = 1000.0
# ... other parameters
```

### Running the Application

1.  **Start the data logger:**
    ```bash
    python -m src.data_collection.data_logger
    ```
2.  **Run a backtest:**
    -   **Rebalancing Strategy:**
        ```bash
        python -m src.analysis.backtester
        ```
    -   **Prediction Strategy:**
        ```bash
        python -m src.analysis.prediction_backtester
        ```
    -   **Hybrid Strategy:**
        ```bash
        python -m src.analysis.hybrid_backtester
        ```
    -   **Moving Average Strategy:**
        ```bash
        python -m src.analysis.moving_average_backtester
        ```
    -   **Average Arbitrage Strategy:**
        ```bash
        python -m src.analysis.avg_arbitrage_backtester
        ```
3.  **Launch the dashboard:**
    ```bash
    streamlit run src/dashboard/dashboard.py
    ```

### Analysis Scripts

This project includes several powerful scripts for deeper analysis. For more details on each, see the [Analysis & Backtesting README](src/analysis/README.md).

-   **Analyze Price Statistics**: Get a detailed statistical summary of a day's market data.
    ```bash
    python -m src.analysis.analyze_prices
    ```
-   **Check Signal Accuracy**: Evaluate the historical accuracy of signals from the `Prediction` and `MovingAverage` strategies.
    ```bash
    python -m src.analysis.signal_accuracy_checker
    ```
-   **Reverse Engineer Past Trades**: Reconstruct the portfolio and market state for each trade from a user's trade history to understand their strategy.
    ```bash
    python -m src.analysis.reverse_engineer --market-data [path_to_market.csv] --user-data [path_to_user.csv]
    ```
    **Example:**
    ```bash
    python -m src.analysis.reverse_engineer --market-data data/market_data_20251226.csv --user-data data/user_data_20251226.csv
    ```

### Trader's Insight

-   **Start with Data**: Before running a backtest, use the **Dashboard** to visually inspect the market data for the day you want to analyze. This can provide valuable context and help you form a hypothesis about which strategy might perform well.
-   **Parameter Tuning**: The profitability of a strategy is highly sensitive to its parameters (e.g., the window sizes in the `MovingAverageStrategy`). Don't be discouraged by initial losses. The best approach is to backtest, analyze the results, tune one parameter at a time, and repeat.
-   **Understand the "Why"**: After a backtest, review the generated `detailed_log_..._trades.csv` file in the `logs/` directory. This provides a trade-by-trade account of the strategy's decisions. Correlate this with the dashboard charts to understand *why* the strategy succeeded or failed in specific market conditions. For example, did the `PredictionStrategy` fail because its `SharpEvent` filter was too sensitive and triggered on noise?
-   **No "One-Size-Fits-All"**: A strategy that is profitable on one day's volatile data may perform poorly on another day's sideways market. The goal of this framework is to find strategies that are consistently profitable across a wide range of market conditions.

### Using the Dashboard

The interactive dashboard is a powerful tool for visualizing market data. For a detailed explanation of each chart and its significance, please see the [Dashboard README](src/dashboard/README.md).

**Key Tips:**
-   **Identify Arbitrage**: Use the **Pair Cost** chart to spot opportunities where the combined cost of an "Up" and "Down" contract is less than $1.00.
-   **Track Recent Activity**: Use the **Zoom Last 15m** button to focus on the current market's activity, which is crucial for making timely decisions.
-   **Assess Liquidity**: Monitor the **Liquidity Depth** and **Liquidity Imbalance** charts to understand market sentiment and the feasibility of executing trades.

## Data Format

The data logger captures comprehensive order book data in date-stamped CSV files with the following columns:

| Column | Description |
|---|---|
| `Timestamp` | When the data was logged (UTC) |
| `TargetTime`| Market's target time (start of 15-min window) |
| `Expiration`| Market expiration time |
| `UpBid` | Best bid price for UP contracts |
| `UpAsk` | Best ask price for UP contracts |
| `UpMid` | Mid-market price for UP contracts |
| `UpSpread` | Bid-ask spread for UP contracts |
| `UpBidLiquidity` | Total UP bid liquidity (top 5 levels) |
| `UpAskLiquidity` | Total UP ask liquidity (top 5 levels) |
| `DownBid` | Best bid price for DOWN contracts |
| `DownAsk` | Best ask price for DOWN contracts |
| `DownMid` | Mid-market price for DOWN contracts |
| `DownSpread` | Bid-ask spread for DOWN contracts |
| `DownBidLiquidity` | Total DOWN bid liquidity (top 5 levels) |
| `DownAskLiquidity` | Total DOWN ask liquidity (top 5 levels) |

## Testing

To run the test suite, use the following command from the root directory:

```bash
python -m pytest
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for informational and educational purposes only. Trading cryptocurrencies and prediction markets involves risk. Always do your own research and never invest more than you can afford to lose.
