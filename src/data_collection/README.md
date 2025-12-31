# Data Collection Module

This module is responsible for fetching and logging real-time data from Polymarket's 15-minute BTC prediction markets.

## Architecture

The data logger uses a multi-threaded architecture to ensure high performance and data integrity:

-   **Thread Pool for Fetching**: A `ThreadPoolExecutor` manages a pool of worker threads that concurrently fetch market data. This allows for multiple data requests to be in flight at the same time, increasing the data collection frequency without blocking.
-   **Thread-Safe Queue**: Fetched data is placed into a thread-safe `queue.Queue`. This acts as a buffer, decoupling the data fetching process from the disk writing process.
-   **Dedicated Writer Thread**: A single, dedicated thread runs in the background, periodically waking up to flush all the data from the queue to the CSV file on disk. This approach minimizes disk I/O operations and prevents data loss or corruption that could occur with multiple writers.

## Scripts

-   **`data_logger.py`**: The main entry point for the data collection process. It initializes the thread pool and the writer thread, and then submits fetch tasks at a regular interval.

-   **`fetch_current_polymarket.py`**: Handles the direct interaction with the Polymarket APIs. It fetches event details to get token IDs and then queries the order book for each outcome (Up/Down).

-   **`get_current_markets.py`**: Identifies the currently active 15-minute BTC market slug from the Polymarket homepage. This ensures the data logger is always targeting the correct, live market.

-   **`find_new_market.py`**: A utility script used by the data logger to detect when a new 15-minute market has started, ensuring a seamless transition from an expiring market to a new one.

## API Endpoints

The data collection process relies on two primary Polymarket APIs:

1.  **Gamma API (`https://gamma-api.polymarket.com/events`)**: Used to fetch high-level event details, including the market's `slug` and the `clobTokenIds` required to query the order book.

2.  **CLOB API (`https://clob.polymarket.com/book`)**: The conditional liquidity order book (CLOB) API. This is queried using a `token_id` to get detailed, real-time order book data, including bid/ask prices and liquidity depth for both "Up" and "Down" contracts.

## Data Flow

1.  The `data_logger.py` script starts and initializes the CSV file, thread pool, and writer thread.
2.  The main loop submits a `fetch_worker` task to the thread pool at a regular interval defined in `config.py`.
3.  The `fetch_worker` calls `fetch_current_polymarket.py` to query the Polymarket APIs.
4.  The fetched and structured data row is put into the thread-safe `data_queue`.
5.  The dedicated `writer_thread` wakes up periodically, drains the queue of all pending data, and writes the batch of rows to the CSV file in a single operation.
