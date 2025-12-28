import pytest
import pandas as pd
from src.analysis.backtester import Backtester
from src.analysis.strategies.base_strategy import Strategy

TEST_DATA_FILE = 'tests/data/test_market_data.csv'

def test_load_data():
    backtester = Backtester()
    backtester.load_data(TEST_DATA_FILE)
    assert not backtester.market_data.empty
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['Timestamp'])
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['TargetTime'])
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['Expiration'])

class DummyStrategy(Strategy):
    def __init__(self, trade_decision):
        self.trade_decision = trade_decision
        self.has_traded = False

    def decide(self, data_point, capital):
        if not self.has_traded:
            self.has_traded = True
            return self.trade_decision
        return None

def test_slippage_applied():
    backtester = Backtester(slippage_seconds=2)
    backtester.load_data(TEST_DATA_FILE)

    # This dummy strategy will decide to trade 'Up' at the first data point
    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    # The trade occurs at 12:00:00, with 2s slippage, the price should be from 12:00:02
    # The 'UpAsk' price at 12:00:02 in the test data is 0.55
    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.55

def test_no_slippage():
    backtester = Backtester(slippage_seconds=0)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.5

def test_pnl_calculation_win():
    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    # Initial capital is 100, cost of trade is 10 * 0.5 = 5. Capital becomes 95.
    # The 'Up' side wins, so PnL is 10 * (1 - 0.5) = 5.
    # Final capital should be 95 (after buy) + 10 (resolution) = 105.
    assert backtester.capital == 105

def test_pnl_calculation_loss():
    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Down', 10, 0.52))
    backtester.run_strategy(strategy)

    # Initial capital is 100, cost of trade is 10 * 0.52 = 5.2. Capital becomes 94.8.
    # The 'Up' side wins, so the 'Down' trade is a loss. PnL is -5.2.
    # Final capital is 94.8.
    assert backtester.capital == 94.8

def test_no_future_data_for_slippage():
    backtester = Backtester(slippage_seconds=10) # 10s slippage, but no data point available
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.5
