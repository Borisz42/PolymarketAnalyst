import csv

print("Comparing historical vs real-time data:")
print("=" * 70)

# Read real-time data
with open('market_data.csv') as f:
    realtime_data = list(csv.DictReader(f))

# Read historical data  
with open('historical_market_data.csv') as f:
    historical_data = list(csv.DictReader(f))

print(f"\nReal-time data (last 15 rows from market_data.csv):")
print(f"{'Time':<20} {'UpPrice':<10} {'DownPrice':<10}")
print("-" * 40)
for row in realtime_data[-15:]:
    print(f"{row['Timestamp']:<20} {row['UpPrice']:<10} {row['DownPrice']:<10}")

print(f"\n\nHistorical data (last 15 rows from historical_market_data.csv):")
print(f"{'Time':<20} {'UpPrice':<10} {'DownPrice':<10}")
print("-" * 40)
for row in historical_data[-15:]:
    print(f"{row['Timestamp']:<20} {row['UpPrice']:<10} {row['DownPrice']:<10}")

# Calculate price ranges
realtime_up_prices = [float(row['UpPrice']) for row in realtime_data[-30:] if row['UpPrice'] and float(row['UpPrice']) > 0]
historical_up_prices = [float(row['UpPrice']) for row in historical_data if row['UpPrice'] and float(row['UpPrice']) > 0]

print(f"\n\nPrice Range Comparison:")
print("=" * 70)
print(f"Real-time data (last 30 points):")
print(f"  Min Up Price: {min(realtime_up_prices):.4f}")
print(f"  Max Up Price: {max(realtime_up_prices):.4f}")
print(f"  Range: {max(realtime_up_prices) - min(realtime_up_prices):.4f}")

print(f"\nHistorical data (all points):")
print(f"  Min Up Price: {min(historical_up_prices):.4f}")
print(f"  Max Up Price: {max(historical_up_prices):.4f}")
print(f"  Range: {max(historical_up_prices) - min(historical_up_prices):.4f}")
