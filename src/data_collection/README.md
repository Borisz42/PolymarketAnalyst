# Data Collection Module

This module is responsible for fetching and logging real-time data from Polymarket's 15-minute BTC prediction markets.

## Scripts

-   **`data_logger.py`**: The main entry point for the data collection process. This script runs in a loop to continuously fetch the latest market data and append it to a date-stamped CSV file in the `data/` directory.

-   **`fetch_current_polymarket.py`**: Handles the direct interaction with the Polymarket APIs. It fetches event details to get token IDs and then queries the order book for each outcome (Up/Down).

-   **`get_current_markets.py`**: Identifies the currently active 15-minute BTC market slug from the Polymarket homepage. This ensures the data logger is always targeting the correct, live market.

-   **`find_new_market.py`**: A utility script used by the data logger to detect when a new 15-minute market has started, ensuring a seamless transition from an expiring market to a new one.

## API Endpoints

The data collection process relies on two primary Polymarket APIs:

1.  **Gamma API (`https://gamma-api.polymarket.com/events`)**: Used to fetch high-level event details, including the market's `slug` and the `clobTokenIds` required to query the order book.

2.  **CLOB API (`https://clob.polymarket.com/book`)**: The conditional liquidity order book (CLOB) API. This is queried using a `token_id` to get detailed, real-time order book data, including bid/ask prices and liquidity depth for both "Up" and "Down" contracts.

## Data Flow

1.  The `data_logger.py` script starts and calls `find_new_market.py` to identify the active market `slug`.
2.  It then enters a loop, calling `fetch_current_polymarket.py` at regular intervals.
3.  `fetch_current_polymarket.py` queries the **Gamma API** to get the market's token IDs.
4.  It then queries the **CLOB API** for each token ID to get the order book data.
5.  The structured data is returned to `data_logger.py`, which formats it and appends it as a new row to the appropriate CSV file in the `data/` directory.
