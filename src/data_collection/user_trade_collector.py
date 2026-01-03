import argparse
import os
import sys
from datetime import datetime
import pandas as pd
import requests

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_collection.find_new_market import generate_15m_slug
from src.config import DATA_DIR, BASE_DATA_FILENAME, TRACKED_USER_ADDRESS

# --- Polymarket API URLs ---
GAMMA_API_URL = "https://gamma-api.polymarket.com/markets"
DATA_API_URL = "https://data-api.polymarket.com/activity"

def get_market_details(slug: str) -> dict | None:
    """Fetches market details from the Gamma API to get the eventId."""
    try:
        response = requests.get(GAMMA_API_URL, params={"slug": slug}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not data:
            print(f"Warning: No market data returned for slug '{slug}'")
            return None
        # The API returns a list, we assume the first is the correct one
        market_data = data[0]
        events = market_data.get("events")
        if not events or not isinstance(events, list) or len(events) == 0:
            print(f"Warning: No 'events' array found for slug '{slug}'")
            return None

        event_data = events[0]
        return {
            "eventId": event_data.get("id"),
            "expirationTime": market_data.get("endDate"),
        }
    except requests.RequestException as e:
        print(f"Error fetching market details for slug '{slug}': {e}")
        return None

def get_user_activity(event_id: str, user_address: str) -> list:
    """Fetches all user trade activity for a specific eventId from the Data API using pagination."""
    all_activities = []
    offset = 0
    limit = 500

    while True:
        params = {
            "eventId": event_id,
            "user": user_address,
            "limit": limit,
            "offset": offset,
            "sortDirection": "ASC",
            "sortBy": "timestamp",
            "type": "TRADE",
        }
        try:
            response = requests.get(DATA_API_URL, params=params, timeout=10)
            response.raise_for_status()
            activities = response.json()
            all_activities.extend(activities)

            if len(activities) < limit or offset >= 10000:
                break  # Last page
            else:
                print(f"  - Fetched {len(all_activities)} activities so far. Continuing to next page...")

            offset += limit

        except requests.RequestException as e:
            print(f"Error fetching user activity for eventId '{event_id}' with offset {offset}: {e}")
            # Return what we have so far, as the rest might not be fetchable
            break
    # Merge duplicates by summing their 'size'
    merged_activities = {}
    for activity in all_activities:
        # Create a key from all items except 'size'
        key_items = frozenset(item for item in activity.items() if item[0] != 'size')
        
        if key_items in merged_activities:
            # If duplicate, sum the 'size'
            existing_size = float(merged_activities[key_items].get('size', 0))
            new_size = float(activity.get('size', 0))
            merged_activities[key_items]['size'] = str(existing_size + new_size) # Keep it as string
        else:
            # If new, add it to our dict, ensuring 'size' is a string
            activity_copy = activity.copy()
            activity_copy['size'] = str(activity.get('size', '0'))
            merged_activities[key_items] = activity_copy

    unique_activities = list(merged_activities.values())
    unique_activities.sort(key=lambda x: x.get("timestamp", 0))
    
    return unique_activities

def get_slugs_for_date(date_str: str) -> dict[str, str]:
    """
    Reads the market data file for a given date, extracts unique target times,
    and generates a dictionary mapping market slugs to their original TargetTime.
    """
    market_data_filename = os.path.join(DATA_DIR, f"{BASE_DATA_FILENAME}_{date_str}.csv")
    try:
        df = pd.read_csv(market_data_filename)
    except FileNotFoundError:
        print(f"Error: Market data file not found at '{market_data_filename}'")
        return {}

    if 'TargetTime' not in df.columns:
        print(f"Error: 'TargetTime' column not found in '{market_data_filename}'")
        return {}

    slug_map = {}
    for ts_str in df['TargetTime'].unique():
        ts_datetime = pd.to_datetime(ts_str)
        slug = generate_15m_slug(ts_datetime.to_pydatetime())
        slug_map[slug] = ts_str

    print(f"Found {len(slug_map)} unique markets for {date_str}.")
    return slug_map

from datetime import timezone

def process_trades(activities: list, market_details: dict, source_target_time: str) -> list[dict]:
    """Processes raw trade activities from the Data API into the desired format."""
    processed = []
    for trade in activities:
        # Filter out invalid trades
        if not trade.get("outcome") or float(trade.get("size", 0)) == 0:
            continue

        # Data API timestamp is an integer (Unix timestamp in seconds)
        timestamp_unix = trade.get("timestamp")
        if timestamp_unix is not None:
            timestamp_dt = datetime.fromtimestamp(int(timestamp_unix), tz=timezone.utc)
            timestamp_formatted = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp_formatted = None

        exp_time_str = market_details.get("expirationTime", "")
        if exp_time_str:
            exp_time_dt = datetime.fromisoformat(exp_time_str.replace('Z', '+00:00'))
            exp_time_formatted = exp_time_dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            exp_time_formatted = None

        processed.append({
            "timestamp": timestamp_formatted,
            "trade_side": trade.get("outcome"),
            "quantity": float(trade.get("size", 0)),
            "price": float(trade.get("price", 0)),
            "TargetTime": source_target_time,
            "ExpirationTime": exp_time_formatted,
        })
    return processed

def main():
    """Main function to collect user trades for a specific date."""
    parser = argparse.ArgumentParser(description="Collect user trades from Polymarket for a given date.")
    parser.add_argument("--date", required=True, help="The date to collect data for, in YYYYMMDD format.")
    args = parser.parse_args()

    print(f"Starting user trade collection for date: {args.date}")
    slug_map = get_slugs_for_date(args.date)

    if not slug_map:
        print("No market slugs found. Exiting.")
        return

    all_trades = []
    for slug, source_target_time in slug_map.items():
        print(f"Processing market: {slug}")
        market_details = get_market_details(slug)
        if not market_details or not market_details.get("eventId"):
            continue

        activities = get_user_activity(market_details["eventId"], TRACKED_USER_ADDRESS)
        if not activities:
            print(f"  - No activity found for user on this market.")
            continue

        trades = process_trades(activities, market_details, source_target_time)
        all_trades.extend(trades)
        print(f"  - Found {len(trades)} trades.")

    if not all_trades:
        print("No trades found for the user on any market for the specified date.")

    # Create DataFrame and save to CSV
    output_df = pd.DataFrame(all_trades)
    output_filename = os.path.join(DATA_DIR, f"user_data_{args.date}.csv")

    # Ensure consistent column order
    columns = ["timestamp", "trade_side", "quantity", "price", "TargetTime", "ExpirationTime"]
    if not output_df.empty:
        output_df = output_df[columns]
    else:
        output_df = pd.DataFrame(columns=columns)

    output_df.to_csv(output_filename, index=False)
    print(f"Operation complete. Saved {len(all_trades)} trades to '{output_filename}'.")

if __name__ == "__main__":
    main()
