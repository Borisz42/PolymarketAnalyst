import requests
import csv
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# --- Configuration ---
DATA_API = "https://data-api.polymarket.com"
API_LIMIT_PER_PAGE = 1000

def fetch_user_trades_for_date_range(wallet_address, start_time_utc):
    """
    Fetches historical trades for a user since a specific start time, handling API pagination efficiently.
    The API returns trades newest-first, so we stop paginating once we see a trade older than the start_time.
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

            # The API returns trades newest to oldest. Stop when we reach a trade
            # that is older than our desired start time.
            last_trade_timestamp = trades_page[-1].get("timestamp", 0)
            last_trade_time_utc = datetime.fromtimestamp(last_trade_timestamp, tz=ZoneInfo("UTC"))

            if last_trade_time_utc < start_time_utc:
                print("Reached trades older than the start of the target date. Stopping API calls.")
                break

            offset += len(trades_page)

        except requests.exceptions.RequestException as e:
            print(f"An error occurred while fetching trades: {e}")
            break

    print(f"Finished fetching. Total trades retrieved: {len(all_trades)}")
    return all_trades

def process_and_filter_trades(trades, start_time_utc, end_time_utc):
    """
    Processes raw trade data, filters for 15-min BTC markets within the date range, and converts timestamps to ET.
    """
    processed_trades = []
    try:
        et_zone = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        print("Error: 'America/New_York' timezone not found. Please ensure your system's timezone database is up to date.")
        return []

    print(f"Filtering {len(trades)} trades for 15-min BTC markets between {start_time_utc.astimezone(et_zone).strftime('%Y-%m-%d %H:%M:%S %Z')} and {end_time_utc.astimezone(et_zone).strftime('%Y-%m-%d %H:%M:%S %Z')}...")

    for trade in trades:
        trade_timestamp = trade.get("timestamp", 0)
        trade_time_utc = datetime.fromtimestamp(trade_timestamp, tz=ZoneInfo("UTC"))

        # Primary filter: Ensure the trade is within the desired time window [start, end).
        if not (start_time_utc <= trade_time_utc < end_time_utc):
            continue

        title = trade.get("title", "")
        # Heuristic filter for 15-minute markets: title contains "Bitcoin Up or Down" and a hyphen in the time description part.
        if "Bitcoin Up or Down" in title and "-" in title.split(" - ")[-1]:
            trade_time_et = trade_time_utc.astimezone(et_zone)
            processed_trades.append({
                "timestamp_et": trade_time_et.strftime('%Y-%m-%d %H:%M:%S'),
                "market_title": title,
                "outcome": trade.get("outcome", "N/A"),
                "side": trade.get("side", "N/A"),
                "size": trade.get("size", 0),
                "price": trade.get("price", 0.0),
            })

    # Sort the final list chronologically before returning
    processed_trades.sort(key=lambda x: x["timestamp_et"])

    print(f"Found {len(processed_trades)} trades matching the criteria.")
    return processed_trades

def save_trades_to_csv(processed_trades, filename):
    """
    Saves the list of processed trades to a CSV file. If the list is empty,
    it creates a file with only the headers.
    """
    headers = ["timestamp_et", "market_title", "outcome", "side", "size", "price"]

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(processed_trades)

        if processed_trades:
            print(f"Successfully saved {len(processed_trades)} trades to {filename}")
        else:
            print(f"No trades to save. Successfully created an empty file with headers: {filename}")
    except IOError as e:
        print(f"Error writing to CSV file: {e}")

def main():
    """
    Main function to parse arguments and orchestrate the trade fetching process.
    """
    parser = argparse.ArgumentParser(description="Fetch historical trades for a Polymarket user for a specific date.")
    parser.add_argument("--address", required=True, help="User's wallet address (0x...).")
    parser.add_argument("--date", required=True, help="Date to fetch trades for (YYYY-MM-DD).")
    parser.add_argument("--output-file", default="user_trades.csv", help="Name of the output CSV file.")

    args = parser.parse_args()

    print(f"Starting trade logger for user: {args.address}")

    try:
        # Interpret the input date as being in the UTC timezone.
        date_dt = datetime.strptime(args.date, "%Y-%m-%d")
        start_of_day_utc = date_dt.replace(tzinfo=ZoneInfo("UTC"))
        end_of_day_utc = start_of_day_utc + timedelta(days=1)
    except ValueError:
        print("Error: Invalid date format. Please use YYYY-MM-DD.")
        return
    except ZoneInfoNotFoundError:
        print("Error: 'UTC' timezone not found. This is a critical system error.")
        return

    # If the user provides a future date, we can stop immediately.
    if start_of_day_utc > datetime.now(ZoneInfo("UTC")):
        print(f"Warning: The specified date {args.date} is in the future. No trades will be fetched.")
        # Create an empty file to signify completion.
        save_trades_to_csv([], args.output_file)
        return

    all_trades = fetch_user_trades_for_date_range(args.address, start_of_day_utc)

    if all_trades:
        # The fetching logic might overshoot, so we need a precise filter here.
        filtered_trades = process_and_filter_trades(all_trades, start_of_day_utc, end_of_day_utc)
        save_trades_to_csv(filtered_trades, args.output_file)
    else:
        print("No trades were fetched. A file will be created with only headers.")
        save_trades_to_csv([], args.output_file)


if __name__ == "__main__":
    main()
