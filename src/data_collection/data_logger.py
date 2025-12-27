import time
import datetime
import csv
import os
import threading
import queue
from concurrent.futures import ThreadPoolExecutor
from .fetch_current_polymarket import get_active_btcusd_markets

DATA_FILE = "data/market_data.csv"
FETCH_INTERVAL_SECONDS = 1
WRITE_INTERVAL_SECONDS = 5
MAX_WORKERS = 15

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
    Background worker to fetch data and put it in the queue.
    """
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time = time.time()
    
    try:
        fetched_data, err = fetch_polymarket_data_struct()
        elapsed_time = time.time() - start_time
        
        if err:
            # Silence simple timeout errors or just print them briefly
            print(f"[{timestamp}] Fetch Error ({elapsed_time:.3f}s): {err}")
            return

        # Check if data is complete
        if not fetched_data or fetched_data.get('order_books') is None:
            print(f"[{timestamp}] Incomplete data")
            return

        # Extract values
        data = fetched_data
        target_time = data.get('target_time_utc', '')
        expiration = data.get('expiration_time_utc', '')

        target_time_str = target_time.strftime('%Y-%m-%d %H:%M:%S') if target_time else ''
        expiration_str = expiration.strftime('%Y-%m-%d %H:%M:%S') if expiration else ''
        
        # Extract order book data
        up_book = data['order_books'].get('Up', {})
        down_book = data['order_books'].get('Down', {})
        
        # UP side data (rounded to 3 decimal places)
        up_bid = round(up_book.get('best_bid', 0.0), 3)
        up_ask = round(up_book.get('best_ask', 0.0), 3)
        up_mid = round(up_book.get('mid_price', 0.0), 3)
        up_spread = round(up_book.get('spread', 0.0), 3)
        up_bid_liq = round(up_book.get('bid_liquidity', 0.0), 3)
        up_ask_liq = round(up_book.get('ask_liquidity', 0.0), 3)
        
        # DOWN side data (rounded to 3 decimal places)
        down_bid = round(down_book.get('best_bid', 0.0), 3)
        down_ask = round(down_book.get('best_ask', 0.0), 3)
        down_mid = round(down_book.get('mid_price', 0.0), 3)
        down_spread = round(down_book.get('spread', 0.0), 3)
        down_bid_liq = round(down_book.get('bid_liquidity', 0.0), 3)
        down_ask_liq = round(down_book.get('ask_liquidity', 0.0), 3)
        
        row = [
            timestamp, target_time_str, expiration_str,
            up_bid, up_ask, up_mid, up_spread, up_bid_liq, up_ask_liq,
            down_bid, down_ask, down_mid, down_spread, down_bid_liq, down_ask_liq
        ]
        
        # Enqueue the valid data row
        data_queue.put(row)
        
        print(f"[{timestamp}] Fetched: Up({up_mid:.3f}) Down({down_mid:.3f}) fetch_time={elapsed_time:.3f}s")

    except Exception as e:
        print(f"[{timestamp}] Worker Exception: {e}")

def writer_thread():
    """
    Dedicated thread that wakes up periodically to flush queue to disk.
    """
    print("Writer thread started.")
    while True:
        time.sleep(WRITE_INTERVAL_SECONDS)
        
        rows_to_write = []
        try:
            # Drain the queue
            while True:
                row = data_queue.get_nowait()
                rows_to_write.append(row)
                data_queue.task_done()
        except queue.Empty:
            pass
        
        if rows_to_write:
            # Sort rows by timestamp (index 0) to ensure strictly ascending order
            rows_to_write.sort(key=lambda x: x[0])
            
            try:
                with open(DATA_FILE, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerows(rows_to_write)
                print(f"--> Flushed {len(rows_to_write)} records to disk.")
            except Exception as e:
                print(f"Error writing to CSV: {e}")

def main():
    print("Starting Threaded Data Logger...")
    print(f" - Fetch Interval: {FETCH_INTERVAL_SECONDS}s")
    print(f" - Write Buffer: {WRITE_INTERVAL_SECONDS}s")
    print(f" - Max Concurrent Requests: {MAX_WORKERS}")
    
    init_csv()
    
    # Start the writer thread
    w_thread = threading.Thread(target=writer_thread, daemon=True)
    w_thread.start()
    
    # Create a thread pool for fetch tasks, use manual shutdown control
    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    
    try:
        while True:
            # Submit a new fetch task
            executor.submit(fetch_worker)
            time.sleep(FETCH_INTERVAL_SECONDS)
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
