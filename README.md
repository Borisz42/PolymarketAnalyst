# Polymarket BTC Monitor

A Python-based tool to monitor **Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets**. It features real-time data logging, an interactive analysis dashboard, and a modular backtesting framework for developing and evaluating trading strategies.

## Features

-   **Data Collection**:
    -   **Automated Market Detection**: Automatically finds the active 15-minute BTC market.
    -   **Real-time Data Logging**: Fetches and logs market data, including comprehensive order book depth.
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
PolymarketAnalyst/
├── AGENTS.md
├── GEMINI.md
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
│   │   ├── backtester.py
│   │   ├── hybrid_backtester.py
│   │   ├── prediction_backtester.py
│   │   ├── signal_accuracy_checker.py
│   │   └── strategies/
│   │       ├── __init__.py
│   │       ├── base_strategy.py
│   │       ├── hybrid_strategy.py
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

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/PolymarketAnalyst.git
    cd PolymarketAnalyst
    ```
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
    ```bash
    python -m src.analysis.backtester
    ```
3.  **Launch the dashboard:**
    ```bash
    streamlit run src/dashboard/dashboard.py
    ```

### Dashboard Tips

-   Watch the **Pair Cost chart** for trading opportunities.
-   Use **Zoom Last 15m** to track recent market activity.
-   Monitor the **Opportunity Indicator** for real-time trading signals.

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
pytest
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for informational and educational purposes only. Trading cryptocurrencies and prediction markets involves risk. Always do your own research and never invest more than you can afford to lose.
