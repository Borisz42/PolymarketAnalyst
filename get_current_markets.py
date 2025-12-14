import datetime
import pytz
from find_new_market import generate_market_url as generate_polymarket_url

def get_current_market_urls():
    """
    Returns a dictionary with the current active market URL for Polymarket (15-min markets).
    'Current' is defined as the market expiring at the next 15-minute interval.
    """
    now = datetime.datetime.now(pytz.utc)
    
    # Target time is the next 15-minute mark
    # Example: If now is 12:05, next target is 12:15.
    base_time = now.replace(second=0, microsecond=0)
    minutes = base_time.minute
    remainder = minutes % 15
    minutes_to_add = 15 - remainder
    target_time = base_time + datetime.timedelta(minutes=minutes_to_add)
    
    # The "Start Time" of this 15-min candle would be target_time - 15 minutes
    start_time_utc = target_time - datetime.timedelta(minutes=15)
    
    # Use START TIME for URL generation, as Polymarket uses the start time in the slug
    polymarket_url = generate_polymarket_url(start_time_utc)
    
    return {
        "polymarket": polymarket_url,
        "target_time_utc": start_time_utc,
        "expiration_time_utc": target_time,
        "target_time_et": start_time_utc.astimezone(pytz.timezone('US/Eastern'))
    }

if __name__ == "__main__":
    urls = get_current_market_urls()
    
    print(f"Current Time (UTC): {datetime.datetime.now(pytz.utc)}")
    print(f"Market Start Time (UTC): {urls['target_time_utc']}")
    print(f"Expiration Time (UTC):   {urls['expiration_time_utc']}")
    print("-" * 50)
    print(f"Polymarket: {urls['polymarket']}")
