import requests
import datetime
import pytz
from typing import List, Dict, Optional
from get_current_markets import get_current_market_urls

# Configuration
POLYMARKET_API_URL = "https://gamma-api.polymarket.com/events"
CLOB_TIMESERIES_URL = "https://clob.polymarket.com/prices-history"

def get_token_ids_from_slug(slug: str) -> Optional[Dict[str, str]]:
    """
    Get token IDs for a given market slug.
    Returns a dict like {'Up': 'token_id_1', 'Down': 'token_id_2'}
    """
    try:
        response = requests.get(POLYMARKET_API_URL, params={"slug": slug})
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"Event not found for slug: {slug}")
            return None

        event = data[0]
        markets = event.get("markets", [])
        if not markets:
            print("Markets not found in event")
            return None
            
        market = markets[0]
        
        # Get Token IDs
        clob_token_ids = eval(market.get("clobTokenIds", "[]"))
        outcomes = eval(market.get("outcomes", "[]"))
        
        if len(clob_token_ids) != 2:
            print(f"Unexpected number of tokens: {len(clob_token_ids)}")
            return None
            
        # Create mapping of outcome to token_id
        token_map = {}
        for outcome, token_id in zip(outcomes, clob_token_ids):
            token_map[outcome] = token_id
            
        return token_map
    except Exception as e:
        print(f"Error fetching token IDs: {e}")
        return None

def fetch_historical_prices(
    token_id: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    interval: Optional[str] = None,
    fidelity: int = 1
) -> Optional[List[Dict]]:
    """
    Fetch historical price data for a token.
    
    Args:
        token_id: The CLOB token ID
        start_ts: Start time as Unix timestamp (seconds)
        end_ts: End time as Unix timestamp (seconds)
        interval: Duration string ('1m', '1h', '6h', '1d', '1w', 'max')
                 Mutually exclusive with start_ts/end_ts
        fidelity: Resolution in minutes (default: 1)
    
    Returns:
        List of dicts with 't' (timestamp) and 'p' (price) keys
    """
    try:
        params = {
            "market": token_id,
            "fidelity": fidelity
        }
        
        # Use either interval OR start_ts/end_ts
        if interval:
            params["interval"] = interval
        else:
            if start_ts:
                params["startTs"] = start_ts
            if end_ts:
                params["endTs"] = end_ts
        
        response = requests.get(CLOB_TIMESERIES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        history = data.get("history", [])
        return history
        
    except Exception as e:
        print(f"Error fetching historical prices: {e}")
        return None

def fetch_current_market_history(
    interval: str = "1d",
    fidelity: int = 15
) -> Optional[Dict]:
    """
    Fetch historical data for the current active BTC 15-minute market.
    
    Args:
        interval: Duration string ('1m', '1h', '6h', '1d', '1w', 'max')
        fidelity: Resolution in minutes (default: 15 for 15-min intervals)
    
    Returns:
        Dict with 'Up' and 'Down' keys, each containing historical price data
    """
    try:
        # Get current market info
        market_info = get_current_market_urls()
        polymarket_url = market_info["polymarket"]
        
        # Extract slug from URL
        slug = polymarket_url.split("/")[-1]
        
        # Get token IDs
        token_map = get_token_ids_from_slug(slug)
        if not token_map:
            return None
        
        # Fetch historical data for each outcome
        result = {}
        for outcome, token_id in token_map.items():
            print(f"Fetching {outcome} history (token: {token_id})...")
            history = fetch_historical_prices(
                token_id=token_id,
                interval=interval,
                fidelity=fidelity
            )
            if history:
                result[outcome] = history
                print(f"  Retrieved {len(history)} data points")
            else:
                result[outcome] = []
                
        return result
        
    except Exception as e:
        print(f"Error fetching current market history: {e}")
        return None

def fetch_custom_range_history(
    slug: str,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    fidelity: int = 15
) -> Optional[Dict]:
    """
    Fetch historical data for a specific market and time range.
    
    Args:
        slug: Market slug (from Polymarket URL)
        start_time: Start datetime (timezone-aware)
        end_time: End datetime (timezone-aware)
        fidelity: Resolution in minutes
    
    Returns:
        Dict with 'Up' and 'Down' keys, each containing historical price data
    """
    try:
        # Get token IDs
        token_map = get_token_ids_from_slug(slug)
        if not token_map:
            return None
        
        # Convert datetimes to Unix timestamps
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())
        
        # Fetch historical data for each outcome
        result = {}
        for outcome, token_id in token_map.items():
            print(f"Fetching {outcome} history (token: {token_id})...")
            history = fetch_historical_prices(
                token_id=token_id,
                start_ts=start_ts,
                end_ts=end_ts,
                fidelity=fidelity
            )
            if history:
                result[outcome] = history
                print(f"  Retrieved {len(history)} data points")
            else:
                result[outcome] = []
                
        return result
        
    except Exception as e:
        print(f"Error fetching custom range history: {e}")
        return None

def main():
    """
    Example usage of the historical data fetcher.
    """
    print("=" * 60)
    print("POLYMARKET HISTORICAL DATA FETCHER")
    print("=" * 60)
    
    # Example 1: Fetch last 24 hours of current market
    print("\n[Example 1] Fetching last 24 hours of current market...")
    print("-" * 60)
    history = fetch_current_market_history(interval="1d", fidelity=15)
    
    if history:
        for outcome, data in history.items():
            if data:
                print(f"\n{outcome} Outcome:")
                print(f"  First data point: {datetime.datetime.fromtimestamp(data[0]['t'], tz=pytz.UTC)} - Price: {data[0]['p']:.4f}")
                print(f"  Last data point:  {datetime.datetime.fromtimestamp(data[-1]['t'], tz=pytz.UTC)} - Price: {data[-1]['p']:.4f}")
                print(f"  Total points: {len(data)}")
    
    # Example 2: Fetch custom time range
    print("\n\n[Example 2] Fetching custom time range...")
    print("-" * 60)
    
    # Get current market slug
    market_info = get_current_market_urls()
    slug = market_info["polymarket"].split("/")[-1]
    
    # Define time range (last 6 hours)
    end_time = datetime.datetime.now(pytz.UTC)
    start_time = end_time - datetime.timedelta(hours=6)
    
    print(f"Slug: {slug}")
    print(f"Time range: {start_time} to {end_time}")
    
    custom_history = fetch_custom_range_history(
        slug=slug,
        start_time=start_time,
        end_time=end_time,
        fidelity=5  # 5-minute resolution
    )
    
    if custom_history:
        for outcome, data in custom_history.items():
            if data:
                print(f"\n{outcome} Outcome:")
                print(f"  Data points: {len(data)}")
                if len(data) > 0:
                    print(f"  First: {datetime.datetime.fromtimestamp(data[0]['t'], tz=pytz.UTC)} - {data[0]['p']:.4f}")
                    print(f"  Last:  {datetime.datetime.fromtimestamp(data[-1]['t'], tz=pytz.UTC)} - {data[-1]['p']:.4f}")

if __name__ == "__main__":
    main()
