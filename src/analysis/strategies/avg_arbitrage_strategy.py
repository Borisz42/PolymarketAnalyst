import math
from collections import defaultdict
from src.analysis.strategies.base_strategy import Strategy

class AvgArbitrageStrategy(Strategy):
    def __init__(self, margin=0.01, initial_trade_capital_percentage=0.05, max_capital_allocation_percentage=0.50):
        super().__init__()
        self.margin = margin
        self.initial_trade_capital_percentage = initial_trade_capital_percentage
        self.max_capital_allocation_percentage = max_capital_allocation_percentage

        # Use a defaultdict to manage state for each market independently
        self.market_states = defaultdict(lambda: {
            'up_qty': 0,
            'down_qty': 0,
            'up_total_cost': 0,
            'down_total_cost': 0,
            'initial_capital_per_market': None
        })

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        state = self.market_states[market_id]

        if state['initial_capital_per_market'] is None:
            state['initial_capital_per_market'] = current_capital

        up_price = market_data_point['UpAsk']
        down_price = market_data_point['DownAsk']

        # First trade logic for this specific market
        if state['up_qty'] == 0 and state['down_qty'] == 0:
            trade_amount = current_capital * self.initial_trade_capital_percentage
            if down_price < up_price and down_price > 0:
                qty_to_buy = math.floor(trade_amount / down_price)
                if qty_to_buy > 0:
                    state['down_qty'] += qty_to_buy
                    state['down_total_cost'] += qty_to_buy * down_price
                    return ('Down', qty_to_buy, down_price, 1.0)
            elif up_price < down_price and up_price > 0:
                qty_to_buy = math.floor(trade_amount / up_price)
                if qty_to_buy > 0:
                    state['up_qty'] += qty_to_buy
                    state['up_total_cost'] += qty_to_buy * up_price
                    return ('Up', qty_to_buy, up_price, 1.0)
            return None

        # Subsequent trades logic (balancing) for this market
        qty_to_buy = 0
        side = None
        price = 0

        if state['up_qty'] < state['down_qty'] and up_price > 0:
            numerator = (state['down_qty'] / (1 + self.margin)) - state['up_total_cost'] - state['down_total_cost']
            if numerator > 0:
                qty_to_buy = math.floor(numerator / up_price)
                side = 'Up'
                price = up_price

        elif state['down_qty'] < state['up_qty'] and down_price > 0:
            numerator = (state['up_qty'] / (1 + self.margin)) - state['down_total_cost'] - state['up_total_cost']
            if numerator > 0:
                qty_to_buy = math.floor(numerator / down_price)
                side = 'Down'
                price = down_price

        if qty_to_buy > 0 and side is not None:
            projected_total_cost = state['up_total_cost'] + state['down_total_cost'] + (qty_to_buy * price)
            if projected_total_cost > self.max_capital_allocation_percentage * state['initial_capital_per_market']:
                return None # Exceeds capital limit

            if side == 'Up':
                state['up_qty'] += qty_to_buy
                state['up_total_cost'] += qty_to_buy * price
            else:
                state['down_qty'] += qty_to_buy
                state['down_total_cost'] += qty_to_buy * price

            return (side, qty_to_buy, price, 1.0)

        return None
