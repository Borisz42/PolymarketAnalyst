import pandas as pd
import src.config as config
from src.analysis.preprocessing import preprocess_base_features, preprocess_moving_average_features
from src.analysis.strategies.prediction_strategy import PredictionStrategy
from src.analysis.strategies.moving_average_strategy import MovingAverageStrategy

def get_winning_side(market_data):
    """Determines the winning side of a market based on final ask prices."""
    final_row = market_data.iloc[-1]
    up_ask = final_row.get('UpAsk', 0)
    down_ask = final_row.get('DownAsk', 0)

    if up_ask == 0:
        winning_side = 'Up'
    elif down_ask == 0:
        winning_side = 'Down'
    elif down_ask > up_ask:
        winning_side = 'Down'
    else:
        winning_side = 'Up'
    return winning_side



def print_accuracy_report(strategy_name, signal_stats):
    """Prints a formatted accuracy report for a given strategy."""
    print(f"\n--- {strategy_name} Signal Accuracy Report ---")

    if not signal_stats:
        print("  No signals were generated.")
        print("------------------------------------------")
        return

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
    print(f"------------------------------------------")


def analyze_signals():
    """Analyzes the accuracy of signals from the Prediction and Moving Average strategies."""
    # Load and preprocess data
    try:
        data = pd.read_csv(config.get_analysis_filename())
    except FileNotFoundError as e:
        print(e)
        return

    # Convert columns to datetime objects
    for col in ['Timestamp', 'TargetTime', 'Expiration']:
        data[col] = pd.to_datetime(data[col], utc=True)

    data = preprocess_base_features(data)
    data = preprocess_moving_average_features(data)

    # Instantiate the stateless strategy
    prediction_strategy = PredictionStrategy()

    # Data structure to hold accuracy stats
    prediction_signal_stats = {}
    ma_signal_stats = {}

    mock_capital = 10000

    # Group data by market
    grouped = data.groupby(['TargetTime', 'Expiration'])

    for market_id, market_data in grouped:
        winning_side = get_winning_side(market_data)

        # Instantiate a new stateful strategy for each market to ensure no state leakage
        ma_strategy = MovingAverageStrategy()

        for _, row in market_data.iterrows():
            # --- Prediction Strategy ---
            prediction_decision = prediction_strategy.decide(row, mock_capital)
            if prediction_decision:
                signal, _, _, score = prediction_decision
                key = (signal, int(score))

                if key not in prediction_signal_stats:
                    prediction_signal_stats[key] = {'correct': 0, 'total': 0}

                prediction_signal_stats[key]['total'] += 1
                if signal == winning_side:
                    prediction_signal_stats[key]['correct'] += 1

            # --- Moving Average Strategy ---
            ma_decision = ma_strategy.decide(row, mock_capital)
            if ma_decision:
                signal, quantity, price, score = ma_decision
                key = (signal, int(score))

                if key not in ma_signal_stats:
                    ma_signal_stats[key] = {'correct': 0, 'total': 0}

                ma_signal_stats[key]['total'] += 1
                if signal == winning_side:
                    ma_signal_stats[key]['correct'] += 1

                # Update the stateful MA strategy
                ma_strategy.update_portfolio(market_id, signal, quantity, price)

    # --- Print summary ---
    print_accuracy_report("Prediction Strategy", prediction_signal_stats)
    print_accuracy_report("Moving Average Strategy", ma_signal_stats)

if __name__ == "__main__":
    analyze_signals()
