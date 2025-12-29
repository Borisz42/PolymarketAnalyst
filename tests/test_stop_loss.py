import pytest
from src.analysis.strategies.hybrid_strategy import HybridStrategy

def test_stop_loss_triggered_when_threshold_exceeded():
    strategy = HybridStrategy()
    market_id = ('2023-01-01 12:00:00', '2023-01-01 12:15:00')

    # Simulate an imbalanced portfolio where rebalancing would exceed the stop-loss threshold
    strategy.update_portfolio(market_id, 'Up', 100, 0.6)
    strategy.update_portfolio(market_id, 'Down', 0, 0)

    market_data_point = {
        'TargetTime': '2023-01-01 12:00:00',
        'Expiration': '2023-01-01 12:15:00',
        'UpAsk': 0.7,
        'DownAsk': 0.61,  # Price that will trigger the stop loss (0.6 + 0.61 = 1.21 > 1.2)
        'UpAskLiquidity': 500,
        'DownAskLiquidity': 500,
        'MinuteFromStart': 8,
        'SharpEvent': False,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 10
    }

    decision = strategy.decide(market_data_point, 1000)

    assert decision is not None, "Stop-loss should have been triggered"
    assert decision[0] == 'Down', "Should be buying the other side to hedge the imbalanced position"
    assert decision[1] == 100, "Should be buying the entire quantity of the imbalanced position"

def test_normal_rebalance_successful_below_threshold():
    strategy = HybridStrategy()
    market_id = ('2023-01-01 12:00:00', '2023-01-01 12:15:00')

    # Simulate an imbalanced portfolio
    strategy.update_portfolio(market_id, 'Up', 100, 0.6)
    strategy.update_portfolio(market_id, 'Down', 50, 0.5)

    market_data_point = {
        'TargetTime': '2023-01-01 12:00:00',
        'Expiration': '2023-01-01 12:15:00',
        'UpAsk': 0.7,
        'DownAsk': 0.2,  # Price low enough to pass safety margin (0.6 + ~0.3 < 1.0)
        'UpAskLiquidity': 500,
        'DownAskLiquidity': 500,
        'MinuteFromStart': 8,
        'SharpEvent': False,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 10
    }

    decision = strategy.decide(market_data_point, 1000)

    assert decision is not None, "A rebalancing trade should have been made"
    assert decision[0] == 'Down', "Should be buying the other side to rebalance"
    assert decision[1] > 0, "Should be buying a positive quantity"

def test_stop_loss_not_triggered_during_normal_trading():
    strategy = HybridStrategy()
    market_id = ('2023-01-01 12:00:00', '2023-01-01 12:15:00')

    # Simulate a balanced portfolio
    strategy.update_portfolio(market_id, 'Up', 100, 0.5)
    strategy.update_portfolio(market_id, 'Down', 100, 0.4)

    market_data_point = {
        'TargetTime': '2023-01-01 12:00:00',
        'Expiration': '2023-01-01 12:15:00',
        'UpAsk': 0.55,
        'DownAsk': 0.45,
        'UpAskLiquidity': 500,
        'DownAskLiquidity': 500,
        'MinuteFromStart': 8,
        'SharpEvent': False,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 10
    }

    decision = strategy.decide(market_data_point, 1000)

    assert decision is None, "No trade should have been made"
