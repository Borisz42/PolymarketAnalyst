import pytest
import pandas as pd
from src.analysis.backtester import Backtester
from src.analysis.strategies.base_strategy import Strategy

TEST_DATA_FILE = 'tests/data/test_market_data.csv'

def test_load_data():
    print("Testing data loading and timestamp parsing...")
    backtester = Backtester()
    backtester.load_data(TEST_DATA_FILE)
    assert not backtester.market_data.empty
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['Timestamp'])
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['TargetTime'])
    assert pd.api.types.is_datetime64_any_dtype(backtester.market_data['Expiration'])
    print("Data loading and timestamp parsing successful.")

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
    print("Testing slippage application...")
    backtester = Backtester(slippage_seconds=2)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.55
    print("Slippage correctly applied.")

def test_no_slippage():
    print("Testing scenario with no slippage...")
    backtester = Backtester(slippage_seconds=0)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.5
    print("No slippage correctly handled.")

def test_pnl_calculation_win():
    print("Testing PnL calculation for a winning trade...")
    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert backtester.capital == 105
    print("PnL for winning trade calculated correctly.")

def test_pnl_calculation_loss():
    print("Testing PnL calculation for a losing trade...")
    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Down', 10, 0.52))
    backtester.run_strategy(strategy)

    assert backtester.capital == 94.8
    print("PnL for losing trade calculated correctly.")

def test_no_future_data_for_slippage():
    print("Testing slippage with no future data point available...")
    backtester = Backtester(slippage_seconds=10)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) > 0
    buy_transaction = [t for t in backtester.transactions if t['Type'] == 'Buy'][0]
    assert buy_transaction['EntryPrice'] == 0.5
    print("Slippage with no future data correctly handled.")
