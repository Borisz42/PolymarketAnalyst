import csv

def analyze_market_data(filename="market_data.csv"):
    count = 0
    sums_list = []
    
    try:
        with open(filename, mode='r', newline='') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader)  # Skip the header row
            
            # Try to find the column indices for 'up price' and 'down price'
            # Assuming typical names, case-insensitive
            up_price_col = -1
            down_price_col = -1
            timestamp_col = -1
            
            for i, col_name in enumerate(header):
                if col_name == 'UpAsk':
                    up_price_col = i
                if col_name == 'DownAsk':
                    down_price_col = i
                if col_name == 'Timestamp':
                    timestamp_col = i
            
            if up_price_col == -1 or down_price_col == -1:
                print(f"Error: Could not find 'UpPrice' or 'DownPrice' columns in {filename}")
                print(f"Header found: {header}")
                return
            if timestamp_col == -1:
                print(f"Error: Could not find 'Timestamp' column in {filename}")
                print(f"Header found: {header}")
                return

            for row in reader:
                try:
                    # Ensure row has enough columns
                    if len(row) > max(up_price_col, down_price_col, timestamp_col):
                        up_price = float(row[up_price_col])
                        down_price = float(row[down_price_col])
                        timestamp_val = row[timestamp_col]
                        
                        total_price = up_price + down_price
                        
                        if 0.9 < total_price < 1.0:
                            count += 1
                            sums_list.append(total_price)
                            print(f"Timestamp: {timestamp_val}, Row sum between 0.9 and 1.0: {total_price:.4f} (UpPrice: {up_price:.4f}, DownPrice: {down_price:.4f})")
                    else:
                        print(f"Skipping row due to insufficient columns: {row}")
                except ValueError:
                    print(f"Skipping row due to non-numeric price values: {row}")
                except IndexError:
                    print(f"Skipping row due to index error (malformed row?): {row}")
    except FileNotFoundError:
        print(f"Error: The file {filename} was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    print(f"Number of lines where (up price + down price) is between 0.9 and 1.0: {count}")
    if sums_list:
        average_sum = sum(sums_list) / len(sums_list)
        print(f"Average of these sums: {average_sum:.4f}")
    else:
        print("No sums were found to calculate an average.")

if __name__ == "__main__":
    analyze_market_data()
