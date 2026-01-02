import requests
import csv
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# --- Configuration ---
DATA_API = "https://data-api.polymarket.com"
API_LIMIT_PER_PAGE = 1000

def fetch_user_trades_since(wallet_address, start_time_utc):
    """
    Fetches historical trades for a user since a specific start time, handling API pagination efficiently.
    """
    all_trades = []
    offset = 0
    print(f"Starting to fetch trades since {start_time_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

    while True:
        url = f"{DATA_API}/trades"
        params = {"user": wallet_address, "limit": API_LIMIT_PER_PAGE, "offset": offset}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            trades_page = response.json()

            if not trades_page:
                print("No more trades found on the API.")
                break

            all_trades.extend(trades_page)
            print(f"Fetched {len(trades_page)} trades. Total so far: {len(all_trades)}")

            last_trade_timestamp = trades_page[-1].get("timestamp", 0)
            last_trade_time_utc = datetime.fromtimestamp(last_trade_timestamp, tz=ZoneInfo("UTC"))

            if last_trade_time_utc < start_time_utc:
                print("Reached trades older than the start date. Stopping API calls.")
                break

            offset += len(trades_page)

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while fetching trades: {e}")
            break

    print(f"Finished fetching. Total trades retrieved: {len(all_trades)}")
    return all_trades

def process_and_filter_trades(trades, start_time_utc):
    """
    Processes raw trade data, filters for 15-min BTC markets, and converts timestamps to ET.
    """
    processed_trades = []
    try:
        et_zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        print("Error: 'America/New_York' timezone not found. Please ensure your system's timezone database is up to date.")
        return []

    print(f"Filtering {len(trades)} trades for 15-min BTC markets since {start_time_utc.astimezone(et_zone).strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    for trade in trades:
        title = trade.get("title", "")
        # Heuristic filter for 15-minute markets: title contains "Bitcoin Up or Down" and a hyphen in the time description part.
        if "Bitcoin Up or Down" in title and "-" in title.split(" - ")[-1]:
            trade_timestamp = trade.get("timestamp", 0)
            trade_time_utc = datetime.fromtimestamp(trade_timestamp, tz=ZoneInfo("UTC"))

            if trade_time_utc >= start_time_utc:
                trade_time_et = trade_time_utc.astimezone(et_zone)
                processed_trades.append({
                    "timestamp_et": trade_time_et.strftime('%Y-%m-%d %H:%M:%S'),
                    "market_title": title,
                    "outcome": trade.get("outcome", "N/A"),
                    "side": trade.get("side", "N/A"),
                    "size": trade.get("size", 0),
                    "price": trade.get("price", 0.0),
                })

    processed_trades.sort(key=lambda x: x["timestamp_et"])

    print(f"Found {len(processed_trades)} trades matching the criteria.")
    return processed_trades

def save_trades_to_csv(processed_trades, filename):
    """
    Saves the list of processed trades to a CSV file.
    """
    if not processed_trades:
        print("No trades to save.")
        return

    headers = ["timestamp_et", "market_title", "outcome", "side", "size", "price"]

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(processed_trades)
        print(f"Successfully saved {len(processed_trades)} trades to {filename}")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")

def main():
    """
    Main function to parse arguments and orchestrate the trade fetching process.
    """
    parser = argparse.ArgumentParser(description="Fetch historical trades for a Polymarket user.")
    parser.add_argument("--address", required=True, help="User's wallet address (0x...).")
    parser.add_argument("--start-date", required=True, help="Start date to fetch trades from (YYYY-MM-DD).")
    parser.add_argument("--output-file", default="user_trades.csv", help="Name of the output CSV file.")

    args = parser.parse_args()

    print(f"Starting trade logger for user: {args.address}")

    try:
        start_date_dt = datetime.strptime(args.start_date, "%Y-%m-%d")
        start_date_utc = start_date_dt.replace(tzinfo=ZoneInfo("UTC"))
    except ValueError:
        print("Error: Invalid date format. Please use YYYY-MM-DD.")
        return

    all_trades = fetch_user_trades_since(args.address, start_date_utc)

    if all_trades:
        filtered_trades = process_and_filter_trades(all_trades, start_date_utc)
        save_trades_to_csv(filtered_trades, args.output_file)
    else:
        print("No trades were fetched.")

if __name__ == "__main__":
    main()
