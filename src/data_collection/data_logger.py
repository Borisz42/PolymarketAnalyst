import time
import datetime
import csv
import os
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from .fetch_current_polymarket import fetch_polymarket_data_struct

import src.config as config

DATA_FILE = config.get_logger_filename()
# Thread-safe queue for buffering data
data_queue = queue.Queue()

def init_csv():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            # Enhanced headers with order book data
            writer.writerow([
                "Timestamp", "TargetTime", "Expiration",
                "UpBid", "UpAsk", "UpMid", "UpSpread", "UpBidLiquidity", "UpAskLiquidity",
                "DownBid", "DownAsk", "DownMid", "DownSpread", "DownBidLiquidity", "DownAskLiquidity"
            ])
        print(f"Created {DATA_FILE} with enhanced order book columns")

def fetch_worker():
    """
    I/O-bound worker. Fetches data and puts the raw result onto the queue.
    By offloading CPU-bound work (data processing, rounding) to the writer
    thread, these concurrent workers become leaner, hold the GIL for less
    time, and improve overall I/O throughput.
    """
    timestamp_utc = datetime.datetime.now(datetime.timezone.utc)
    start_time = time.time()
    
    try:
        fetched_data, err = fetch_polymarket_data_struct()
        elapsed_time = time.time() - start_time
        
        if err:
            # Log errors with a formatted timestamp
            print(f"[{timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')}] Fetch Error ({elapsed_time:.3f}s): {err}")
            return

        # Check for essential data before queueing
        if not fetched_data or 'order_books' not in fetched_data:
            print(f"[{timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')}] Incomplete data received")
            return

        # --- OPTIMIZATION: Put raw data on queue ---
        # The worker's only job is I/O. It puts the raw timestamp and data
        # on the queue. All CPU-bound processing is deferred to the writer.
        data_queue.put((timestamp_utc, fetched_data))
        
        # For logging, we can quickly access a key value
        up_mid = fetched_data['order_books'].get('Up', {}).get('mid_price', 0.0)
        down_mid = fetched_data['order_books'].get('Down', {}).get('mid_price', 0.0)
        
        print(f"[{timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')}] Fetched: Up({up_mid:.3f}) Down({down_mid:.3f}) fetch_time={elapsed_time:.3f}s")

    except Exception as e:
        print(f"[{timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')}] Worker Exception: {e}")

def writer_thread():
    """
    CPU-bound worker. Drains the queue, processes the raw data in a batch,
    and writes the final, formatted rows to disk. This centralizes the CPU work
    for better efficiency and cache locality.
    """
    print("Writer thread started.")
    while True:
        time.sleep(config.WRITE_INTERVAL_SECONDS)
        
        raw_data_batch = []
        try:
            # Drain the queue of all raw data
            while True:
                raw_data_batch.append(data_queue.get_nowait())
                data_queue.task_done()
        except queue.Empty:
            pass
        
        if raw_data_batch:
            # --- OPTIMIZATION: Centralized CPU Work ---
            # All data processing happens here in a single, efficient batch.

            # 1. Sort by the timestamp object (the first element of the tuple)
            raw_data_batch.sort(key=lambda x: x[0])

            final_rows_to_write = []
            for timestamp_utc, data in raw_data_batch:
                # 2. Perform all string formatting and rounding in this loop
                timestamp_str = timestamp_utc.strftime('%Y-%m-%d %H:%M:%S')
                target_time = data.get('target_time_utc', '')
                expiration = data.get('expiration_time_utc', '')
                target_time_str = target_time.strftime('%Y-%m-%d %H:%M:%S') if target_time else ''
                expiration_str = expiration.strftime('%Y-%m-%d %H:%M:%S') if expiration else ''

                up_book = data.get('order_books', {}).get('Up', {})
                down_book = data.get('order_books', {}).get('Down', {})

                # Process and round all numeric data
                row = [
                    timestamp_str, target_time_str, expiration_str,
                    round(up_book.get('best_bid', 0.0), 3),
                    round(up_book.get('best_ask', 0.0), 3),
                    round(up_book.get('mid_price', 0.0), 3),
                    round(up_book.get('spread', 0.0), 3),
                    round(up_book.get('bid_liquidity', 0.0), 3),
                    round(up_book.get('ask_liquidity', 0.0), 3),
                    round(down_book.get('best_bid', 0.0), 3),
                    round(down_book.get('best_ask', 0.0), 3),
                    round(down_book.get('mid_price', 0.0), 3),
                    round(down_book.get('spread', 0.0), 3),
                    round(down_book.get('bid_liquidity', 0.0), 3),
                    round(down_book.get('ask_liquidity', 0.0), 3)
                ]
                final_rows_to_write.append(row)
            
            # 3. Perform the single I/O operation
            try:
                with open(DATA_FILE, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerows(final_rows_to_write)
                print(f"--> Flushed {len(final_rows_to_write)} records to disk.")
            except Exception as e:
                print(f"Error writing to CSV: {e}")

def main():
    print("Starting Threaded Data Logger...")
    print(f" - Fetch Interval: {config.FETCH_INTERVAL_SECONDS}s")
    print(f" - Write Buffer: {config.WRITE_INTERVAL_SECONDS}s")
    print(f" - Max Concurrent Requests: {config.MAX_WORKERS}")
    
    init_csv()
    
    # Start the writer thread
    w_thread = threading.Thread(target=writer_thread, daemon=True)
    w_thread.start()
    
    # Create a thread pool for fetch tasks, use manual shutdown control
    executor = ThreadPoolExecutor(max_workers=config.MAX_WORKERS)
    
    try:
        while True:
            # Submit a new fetch task
            executor.submit(fetch_worker)
            time.sleep(config.FETCH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopping logger...")
        # Cancel pending futures and don't wait for running ones
        # This ensures we exit immediately when user hits Ctrl+C
        executor.shutdown(wait=False, cancel_futures=True)
        print("Logged stopped.")
    except Exception as e:
        print(f"Main loop error: {e}")
        executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
