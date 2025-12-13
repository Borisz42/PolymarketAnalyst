import requests
import datetime
import pytz
import csv
from typing import List, Dict, Optional

# Configuration
POLYMARKET_API_URL = "https://gamma-api.polymarket.com/events"
CLOB_TIMESERIES_URL = "https://clob.polymarket.com/prices-history"
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"

def get_markets_for_time_range(hours_back: float = 1.0) -> List[Dict]:
    """
    Generate BTC market slugs for all 15-minute intervals in the specified time range.
    Markets expire every hour at :00, :15, :30, :45.
    Each market is active from target_time to expiration_time (15 minutes).
    """
    current_time = datetime.datetime.now(pytz.UTC)
    start_time = current_time - datetime.timedelta(hours=hours_back)
    
    markets = []
    
    # Generate markets for every 15-minute interval
    # Start from the first 15-min boundary before start_time
    current = start_time.replace(second=0, microsecond=0)
    
    # Round down to nearest 15-minute mark
    minute = current.minute
    if minute < 15:
        current = current.replace(minute=0)
    elif minute < 30:
        current = current.replace(minute=15)
    elif minute < 45:
        current = current.replace(minute=30)
    else:
        current = current.replace(minute=45)
    
    # Generate markets until current time
    while current <= current_time:
        # Calculate expiration time (15 minutes after target)
        expiration_time = current + datetime.timedelta(minutes=15)
        
        # Only include markets that have already started (target_time <= current_time)
        if current <= current_time:
            # Generate slug based on expiration timestamp
            expiration_ts = int(expiration_time.timestamp())
            slug = f"btc-updown-15m-{expiration_ts}"
            
            markets.append({
                'slug': slug,
                'target_time': current,
                'expiration_time': expiration_time,
                'url': f"https://polymarket.com/event/{slug}"
            })
        
        # Move to next 15-minute interval
        current += datetime.timedelta(minutes=15)
    
    # Sort by target time
    markets.sort(key=lambda x: x['target_time'])
    return markets

def get_token_ids_from_slug(slug: str) -> Optional[Dict]:
    """Get token IDs and strike price for a market slug."""
    try:
        response = requests.get(POLYMARKET_API_URL, params={"slug": slug})
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None

        event = data[0]
        markets_data = event.get("markets", [])
        if not markets_data:
            return None
            
        market = markets_data[0]
        
        clob_token_ids = eval(market.get("clobTokenIds", "[]"))
        outcomes = eval(market.get("outcomes", "[]"))
        
        if len(clob_token_ids) != 2:
            return None
            
        token_map = {}
        for outcome, token_id in zip(outcomes, clob_token_ids):
            token_map[outcome] = token_id
            
        return {'token_map': token_map}
    except Exception as e:
        print(f"Error fetching token IDs for {slug}: {e}")
        return None

def fetch_market_data(token_id: str, start_ts: int, end_ts: int, fidelity: int = 1) -> Optional[List[Dict]]:
    """Fetch historical price data for a specific time range."""
    try:
        params = {
            "market": token_id,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity
        }
        
        response = requests.get(CLOB_TIMESERIES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        return data.get("history", [])
    except Exception as e:
        print(f"  Error: {e}")
        return None

def get_binance_price_at_time(target_time: datetime.datetime) -> Optional[float]:
    """Get BTC price at a specific time from Binance."""
    try:
        timestamp_ms = int(target_time.timestamp() * 1000)
        params = {
            "symbol": SYMBOL,
            "interval": "1m",
            "startTime": timestamp_ms,
            "limit": 1
        }
        response = requests.get(BINANCE_KLINES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return None
        
        close_price = float(data[0][4])
        return close_price
    except Exception as e:
        return None

def fetch_historical_data(hours_back: float = 1.0, fidelity: int = 1) -> List[Dict]:
    """
    Fetch historical data from all markets that were active in the time range.
    Only includes data from when each market was actually active.
    """
    print("=" * 70)
    print(f"FETCHING HISTORICAL DATA FROM LAST {hours_back} HOUR(S)")
    print("=" * 70)
    
    # Get all markets that were active
    markets = get_markets_for_time_range(hours_back)
    print(f"\nFound {len(markets)} markets active during this period:")
    for m in markets:
        print(f"  {m['slug']}: {m['target_time'].strftime('%H:%M')} - {m['expiration_time'].strftime('%H:%M')}")
    
    all_data_points = []
    
    for i, market in enumerate(markets, 1):
        print(f"\n[{i}/{len(markets)}] Processing {market['slug']}...")
        
        # Get token IDs
        market_info = get_token_ids_from_slug(market['slug'])
        if not market_info:
            print("  ⚠ Could not fetch token IDs")
            continue
        
        token_map = market_info['token_map']
        
        # Fetch data only for when this market was active
        start_ts = int(market['target_time'].timestamp())
        end_ts = int(market['expiration_time'].timestamp())
        
        print(f"  Fetching data from {market['target_time'].strftime('%H:%M:%S')} to {market['expiration_time'].strftime('%H:%M:%S')}")
        
        up_history = fetch_market_data(token_map.get('Up', ''), start_ts, end_ts, fidelity)
        down_history = fetch_market_data(token_map.get('Down', ''), start_ts, end_ts, fidelity)
        
        if not up_history or not down_history:
            print("  ⚠ No data available")
            continue
        
        print(f"  ✓ Retrieved {len(up_history)} data points")
        
        # Get strike price
        strike_price = get_binance_price_at_time(market['target_time'])
        
        # Merge data
        down_dict = {point['t']: point['p'] for point in down_history}
        
        for up_point in up_history:
            timestamp = up_point['t']
            point_time = datetime.datetime.fromtimestamp(timestamp, tz=pytz.UTC)
            
            # Get current BTC price
            current_price = get_binance_price_at_time(point_time)
            
            data_point = {
                'timestamp': point_time.strftime('%Y-%m-%d %H:%M:%S'),
                'target_time': market['target_time'],
                'expiration': market['expiration_time'],
                'strike': strike_price if strike_price else 0.0,
                'current_price': current_price if current_price else 0.0,
                'up_price': up_point['p'],
                'down_price': down_dict.get(timestamp, 0.0)
            }
            
            all_data_points.append(data_point)
    
    print(f"\n✓ Total data points collected: {len(all_data_points)}")
    
    # Sort by timestamp
    all_data_points.sort(key=lambda x: x['timestamp'])
    
    return all_data_points

def export_to_csv(data_points: List[Dict], filename: str = "historical_market_data.csv"):
    """Export data points to CSV file."""
    if not data_points:
        print("No data to export")
        return
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'TargetTime', 'Expiration', 'Strike', 'CurrentPrice', 'UpPrice', 'DownPrice'])
        
        for point in data_points:
            writer.writerow([
                point['timestamp'],
                point['target_time'],
                point['expiration'],
                point['strike'],
                point['current_price'],
                point['up_price'],
                point['down_price']
            ])
    
    print(f"\n✓ Exported {len(data_points)} data points to {filename}")

def main():
    """Main function to fetch and export historical data."""
    print("=" * 70)
    print("POLYMARKET HISTORICAL DATA EXPORTER")
    print("=" * 70)
    print()
    
    # Fetch data from last hour
    data_points = fetch_historical_data(hours_back=1.0, fidelity=1)
    
    if data_points:
        # Export to CSV
        export_to_csv(data_points, "historical_market_data.csv")
        
        # Print summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Total data points: {len(data_points)}")
        if data_points:
            print(f"First timestamp: {data_points[0]['timestamp']}")
            print(f"Last timestamp:  {data_points[-1]['timestamp']}")
    else:
        print("\n⚠ No data points retrieved")

if __name__ == "__main__":
    main()
