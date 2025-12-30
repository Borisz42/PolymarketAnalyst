from decimal import Decimal
import pandas as pd
import math
from .base_strategy import Strategy

class OptimizedHybridStrategy(Strategy):
    def __init__(self):
        # Parameters from HybridStrategy
        self.MAX_HEDGING_COST = 0.98
        self.STOP_LOSS_THRESHOLD = 1.25
        self.MAX_ALLOCATION_PER_REBALANCE = 0.5
        self.MIN_BALANCE_QTY = 1
        self.MAX_UNHEDGED_DELTA = 50
        self.MIN_LIQUIDITY_MULTIPLIER = 3.0
        self.MIN_MINUTE = 2
        self.MAX_MINUTE = 7
        self.MAX_ALLOCATION_PER_TRADE = 0.075
        self.PRICE_DELTA_WEIGHT = 1.0
        self.LIQUIDITY_IMBALANCE_WEIGHT = 1.0
        self.MIN_SCORE_THRESHOLD = 1

        # New parameters for OptimizedHybridStrategy
        self.VOLATILITY_THRESHOLD = 0.02  # Updated threshold for the new Volatility metric
        self.TRAILING_STOP_PERCENT = 0.1  # 10% trailing stop

        self.portfolio_state = {}

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {
                'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0,
                'high_water_mark': 0.0, 'trailing_stop_price': 0.0
            }
        return self.portfolio_state[market_id]

    def _get_signal(self, market_data_point):
        up_score = 0
        down_score = 0

        if market_data_point["UpMidDelta"] > 0:
            up_score += self.PRICE_DELTA_WEIGHT
        if market_data_point["DownMidDelta"] > 0:
            down_score += self.PRICE_DELTA_WEIGHT

        if market_data_point["BidLiquidityImbalance"] > 0:
            up_score += self.LIQUIDITY_IMBALANCE_WEIGHT
        elif market_data_point["BidLiquidityImbalance"] < 0:
            down_score += self.LIQUIDITY_IMBALANCE_WEIGHT

        side = None
        if up_score >= self.MIN_SCORE_THRESHOLD:
            side = "Up"
        elif down_score >= self.MIN_SCORE_THRESHOLD:
            side = "Down"
        return side

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        portfolio = self._get_or_init_portfolio(market_id)
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']

        # Trailing Stop-Loss Logic
        if qty_yes > 0 and qty_no == 0: # Unhedged "Up" position
            current_price = market_data_point.get("UpMid")
            if current_price > portfolio['high_water_mark']:
                portfolio['high_water_mark'] = current_price
                portfolio['trailing_stop_price'] = current_price * (1 - self.TRAILING_STOP_PERCENT)

            if current_price < portfolio['trailing_stop_price']:
                return ('Down', qty_yes, market_data_point.get("DownAsk"), 0)

        if qty_no > 0 and qty_yes == 0: # Unhedged "Down" position
            current_price = market_data_point.get("DownMid")
            if current_price > portfolio['high_water_mark']:
                portfolio['high_water_mark'] = current_price
                portfolio['trailing_stop_price'] = current_price * (1 - self.TRAILING_STOP_PERCENT)

            if current_price < portfolio['trailing_stop_price']:
                return ('Up', qty_no, market_data_point.get("UpAsk"), 0)

        # Initial Trade Logic
        if qty_yes == 0 and qty_no == 0:
            minute = market_data_point.get("MinuteFromStart")
            sharp_event = market_data_point.get("SharpEvent")
            volatility = market_data_point.get("Volatility")

            if pd.isna(market_data_point.get("UpMidDelta")) or pd.isna(volatility):
                return None

            if minute is None or not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
                return None

            if not sharp_event:
                return None

            # Volatility Filter
            if volatility > self.VOLATILITY_THRESHOLD:
                return None

            side = self._get_signal(market_data_point)
            if not side:
                return None

            ask_price = market_data_point.get("UpAsk") if side == "Up" else market_data_point.get("DownAsk")
            if ask_price is None or ask_price <= 0 or ask_price >= 1.0:
                return None

            trade_capital = current_capital * self.MAX_ALLOCATION_PER_TRADE
            quantity = math.floor(trade_capital / ask_price)
            if quantity == 0:
                return None

            cost = quantity * ask_price
            if cost > current_capital:
                return None

            portfolio['high_water_mark'] = ask_price
            portfolio['trailing_stop_price'] = ask_price * (1 - self.TRAILING_STOP_PERCENT)

            return (side, quantity, ask_price, 0)

        return None

    def update_portfolio(self, market_id, side, quantity, price):
        portfolio = self._get_or_init_portfolio(market_id)
        cost = quantity * price
        if side == 'Up':
            portfolio['qty_yes'] += quantity
            portfolio['cost_yes'] += cost
        elif side == 'Down':
            portfolio['qty_no'] += quantity
            portfolio['cost_no'] += cost
