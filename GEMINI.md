# Project Overview

This project is a Python-based tool for monitoring, analyzing, and backtesting trading strategies on Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets. It features real-time data logging, an interactive dashboard, and a sophisticated backtesting engine.

**Main Technologies:**
*   **Python:** The core language for all scripts.
*   **Streamlit:** Used for the interactive web dashboard.
*   **Pandas:** Used for data manipulation and analysis.
*   **Plotly:** Used for creating interactive charts in the dashboard.

**Architecture:**

The project is composed of several key modules, located in the `src` directory:

*   `src/data_collection/data_logger.py`: A multi-threaded script that fetches market data from Polymarket at regular intervals and logs it to `data/market_data.csv`.
*   `src/dashboard/dashboard.py`: A Streamlit application that provides a visualization of the historical market data, including price trends and liquidity.
*   `src/analysis/backtester.py`: A backtesting engine that simulates a `RebalancingStrategy` on the historical data in `data/market_data.csv`. It includes risk management and detailed performance reporting.
*   `src/analysis/slipp_backtester.py`: A second backtester, with a different `RebalancingStrategy` that incorporates liquidity imbalance as a primary factor in its trading decisions.
*   `src/data_collection/fetch_current_polymarket.py`: A utility script for fetching data from the Polymarket API.
*   `risk_engine.py`, `state_manager.py`, and `accumulator.py`: These modules seem to contain the core logic for the trading strategy, risk management, and state tracking, which are utilized by the backtesting scripts.

# Building and Running

## 1. Start the Data Logger

To begin collecting market data, run the following command in your terminal from the root directory of the project:

```bash
python -m src.data_collection.data_logger
```

This will create and continuously update the `data/market_data.csv` file.

## 2. Launch the Dashboard

To view the interactive dashboard, open a new terminal and run:

```bash
streamlit run src/dashboard/dashboard.py
```

This will open the dashboard in your web browser, typically at `http://localhost:8501`.

## 3. Run the Backtester

To test the trading strategy on the collected historical data, run the backtester with the following command:

```bash
python -m src.analysis.backtester
```

The backtester will output a detailed report of the strategy's performance.

You can also run the alternative backtester, which uses a liquidity-based strategy:
```bash
python -m src.analysis.slipp_backtester
```

# Development Conventions

*   **Data Storage:** All market data is stored in a single CSV file, `data/market_data.csv`.
*   **Configuration:** Key parameters for the backtesting strategy, such as `INITIAL_CAPITAL` and `SAFETY_MARGIN_M`, are configured as global variables within the backtesting scripts.
*   **Modularity:** The project is well-structured, with distinct modules for data logging, visualization, and backtesting located in the `src` directory.
*   **Error Handling:** The `src/data_collection/data_logger.py` script includes error handling for network requests.
*   **Concurrency:** The `src/data_collection/data_logger.py` script uses threading to fetch and write data concurrently, ensuring that data collection is not blocked by disk I/O.
*   **Strategy-based Naming:** The two backtesting scripts (`src/analysis/backtester.py` and `src/analysis/slipp_backtester.py`) suggest a convention of creating separate files for different backtesting strategies.