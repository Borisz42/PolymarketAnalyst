import pandas as pd
import src.config as config
from src.analysis.prediction_backtester import preprocess_data
from src.analysis.strategies.prediction_strategy import PredictionStrategy

def get_winning_side(market_data):
    """Determines the winning side of a market."""
    final_row = market_data.iloc[-1]
    if final_row['UpMid'] == 0:
        return 'Up'
    elif final_row['DownMid'] == 0:
        return 'Down'
    return 'Up' if final_row['UpMid'] > final_row['DownMid'] else 'Down'


def get_confidence_score(market_data_point):
    """Calculates a confidence score based on the PredictionStrategy's logic."""
    up_score = 0
    down_score = 0

    # Signal 1: Price Delta
    if market_data_point["UpMidDelta"] > 0:
        up_score += 1
    if market_data_point["DownMidDelta"] > 0:
        down_score += 1

    # Signal 2: Liquidity Imbalance
    if market_data_point["BidLiquidityImbalance"] > 0:
        up_score += 1
    elif market_data_point["BidLiquidityImbalance"] < 0:
        down_score += 1

    return abs(up_score - down_score)

def analyze_signals():
    """Analyzes the accuracy of the PredictionStrategy's signals."""
    # Load and preprocess data
    try:
        data = pd.read_csv(config.get_analysis_filename())
    except FileNotFoundError as e:
        print(e)
        return

    # Convert columns to datetime objects
    for col in ['Timestamp', 'TargetTime', 'Expiration']:
        data[col] = pd.to_datetime(data[col], utc=True)

    data = preprocess_data(data)

    # Instantiate the strategy
    strategy = PredictionStrategy()

    correct_signals = 0
    total_signals = 0
    mock_capital = 10000

    # Group data by market
    grouped = data.groupby(['TargetTime', 'Expiration'])

    for market_id, market_data in grouped:
        winning_side = get_winning_side(market_data)

        for _, row in market_data.iterrows():
            decision = strategy.decide(row, mock_capital)
            if decision:
                signal, _, _ = decision
                confidence = get_confidence_score(row)
                total_signals += 1
                if signal == winning_side:
                    correct_signals += 1
                print(f"Signal: {signal}, Confidence: {confidence}, Winning Side: {winning_side}, Correct: {signal == winning_side}")

    # Print summary
    accuracy = correct_signals / total_signals if total_signals > 0 else 0
    print(f"\n--- Signal Accuracy Report ---")
    print(f"Total Signals: {total_signals}")
    print(f"Correct Signals: {correct_signals}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"------------------------------")

if __name__ == "__main__":
    analyze_signals()
