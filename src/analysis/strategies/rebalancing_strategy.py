from decimal import Decimal
from .base_strategy import Strategy

class RebalancingStrategy(Strategy):
    def __init__(self):
        # Parameters from plan
        self.SAFETY_MARGIN_M = 0.99
        self.MAX_TRADE_SIZE = 500
        self.MIN_BALANCE_QTY = 1

        # Risk management parameters (from risk_engine.py)
        self.MAX_UNHEDGED_DELTA = 50  # Maximum position imbalance
        self.MIN_LIQUIDITY_MULTIPLIER = 3.0  # Opposite side must have 3x liquidity
        self.STOP_LOSS_PERCENT = 2.0  # Stop loss at 2% loss

        # Portfolio state per market
        self.portfolio_state = {}  # key: market_id, value: {'qty_yes': int, 'qty_no': int, 'cost_yes': float, 'cost_no': float}

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0}
        return self.portfolio_state[market_id]

    def calculate_state(self, portfolio):
        """
        Calculate current position state (from accumulator.py logic).
        Returns dict with avg_yes, avg_no, pair_cost, delta, locked_profit.
        """
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']

        avg_yes = Decimal(str(cost_yes / qty_yes)) if qty_yes > 0 else Decimal('0')
        avg_no = Decimal(str(cost_no / qty_no)) if qty_no > 0 else Decimal('0')

        pair_cost = avg_yes + avg_no
        delta = qty_yes - qty_no

        # Calculate locked profit (from accumulator.py)
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
        """
        Check if there's sufficient liquidity on the opposite side (from accumulator.py).
        Returns True if liquidity constraint is met.
        """
        opposite_side = 'Down' if target_side == 'Up' else 'Up'
        required_liquidity = qty_to_buy * self.MIN_LIQUIDITY_MULTIPLIER

        # Get available liquidity from order book
        if opposite_side == 'Up':
            available_liquidity = market_data_point.get('UpAskLiquidity', 0)
        else:
            available_liquidity = market_data_point.get('DownAskLiquidity', 0)

        return available_liquidity >= required_liquidity

    def check_delta_constraint(self, portfolio, target_side, qty_to_buy):
        """
        Check if trade would violate delta constraint (from risk_engine.py).
        Returns True if delta constraint is met.
        """
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

        if target_side == 'Up':  # 'Up' is YES
            new_cost_yes = cost_yes + qty_to_buy * price
            new_qty_yes = qty_yes + qty_to_buy
            if new_qty_yes == 0: return False
            new_avg_p_yes = new_cost_yes / new_qty_yes
            new_combined_avg_p = new_avg_p_yes + avg_p_no
        elif target_side == 'Down':  # 'Down' is NO
            new_cost_no = cost_no + qty_to_buy * price
            new_qty_no = qty_no + qty_to_buy
            if new_qty_no == 0: return False
            new_avg_p_no = new_cost_no / new_qty_no
            new_combined_avg_p = avg_p_yes + new_avg_p_no
        else:
            return False

        return new_combined_avg_p < self.SAFETY_MARGIN_M

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        portfolio = self._get_or_init_portfolio(market_id)
        side_to_buy = None

        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']

        # --- LOGIC FOR BALANCED PORTFOLIO (Increase Position) ---
        if qty_yes == qty_no:
            if qty_yes >= self.MAX_TRADE_SIZE:
                return None

            # Use best ask prices from order book data
            price_yes = market_data_point.get('UpAsk', 0)
            price_no = market_data_point.get('DownAsk', 0)

            # Only increase position if buying a pair is profitable
            if price_yes > 0 and price_no > 0 and (price_yes + price_no < self.SAFETY_MARGIN_M):
                # Determine the max quantity we can possibly add
                qty_to_try = self.MAX_TRADE_SIZE - qty_yes

                # Search for the largest, safe, and affordable quantity to buy
                while qty_to_try > 0:
                    # Decide which side to buy first (the more expensive one, to lock in profit)
                    side_to_buy = 'Up' if price_yes > price_no else 'Down'
                    price_to_buy = price_yes if side_to_buy == 'Up' else price_no

                    cost = qty_to_try * price_to_buy
                    if cost > current_capital:
                        qty_to_try -= 1
                        continue

                    # Check all constraints
                    if not self.check_delta_constraint(portfolio, side_to_buy, qty_to_try):
                        qty_to_try -= 1
                        continue

                    if not self.check_liquidity_constraint(market_data_point, side_to_buy, qty_to_try):
                        qty_to_try -= 1
                        continue

                    if self.check_safety_margin(portfolio, side_to_buy, qty_to_try, price_to_buy):
                        # Found the optimal amount, return it
                        return (side_to_buy, qty_to_try, price_to_buy, 1.0)

                    qty_to_try -= 1

            return None # Conditions not met to increase position

        # --- LOGIC FOR UNBALANCED PORTFOLIO (Rebalancing from equalizer.py) ---
        quantity_delta = abs(qty_yes - qty_no)

        if quantity_delta < self.MIN_BALANCE_QTY:
            return None

        price_yes = market_data_point.get('UpAsk', 0)
        price_no = market_data_point.get('DownAsk', 0)

        target_side = None
        target_price = 0.0

        if qty_yes > qty_no:
            target_side = 'Down'
            target_price = price_no
        else: # qty_no > qty_yes
            target_side = 'Up'
            target_price = price_yes

        if target_price <= 0:
            return None

        qty_to_buy = int(min(quantity_delta, self.MAX_TRADE_SIZE))

        while qty_to_buy > 0:
            cost = qty_to_buy * target_price
            if cost > current_capital:
                qty_to_buy -= 1
                continue

            # Check all constraints
            if not self.check_delta_constraint(portfolio, target_side, qty_to_buy):
                qty_to_buy -= 1
                continue

            if not self.check_liquidity_constraint(market_data_point, target_side, qty_to_buy):
                qty_to_buy -= 1
                continue

            if self.check_safety_margin(portfolio, target_side, qty_to_buy, target_price):
                return (target_side, qty_to_buy, target_price, 1.0)

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
