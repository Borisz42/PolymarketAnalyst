import pandas as pd
from .base_strategy import Strategy

class PredictionStrategy(Strategy):
    def __init__(self):
        # Configuration
        self.MIN_MINUTE = 1
        self.MAX_MINUTE = 10
        self.MAX_ENTRY_PRICE = 0.95
        self.QUANTITY = 1.0 # Buy 1 share per trade

        # State
        self.entered_markets = set()

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])

        # --- State filter: only one trade per market
        if market_id in self.entered_markets:
            return None

        # We assume the dataframe passed to the backtester is pre-processed with these columns.
        minute = market_data_point.get("MinuteFromStart")
        sharp_event = market_data_point.get("SharpEvent")
        up_mid_delta = market_data_point.get("UpMidDelta")
        down_mid_delta = market_data_point.get("DownMidDelta")
        bid_liquidity_imbalance = market_data_point.get("BidLiquidityImbalance")

        # The first row for each market will have NaN deltas after pre-processing
        if pd.isna(up_mid_delta) or pd.isna(down_mid_delta):
            return None

        # --- Time filter
        if minute is None or not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
            return None

        # --- Sharp event filter
        if not sharp_event:
            return None

        # --- Directional logic
        side = None
        ask_price = None
        liquidity_ok = False

        if up_mid_delta > 0:
            side = "Up"
            ask_price = market_data_point.get("UpAsk")
            if bid_liquidity_imbalance is not None:
                liquidity_ok = bid_liquidity_imbalance > 0

        elif down_mid_delta > 0:
            side = "Down"
            ask_price = market_data_point.get("DownAsk")
            if bid_liquidity_imbalance is not None:
                liquidity_ok = bid_liquidity_imbalance < 0
        else:
            return None

        # --- Liquidity confirmation
        if not liquidity_ok:
            return None

        # --- Price sanity check
        if ask_price is None or ask_price <= 0 or ask_price > self.MAX_ENTRY_PRICE:
            return None

        # --- Capital check
        cost = self.QUANTITY * ask_price
        if cost > current_capital:
            return None

        # ===== DECISION: ENTER TRADE =====
        self.entered_markets.add(market_id)

        return (side, self.QUANTITY, ask_price)
