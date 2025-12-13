import requests
import datetime
import pytz
from export_historical_csv import get_current_btc_token_ids

CLOB_TIMESERIES_URL = "https://clob.polymarket.com/prices-history"

print("Getting token IDs...")
token_map = get_current_btc_token_ids()
up_token = token_map['Up']

print(f"\nTesting different API parameters for token: {up_token[:20]}...")
print("=" * 80)

# Test 1: Different fidelity values with interval='max'
print("\n[TEST 1] Different fidelity values with interval='max'")
print("-" * 80)
for fidelity in [1, 5, 10, 15, 30, 60]:
    try:
        params = {
            "market": up_token,
            "interval": "max",
            "fidelity": fidelity
        }
        response = requests.get(CLOB_TIMESERIES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        history = data.get("history", [])
        
        if len(history) >= 2:
            # Calculate average gap
            gaps = []
            for i in range(min(10, len(history)-1)):
                gap = (history[i+1]['t'] - history[i]['t']) / 60
                gaps.append(gap)
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            print(f"Fidelity {fidelity:3d} min: {len(history):4d} points, avg gap: {avg_gap:.1f} min")
    except Exception as e:
        print(f"Fidelity {fidelity:3d} min: ERROR - {e}")

# Test 2: Different interval values with fidelity=1
print("\n[TEST 2] Different interval values with fidelity=1")
print("-" * 80)
for interval in ['1m', '5m', '10m', '30m', '1h', '6h', '1d', '1w', 'max']:
    try:
        params = {
            "market": up_token,
            "interval": interval,
            "fidelity": 1
        }
        response = requests.get(CLOB_TIMESERIES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        history = data.get("history", [])
        
        if len(history) >= 2:
            # Calculate average gap
            gaps = []
            for i in range(min(10, len(history)-1)):
                gap = (history[i+1]['t'] - history[i]['t']) / 60
                gaps.append(gap)
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            first_time = datetime.datetime.fromtimestamp(history[0]['t'], tz=pytz.UTC)
            last_time = datetime.datetime.fromtimestamp(history[-1]['t'], tz=pytz.UTC)
            
            print(f"Interval {interval:4s}: {len(history):4d} points, avg gap: {avg_gap:.1f} min, range: {first_time.strftime('%m-%d %H:%M')} to {last_time.strftime('%m-%d %H:%M')}")
    except Exception as e:
        print(f"Interval {interval:4s}: ERROR - {e}")

# Test 3: Specific time range with fidelity=1
print("\n[TEST 3] Last 1 hour with different fidelity values (using startTs/endTs)")
print("-" * 80)
current_time = datetime.datetime.now(pytz.UTC)
hour_ago = current_time - datetime.timedelta(hours=1)
start_ts = int(hour_ago.timestamp())
end_ts = int(current_time.timestamp())

for fidelity in [1, 5, 10, 15]:
    try:
        params = {
            "market": up_token,
            "startTs": start_ts,
            "endTs": end_ts,
            "fidelity": fidelity
        }
        response = requests.get(CLOB_TIMESERIES_URL, params=params)
        response.raise_for_status()
        data = response.json()
        history = data.get("history", [])
        
        if len(history) >= 2:
            gaps = []
            for i in range(len(history)-1):
                gap = (history[i+1]['t'] - history[i]['t']) / 60
                gaps.append(gap)
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            
            print(f"Fidelity {fidelity:2d} min: {len(history):3d} points, avg gap: {avg_gap:.1f} min")
        else:
            print(f"Fidelity {fidelity:2d} min: {len(history):3d} points")
    except Exception as e:
        print(f"Fidelity {fidelity:2d} min: ERROR - {e}")

# Test 4: Very recent data (last 15 minutes) with fidelity=1
print("\n[TEST 4] Last 15 minutes with fidelity=1")
print("-" * 80)
current_time = datetime.datetime.now(pytz.UTC)
fifteen_min_ago = current_time - datetime.timedelta(minutes=15)
start_ts = int(fifteen_min_ago.timestamp())
end_ts = int(current_time.timestamp())

try:
    params = {
        "market": up_token,
        "startTs": start_ts,
        "endTs": end_ts,
        "fidelity": 1
    }
    response = requests.get(CLOB_TIMESERIES_URL, params=params)
    response.raise_for_status()
    data = response.json()
    history = data.get("history", [])
    
    print(f"Total points: {len(history)}")
    if history:
        print("\nAll data points:")
        for point in history:
            dt = datetime.datetime.fromtimestamp(point['t'], tz=pytz.UTC)
            print(f"  {dt} - Price: {point['p']:.4f}")
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("The test results above show the maximum granularity available from the API.")
