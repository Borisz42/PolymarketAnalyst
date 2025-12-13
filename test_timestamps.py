import datetime
import pytz
from export_historical_csv import *

# Test: Check what timestamps we're sending to the API
print("=" * 70)
print("TIMESTAMP VERIFICATION TEST")
print("=" * 70)

# Current time in different zones
now_utc = datetime.datetime.now(pytz.UTC)
now_et = datetime.datetime.now(pytz.timezone('US/Eastern'))

print(f"\nCurrent time UTC: {now_utc}")
print(f"Current time ET:  {now_et}")
print(f"UTC timestamp:    {int(now_utc.timestamp())}")
print(f"ET timestamp:     {int(now_et.timestamp())}")

# Test market generation
print("\n" + "=" * 70)
print("TESTING MARKET GENERATION")
print("=" * 70)

markets = get_markets_for_time_range(hours_back=1.0)
print(f"\nGenerated {len(markets)} markets:")
for m in markets:
    print(f"\nSlug: {m['slug']}")
    print(f"  Target:     {m['target_time']} UTC")
    print(f"  Expiration: {m['expiration_time']} UTC")
    print(f"  Target TS:  {int(m['target_time'].timestamp())}")
    print(f"  Expiry TS:  {int(m['expiration_time'].timestamp())}")

# Test: Fetch a small sample and check timestamps
print("\n" + "=" * 70)
print("TESTING ACTUAL API CALL")
print("=" * 70)

if markets:
    test_market = markets[-1]  # Most recent market
    print(f"\nTesting market: {test_market['slug']}")
    
    market_info = get_token_ids_from_slug(test_market['slug'])
    if market_info:
        token_id = market_info['token_map']['Up']
        print(f"Token ID: {token_id[:20]}...")
        
        start_ts = int(test_market['target_time'].timestamp())
        end_ts = int(test_market['expiration_time'].timestamp())
        
        print(f"\nAPI Request:")
        print(f"  Start timestamp: {start_ts} ({test_market['target_time']})")
        print(f"  End timestamp:   {end_ts} ({test_market['expiration_time']})")
        
        data = fetch_market_data(token_id, start_ts, end_ts, fidelity=1)
        
        if data:
            print(f"\nReceived {len(data)} data points")
            print(f"\nFirst 5 data points:")
            for i, point in enumerate(data[:5]):
                dt = datetime.datetime.fromtimestamp(point['t'], tz=pytz.UTC)
                print(f"  {i+1}. {dt} - Price: {point['p']:.4f}")
            
            print(f"\nLast 5 data points:")
            for i, point in enumerate(data[-5:]):
                dt = datetime.datetime.fromtimestamp(point['t'], tz=pytz.UTC)
                print(f"  {i+1}. {dt} - Price: {point['p']:.4f}")
        else:
            print("No data received")
