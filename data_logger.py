import time
import datetime
import csv
import os
from fetch_current_polymarket import fetch_polymarket_data_struct

DATA_FILE = "market_data.csv"
LOOGING_INTERVAL_SECONDS = 5


def init_csv():
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "TargetTime", "Expiration", "UpPrice", "DownPrice"])
        print(f"Created {DATA_FILE}")

def log_data():
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    fetched_data, err = fetch_polymarket_data_struct()
    
    # Check if data is complete
    data = None
    if fetched_data and \
       fetched_data.get('prices') is not None:
         data = fetched_data
    else:
        error_msg = err if err else "Missing fields"
        print(f"[{timestamp}] Error: Could not retrieve full data ({error_msg})")
        return

    # Extract values
    target_time = data.get('target_time_utc', '')
    expiration = data.get('expiration_time_utc', '')
    up_price = data['prices'].get('Up', 0.0)
    down_price = data['prices'].get('Down', 0.0)
    
    row = [timestamp, target_time, expiration, up_price, down_price]
    
    with open(DATA_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(row)
        
    print(f"[{timestamp}] Logged: Up={up_price}, Down={down_price}")

def main():
    print("Starting Data Logger...")
    init_csv()
    
    while True:
        try:
            log_data()
            time.sleep(LOOGING_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopping logger...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(LOOGING_INTERVAL_SECONDS)   

if __name__ == "__main__":
    main()
