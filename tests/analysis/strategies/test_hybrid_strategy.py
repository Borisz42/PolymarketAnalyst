import pytest
from src.analysis.strategies.hybrid_strategy import HybridStrategy

@pytest.fixture
def strategy():
    return HybridStrategy()

def test_stop_loss_rebalance_triggered(strategy):
    # Initial trade to create an imbalance
    strategy.update_portfolio(('2023-01-01 12:00:00', '2023-01-01 12:15:00'), 'Up', 100, 0.6)

    # Market data that should trigger the stop-loss
    market_data = {
        'TargetTime': '2023-01-01 12:00:00',
        'Expiration': '2023-01-01 12:15:00',
        'UpAsk': 0.4,
        'DownAsk': 0.6,
        'UpAskLiquidity': 200,
        'DownAskLiquidity': 200,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 0.1,
        'MinuteFromStart': 8,
        'SharpEvent': True
    }

    # The cost to hedge (0.6) plus the current DownAsk price (0.6) is 1.2, which is > STOP_LOSS_THRESHOLD (1.10)
    # A stop-loss rebalance should be triggered
    decision = strategy.decide(market_data, 1000)

    assert decision is not None
    assert decision[0] == 'Down'
    assert decision[1] > 0
    assert decision[2] == 0.6

def test_stop_loss_not_triggered(strategy):
    # Initial trade to create an imbalance
    strategy.update_portfolio(('2023-01-01 12:00:00', '2023-01-01 12:15:00'), 'Up', 100, 0.4)

    # Market data that should NOT trigger the stop-loss, but a normal rebalance
    market_data = {
        'TargetTime': '2023-01-01 12:00:00',
        'Expiration': '2023-01-01 12:15:00',
        'UpAsk': 0.6,
        'DownAsk': 0.4,
        'UpAskLiquidity': 200,
        'DownAskLiquidity': 200,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 0.1,
        'MinuteFromStart': 8,
        'SharpEvent': True
    }

    # The cost to hedge (0.4) plus the current DownAsk price (0.4) is 0.8, which is < MAX_HEDGING_COST (0.99)
    # A normal rebalance should be triggered
    decision = strategy.decide(market_data, 1000)

    assert decision is not None
    assert decision[0] == 'Down'
    assert decision[1] > 0
    assert decision[2] == 0.4
