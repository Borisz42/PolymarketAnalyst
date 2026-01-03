import math

from src.analysis.strategies.base_strategy import Strategy

class AvgArbitrageStrategy(Strategy):
    def __init__(self, margin=0.01, initial_trade_capital_percentage=0.05, max_capital_allocation_percentage=0.50):
        super().__init__()
        self.margin = margin
        self.initial_trade_capital_percentage = initial_trade_capital_percentage
        self.max_capital_allocation_percentage = max_capital_allocation_percentage

        # State variables, reset for each market
        self.up_qty = 0
        self.down_qty = 0
        self.up_total_cost = 0
        self.down_total_cost = 0
        self.initial_capital_per_market = None

    def decide(self, market_data_point, current_capital):
        if self.initial_capital_per_market is None:
            self.initial_capital_per_market = current_capital

        up_price = market_data_point['UpAsk']
        down_price = market_data_point['DownAsk']

        # First trade logic
        if self.up_qty == 0 and self.down_qty == 0:
            trade_amount = current_capital * self.initial_trade_capital_percentage
            if down_price < up_price and down_price > 0:
                qty_to_buy = math.floor(trade_amount / down_price)
                if qty_to_buy > 0:
                    self.down_qty += qty_to_buy
                    self.down_total_cost += qty_to_buy * down_price
                    return ('Down', qty_to_buy, down_price, 1.0)
            elif up_price < down_price and up_price > 0:
                qty_to_buy = math.floor(trade_amount / up_price)
                if qty_to_buy > 0:
                    self.up_qty += qty_to_buy
                    self.up_total_cost += qty_to_buy * up_price
                    return ('Up', qty_to_buy, up_price, 1.0)
            return None

        # Subsequent trades logic (balancing)
        qty_to_buy = 0
        side = None
        price = 0

        # Case 1: Need to buy 'Up' shares to balance
        if self.up_qty < self.down_qty and up_price > 0:
            numerator = (self.down_qty / (1 + self.margin)) - self.up_total_cost - self.down_total_cost
            if numerator > 0:
                qty_to_buy = math.floor(numerator / up_price)
                side = 'Up'
                price = up_price

        # Case 2: Need to buy 'Down' shares to balance
        elif self.down_qty < self.up_qty and down_price > 0:
            numerator = (self.up_qty / (1 + self.margin)) - self.down_total_cost - self.up_total_cost
            if numerator > 0:
                qty_to_buy = math.floor(numerator / down_price)
                side = 'Down'
                price = down_price

        if qty_to_buy > 0 and side is not None:
            # Check capital allocation limit
            projected_total_cost = self.up_total_cost + self.down_total_cost + (qty_to_buy * price)
            if projected_total_cost > self.max_capital_allocation_percentage * self.initial_capital_per_market:
                return None # Exceeds capital limit

            # Update state and return trade
            if side == 'Up':
                self.up_qty += qty_to_buy
                self.up_total_cost += qty_to_buy * price
            else: # side == 'Down'
                self.down_qty += qty_to_buy
                self.down_total_cost += qty_to_buy * price

            return (side, qty_to_buy, price, 1.0)

        return None
