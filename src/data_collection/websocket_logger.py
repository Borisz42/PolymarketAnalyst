import requests
import datetime
import pytz
import asyncio
import websockets
import json
import time
import os
import csv

# Configuration
POLYMARKET_API_URL = "https://gamma-api.polymarket.com/events"
WEBSOCKET_URI = "wss://clob.polymarket.com/ws"
DATA_DIR = "data"

def generate_15m_slug(target_time):
    """
    Generates the Polymarket event slug for a 15-minute market.
    Format: btc-updown-15m-[TIMESTAMP]
    The timestamp is the expiration time (Unix timestamp).
    """
    # Ensure time is in UTC for timestamp calculation
    if target_time.tzinfo is None:
        target_time = pytz.utc.localize(target_time)

    timestamp = int(target_time.timestamp())
    return f"btc-updown-15m-{timestamp}"

def get_data_filename():
    """Generates the filename for the CSV data based on the current date."""
    date_str = datetime.datetime.now(pytz.utc).strftime("%Y%m%d")
    return os.path.join(DATA_DIR, f"websocket_data_{date_str}.csv")

def init_csv_file(filename):
    """Initializes the CSV file with headers if it doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(filename):
        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "UpBid", "UpAsk", "DownBid", "DownAsk"])
        print(f"Created new data file: {filename}")

def write_to_csv(filename, data_row):
    """Appends a single row of data to the CSV file."""
    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(data_row)

def get_current_market_slug():
    """Determines the slug for the current 15-minute BTC market."""
    now = datetime.datetime.now(pytz.utc)
    base_time = now.replace(second=0, microsecond=0)
    minutes = base_time.minute
    remainder = minutes % 15
    minutes_to_add = 15 - remainder
    target_time = base_time + datetime.timedelta(minutes=minutes_to_add)
    start_time_utc = target_time - datetime.timedelta(minutes=15)
    return generate_15m_slug(start_time_utc)

def get_market_info(slug):
    """Fetches market info from the Polymarket Gamma API to get the conditionId, token IDs, and expiration time."""
    try:
        response = requests.get(POLYMARKET_API_URL, params={"slug": slug}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            return None, None, None
        market = data[0]["markets"][0]
        condition_id = market.get("conditionId")
        clob_token_ids_str = market.get("clobTokenIds")
        end_date_str = market.get("endDate")

        if not all([condition_id, clob_token_ids_str, end_date_str]):
            return None, None, None

        clob_token_ids = json.loads(clob_token_ids_str)
        # The endDate string is in ISO 8601 format with 'Z' for UTC
        expiration_time = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        return condition_id, clob_token_ids, expiration_time
    except (requests.exceptions.RequestException, KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
        print(f"Error fetching or parsing market info for slug {slug}: {e}")
        return None, None, None

async def websocket_client(condition_id, token_ids, expiration_time):
    """Connects to the Polymarket WebSocket, subscribes to a market, and logs data until the market expires."""
    print("Starting WebSocket client...")
    up_token_id, down_token_id = token_ids[0], token_ids[1]

    reconnection_attempts = 0
    while datetime.datetime.now(pytz.utc) < expiration_time:
        try:
            async with websockets.connect(WEBSOCKET_URI) as websocket:
                reconnection_attempts = 0 # Reset on successful connection
                print(f"WebSocket connected. Subscribing to market: {condition_id}")
                await websocket.send(json.dumps({
                    "type": "SUBSCRIBE", "channel": "market", "market": condition_id,
                }))

                last_log_second, in_arbitrage = -1, False
                prices = {"Up": {"bid": 0, "ask": 0}, "Down": {"bid": 0, "ask": 0}}
                filename = get_data_filename()
                init_csv_file(filename)

                async for message in websocket:
                    # Check for market expiration at the start of each message processing
                    if datetime.datetime.now(pytz.utc) >= expiration_time:
                        print("Market has expired. Closing WebSocket connection.")
                        break

                    data = json.loads(message)

                    if data.get("event_type") == "price_change":
                        for change in data.get("price_changes", []):
                            asset_id = change.get("asset_id")
                            outcome = "Up" if asset_id == up_token_id else "Down" if asset_id == down_token_id else None
                            if outcome:
                                prices[outcome]["bid"] = float(change.get("best_bid", 0))
                                prices[outcome]["ask"] = float(change.get("best_ask", 0))

                        up_ask, down_ask = prices["Up"]["ask"], prices["Down"]["ask"]
                        in_arbitrage = up_ask > 0 and down_ask > 0 and (up_ask + down_ask < 1)

                        current_time = datetime.datetime.now(pytz.utc)
                        timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

                        log_row = [timestamp_str, prices["Up"]["bid"], up_ask, prices["Down"]["bid"], down_ask]

                        current_filename = get_data_filename()
                        if current_filename != filename:
                            filename = current_filename
                            init_csv_file(filename)

                        if in_arbitrage or current_time.second != last_log_second:
                            write_to_csv(filename, log_row)
                            print(f"Logged: {log_row} | Arbitrage: {in_arbitrage}")
                            if not in_arbitrage:
                                last_log_second = current_time.second

        except websockets.exceptions.ConnectionClosed as e:
            print(f"WebSocket closed: {e}. Reconnecting in 5s...")
            reconnection_attempts += 1
            if reconnection_attempts > 5:
                print("Too many reconnection attempts. Exiting client for this market.")
                break
            await asyncio.sleep(5)
        except Exception as e:
            print(f"An error occurred: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    while True:
        print("Searching for the next active market...")
        slug = get_current_market_slug()
        print(f"Found potential market slug: {slug}")

        condition_id, token_ids, expiration_time = get_market_info(slug)

        if condition_id and token_ids and expiration_time:
            print(f"Found active market. Condition ID: {condition_id}")
            print(f"Market expires at (UTC): {expiration_time}")

            # Run the websocket client until the market expires
            asyncio.run(websocket_client(condition_id, token_ids, expiration_time))

            print("Market expired. Waiting for 30 seconds before searching for the next one.")
            time.sleep(30)
        else:
            print("No active market found or failed to fetch info. Retrying in 60 seconds...")
            time.sleep(60)
