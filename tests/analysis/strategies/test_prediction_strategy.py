import pytest
from src.analysis.strategies.prediction_strategy import PredictionStrategy

@pytest.fixture
def strategy():
    return PredictionStrategy()

def test_decide_returns_correct_format(strategy):
    market_data = {
        'MinuteFromStart': 5,
        'SharpEvent': True,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 0.1,
        'UpAsk': 0.5,
        'DownAsk': 0.5,
    }
    decision = strategy.decide(market_data, 1000)
    assert decision is not None
    assert len(decision) == 4
    assert decision[0] in ['Up', 'Down']
    assert isinstance(decision[1], int)
    assert isinstance(decision[2], float)
    assert isinstance(decision[3], float)

def test_decide_time_filter(strategy):
    market_data = {
        'MinuteFromStart': 1, # Before the trading window
        'SharpEvent': True,
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 0.1,
        'UpAsk': 0.5,
        'DownAsk': 0.5,
    }
    decision = strategy.decide(market_data, 1000)
    assert decision is None

def test_decide_sharp_event_filter(strategy):
    market_data = {
        'MinuteFromStart': 5,
        'SharpEvent': False, # No sharp event
        'UpMidDelta': 0.01,
        'DownMidDelta': -0.01,
        'BidLiquidityImbalance': 0.1,
        'UpAsk': 0.5,
        'DownAsk': 0.5,
    }
    decision = strategy.decide(market_data, 1000)
    assert decision is None

def test_decide_no_signal(strategy):
    market_data = {
        'MinuteFromStart': 5,
        'SharpEvent': True,
        'UpMidDelta': 0, # No price delta
        'DownMidDelta': 0,
        'BidLiquidityImbalance': 0, # No liquidity imbalance
        'UpAsk': 0.5,
        'DownAsk': 0.5,
    }
    decision = strategy.decide(market_data, 1000)
    assert decision is None
