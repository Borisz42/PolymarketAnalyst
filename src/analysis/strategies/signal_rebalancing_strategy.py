from decimal import Decimal
import pandas as pd
from .base_strategy import Strategy
import math

class SignalRebalancingStrategy(Strategy):
    def __init__(self,
                 price_delta_weight=1.0,
                 liquidity_imbalance_weight=1.0,
                 min_score_threshold=1,
                 min_minute=2,
                 max_minute=7,
                 risk_per_trade=0.005,
                 max_allocation_per_trade=0.1,
                 safety_margin_m=0.99,
                 max_trade_size=500,
                 min_balance_qty=1,
                 max_unhedged_delta=50,
                 min_liquidity_multiplier=3.0,
                 stop_loss_percent=2.0):
        # Parameters from PredictionStrategy
        self.MIN_MINUTE = min_minute
        self.MAX_MINUTE = max_minute
        self.RISK_PER_TRADE = risk_per_trade
        self.MAX_ALLOCATION_PER_TRADE = max_allocation_per_trade
        self.PRICE_DELTA_WEIGHT = price_delta_weight
        self.LIQUIDITY_IMBALANCE_WEIGHT = liquidity_imbalance_weight
        self.MIN_SCORE_THRESHOLD = min_score_threshold

        # Parameters from RebalancingStrategy
        self.SAFETY_MARGIN_M = safety_margin_m
        self.MAX_TRADE_SIZE = max_trade_size
        self.MIN_BALANCE_QTY = min_balance_qty
        self.MAX_UNHEDGED_DELTA = max_unhedged_delta
        self.MIN_LIQUIDITY_MULTIPLIER = min_liquidity_multiplier
        self.STOP_LOSS_PERCENT = stop_loss_percent

        # Portfolio state per market
        self.portfolio_state = {}

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

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0}
        return self.portfolio_state[market_id]

    def calculate_state(self, portfolio):
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']

        avg_yes = Decimal(str(cost_yes / qty_yes)) if qty_yes > 0 else Decimal('0')
        avg_no = Decimal(str(cost_no / qty_no)) if qty_no > 0 else Decimal('0')

        pair_cost = avg_yes + avg_no
        delta = qty_yes - qty_no

        paired_qty = min(qty_yes, qty_no)
        locked_profit = Decimal('0')

        if paired_qty > 0 and pair_cost < Decimal('1.00'):
            locked_profit = Decimal(str(paired_qty)) * (Decimal('1.00') - pair_cost)

        return {
            'avg_yes': float(avg_yes),
            'avg_no': float(avg_no),
            'pair_cost': float(pair_cost),
            'delta': delta,
            'locked_profit': float(locked_profit)
        }

    def check_liquidity_constraint(self, market_data_point, target_side, qty_to_buy):
        opposite_side = 'Down' if target_side == 'Up' else 'Up'
        required_liquidity = qty_to_buy * self.MIN_LIQUIDITY_MULTIPLIER

        if opposite_side == 'Up':
            available_liquidity = market_data_point.get('UpAskLiquidity', 0)
        else:
            available_liquidity = market_data_point.get('DownAskLiquidity', 0)

        return available_liquidity >= required_liquidity

    def check_delta_constraint(self, portfolio, target_side, qty_to_buy):
        current_delta = portfolio['qty_yes'] - portfolio['qty_no']

        if target_side == 'Up':
            new_delta = current_delta + qty_to_buy
        else:
            new_delta = current_delta - qty_to_buy

        return abs(new_delta) <= self.MAX_UNHEDGED_DELTA

    def check_safety_margin(self, portfolio, target_side, qty_to_buy, price):
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']

        avg_p_yes = cost_yes / qty_yes if qty_yes > 0 else 0
        avg_p_no = cost_no / qty_no if qty_no > 0 else 0

        new_combined_avg_p = -1

        if target_side == 'Up':
            new_cost_yes = cost_yes + qty_to_buy * price
            new_qty_yes = qty_yes + qty_to_buy
            new_avg_p_yes = new_cost_yes / new_qty_yes
            new_combined_avg_p = new_avg_p_yes + avg_p_no
        elif target_side == 'Down':
            new_cost_no = cost_no + qty_to_buy * price
            new_qty_no = qty_no + qty_to_buy
            new_avg_p_no = new_cost_no / new_qty_no
            new_combined_avg_p = avg_p_yes + new_avg_p_no
        else:
            return False

        return new_combined_avg_p < self.SAFETY_MARGIN_M

    def decide(self, market_data_point, current_capital):
        minute = market_data_point.get("MinuteFromStart")
        sharp_event = market_data_point.get("SharpEvent")
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        portfolio = self._get_or_init_portfolio(market_id)

        # Signal-based trading logic
        if not pd.isna(market_data_point.get("UpMidDelta")) and (self.MIN_MINUTE <= minute <= self.MAX_MINUTE) and sharp_event:
            side = self._get_signal(market_data_point)
            if side:
                ask_price = market_data_point.get("UpAsk") if side == "Up" else market_data_point.get("DownAsk")
                if ask_price and 0 < ask_price < 1.0:
                    trade_capital = current_capital * self.RISK_PER_TRADE
                    trade_capital = min(trade_capital, current_capital * self.MAX_ALLOCATION_PER_TRADE)
                    quantity = math.floor(trade_capital / ask_price)
                    if quantity > 0 and (quantity * ask_price) <= current_capital:
                        return (side, quantity, ask_price)

        # Rebalancing logic
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        quantity_delta = abs(qty_yes - qty_no)

        if quantity_delta >= self.MIN_BALANCE_QTY:
            target_side = 'Down' if qty_yes > qty_no else 'Up'
            target_price = market_data_point.get('DownAsk', 0) if target_side == 'Down' else market_data_point.get('UpAsk', 0)

            if target_price > 0:
                qty_to_buy = int(min(quantity_delta, self.MAX_TRADE_SIZE))
                while qty_to_buy > 0:
                    cost = qty_to_buy * target_price
                    if cost <= current_capital and self.check_delta_constraint(portfolio, target_side, qty_to_buy) and self.check_liquidity_constraint(market_data_point, target_side, qty_to_buy) and self.check_safety_margin(portfolio, target_side, qty_to_buy, target_price):
                        return (target_side, qty_to_buy, target_price)
                    qty_to_buy -= 1
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
