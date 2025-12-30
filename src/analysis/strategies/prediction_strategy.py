import pandas as pd
from .base_strategy import Strategy
import math

class PredictionStrategy(Strategy):
    def __init__(self, price_delta_weight=1.0, liquidity_imbalance_weight=1.0, min_score_threshold=1):
        # Configuration
        self.MIN_MINUTE = 2
        self.MAX_MINUTE = 7
        self.RISK_PER_TRADE = 0.005 # Risk 0.5% of capital per trade
        self.MAX_ALLOCATION_PER_TRADE = 0.1 # Max 10% of capital per trade
        self.PRICE_DELTA_WEIGHT = price_delta_weight
        self.LIQUIDITY_IMBALANCE_WEIGHT = liquidity_imbalance_weight
        self.MIN_SCORE_THRESHOLD = min_score_threshold

    def _get_signal(self, market_data_point):
        up_score = 0
        down_score = 0

        # Signal 1: Price Delta
        if market_data_point["UpMidDelta"] > 0:
            up_score += self.PRICE_DELTA_WEIGHT
        if market_data_point["DownMidDelta"] > 0:
            down_score += self.PRICE_DELTA_WEIGHT

        # Signal 2: Liquidity Imbalance
        if market_data_point["BidLiquidityImbalance"] > 0:
            up_score += self.LIQUIDITY_IMBALANCE_WEIGHT
        elif market_data_point["BidLiquidityImbalance"] < 0:
            down_score += self.LIQUIDITY_IMBALANCE_WEIGHT

        side = None
        score = 0

        if up_score >= self.MIN_SCORE_THRESHOLD:
            side = "Up"
            score = up_score
        elif down_score >= self.MIN_SCORE_THRESHOLD:
            side = "Down"
            score = down_score

        return side, score

    def decide(self, market_data_point, current_capital):
        # We assume the dataframe passed to the backtester is pre-processed with these columns.
        minute = market_data_point.get("MinuteFromStart")
        sharp_event = market_data_point.get("SharpEvent")

        # The first row for each market will have NaN deltas after pre-processing, so _get_signal will correctly return no signal.
        if pd.isna(market_data_point.get("UpMidDelta")):
            return None

        # --- Time filter
        if minute is None or not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
            return None

        # --- Sharp event filter
        if not sharp_event:
            return None

        # --- Decision based on pre-calculated signal ---
        side, score = self._get_signal(market_data_point)

        if not side:
            return None

        ask_price = None
        if side == "Up":
            ask_price = market_data_point.get("UpAsk")
        else: # Down
            ask_price = market_data_point.get("DownAsk")

        # --- Price sanity check
        if ask_price is None or ask_price <= 0 or ask_price >= 1.0:
            return None

        # --- Calculate trade size based on capital
        trade_capital = current_capital * self.RISK_PER_TRADE

        # Enforce max allocation
        trade_capital = min(trade_capital, current_capital * self.MAX_ALLOCATION_PER_TRADE)

        quantity = math.floor(trade_capital / ask_price)

        if quantity == 0:
            return None

        # --- Capital check
        cost = quantity * ask_price
        if cost > current_capital:
            return None

        # ===== DECISION: ENTER TRADE =====
        return (side, quantity, ask_price, score)
