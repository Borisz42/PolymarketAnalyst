import datetime
import pytz

now = datetime.datetime.now(pytz.UTC)
now_ts = int(now.timestamp())
hour_ago_ts = now_ts - 3600

with open('market_urls_2025.txt') as f:
    urls = [l.strip() for l in f if 'btc-updown-15m' in l]

print(f'Total BTC markets: {len(urls)}')
print(f'Current time: {now}')
print(f'\nFirst 10 markets:')
for url in urls[:10]:
    try:
        ts = int(url.split('-')[-1])
        dt = datetime.datetime.fromtimestamp(ts, tz=pytz.UTC)
        print(f'{dt} - {url.split("/")[-1]}')
    except:
        pass

