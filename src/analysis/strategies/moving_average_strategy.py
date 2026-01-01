from .base_strategy import Strategy
import pandas as pd
import math

class MovingAverageStrategy(Strategy):
    def __init__(self, volatility_threshold=0.01, spread_threshold=0.05, imbalance_threshold=100):
        # Configuration for anti-signals
        self.VOLATILITY_THRESHOLD = volatility_threshold
        self.SPREAD_THRESHOLD = spread_threshold
        self.IMBALANCE_THRESHOLD = imbalance_threshold

        # --- Time filter
        self.MIN_MINUTE = 3
        self.MAX_MINUTE = 9

        # --- Risk Management
        self.RISK_PER_TRADE = 0.01
        self.MAX_ALLOCATION_PER_TRADE = 0.1

        self.portfolio = {}

    def update_portfolio(self, market_id, side, quantity, price):
        if market_id not in self.portfolio:
            self.portfolio[market_id] = {'Up': 0, 'Down': 0}
        self.portfolio[market_id][side] += quantity

    def decide(self, market_data_point, current_capital):
        # --- Data Sanity Checks ---
        required_cols = [
            "Up_MA_Crossover", "Down_MA_Crossover",
            "UpMid_Volatility", "DownMid_Volatility", "Up_Spread", "Down_Spread",
            "MinuteFromStart", "UpAsk", "DownAsk", "TargetTime", "Expiration"
        ]
        for col in required_cols:
            if pd.isna(market_data_point.get(col)):
                return None

        # --- Time filter ---
        minute = market_data_point.get("MinuteFromStart")
        if not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
            return None

        # --- Anti-Signal Filters ---
        if market_data_point["UpMid_Volatility"] > self.VOLATILITY_THRESHOLD or \
           market_data_point["DownMid_Volatility"] > self.VOLATILITY_THRESHOLD:
            return None # Market is too volatile

        if market_data_point["Up_Spread"] > self.SPREAD_THRESHOLD or \
           market_data_point["Down_Spread"] > self.SPREAD_THRESHOLD:
            return None # Spread is too wide

        # --- Signal Generation (using pre-computed crossovers) ---
        side = None
        score = 1

        if market_data_point["Up_MA_Crossover"]:
            side = "Up"
        elif market_data_point["Down_MA_Crossover"]:
            side = "Down"

        if not side:
            return None

        # --- Imbalance Filter ---
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        current_position = self.portfolio.get(market_id, {'Up': 0, 'Down': 0})
        up_shares = current_position['Up']
        down_shares = current_position['Down']

        if side == "Up" and up_shares > down_shares + self.IMBALANCE_THRESHOLD:
            return None

        if side == "Down" and down_shares > up_shares + self.IMBALANCE_THRESHOLD:
            return None

        # --- Trade Execution ---
        ask_price = market_data_point.get("UpAsk") if side == "Up" else market_data_point.get("DownAsk")

        if ask_price is None or ask_price <= 0.05 or ask_price >= 0.95: # Price sanity check
            return None

        # Calculate trade size
        trade_capital = current_capital * self.RISK_PER_TRADE
        trade_capital = min(trade_capital, current_capital * self.MAX_ALLOCATION_PER_TRADE)
        quantity = math.floor(trade_capital / ask_price)

        if quantity == 0:
            return None

        cost = quantity * ask_price
        if cost > current_capital:
            return None

        return (side, quantity, ask_price, score)
