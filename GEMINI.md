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
*   `src/analysis/backtester.py`: A backtesting engine that simulates a `RebalancingStrategy` on historical data from the date-stamped CSV specified by the `ANALYSIS_DATE` in the config.
*   `src/analysis/slipp_backtester.py`: A second backtester, with a different `RebalancingStrategy`, also using the `ANALYSIS_DATE` from the config.
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

## 3. Run the Backtester

To test the trading strategy on the collected historical data, run the backtester with the following command:

```bash
python -m src.analysis.backtester
```

The backtester will output a detailed report of the strategy's performance, using the data file specified by `ANALYSIS_DATE` in `src/config.py`.

You can also run the alternative backtester, which uses a liquidity-based strategy:
```bash
python -m src.analysis.slipp_backtester
```

# Development Conventions

*   **Data Storage:** All market data is stored in date-stamped CSV files, e.g., `data/market_data_YYYYMMDD.csv`. The data logger always writes to the current day's file.
*   **Configuration:** Key parameters are configured in `src/config.py`. To analyze or backtest a specific day's data, set the `ANALYSIS_DATE` variable. If `ANALYSIS_DATE` is `0`, **the latest available data file** in the `data/` directory will be used for analysis. Otherwise, it should be an integer in `yyyymmdd` format (e.g., `20231225`).
*   **Modularity:** The project is well-structured, with distinct modules for data logging, visualization, and backtesting located in the `src` directory.
*   **Error Handling:** The `src/data_collection/data_logger.py` script includes error handling for network requests.
*   **Concurrency:** The `src/data_collection/data_logger.py` script uses threading to fetch and write data concurrently, ensuring that data collection is not blocked by disk I/O.
*   **Strategy-based Naming:** The two backtesting scripts (`src/analysis/backtester.py` and `src/analysis/slipp_backtester.py`) suggest a convention of creating separate files for different backtesting strategies.