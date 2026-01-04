import math
from collections import defaultdict
from src.analysis.strategies.base_strategy import Strategy

class AvgArbitrageStrategy(Strategy):
    def __init__(self, margin=0.01, initial_trade_capital_percentage=0.05, max_capital_allocation_percentage=0.50):
        super().__init__()
        self.margin = margin
        self.initial_trade_capital_percentage = initial_trade_capital_percentage
        self.max_capital_allocation_percentage = max_capital_allocation_percentage
        self.min_imbalance_threshold = 5  

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

        if up_price is None or down_price is None or up_price == 0 or down_price == 0:
            return None  # Cannot make a decision without both prices

        # First trade logic for this specific market
        if state['up_qty'] == 0 and state['down_qty'] == 0:
            qty_to_buy = math.floor(current_capital * self.initial_trade_capital_percentage)
            if down_price < up_price and 0.4 < down_price < 0.6:
                if qty_to_buy > 0:
                    state['down_qty'] += qty_to_buy
                    state['down_total_cost'] += qty_to_buy * down_price
                    return ('Down', qty_to_buy, down_price, 1.0)
            elif up_price < down_price and 0.4 < up_price < 0.6:
                if qty_to_buy > 0:
                    state['up_qty'] += qty_to_buy
                    state['up_total_cost'] += qty_to_buy * up_price
                    return ('Up', qty_to_buy, up_price, 1.0)
            return None

        # Subsequent trades logic (balancing) for this market
        qty_to_buy = 0
        side = None
        price = 0

        average_down_cost = 0 if state['down_qty'] == 0 else (state['down_total_cost'] / state['down_qty'])
        average_up_cost = 0 if state['up_qty'] == 0 else (state['up_total_cost'] / state['up_qty'])

        if state['up_qty'] < state['down_qty'] and average_down_cost + up_price < (1 - self.margin):
            numerator = (state['down_qty'] / (1 + self.margin)) - state['up_total_cost'] - state['down_total_cost']
            qty_to_buy = math.floor(numerator / up_price)
            if state['up_qty'] + qty_to_buy > state['down_qty'] + self.min_imbalance_threshold:
                side = 'Up'
                price = up_price

        elif state['down_qty'] < state['up_qty'] and average_up_cost + down_price < (1 - self.margin):
            numerator = (state['up_qty'] / (1 + self.margin)) - state['down_total_cost'] - state['up_total_cost']
            qty_to_buy = math.floor(numerator / down_price)
            if state['down_qty'] + qty_to_buy > state['up_qty'] + self.min_imbalance_threshold:
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
