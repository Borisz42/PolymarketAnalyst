import src.config as config
import pandas as pd
import datetime
import os
import time
from collections import deque
from decimal import Decimal
import logging
import inspect

DATA_FILE = config.get_analysis_filename()

# Global Configuration Variables
INITIAL_CAPITAL = config.INITIAL_CAPITAL


class Backtester:
    def __init__(self, initial_capital=INITIAL_CAPITAL, slippage_seconds=config.SLIPPAGE_SECONDS):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_seconds = slippage_seconds
        self.transactions = [] # List of (timestamp, type, market_id, side, quantity, price, value, PnL)
        self.open_positions = [] # Changed to a list to allow multiple open positions per market
        self.market_data = pd.DataFrame()
        self.market_history = {} # Stores historical data grouped by market for resolution
        self.pending_market_summaries = {} # Key: market_id_tuple, Value: list of resolved_position_info dictionaries
        self.transactions_by_market = {} # OPTIMIZATION: Store transactions grouped by market
        
        # Risk tracking (from risk_engine.py)
        self.max_drawdown = 0.0
        self.portfolio_history = []  # Tracks (timestamp, capital) after each market resolution
        self.risk_events = []  # Track risk-related events

        self._setup_logging()

    def _setup_logging(self):
        """Sets up timestamped file logging and a console logger."""
        os.makedirs('logs', exist_ok=True)
        run_timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f'logs/backtest_run_{run_timestamp}.log'

        # File Logger (detailed logs)
        self.logger = logging.getLogger(f'BacktesterFileLogger_{id(self)}')
        self.logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(log_filename)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        self.logger.propagate = False

        # Console Logger (for progress and summaries)
        self.console_logger = logging.getLogger(f'BacktesterConsoleLogger_{id(self)}')
        self.console_logger.setLevel(logging.INFO)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        self.console_logger.addHandler(console_handler)
        self.console_logger.propagate = False

        self.logger.info(f"Logging initialized for backtest run: {run_timestamp}")

    def _log_and_print(self, message, level='info'):
        """Logs a message to the file and prints it to the console."""
        if level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        # Add other levels as needed
        self.console_logger.info(message)

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            self.logger.error(f"Data file not found at {file_path}")
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        date_columns = ['Timestamp', 'TargetTime', 'Expiration']
        self.market_data = pd.read_csv(file_path, parse_dates=date_columns)

        for col in date_columns:
            self.market_data[col] = self.market_data[col].dt.tz_localize('UTC')
        
        self.market_data.sort_values(by='Timestamp', inplace=True)

        grouped_by_market = self.market_data.groupby(['TargetTime', 'Expiration'])
        self.market_history = {market_id: group for market_id, group in grouped_by_market}

        self.logger.info(f"Loaded {len(self.market_data)} data points from {file_path}")

    def _resolve_single_position(self, market_id_tuple, position, current_timestamp):
        """Resolves a single expired market position and returns its PnL details."""
        if market_id_tuple not in self.market_history:
            self.logger.warning(f"Market ID {market_id_tuple} not found in market history for resolution.")
            return {'pnl': 0, 'winning_side': 'Error'} 

        market_specific_data = self.market_history[market_id_tuple]
        last_dp = market_specific_data.iloc[-1]

        winning_side = None
        up_ask = last_dp.get('UpAsk', last_dp.get('UpPrice', 0))
        down_ask = last_dp.get('DownAsk', last_dp.get('DownPrice', 0))
        
        if up_ask == 0:
            winning_side = 'Up'
        elif down_ask == 0:
            winning_side = 'Down'
        elif down_ask > up_ask:
            winning_side = 'Down'
        else:
            winning_side = 'Up'
        
        pnl = 0
        if position['side'] == winning_side:
            pnl = position['quantity'] * (1 - position['entry_price'])
            self.capital += position['quantity']
        else:
            pnl = - (position['quantity'] * position['entry_price'])

        resolution_log_entry = {
            'Timestamp': current_timestamp, 'Type': 'Resolution', 'MarketID': market_id_tuple,
            'Side': position['side'], 'Quantity': position['quantity'], 'EntryPrice': position['entry_price'],
            'Value': position['quantity'] * position['entry_price'], 'PnL': pnl, 'WinningSide': winning_side
        }
        self.transactions.append(resolution_log_entry)
        self.transactions_by_market.setdefault(market_id_tuple, []).append(resolution_log_entry)
        self.logger.info(f"RESOLUTION: {resolution_log_entry}")
        
        return {
            'market_id': market_id_tuple, 'side': position['side'], 'quantity': position['quantity'],
            'entry_price': position['entry_price'], 'pnl': pnl, 'winning_side': winning_side
        }

    def _print_market_summary(self, market_id_tuple, resolved_positions_data):
        """Logs and prints a consolidated summary for a fully resolved market."""
        market_id_formatted = f"({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')})"

        total_up_shares, total_up_cost, total_down_shares, total_down_cost, total_market_pnl = 0, 0.0, 0, 0.0, 0.0
        for res in resolved_positions_data:
            total_market_pnl += res['pnl']
            if res['side'] == 'Up':
                total_up_shares += res['quantity']
                total_up_cost += res['quantity'] * res['entry_price']
            else:
                total_down_shares += res['quantity']
                total_down_cost += res['quantity'] * res['entry_price']
        
        avg_up_price = total_up_cost / total_up_shares if total_up_shares > 0 else 0.0
        avg_down_price = total_down_cost / total_down_shares if total_down_shares > 0 else 0.0

        # --- OPTIMIZATION: Use pre-grouped transactions ---
        # Instead of searching the global transactions list, this pulls from a pre-grouped
        # dictionary, which is significantly faster.
        market_buy_txs = [
            t for t in self.transactions_by_market.get(market_id_tuple, [])
            if t['Type'] == 'Buy'
        ]
        total_trades = len(market_buy_txs)
        avg_trade_size = sum(t['Quantity'] for t in market_buy_txs) / total_trades if total_trades > 0 else 0
        
        avg_time_between_trades_str = "N/A"
        if total_trades > 1:
            market_buy_txs.sort(key=lambda x: x['Timestamp'])
            timestamps = [t['Timestamp'] for t in market_buy_txs]
            time_diffs = [(timestamps[i] - timestamps[i-1]).total_seconds() for i in range(1, len(timestamps))]
            avg_seconds = sum(time_diffs) / len(time_diffs)
            avg_time_between_trades_str = f"{avg_seconds:.1f}s" if avg_seconds < 60 else f"{int(avg_seconds // 60)}m {int(avg_seconds % 60)}s"

        summary_lines = [
            f"\n--- Market Resolution Summary for {market_id_formatted} ---",
            f"Total PnL for market: ${total_market_pnl:.2f}",
            f"Up Shares: {total_up_shares}, Avg Entry Price: ${avg_up_price:.2f}",
            f"Down Shares: {total_down_shares}, Avg Entry Price: ${avg_down_price:.2f}"
        ]

        resolution_timestamp = market_id_tuple[1]
        portfolio_value_at_resolution = next((capital for ts, capital in self.portfolio_history if ts >= resolution_timestamp), None)
        if portfolio_value_at_resolution is not None:
             summary_lines.append(f"Portfolio Value After Resolution: ${portfolio_value_at_resolution:.2f}")

        summary_lines.extend([
            f"Execution Stats:",
            f"  Total Trades: {total_trades}",
            f"  Avg Trade Size: {avg_trade_size:.1f} shares",
            f"  Avg Time Between Trades: {avg_time_between_trades_str}",
            "--------------------------------------------------"
        ])

        full_summary = "\n".join(summary_lines)
        self.logger.info(full_summary)

    def _calculate_max_drawdown(self):
        if not self.portfolio_history:
            return 0.0
        peak = self.initial_capital
        max_drawdown = 0.0
        for _, value in self.portfolio_history:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return max_drawdown

    def _apply_slippage(self, current_timestamp, market_id_tuple, side, entry_price):
        """
        Applies slippage to the entry price by looking ahead in the data.

        --- OPTIMIZATION: Use pre-grouped market history ---
        Instead of filtering the entire `market_data` DataFrame on every call,
        this optimized version performs a lookup in the `market_history` dictionary,
        which is pre-grouped by market. This dramatically reduces the search space
        from the whole dataset to just the relevant market's data, leading to a
        significant performance improvement, especially with large datasets.
        """
        if self.slippage_seconds <= 0:
            return entry_price
        slippage_timestamp = current_timestamp + pd.Timedelta(seconds=self.slippage_seconds)

        market_specific_data = self.market_history.get(market_id_tuple)
        if market_specific_data is None:
            return entry_price # Should not happen if data is consistent

        # Find the first data point at or after the slippage_timestamp within the specific market
        future_data = market_specific_data[market_specific_data['Timestamp'] >= slippage_timestamp]

        if not future_data.empty:
            slippage_row = future_data.iloc[0]
            price_col = 'UpAsk' if side == 'Up' else 'DownAsk'
            slipped_price = slippage_row.get(price_col, entry_price)
            if slipped_price > 0:
                return slipped_price
        return entry_price

    def run_strategy(self, strategy_instance):
        # --- Parameter Logging ---
        self.logger.info("--- Backtest Configuration ---")
        self.logger.info(f"Initial Capital: ${self.initial_capital}")
        self.logger.info(f"Slippage (seconds): {self.slippage_seconds}")
        # Note: Data file used is logged during load_data

        self.logger.info("\n--- Strategy Parameters ---")
        self.logger.info(f"Strategy Class: {strategy_instance.__class__.__name__}")

        # Get all attributes of the strategy instance
        strategy_params = inspect.getmembers(strategy_instance, lambda a: not(inspect.isroutine(a)))

        # Filter for non-private attributes (those not starting with '_')
        public_params = {name: value for name, value in strategy_params if not name.startswith('_')}

        for param, value in public_params.items():
             self.logger.info(f"  {param}: {value}")
        self.logger.info("----------------------------\n")

        current_timestamp = None
        # --- OPTIMIZATION: Group by Timestamp ---
        # Grouping data by timestamp once before the loop is much more efficient
        # than iterating through unique timestamps and filtering the DataFrame on each iteration.
        # This avoids redundant data scanning.
        grouped_by_timestamp = self.market_data.groupby('Timestamp', sort=False)
        n_unique_timestamps = len(grouped_by_timestamp)
        start_time = time.time()

        self.console_logger.info("Running backtest...")
        for i, (current_timestamp, current_data_points) in enumerate(grouped_by_timestamp):
            # Progress logging
            if n_unique_timestamps > 50 and (i + 1) % (n_unique_timestamps // 50) == 0:
                elapsed_time = time.time() - start_time
                progress = (i + 1) / n_unique_timestamps
                eta = (elapsed_time / progress) * (1 - progress) if progress > 0 else 0
                print(f"\r  -> Progress: {progress:.0%}, "
                      f"Elapsed: {datetime.timedelta(seconds=int(elapsed_time))}, "
                      f"ETA: {datetime.timedelta(seconds=int(eta))}", end="")

            positions_to_remove_indices = []

            # Process open positions for expiration at current_timestamp or earlier
            for pos_index, position in enumerate(self.open_positions):
                if current_timestamp >= position['expiration']:
                    market_id_tuple = position['market_id']

                    resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)

                    if market_id_tuple not in self.pending_market_summaries:
                        self.pending_market_summaries[market_id_tuple] = []
                    self.pending_market_summaries[market_id_tuple].append(resolved_info)

                    positions_to_remove_indices.append(pos_index)

            # Remove resolved positions from self.open_positions
            if positions_to_remove_indices:
                for index in sorted(positions_to_remove_indices, reverse=True):
                    del self.open_positions[index]
                self.portfolio_history.append((current_timestamp, self.capital))

            # No need to filter `market_data` anymore, as `current_data_points` is the slice.
            for _, row in current_data_points.iterrows():
                market_id_tuple = (row['TargetTime'], row['Expiration'])
                trade_decision = strategy_instance.decide(row, self.capital)
                
                if trade_decision:
                    if current_timestamp >= row['Expiration']:
                        self.logger.warning(f"Trade rejected for {market_id_tuple} at {current_timestamp}: market already expired.")
                        continue
                    side, quantity, entry_price, _ = trade_decision
                    entry_price = self._apply_slippage(current_timestamp, market_id_tuple, side, entry_price)
                    cost = quantity * entry_price
                    if self.capital >= cost:
                        self.capital -= cost
                        if hasattr(strategy_instance, 'update_portfolio'):
                            strategy_instance.update_portfolio(market_id_tuple, side, quantity, entry_price)
                        self.open_positions.append({
                            'market_id': market_id_tuple, 'side': side, 'quantity': quantity,
                            'entry_price': entry_price, 'expiration': row['Expiration']
                        })
                        trade_log_entry = {
                            'Timestamp': current_timestamp, 'Type': 'Buy', 'MarketID': market_id_tuple,
                            'Side': side, 'Quantity': quantity, 'EntryPrice': entry_price,
                            'Value': cost, 'PnL': -cost
                        }
                        self.transactions.append(trade_log_entry)
                        self.transactions_by_market.setdefault(market_id_tuple, []).append(trade_log_entry)
                        self.logger.info(f"TRADE: {trade_log_entry}")
                    else:
                        event = {
                            'timestamp': current_timestamp, 'event': 'Insufficient Capital',
                            'details': f"Needed ${cost:.2f}, had ${self.capital:.2f}"
                        }
                        self.risk_events.append(event)
                        self.logger.warning(f"INSUFFICIENT CAPITAL: {event['details']}")
        
        final_timestamp = current_timestamp if current_timestamp else datetime.datetime.now(datetime.timezone.utc)
        for position in self.open_positions[:]:
            market_id_tuple = position['market_id']
            resolved_info = self._resolve_single_position(market_id_tuple, position, final_timestamp)
            if market_id_tuple not in self.pending_market_summaries:
                self.pending_market_summaries[market_id_tuple] = []
            self.pending_market_summaries[market_id_tuple].append(resolved_info)
            self.open_positions.remove(position)

        for market_id_tuple, resolutions_data in self.pending_market_summaries.items():
            self._print_market_summary(market_id_tuple, resolutions_data)
        self.pending_market_summaries.clear()

    def generate_report(self):
        buy_trades = [t for t in self.transactions if t['Type'] == 'Buy']
        resolution_trades = [t for t in self.transactions if t['Type'] == 'Resolution']
        total_pnl = self.capital - self.initial_capital
        roi = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        self.max_drawdown = self._calculate_max_drawdown()
        
        report_lines = [
            "\n--- Backtest Report ---",
            f"Initial Capital: ${self.initial_capital:.2f}",
            f"Final Capital:   ${self.capital:.2f}",
            f"Total PnL:       ${total_pnl:.2f} ({roi:+.2f}%)",
            f"Max Drawdown:    {self.max_drawdown * 100:.2f}%"
        ]

        total_up_shares = sum(t['Quantity'] for t in buy_trades if t['Side'] == 'Up')
        total_down_shares = sum(t['Quantity'] for t in buy_trades if t['Side'] == 'Down')
        markets_played = set(t['MarketID'] for t in buy_trades)
        num_markets_played = len(markets_played)
        market_pnl = {}
        for t in resolution_trades:
            market_pnl.setdefault(t['MarketID'], 0.0)
            market_pnl[t['MarketID']] += t.get('PnL', 0.0)
        
        num_markets_won = sum(1 for pnl in market_pnl.values() if pnl > 0)
        winning_trades_count = sum(1 for t in resolution_trades if t['PnL'] > 0)
        losing_trades_count = len(resolution_trades) - winning_trades_count
        
        report_lines.extend([
            f"Number of Markets Traded: {num_markets_played}",
            f"Number of Markets Won: {num_markets_won}",
            f"Number of Trading actions: {len(buy_trades)}",
            f"Number of Winning Trades: {winning_trades_count}",
            f"Number of Losing Trades: {losing_trades_count}",
            f"Total Up Shares: {total_up_shares}",
            f"Total Down Shares: {total_down_shares}"
        ])
        
        if self.risk_events:
            report_lines.append(f"\n--- Risk Events ---")
            report_lines.append(f"Total Risk Events: {len(self.risk_events)}")
            event_types = {}
            for event in self.risk_events:
                event_types.setdefault(event['event'], 0)
                event_types[event['event']] += 1
            for event_type, count in event_types.items():
                report_lines.append(f"  {event_type}: {count}")

        report_lines.append("\n--- Imbalanced Market Analysis ---")
        market_shares = {}
        for trade in buy_trades:
            market_id = trade['MarketID']
            if market_id not in market_shares:
                market_shares[market_id] = {'Up': 0, 'Down': 0}
            market_shares[market_id][trade['Side']] += trade['Quantity']

        imbalanced_count = 0
        for market_id, shares in market_shares.items():
            if shares['Up'] != shares['Down']:
                imbalanced_count += 1
                market_id_formatted = f"({market_id[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id[1].strftime('%Y-%m-%d %H:%M:%S')})"
                report_lines.append(f"Market {market_id_formatted} is imbalanced: Up={shares['Up']}, Down={shares['Down']}")
        
        if imbalanced_count == 0:
            report_lines.append("All traded markets are balanced.")
        report_lines.append("------------------------------------")

        full_report = "\n".join(report_lines)
        self._log_and_print(full_report)

if __name__ == "__main__":
    from .strategies.rebalancing_strategy import RebalancingStrategy

    backtester = Backtester(initial_capital=INITIAL_CAPITAL)
    
    try:
        backtester.load_data(DATA_FILE)
    except FileNotFoundError as e:
        # Use the logger if the backtester object was created
        if 'backtester' in locals() and hasattr(backtester, 'logger'):
             backtester.logger.error(f"Failed to load data: {e}")
             backtester.console_logger.error(f"Failed to load data: {e}")
        else:
             print(f"Failed to load data: {e}")
        exit()

    strategy = RebalancingStrategy()
    backtester.run_strategy(strategy)
    backtester.generate_report()
