import time
import datetime
import csv
import os
import logging
from functools import wraps
from fetch_current_polymarket import fetch_polymarket_data_struct

import json

# --- Configuration ---
DEFAULT_CONFIG = {
  "logging_interval_seconds": 10,
  "output_file": "market_data.csv",
  "error_log_file": "data_logger_errors.log",
  "enable_buffering": True,
  "buffer_size": 6,
  "enable_validation": True,
  "enable_market_markers": True,
  "enable_daily_rotation": True
}

def load_config():
    try:
        with open('logger_config.json', 'r') as f:
            config = json.load(f)
            # Merge with defaults to ensure all keys are present
            return {**DEFAULT_CONFIG, **config}
    except FileNotFoundError:
        logging.warning("logger_config.json not found, using default settings.")
        return DEFAULT_CONFIG
    except json.JSONDecodeError:
        logging.error("Error decoding logger_config.json, using default settings.")
        return DEFAULT_CONFIG

config = load_config()

DATA_FILE_BASENAME = config['output_file']
ERROR_LOG_FILE = config['error_log_file']
LOGGING_INTERVAL_SECONDS = config['logging_interval_seconds']
BUFFER_SIZE = config['buffer_size']
ENABLE_BUFFERING = config['enable_buffering']
ENABLE_VALIDATION = config['enable_validation']
ENABLE_MARKET_MARKERS = config['enable_market_markers']
ENABLE_DAILY_ROTATION = config['enable_daily_rotation']

def get_data_file():
    if ENABLE_DAILY_ROTATION:
        date_str = datetime.datetime.now().strftime('%Y-%m-%d')
        return f"{DATA_FILE_BASENAME.replace('.csv', '')}_{date_str}.csv"
    return DATA_FILE_BASENAME

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(ERROR_LOG_FILE),
        logging.StreamHandler()
    ]
)

def retry(tries=3, delay=5, backoff=2):
    """Retry decorator with exponential backoff."""
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except Exception as e:
                    msg = f"{str(e)}, Retrying in {mdelay} seconds..."
                    logging.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)
        return f_retry
    return deco_retry

def init_csv():
    data_file = get_data_file()
    if not os.path.exists(data_file):
        with open(data_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "TargetTime", "Expiration", "Strike", "CurrentPrice", "UpPrice", "DownPrice", "BidAskSpread", "AnomalyFlag"])
        logging.info(f"Created {data_file}")

@retry(tries=3, delay=5, backoff=2)
def fetch_data_with_retry():
    return fetch_polymarket_data_struct()




buffer = []

def flush_buffer():
    global buffer
    if buffer:
        data_file = get_data_file()
        with open(data_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerows(buffer)
        logging.info(f"Flushed {len(buffer)} rows to {data_file}")
        buffer = []

def main():
    logging.info("Starting Data Logger...")
    init_csv()
    previous_expiration_time = None
    previous_up_price = None
    previous_down_price = None
    
    # Statistics
    start_time = time.time()
    logs_written = 0
    successful_fetches = 0
    failed_fetches = 0
    total_latency = 0

    try:
        while True:
            try:
                log_start_time = time.time()
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                fetched_data, err = fetch_data_with_retry()
                data = fetched_data or {}
                
                if err:
                    logging.error(f"Could not retrieve full data after retries: {err}")
                    failed_fetches += 1
                else:
                    successful_fetches += 1

                expiration = data.get('expiration_time_utc')

                # Market Transition Handling
                if ENABLE_MARKET_MARKERS and previous_expiration_time and expiration and previous_expiration_time != expiration:
                    logging.info(f"Market transition detected from {previous_expiration_time} to {expiration}")
                    if ENABLE_BUFFERING:
                        flush_buffer()
                    data_file = get_data_file()
                    with open(data_file, mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(["-"*20, "MARKET TRANSITION", "-"*20, "-"*20, "-"*20, "-"*20, "-"*20, "-"*20, "-"*20])
                    previous_up_price = None
                    previous_down_price = None

                previous_expiration_time = expiration

                # Extract values, logging what we can
                target_time = data.get('target_time_utc', '')
                strike = data.get('price_to_beat')
                current_price = data.get('current_price')
                up_price = data.get('prices', {}).get('Up')
                down_price = data.get('prices', {}).get('Down')
                
                # Data Validation
                anomaly_flag = False
                bid_ask_spread = None

                if ENABLE_VALIDATION:
                    if up_price is not None and down_price is not None:
                        # Price range validation
                        if not (0.0 <= up_price <= 1.0 and 0.0 <= down_price <= 1.0):
                            logging.warning(f"Price out of range: Up={up_price}, Down={down_price}")
                        
                        # Bid-ask spread
                        bid_ask_spread = abs(up_price - (1 - down_price))

                        # Anomaly detection
                        if previous_up_price is not None and previous_down_price is not None:
                            if abs(up_price - previous_up_price) > 0.5 or abs(down_price - previous_down_price) > 0.5:
                                anomaly_flag = True
                                logging.warning(f"Anomaly detected: Large price jump. Previous: Up={previous_up_price}, Down={previous_down_price}. Current: Up={up_price}, Down={down_price}")
                
                previous_up_price = up_price
                previous_down_price = down_price

                # Validate data completeness
                if strike is None or current_price is None or up_price is None or down_price is None:
                    logging.warning(f"Logging partial data: {data}")

                row = [timestamp, target_time, expiration, strike, current_price, up_price, down_price, bid_ask_spread, anomaly_flag]
                
                if ENABLE_BUFFERING:
                    buffer.append(row)
                    if len(buffer) >= BUFFER_SIZE:
                        flush_buffer()
                else:
                    data_file = get_data_file()
                    with open(data_file, mode='a', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(row)
                
                logs_written += 1
                log_end_time = time.time()
                latency = log_end_time - log_start_time
                total_latency += latency

                logging.info(f"Logged: Strike={strike}, Current={current_price}, Up={up_price}, Down={down_price}")

                if logs_written % 100 == 0:
                    uptime = time.time() - start_time
                    success_rate = (successful_fetches / (successful_fetches + failed_fetches)) * 100 if (successful_fetches + failed_fetches) > 0 else 100
                    avg_latency = total_latency / logs_written if logs_written > 0 else 0
                    logging.info(f"--- Statistics ---")
                    logging.info(f"Uptime: {datetime.timedelta(seconds=uptime)}")
                    logging.info(f"Logs written: {logs_written}")
                    logging.info(f"Success rate: {success_rate:.2f}%")
                    logging.info(f"Average latency: {avg_latency:.4f}s")
                    logging.info(f"--- End Statistics ---")


                time.sleep(LOGGING_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logging.info("\nStopping logger...")
                break
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}")
                time.sleep(LOGGING_INTERVAL_SECONDS)
    finally:
        if ENABLE_BUFFERING:
            flush_buffer()





if __name__ == "__main__":
    main()