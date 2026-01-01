# AGENTS.md

This document provides guidance for AI agents working on the Polymarket BTC Monitor codebase.

## Project Overview

This project is a tool for monitoring and analyzing Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets. It includes a data collection service, a backtesting engine, and an interactive dashboard. The primary goal is to develop and test profitable trading strategies.

**Main Technologies:**
*   **Python:** The core language for all scripts.
*   **Streamlit:** Used for the interactive web dashboard.
*   **Pandas:** Used for data manipulation and analysis.
*   **Plotly:** Used for creating interactive charts in the dashboard.

## Core Components

-   **`src/data_collection/data_logger.py`**: A multi-threaded script that runs in the background to collect real-time market data and save it to CSV files in the `data/` directory.
-   **`src/analysis/backtester.py`**: The main backtesting engine. It simulates trading strategies on historical data, handles PnL calculations, and provides a detailed report. It is strategy-agnostic.
-   **`src/analysis/prediction_backtester.py`**: A specialized backtester script that includes a `preprocess_data` function to create features needed for the `PredictionStrategy`. It uses the main `Backtester` class to run the simulation.
-   **`src/analysis/hybrid_backtester.py`**: A backtester script for the `HybridStrategy`.
-   **`src/analysis/signal_accuracy_checker.py`**: A script to analyze the accuracy of trading signals.
-   **`src/analysis/strategies/`**: This directory contains the trading strategies. All strategies inherit from `src/analysis/strategies/base_strategy.py`.
-   **`src/config.py`**: Centralized configuration for the project. The `ANALYSIS_DATE` variable is important for selecting which day's data to use for backtesting. Set to `0` to use the latest data.
-   **`src/dashboard/dashboard.py`**: A Streamlit-based interactive dashboard for visualizing market data.

## How to Run

### Data Logger

To start collecting data, run the following command from the root directory:

```bash
python -m src.data_collection.data_logger
```

### Backtesters

Before running a backtester, ensure the `ANALYSIS_DATE` in `src/config.py` is set to the desired date (`yyyymmdd` format) or `0` for the latest data.

-   **To run the `RebalancingStrategy`:**
    ```bash
    python -m src.analysis.backtester
    ```
-   **To run the `PredictionStrategy`:**
    ```bash
    python -m src.analysis.prediction_backtester
    ```
-   **To run the `HybridStrategy`:**
    ```bash
    python -m src.analysis.hybrid_backtester
    ```

### Analysis

-   **To run the signal accuracy checker:**
    ```bash
    python -m src.analysis.signal_accuracy_checker
    ```

### Tests

To run the test suite, use `pytest`:

```bash
python -m pytest
```
You may need to install pytest first: `pip install pytest`.

## Strategies

### `RebalancingStrategy`

-   **Objective**: To accumulate paired positions (both UP and DOWN) when profitable opportunities arise.
-   **Logic**: It seeks to maintain a balanced portfolio. When the portfolio is balanced, it looks for opportunities to buy a pair of UP and DOWN contracts where the combined cost is less than $1.00 (controlled by `SAFETY_MARGIN_M`). When unbalanced, it seeks to buy the contract that will bring the portfolio back to a balanced state.
-   **Constraints**: It incorporates several risk management constraints, including `MAX_UNHEDGED_DELTA`, `MIN_LIQUIDITY_MULTIPLIER`, and `MAX_TRADE_SIZE`.

### `PredictionStrategy`

-   **Objective**: To make directional trades based on sharp price movements and liquidity imbalances.
-   **Logic**: This is an event-driven strategy. It only considers trading when a "SharpEvent" occurs (a significant price change). It then calculates a score based on price delta and liquidity imbalance to decide whether to buy an UP or DOWN contract.
-   **Features**: This strategy relies on pre-calculated features created in `src/analysis/prediction_backtester.py`. These features include `MinuteFromStart`, `UpMidDelta`, `DownMidDelta`, `BidLiquidityImbalance`, and `SharpEvent`.
-   **Time Window**: It only trades within a specific time window of the market's 15-minute duration, defined by `MIN_MINUTE` and `MAX_MINUTE`.

### `HybridStrategy`

-   **Objective**: To combine the `PredictionStrategy` and `RebalancingStrategy` to improve performance.
-   **Logic**: It uses the `PredictionStrategy`'s signal to initiate a trade, and then uses the `RebalancingStrategy`'s logic to manage the position. This allows the strategy to enter trades based on market momentum, and then manage risk by seeking to create balanced pairs.

## Development Conventions

-   **Data Storage:** All market data is stored in date-stamped CSV files, e.g., `data/market_data_YYYYMMDD.csv`. The data logger always writes to the current day's file.
-   **Configuration:** Key parameters are configured in `src/config.py`. To analyze or backtest a specific day's data, set the `ANALYSIS_DATE` variable. If `ANALYSIS_DATE` is `0`, **the latest available data file** in the `data/` directory will be used for analysis. Otherwise, it should be an integer in `yyyymmdd` format (e.g., `20231225`).
-   **Modular Strategies:** The project uses a modular design for trading strategies.
    -   All strategies are located in the `src/analysis/strategies/` directory.
    -   Each strategy should be in its own file and inherit from the `Strategy` base class in `src/analysis/strategies/base_strategy.py`.
    -   To test a new strategy, create a new runner script in `src/analysis/` similar to `prediction_backtester.py`.
-   **Dependencies:** Project dependencies are managed in `requirements.txt`. To install them, run `pip install -r requirements.txt`.
-   **Imports:** Scripts in `src/analysis` that are intended to be run as standalone modules should use absolute imports (e.g., `from src.analysis...`) rather than relative imports to avoid `ImportError`.
-   **Testing**:
    -   When adding new features, please add corresponding tests in the `tests/` directory.
    -   Always run the full test suite with `python -m pytest` before submitting changes.
