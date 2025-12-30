from decimal import Decimal
import pandas as pd
import math
from .base_strategy import Strategy

class HybridStrategy(Strategy):
    def __init__(self):
        # Parameters from RebalancingStrategy
        self.MAX_HEDGING_COST = 0.98
        self.STOP_LOSS_THRESHOLD = 1.30
        self.MAX_ALLOCATION_PER_REBALANCE = 0.5
        self.MIN_BALANCE_QTY = 1

        # Risk management parameters from RebalancingStrategy
        self.MAX_UNHEDGED_DELTA = 50
        self.MIN_LIQUIDITY_MULTIPLIER = 3.0

        # Parameters from PredictionStrategy
        self.MIN_MINUTE = 2
        self.MAX_MINUTE = 7
        self.MAX_ALLOCATION_PER_TRADE = 0.05
        self.PRICE_DELTA_WEIGHT = 1.0
        self.LIQUIDITY_IMBALANCE_WEIGHT = 1.0
        self.MIN_SCORE_THRESHOLD = 1

        # Portfolio state per market
        self.portfolio_state = {}

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0}
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

    def check_hedging_cost_constraint(self, portfolio, target_side, qty_to_buy, price):
        qty_yes, qty_no = portfolio['qty_yes'], portfolio['qty_no']
        cost_yes, cost_no = portfolio['cost_yes'], portfolio['cost_no']
        avg_p_yes = cost_yes / qty_yes if qty_yes > 0 else 0
        avg_p_no = cost_no / qty_no if qty_no > 0 else 0

        if target_side == 'Up':
            new_cost_yes = cost_yes + qty_to_buy * price
            new_qty_yes = qty_yes + qty_to_buy
            if new_qty_yes == 0: return False
            new_avg_p_yes = new_cost_yes / new_qty_yes
            new_combined_avg_p = new_avg_p_yes + avg_p_no
        elif target_side == 'Down':
            new_cost_no = cost_no + qty_to_buy * price
            new_qty_no = qty_no + qty_to_buy
            if new_qty_no == 0: return False
            new_avg_p_no = new_cost_no / new_qty_no
            new_combined_avg_p = avg_p_yes + new_avg_p_no
        else:
            return False
        return new_combined_avg_p < self.MAX_HEDGING_COST

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        portfolio = self._get_or_init_portfolio(market_id)
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']

        # Use prediction signal to initiate a trade
        if qty_yes == 0 and qty_no == 0:
            minute = market_data_point.get("MinuteFromStart")
            sharp_event = market_data_point.get("SharpEvent")

            if pd.isna(market_data_point.get("UpMidDelta")):
                return None

            if minute is None or not (self.MIN_MINUTE <= minute <= self.MAX_MINUTE):
                return None

            if not sharp_event:
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
            return (side, quantity, ask_price)

        # Use rebalancing logic to manage the position
        if qty_yes != qty_no:
            quantity_delta = abs(qty_yes - qty_no)
            if quantity_delta < self.MIN_BALANCE_QTY:
                return None

            price_yes = market_data_point.get('UpAsk', 0)
            price_no = market_data_point.get('DownAsk', 0)
            target_side = 'Down' if qty_yes > qty_no else 'Up'
            target_price = price_no if target_side == 'Down' else price_yes

            if target_price <= 0:
                return None

            # First, try to rebalance with the safety margin
            qty_to_buy = int(min(quantity_delta, current_capital * self.MAX_ALLOCATION_PER_REBALANCE))
            trade = None
            while qty_to_buy > 0:
                cost = qty_to_buy * target_price
                if cost > current_capital:
                    qty_to_buy -= 1
                    continue
                if self.check_delta_constraint(portfolio, target_side, qty_to_buy) and \
                   self.check_liquidity_constraint(market_data_point, target_side, qty_to_buy) and \
                   self.check_hedging_cost_constraint(portfolio, target_side, qty_to_buy, target_price):
                    trade = (target_side, qty_to_buy, target_price)
                    break
                qty_to_buy -= 1

            if trade:
                return trade

            # If rebalancing with the safety margin fails, try a stop-loss rebalance
            state = self.calculate_state(portfolio)
            avg_yes = state['avg_yes']
            avg_no = state['avg_no']

            stop_loss_triggered = False
            if target_side == 'Down' and avg_yes + target_price >= self.STOP_LOSS_THRESHOLD:
                stop_loss_triggered = True
            elif target_side == 'Up' and avg_no + target_price >= self.STOP_LOSS_THRESHOLD:
                stop_loss_triggered = True

            if stop_loss_triggered:
                qty_to_buy = int(min(quantity_delta, current_capital * self.MAX_ALLOCATION_PER_REBALANCE))
                while qty_to_buy > 0:
                    cost = qty_to_buy * target_price
                    if cost > current_capital:
                        qty_to_buy -= 1
                        continue
                    if self.check_delta_constraint(portfolio, target_side, qty_to_buy) and \
                       self.check_liquidity_constraint(market_data_point, target_side, qty_to_buy):
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
