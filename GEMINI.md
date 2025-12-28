# Project Overview

This project is a Python-based tool for monitoring, analyzing, and backtesting trading strategies on Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets. It features real-time data logging, an interactive dashboard, and a sophisticated backtesting engine.

**Main Technologies:**
*   **Python:** The core language for all scripts.
*   **Streamlit:** Used for the interactive web dashboard.
*   **Pandas:** Used for data manipulation and analysis.
*   **Plotly:** Used for creating interactive charts in the dashboard.

**Architecture:**

The project is composed of several key modules, located in the `src` directory:

*   `src/config.py`: Centralized configuration for data file paths, date stamping format, initial capital, and other global parameters. It includes an `ANALYSIS_DATE` setting to specify which day's data the backtesters and dashboard should use.
*   `src/data_collection/data_logger.py`: A multi-threaded script that fetches market data from Polymarket at regular intervals and **always logs to the current day's** date-stamped CSV file in the `data/` directory (e.g., `data/market_data_YYYYMMDD.csv`).
*   `src/dashboard/dashboard.py`: A Streamlit application that provides a visualization of historical market data. It reads from the date-stamped CSV specified by the `ANALYSIS_DATE` in the config.
*   `src/analysis/backtester.py`: A generic backtesting engine that can simulate various trading strategies on historical data.
*   `src/analysis/strategies/`: A directory containing the different trading strategies that can be used with the backtester.
*   `src/analysis/backtester.py`: A backtesting engine that simulates a `RebalancingStrategy` on historical data from the date-stamped CSV specified by the `ANALYSIS_DATE` in the config.
*   `src/analysis/prediction_backtester.py`: A second backtester, which uses a `PredictionStrategy` on historical data from the date-stamped CSV specified by the `ANALYSIS_DATE` in the config.
*   `src/analysis/analyze_prices.py`: A script for analyzing historical market data from a given day. It provides summary statistics, and determines market resolution outcomes. The script logs which specific markets resolved to "Up" and which to "Down".
*   `src/data_collection/fetch_current_polymarket.py`: A utility script for fetching data from the Polymarket API.
*   `risk_engine.py`, `state_manager.py`, and `accumulator.py`: These modules seem to contain the core logic for the trading strategy, risk management, and state tracking, which are utilized by the backtesting scripts.

# Building and Running

## 1. Start the Data Logger

To begin collecting market data, run the following command in your terminal from the root directory of the project:

```bash
python -m src.data_collection.data_logger
```

This will create and continuously update the `data/market_data_YYYYMMDD.csv` file (where YYYYMMDD is the current date).

## 2. Launch the Dashboard

To view the interactive dashboard, open a new terminal and run:

```bash
streamlit run src/dashboard/dashboard.py
```

This will open the dashboard in your web browser, typically at `http://localhost:8501`, reading from the data file specified by `ANALYSIS_DATE` in `src/config.py`.

## 3. Run the Backtester with Different Strategies

To test a trading strategy on the collected historical data, run the appropriate backtesting script:

**Rebalancing Strategy:**
```bash
python -m src.analysis.backtester
```

**Prediction Strategy:**
```bash
python -m src.analysis.prediction_backtester
```

The backtester will output a detailed report of the strategy's performance, using the data file specified by `ANALYSIS_DATE` in `src/config.py`.
## 4. Run Price Analysis

To run the price analysis script on the collected historical data, run the following command:
```bash
python -m src.analysis.analyze_prices
```

# Development Conventions

*   **Data Storage:** All market data is stored in date-stamped CSV files, e.g., `data/market_data_YYYYMMDD.csv`. The data logger always writes to the current day's file.
*   **Configuration:** Key parameters are configured in `src/config.py`. To analyze or backtest a specific day's data, set the `ANALYSIS_DATE` variable. If `ANALYSIS_DATE` is `0`, **the latest available data file** in the `data/` directory will be used for analysis. Otherwise, it should be an integer in `yyyymmdd` format (e.g., `20231225`).
*   **Modular Strategies:** The project uses a modular design for trading strategies.
    *   All strategies are located in the `src/analysis/strategies/` directory.
    *   Each strategy should be in its own file and inherit from the `Strategy` base class in `src/analysis/strategies/base_strategy.py`.
    *   To test a new strategy, create a new runner script in `src/analysis/` similar to `prediction_backtester.py`.
*   **Dependencies:** The project does not have a `requirements.txt` file. Dependencies must be installed manually. So far, `pandas` and `streamlit` are known dependencies.
*   **Imports:** Scripts within the `src/analysis/` package that are executed as modules must use relative imports (e.g., `from . import ...`) to access other modules within the same package.
