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

    # Market 1 winner is 'Up'. This is a winning trade.
    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    # Cost = 10 * 0.55 (with slippage) = 5.5. Capital becomes 94.5.
    # Win, so capital becomes 94.5 + 10 = 104.5.
    assert backtester.capital == 104.5
    print("PnL for winning trade calculated correctly.")

def test_pnl_calculation_loss():
    print("Testing PnL calculation for a losing trade...")
    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)

    # Market 1 winner is 'Up'. This is a losing trade.
    strategy = DummyStrategy(trade_decision=('Down', 10, 0.52))
    backtester.run_strategy(strategy)

    # Cost = 10 * 0.48 (with slippage) = 4.8. Capital becomes 95.2.
    # Loss, so capital remains 95.2.
    assert backtester.capital == 95.2
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

def test_dummy_strategy_trades_once():
    print("Testing that DummyStrategy trades only once...")
    backtester = Backtester()
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    buy_transactions = [t for t in backtester.transactions if t['Type'] == 'Buy']
    assert len(buy_transactions) == 1
    print("DummyStrategy correctly traded only once.")

def test_insufficient_capital():
    print("Testing insufficient capital scenario...")
    backtester = Backtester(initial_capital=4)
    backtester.load_data(TEST_DATA_FILE)

    strategy = DummyStrategy(trade_decision=('Up', 10, 0.5))
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) == 0
    print("Insufficient capital scenario correctly handled.")

def test_multiple_markets():
    print("Testing backtester with multiple markets...")

    class MultiMarketDummyStrategy(Strategy):
        def __init__(self, decisions_by_market):
            self.decisions_by_market = decisions_by_market
            self.traded_markets = set()

        def decide(self, data_point, capital):
            market_id = (data_point['TargetTime'], data_point['Expiration'])
            if market_id not in self.traded_markets and market_id in self.decisions_by_market:
                self.traded_markets.add(market_id)
                return self.decisions_by_market[market_id]
            return None

    market1_id = (pd.to_datetime('2025-12-26 10:45:00+00:00'), pd.to_datetime('2025-12-26 10:45:00+00:00'))
    market2_id = (pd.to_datetime('2025-12-26 11:00:00+00:00'), pd.to_datetime('2025-12-26 11:00:00+00:00'))

    decisions = {
        market1_id: ('Up', 10, 0.5), # Win
        market2_id: ('Down', 10, 0.52) # Win
    }

    backtester = Backtester(initial_capital=100)
    backtester.load_data(TEST_DATA_FILE)
    strategy = MultiMarketDummyStrategy(decisions)
    backtester.run_strategy(strategy)

    # M1: Win -> Capital becomes 104.5
    # M2: Trade at 10:45:14, slippage to 10:45:16, DownAsk is 0.58.
    # Cost = 10 * 0.58 = 5.8. Capital becomes 104.5 - 5.8 = 98.7
    # Win, so capital becomes 98.7 + 10 = 108.7
    assert round(backtester.capital, 2) == 108.7
    print("Multiple markets correctly handled.")

def test_trade_at_expiration():
    print("Testing a trade at the exact moment of market expiration...")

    class ExpirationDummyStrategy(Strategy):
        def __init__(self, trade_decision, trade_timestamp):
            self.trade_decision = trade_decision
            self.trade_timestamp = trade_timestamp
            self.has_traded = False

        def decide(self, data_point, capital):
            if not self.has_traded and data_point['Timestamp'] == self.trade_timestamp:
                self.has_traded = True
                return self.trade_decision
            return None

    backtester = Backtester()
    backtester.load_data(TEST_DATA_FILE)

    expiration_time = pd.to_datetime('2025-12-26 10:45:00+00:00')

    strategy = ExpirationDummyStrategy(trade_decision=('Up', 10, 0.5), trade_timestamp=expiration_time)
    backtester.run_strategy(strategy)

    assert len(backtester.transactions) == 0
    print("Trade at expiration correctly rejected.")
