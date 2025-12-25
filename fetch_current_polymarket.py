import requests
import time
import datetime
from get_current_markets import get_current_market_urls

# Configuration
POLYMARKET_API_URL = "https://gamma-api.polymarket.com/events"
CLOB_API_URL = "https://clob.polymarket.com/book"

# Global cache to store token IDs for the current market slug
_market_cache = {
    "slug": None,
    "clob_token_ids": None,
    "outcomes": None
}

def get_clob_price(token_id):
    """
    Fetch order book data for a token.
    Returns dict with bid, ask, mid, spread, and liquidity depth.
    """
    try:
        #t_start = time.time()
        response = requests.get(CLOB_API_URL, params={"token_id": token_id}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # data structure: {'bids': [{'price': '0.38', 'size': '...'}, ...], 'asks': ...}
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        best_bid = 0.0
        best_ask = 0.0
        bid_liquidity = 0.0
        ask_liquidity = 0.0
        
        if bids:
            # Bids: We want the HIGHEST price someone is willing to pay
            best_bid = max(float(b['price']) for b in bids)
            # Calculate total liquidity (sum of top 5 levels)
            bid_liquidity = sum(float(b['size']) for b in sorted(bids, key=lambda x: float(x['price']), reverse=True)[:5])
            
        if asks:
            # Asks: We want the LOWEST price someone is willing to sell for
            best_ask = min(float(a['price']) for a in asks)
            # Calculate total liquidity (sum of top 5 levels)
            ask_liquidity = sum(float(a['size']) for a in sorted(asks, key=lambda x: float(x['price']))[:5])
        
        # Calculate mid price and spread
        mid_price = 0.0
        spread = 0.0
        if best_bid > 0 and best_ask > 0:
            mid_price = (best_bid + best_ask) / 2.0
            spread = best_ask - best_bid
            
        #print(f"    [Time] CLOB {token_id}: {time.time() - t_start:.3f}s")
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'spread': spread,
            'bid_liquidity': bid_liquidity,
            'ask_liquidity': ask_liquidity
        }
    except Exception as e:
        return None

def get_polymarket_data(slug):
    """
    Fetch comprehensive market data including order book depth.
    Returns dict with prices and order book data for each outcome.
    """
    global _market_cache
    try:
        clob_token_ids = []
        outcomes = []

        # Check if we have cached data for this slug
        if _market_cache["slug"] == slug:
            clob_token_ids = _market_cache["clob_token_ids"]
            outcomes = _market_cache["outcomes"]
        else:
            # 1. Get Event Details to find Token IDs
            t_start = time.time()
            response = requests.get(POLYMARKET_API_URL, params={"slug": slug}, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data:
                return None, "Event not found"

            event = data[0]
            markets = event.get("markets", [])
            if not markets:
                return None, "Markets not found in event"
                
            market = markets[0]
            
            # Get Token IDs
            # clobTokenIds is a list of strings
            clob_token_ids = eval(market.get("clobTokenIds", "[]"))
            outcomes = eval(market.get("outcomes", "[]"))
            
            if len(clob_token_ids) != 2:
                return None, "Unexpected number of tokens"
                
            print(f"   [Time] Gamma API {slug}: {time.time() - t_start:.3f}s")
            
            # Update cache
            _market_cache["slug"] = slug
            _market_cache["clob_token_ids"] = clob_token_ids
            _market_cache["outcomes"] = outcomes
            
        # 2. Fetch Order Book Data for each Token from CLOB
        order_books = {}
        
        for outcome, token_id in zip(outcomes, clob_token_ids):
            book_data = get_clob_price(token_id)
            if book_data is not None:
                order_books[outcome] = book_data
            else:
                # Return default values if fetch fails
                order_books[outcome] = {
                    'best_bid': 0.0,
                    'best_ask': 0.0,
                    'mid_price': 0.0,
                    'spread': 0.0,
                    'bid_liquidity': 0.0,
                    'ask_liquidity': 0.0
                }
            
        return order_books, None
    except Exception as e:
        return None, str(e)



def fetch_polymarket_data_struct():
    """
    Fetches current Polymarket data and returns a structured dictionary.
    Returns comprehensive order book data including bids, asks, spreads, and liquidity.
    """
    try:
        # Get current market info
        market_info = get_current_market_urls()
        polymarket_url = market_info["polymarket"]
        target_time_utc = market_info["target_time_utc"]
        expiration_time_utc = market_info["expiration_time_utc"]
        
        # Extract slug from URL
        slug = polymarket_url.split("/")[-1]
        
        # Fetch Data
        order_books, poly_err = get_polymarket_data(slug)
        
        if poly_err:
            return None, f"Polymarket Error: {poly_err}"
            
        return {
            "order_books": order_books,  # {'Up': {best_bid, best_ask, ...}, 'Down': {...}}
            "slug": slug,
            "target_time_utc": target_time_utc,
            "expiration_time_utc": expiration_time_utc
        }, None        
    except Exception as e:
        return None, str(e)

def main():
    data, err = fetch_polymarket_data_struct()
    
    if err:
        print(f"Error: {err}")
        return

    print(f"Fetching data for: {data['slug']}")
    print(f"Target Time (UTC): {data['target_time_utc']}")
    print("-" * 50)
    
    up_book = data['order_books'].get("Up", {})
    down_book = data['order_books'].get("Down", {})
    
    print(f"UP   - Bid: ${up_book.get('best_bid', 0):.3f} | Ask: ${up_book.get('best_ask', 0):.3f} | Mid: ${up_book.get('mid_price', 0):.3f} | Spread: ${up_book.get('spread', 0):.4f}")
    print(f"DOWN - Bid: ${down_book.get('best_bid', 0):.3f} | Ask: ${down_book.get('best_ask', 0):.3f} | Mid: ${down_book.get('mid_price', 0):.3f} | Spread: ${down_book.get('spread', 0):.4f}")
    print(f"UP Liquidity   - Bid: {up_book.get('bid_liquidity', 0):.1f} | Ask: {up_book.get('ask_liquidity', 0):.1f}")
    print(f"DOWN Liquidity - Bid: {down_book.get('bid_liquidity', 0):.1f} | Ask: {down_book.get('ask_liquidity', 0):.1f}")

if __name__ == "__main__":
    main()
