from export_historical_csv import *
import datetime
import pytz

print("Fetching token IDs...")
token_map = get_current_btc_token_ids()

print("\nFetching ALL historical data...")
up_hist = fetch_all_historical_prices(token_map['Up'], fidelity=1)

print(f"\nTotal data points available: {len(up_hist)}")

# Show time distribution
print(f"\nFirst 10 data points:")
for p in up_hist[:10]:
    dt = datetime.datetime.fromtimestamp(p['t'], tz=pytz.UTC)
    print(f"  {dt} - Price: {p['p']:.4f}")

print(f"\nLast 10 data points:")
for p in up_hist[-10:]:
    dt = datetime.datetime.fromtimestamp(p['t'], tz=pytz.UTC)
    print(f"  {dt} - Price: {p['p']:.4f}")

# Check spacing between data points
print(f"\nTime gaps between consecutive data points (first 20):")
for i in range(min(20, len(up_hist)-1)):
    gap_seconds = up_hist[i+1]['t'] - up_hist[i]['t']
    gap_minutes = gap_seconds / 60
    print(f"  Gap {i+1}: {gap_minutes:.1f} minutes")
