import unittest
import pandas as pd
from src.analysis.strategies.avg_arbitrage_strategy import AvgArbitrageStrategy

class TestAvgArbitrageStrategy(unittest.TestCase):

    def setUp(self):
        """Set up a strategy instance for each test."""
        self.strategy = AvgArbitrageStrategy(
            margin=0.01,
            initial_trade_capital_percentage=0.05,
            max_capital_allocation_percentage=0.50
        )
        self.initial_capital = 1000

    def test_first_trade_cheaper_down(self):
        """Test the first trade logic when Down side is cheaper."""
        market_data_point = {'UpAsk': 0.6, 'DownAsk': 0.4}
        side, quantity, price, score = self.strategy.decide(market_data_point, self.initial_capital)

        expected_trade_amount = self.initial_capital * 0.05
        expected_quantity = int(expected_trade_amount / 0.4)

        self.assertEqual(side, 'Down')
        self.assertEqual(quantity, expected_quantity)
        self.assertEqual(price, 0.4)
        self.assertEqual(self.strategy.down_qty, expected_quantity)
        self.assertEqual(self.strategy.down_total_cost, expected_quantity * 0.4)

    def test_first_trade_cheaper_up(self):
        """Test the first trade logic when Up side is cheaper."""
        market_data_point = {'UpAsk': 0.3, 'DownAsk': 0.7}
        side, quantity, price, score = self.strategy.decide(market_data_point, self.initial_capital)

        expected_trade_amount = self.initial_capital * 0.05
        expected_quantity = int(expected_trade_amount / 0.3)

        self.assertEqual(side, 'Up')
        self.assertEqual(quantity, expected_quantity)
        self.assertEqual(price, 0.3)
        self.assertEqual(self.strategy.up_qty, expected_quantity)
        self.assertEqual(self.strategy.up_total_cost, expected_quantity * 0.3)

    def test_no_first_trade_if_prices_are_zero(self):
        """Test that no trade occurs if a price is zero."""
        market_data_point = {'UpAsk': 0.5, 'DownAsk': 0}
        result = self.strategy.decide(market_data_point, self.initial_capital)
        self.assertEqual(result, (None, 0, 0, 0))

    def test_subsequent_trade_balance_up(self):
        """Test balancing by buying Up shares."""
        # Initial state: 100 Down shares at 0.4
        self.strategy.down_qty = 100
        self.strategy.down_total_cost = 40
        self.strategy.initial_capital_per_market = self.initial_capital

        market_data_point = {'UpAsk': 0.55, 'DownAsk': 0.45}

        # Formula: up_qty_to_buy = floor(((100 / 1.01) - 0 - 40) / 0.55)
        # = floor((99.0099 - 40) / 0.55) = floor(59.0099 / 0.55) = floor(107.29) = 107
        expected_qty = 107

        side, quantity, price, score = self.strategy.decide(market_data_point, self.initial_capital)

        self.assertEqual(side, 'Up')
        self.assertEqual(quantity, expected_qty)
        self.assertEqual(price, 0.55)
        self.assertEqual(self.strategy.up_qty, expected_qty)

    def test_subsequent_trade_balance_down(self):
        """Test balancing by buying Down shares."""
        # Initial state: 150 Up shares at 0.3
        self.strategy.up_qty = 150
        self.strategy.up_total_cost = 45
        self.strategy.initial_capital_per_market = self.initial_capital

        market_data_point = {'UpAsk': 0.35, 'DownAsk': 0.65}

        # Formula: down_qty_to_buy = floor(((150 / 1.01) - 45 - 0) / 0.65)
        # = floor((148.5148 - 45) / 0.65) = floor(103.5148 / 0.65) = floor(159.25) = 159
        expected_qty = 159

        side, quantity, price, score = self.strategy.decide(market_data_point, self.initial_capital)

        self.assertEqual(side, 'Down')
        self.assertEqual(quantity, expected_qty)
        self.assertEqual(price, 0.65)
        self.assertEqual(self.strategy.down_qty, expected_qty)

    def test_capital_allocation_limit(self):
        """Test that a trade is blocked if it exceeds the capital limit."""
        self.strategy.up_qty = 200
        self.strategy.up_total_cost = 100
        self.strategy.down_qty = 100
        self.strategy.down_total_cost = 400 # Total cost is 500, which is 50% of 1000
        self.strategy.initial_capital_per_market = self.initial_capital

        # This trade would normally be valid, but will push capital over the limit
        market_data_point = {'UpAsk': 0.5, 'DownAsk': 0.5}

        result = self.strategy.decide(market_data_point, self.initial_capital)

        self.assertEqual(result, (None, 0, 0, 0))

    def test_no_trade_if_formula_is_negative(self):
        """Test no trade occurs if the balancing formula result is negative."""
        # Invariant is already violated (cost > payout / margin), so no trade should happen
        self.strategy.down_qty = 100
        self.strategy.down_total_cost = 99.5 # Cost is higher than 100/1.01
        self.strategy.initial_capital_per_market = self.initial_capital

        market_data_point = {'UpAsk': 0.1, 'DownAsk': 0.9}

        result = self.strategy.decide(market_data_point, self.initial_capital)
        self.assertEqual(result, (None, 0, 0, 0))

if __name__ == '__main__':
    unittest.main()
