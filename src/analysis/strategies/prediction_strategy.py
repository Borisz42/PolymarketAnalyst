import pandas as pd
from .base_strategy import Strategy
import math

class PredictionStrategy(Strategy):
    def __init__(self):
        # Configuration
        self.MIN_MINUTE = 2
        self.MAX_MINUTE = 7
        self.RISK_PER_TRADE = 0.02 # Risk 2% of capital per trade
        self.MAX_ALLOCATION_PER_TRADE = 0.1 # Max 10% of capital per trade

    def _get_signal(self, market_data_point):
        up_score = 0
        down_score = 0

        # Signal 1: Price Delta
        if market_data_point["UpMidDelta"] > 0:
            up_score += 1
        if market_data_point["DownMidDelta"] > 0:
            down_score += 1

        # Signal 2: Liquidity Imbalance
        if market_data_point["BidLiquidityImbalance"] > 0:
            up_score += 1
        elif market_data_point["BidLiquidityImbalance"] < 0:
            down_score += 1

        signal_strength = 0
        side = None

        if up_score >= 2:
            side = "Up"
            signal_strength = up_score
        elif down_score >= 2:
            side = "Down"
            signal_strength = down_score

        return side, signal_strength

    def decide(self, market_data_point, current_capital):
        # We assume the dataframe passed to the backtester is pre-processed with these columns.
        minute = market_data_point.get("MinuteFromStart")
        sharp_event = market_data_point.get("SharpEvent")

        # The first row for each market will have NaN deltas after pre-processing, so _get_signal will correctly return no signal.
        # --- Time filter
        if minute is None or not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
            return None

        # --- Sharp event filter
        if not sharp_event:
            return None

        # --- Decision based on pre-calculated signal ---
        side, signal_strength = self._get_signal(market_data_point)

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

        # --- Calculate trade size based on signal strength and capital
        # Since signal_strength is always 2, we can simplify the scaling factor.
        # This can be made more complex if signal generation becomes more granular.
        scaled_risk = self.RISK_PER_TRADE

        # Calculate position size based on scaled risk
        trade_capital = current_capital * scaled_risk

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
        return (side, quantity, ask_price)
