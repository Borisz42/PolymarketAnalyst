import datetime
import pytz

# Base URL for Polymarket events
BASE_URL = "https://polymarket.com/event/"

def generate_slug(target_time):
    """
    Generates the Polymarket event slug for a given datetime.
    Format: bitcoin-up-or-down-[month]-[day]-[hour][am/pm]-et
    Example: bitcoin-up-or-down-november-26-1pm-et
    """
    # Ensure time is in Eastern Time
    et_tz = pytz.timezone('US/Eastern')
    if target_time.tzinfo is None:
        # Assume UTC if no timezone is provided, then convert to ET
        target_time = pytz.utc.localize(target_time).astimezone(et_tz)
    else:
        target_time = target_time.astimezone(et_tz)

    # Format components
    month = target_time.strftime("%B").lower()
    day = target_time.day
    
    # Hour formatting: 12-hour format with am/pm, lowercase, no leading zero for single digits
    hour_int = int(target_time.strftime("%I"))
    am_pm = target_time.strftime("%p").lower()
    
    slug = f"bitcoin-up-or-down-{month}-{day}-{hour_int}{am_pm}-et"
    return slug

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

def generate_market_url(target_time):
    """
    Generates the full Polymarket URL for a given datetime.
    Detects if it should be an hourly or 15-minute market based on minutes?
    Actually, let's switch entirely to 15m markets as requested.
    """
    slug = generate_15m_slug(target_time)
    return f"{BASE_URL}{slug}"

def get_next_market_urls(num_hours=5):
    """
    Generates URLs for the next 'num_hours' 15-minute markets.
    """
    urls = []
    now = datetime.datetime.now(pytz.utc)
    
    # Start from the next 15-minute interval
    # Example: 12:07 -> 12:15 expiration
    # Example: 12:14 -> 12:30 expiration (buffer needed?)
    # Usually markets close bets a bit before.
    # Let's target the next standard 15m block: 00, 15, 30, 45
    
    base_time = now.replace(second=0, microsecond=0)
    minutes = base_time.minute
    remainder = minutes % 15
    minutes_to_add = 15 - remainder
    next_quarter = base_time + datetime.timedelta(minutes=minutes_to_add)
    
    for i in range(num_hours * 4): # Fetch enough for X hours
        target_time = next_quarter + datetime.timedelta(minutes=15 * i)
        urls.append(generate_market_url(target_time))
        
    return urls

def get_current_market_url():
    """
    Determines the URL for the 'current' necessary market.
    Logic: The NEXT expiring 15-min market.
    """
    now = datetime.datetime.now(pytz.utc)
    
    # Calculate next 15-minute interval
    base_time = now.replace(second=0, microsecond=0)
    minutes = base_time.minute
    remainder = minutes % 15
    minutes_to_add = 15 - remainder
    
    # If we are very close to the expiration (e.g. < 2 mins), maybe jump to the next one?
    # For now, let's rigidly stick to the next quarter hour.
    next_quarter = base_time + datetime.timedelta(minutes=minutes_to_add)
    return generate_market_url(next_quarter)

def generate_urls_until_year_end():
    """
    Generates URLs for every hour from now until Jan 1, 2026.
    Saves them to 'market_urls_2025.txt'.
    """
    urls = []
    now = datetime.datetime.now(pytz.utc)
    
    # Start from the next full hour
    current_target = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    
    # End date: Jan 1, 2026 00:00 UTC (approx, depends on ET)
    # Let's just go until the year changes in ET
    et_tz = pytz.timezone('US/Eastern')
    
    print(f"Generating URLs starting from: {current_target.astimezone(et_tz)}")
    
    while True:
        # Check if we reached 2026 in ET
        et_time = current_target.astimezone(et_tz)
        if et_time.year >= 2026:
            break
            
        urls.append(generate_market_url(current_target))
        current_target += datetime.timedelta(hours=1)
        
    with open("market_urls_2025.txt", "w") as f:
        for url in urls:
            f.write(url + "\n")
            
    print(f"Generated {len(urls)} URLs and saved to 'market_urls_2025.txt'")

if __name__ == "__main__":
    print("--- Polymarket URL Generator ---")
    
    # Test with the user's specific example time to verify logic
    # User example: bitcoin-up-or-down-november-26-1pm-et
    # This corresponds to Nov 26, 1 PM ET.
    
    et_tz = pytz.timezone('US/Eastern')
    test_time = et_tz.localize(datetime.datetime(2025, 11, 26, 13, 0, 0))
    print(f"Test Time (ET): {test_time}")
    print(f"Generated URL: {generate_market_url(test_time)}")
    
    print("\n--- Current Market URL ---")
    print(f"Current Time (UTC): {datetime.datetime.now(pytz.utc)}")
    print(f"Current Market URL: {get_current_market_url()}")
    
    print("\n--- Generating URLs until 2026 ---")
    generate_urls_until_year_end()
