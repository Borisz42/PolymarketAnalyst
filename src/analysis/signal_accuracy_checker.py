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

    # Data structure to hold accuracy stats
    # { ('Up', 1): {'correct': 0, 'total': 0}, ... }
    signal_stats = {}

    mock_capital = 10000

    # Group data by market
    grouped = data.groupby(['TargetTime', 'Expiration'])

    for market_id, market_data in grouped:
        winning_side = get_winning_side(market_data)

        for _, row in market_data.iterrows():
            decision = strategy.decide(row, mock_capital)
            if decision:
                signal, _, _, score = decision
                key = (signal, int(score))

                if key not in signal_stats:
                    signal_stats[key] = {'correct': 0, 'total': 0}

                signal_stats[key]['total'] += 1
                if signal == winning_side:
                    signal_stats[key]['correct'] += 1

    # --- Print summary ---
    print(f"\n--- Signal Accuracy Report ---")

    total_correct = 0
    total_signals = 0

    # Sort by signal type, then strength
    sorted_keys = sorted(signal_stats.keys(), key=lambda x: (x[0], x[1]))

    for key in sorted_keys:
        stats = signal_stats[key]
        signal_type, signal_strength = key
        accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        total_correct += stats['correct']
        total_signals += stats['total']

        print(f"  Signal: {signal_type}, Strength: {signal_strength}")
        print(f"    Correct: {stats['correct']} / {stats['total']}")
        print(f"    Accuracy: {accuracy:.2%}\n")


    # Overall Accuracy
    overall_accuracy = total_correct / total_signals if total_signals > 0 else 0
    print(f"--- Overall Summary ---")
    print(f"Total Signals: {total_signals}")
    print(f"Correct Signals: {total_correct}")
    print(f"Overall Accuracy: {overall_accuracy:.2%}")
    print(f"-----------------------")

if __name__ == "__main__":
    analyze_signals()
