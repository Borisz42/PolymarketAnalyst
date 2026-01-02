import requests
import csv
import argparse
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# --- Configuration ---
DATA_API = "https://data-api.polymarket.com"
API_LIMIT_PER_PAGE = 1000

def fetch_and_process_trades(wallet_address, start_time_utc, end_time_utc, temp_filename):
    """
    Fetches user trades, filters them, and saves them to a temporary CSV file without sorting.
    This preserves memory by processing data in chunks and provides progress updates.
    """
    try:
        et_zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        print("Error: 'America/New_York' timezone not found. Please ensure your system's timezone database is up to date.")
        return 0

    headers = ["timestamp_et", "market_title", "outcome", "side", "size", "price"]
    total_trades_saved = 0
    total_trades_scanned = 0
    offset = 0

    print(f"Starting to fetch and process trades from {start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} to {end_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

    try:
        with open(temp_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

            while True:
                url = f"{DATA_API}/trades"
                params = {"user": wallet_address, "limit": API_LIMIT_PER_PAGE, "offset": offset}
                try:
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    trades_page = response.json()
                except requests.exceptions.RequestException as e:
                    print(f"An error occurred while fetching trades: {e}")
                    break

                if not trades_page:
                    print("No more trades found on the API.")
                    break

                total_trades_scanned += len(trades_page)
                page_filtered_trades = []

                for trade in trades_page:
                    trade_timestamp = trade.get("timestamp", 0)
                    trade_time_utc = datetime.fromtimestamp(trade_timestamp, tz=ZoneInfo("UTC"))

                    if not (start_time_utc <= trade_time_utc < end_time_utc):
                        continue

                    title = trade.get("title", "")
                    if "Bitcoin Up or Down" in title and "-" in title.split(" - ")[-1]:
                        trade_time_et = trade_time_utc.astimezone(et_zone)
                        page_filtered_trades.append({
                            "timestamp_et": trade_time_et.strftime('%Y-%m-%d %H:%M:%S'),
                            "market_title": title,
                            "outcome": trade.get("outcome", "N/A"),
                            "side": trade.get("side", "N/A"),
                            "size": trade.get("size", 0),
                            "price": trade.get("price", 0.0),
                        })

                if page_filtered_trades:
                    writer.writerows(page_filtered_trades)
                    total_trades_saved += len(page_filtered_trades)

                print(f"Scanned: {total_trades_scanned} | Saved: {total_trades_saved} | Current Page Matches: {len(page_filtered_trades)}")

                last_trade_timestamp = trades_page[-1].get("timestamp", 0)
                last_trade_time_utc = datetime.fromtimestamp(last_trade_timestamp, tz=ZoneInfo("UTC"))
                if last_trade_time_utc < start_time_utc:
                    print("Reached trades older than the start of the target date. Stopping API calls.")
                    break

                offset += len(trades_page)

    except IOError as e:
        print(f"Error writing to temporary file: {e}")
        return 0

    print(f"\nFinished fetching. Total trades scanned: {total_trades_scanned}. Total matching trades found: {total_trades_saved}.")
    return total_trades_saved

def sort_and_save_final_csv(temp_filename, final_filename):
    """
    Reads the temporary CSV, sorts its contents chronologically, and saves to the final output file.
    """
    headers = ["timestamp_et", "market_title", "outcome", "side", "size", "price"]
    try:
        with open(temp_filename, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            all_trades = list(reader)

        if not all_trades:
            print("No matching trades were found. Creating an empty output file.")
            with open(final_filename, 'w', newline='', encoding='utf-8') as final_csv:
                writer = csv.DictWriter(final_csv, fieldnames=headers)
                writer.writeheader()
            return

        print(f"Sorting {len(all_trades)} trades...")
        all_trades.sort(key=lambda x: x["timestamp_et"])

        with open(final_filename, 'w', newline='', encoding='utf-8') as final_csv:
            writer = csv.DictWriter(final_csv, fieldnames=headers)
            writer.writeheader()
            writer.writerows(all_trades)

        print(f"Successfully sorted and saved {len(all_trades)} trades to {final_filename}")

    except FileNotFoundError:
        print(f"Warning: Temporary file '{temp_filename}' not found. Creating an empty output file.")
        with open(final_filename, 'w', newline='', encoding='utf-8') as final_csv:
            writer = csv.DictWriter(final_csv, fieldnames=headers)
            writer.writeheader()
    except IOError as e:
        print(f"Error during file operations: {e}")


def main():
    parser = argparse.ArgumentParser(description="Fetch historical trades for a Polymarket user for a specific date.")
    parser.add_argument("--address", required=True, help="User's wallet address (0x...).")
    parser.add_argument("--date", required=True, help="Date to fetch trades for (YYYY-MM-DD).")
    parser.add_argument("--output-file", default="user_trades.csv", help="Name of the output CSV file.")
    args = parser.parse_args()

    print(f"Starting trade logger for user: {args.address}")

    try:
        date_dt = datetime.strptime(args.date, "%Y-%m-%d")
        start_of_day_utc = date_dt.replace(tzinfo=ZoneInfo("UTC"))
        end_of_day_utc = start_of_day_utc + timedelta(days=1)
    except (ValueError, ZoneInfoNotFoundError) as e:
        print(f"Error parsing date or timezone: {e}")
        return

    if start_of_day_utc > datetime.now(ZoneInfo("UTC")):
        print(f"Warning: The specified date {args.date} is in the future. No trades will be fetched.")
        headers = ["timestamp_et", "market_title", "outcome", "side", "size", "price"]
        with open(args.output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
        return

    temp_csv_file = f"temp_{os.path.basename(args.output_file)}"

    try:
        fetch_and_process_trades(args.address, start_of_day_utc, end_of_day_utc, temp_csv_file)
        sort_and_save_final_csv(temp_csv_file, args.output_file)
    finally:
        try:
            if os.path.exists(temp_csv_file):
                os.remove(temp_csv_file)
                print(f"Removed temporary file: {temp_csv_file}")
        except OSError as e:
            print(f"Error removing temporary file: {e}")

if __name__ == "__main__":
    main()
