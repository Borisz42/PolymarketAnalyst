import time
import requests
import statistics

ENDPOINTS = [
    ("Gamma API", "https://gamma-api.polymarket.com/events?slug=bitcoin-price"),
    ("CLOB API", "https://clob.polymarket.com/book?token_id=123") # invalid token but checks connection
]

def check_latency(name, url, count=5):
    print(f"\nTesting connection to {name} ({url})...")
    times = []
    
    session = requests.Session()
    
    for i in range(count):
        try:
            start = time.time()
            header_only = False
            # Just get headers if possible to be faster? No, let's test full roundtrip behavior
            resp = session.get(url, timeout=5)
            # We don't care about 404/400, just that we got a response
            elapsed = time.time() - start
            times.append(elapsed)
            print(f"  Request {i+1}: {elapsed:.4f}s | Status: {resp.status_code}")
            time.sleep(0.5)
        except Exception as e:
            print(f"  Request {i+1}: FAILED ({e})")

    if times:
        avg = statistics.mean(times)
        p_min = min(times)
        p_max = max(times)
        print(f"  --> Msg: {avg:.4f}s | Min: {p_min:.4f}s | Max: {p_max:.4f}s")
    else:
        print("  --> ALL FAILED")

def check_internet():
    print("Testing general internet (google.com)...")
    try:
        start = time.time()
        requests.get("https://www.google.com", timeout=3)
        print(f"  --> Success in {time.time()-start:.4f}s")
    except Exception as e:
        print(f"  --> FAILED: {e}")

if __name__ == "__main__":
    print("=== Network Diagnostic Tool ===")
    check_internet()
    for name, url in ENDPOINTS:
        check_latency(name, url)
    print("\nDone.")
