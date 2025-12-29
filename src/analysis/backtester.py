import src.config as config
import pandas as pd
import datetime
import os
from collections import deque
from decimal import Decimal

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
        
        # Risk tracking (from risk_engine.py)
        self.max_drawdown = 0.0
        self.portfolio_history = []  # Tracks (timestamp, capital) after each market resolution
        self.risk_events = []  # Track risk-related events

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        # --- OPTIMIZATION: Use `parse_dates` in `read_csv` ---
        # Parsing dates directly during CSV loading is more efficient than loading as strings and then converting.
        # This is measurably faster and reduces peak memory usage.
        date_columns = ['Timestamp', 'TargetTime', 'Expiration']
        self.market_data = pd.read_csv(file_path, parse_dates=date_columns)

        for col in date_columns:
            # `read_csv` creates timezone-naive columns. We must localize to UTC to match original behavior.
            self.market_data[col] = self.market_data[col].dt.tz_localize('UTC')
        
        # Sort data by timestamp to ensure chronological processing
        self.market_data.sort_values(by='Timestamp', inplace=True)

        # Group data by market identifier for easier lookup during resolution
        for _, row in self.market_data.iterrows():
            market_id = (row['TargetTime'], row['Expiration'])
            if market_id not in self.market_history:
                self.market_history[market_id] = []
            self.market_history[market_id].append(row)

        print(f"Loaded {len(self.market_data)} data points from {file_path}")

    def _resolve_single_position(self, market_id_tuple, position, current_timestamp):
        """Resolves a single expired market position and returns its PnL details."""
        if market_id_tuple not in self.market_history:
            return {'pnl': 0, 'winning_side': 'Error'} 

        market_specific_data = self.market_history[market_id_tuple]
        last_dp = market_specific_data[-1] # The final state of the market

        winning_side = None
        # In Polymarket, the winning contract resolves to $1, the loser to $0.
        # We check the ask price at resolution time.
        up_ask = last_dp.get('UpAsk', 0)
        down_ask = last_dp.get('DownAsk', 0)
        
        if up_ask > down_ask: # e.g., UpAsk is ~1.0, DownAsk is ~0.0
            winning_side = 'Up'
        else: # e.g., DownAsk is ~1.0, UpAsk is ~0.0
            winning_side = 'Down'
        
        pnl = 0

        if position['side'] == winning_side:
            pnl = position['quantity'] * (1 - position['entry_price'])
            self.capital += position['quantity']
        else:
            pnl = - (position['quantity'] * position['entry_price'])

        self.transactions.append({
            'Timestamp': current_timestamp,
            'Type': 'Resolution',
            'MarketID': market_id_tuple,
            'Side': position['side'],
            'Quantity': position['quantity'],
            'EntryPrice': position['entry_price'],
            'Value': position['quantity'] * position['entry_price'],
            'PnL': pnl,
            'WinningSide': winning_side
        })
        
        return {
            'market_id': market_id_tuple,
            'side': position['side'],
            'quantity': position['quantity'],
            'entry_price': position['entry_price'],
            'pnl': pnl,
            'winning_side': winning_side
        }

    def _print_market_summary(self, market_id_tuple, resolved_positions_data):
        """Prints a consolidated summary for a fully resolved market."""
        market_id_formatted = f"({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')})"

        total_up_shares = 0
        total_up_cost = 0.0
        total_down_shares = 0
        total_down_cost = 0.0
        total_market_pnl = 0.0

        for res in resolved_positions_data:
            total_market_pnl += res['pnl']
            if res['side'] == 'Up':
                total_up_shares += res['quantity']
                total_up_cost += res['quantity'] * res['entry_price']
            elif res['side'] == 'Down':
                total_down_shares += res['quantity']
                total_down_cost += res['quantity'] * res['entry_price']
        
        avg_up_price = total_up_cost / total_up_shares if total_up_shares > 0 else 0.0
        avg_down_price = total_down_cost / total_down_shares if total_down_shares > 0 else 0.0

        # Filter transactions for this market to get execution details
        market_txs = [t for t in self.transactions if t['MarketID'] == market_id_tuple and t['Type'] == 'Buy']
        
        # Calculate execution metrics
        total_trades = len(market_txs)
        avg_trade_size = sum(t['Quantity'] for t in market_txs) / total_trades if total_trades > 0 else 0
        
        # Calculate time between trades
        avg_time_between_trades_str = "N/A"
        if total_trades > 1:
            # Sort by timestamp
            market_txs.sort(key=lambda x: x['Timestamp'])
            
            timestamps = [t['Timestamp'] for t in market_txs]
            time_diffs = []
            for i in range(1, len(timestamps)):
                diff = (timestamps[i] - timestamps[i-1]).total_seconds()
                time_diffs.append(diff)
            
            avg_seconds = sum(time_diffs) / len(time_diffs)
            
            if avg_seconds < 60:
                avg_time_between_trades_str = f"{avg_seconds:.1f}s"
            else:
                avg_m = int(avg_seconds // 60)
                avg_s = int(avg_seconds % 60)
                avg_time_between_trades_str = f"{avg_m}m {avg_s}s"

        print(f"\n--- Market Resolution Summary for {market_id_formatted} ---")
        print(f"Total PnL for market: ${total_market_pnl:.2f}")
        print(f"Up Shares: {total_up_shares}, Avg Entry Price: ${avg_up_price:.2f}")
        print(f"Down Shares: {total_down_shares}, Avg Entry Price: ${avg_down_price:.2f}")

        # Find the portfolio value at the time of this market's resolution
        resolution_timestamp = market_id_tuple[1]
        portfolio_value_at_resolution = self.initial_capital

        # Find the portfolio value recorded at the first timestamp >= resolution_timestamp
        portfolio_value_at_resolution = None
        for ts, capital in self.portfolio_history:
            if ts >= resolution_timestamp:
                portfolio_value_at_resolution = capital
                break  # Found the first snapshot after resolution

        if portfolio_value_at_resolution is not None:
             print(f"Portfolio Value After Resolution: ${portfolio_value_at_resolution:.2f}")

        print(f"Execution Stats:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Avg Trade Size: {avg_trade_size:.1f} shares")
        print(f"  Avg Time Between Trades: {avg_time_between_trades_str}")
        print("--------------------------------------------------")

    def _calculate_max_drawdown(self):
        """Calculates the maximum drawdown from the portfolio history."""
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
        """Applies slippage to the entry price."""
        if self.slippage_seconds <= 0:
            return entry_price

        slippage_timestamp = current_timestamp + pd.Timedelta(seconds=self.slippage_seconds)

        # Find the first data point at or after the slippage_timestamp
        future_data = self.market_data[
            (self.market_data['Timestamp'] >= slippage_timestamp) &
            (self.market_data['TargetTime'] == market_id_tuple[0]) &
            (self.market_data['Expiration'] == market_id_tuple[1])
        ]

        if not future_data.empty:
            slippage_row = future_data.iloc[0]
            if side == 'Up':
                slipped_price = slippage_row.get('UpAsk', entry_price)
            elif side == 'Down':
                slipped_price = slippage_row.get('DownAsk', entry_price)
            else:
                slipped_price = entry_price

            if slipped_price > 0:
                return slipped_price

        return entry_price

    def run_strategy(self, strategy_instance):
        current_timestamp = None
        unique_timestamps = self.market_data['Timestamp'].unique()
        
        for ts_np in unique_timestamps:
            current_timestamp = pd.to_datetime(ts_np)
            
            positions_to_remove_indices = []
            
            # Process open positions for expiration at current_timestamp or earlier
            for i, position in enumerate(self.open_positions):
                if current_timestamp >= position['expiration']:
                    market_id_tuple = position['market_id']
                    
                    resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
                    
                    if market_id_tuple not in self.pending_market_summaries:
                        self.pending_market_summaries[market_id_tuple] = []
                    self.pending_market_summaries[market_id_tuple].append(resolved_info)
                    
                    positions_to_remove_indices.append(i)
            
            # Remove resolved positions from self.open_positions
            if positions_to_remove_indices:
                for index in sorted(positions_to_remove_indices, reverse=True):
                    del self.open_positions[index]

                # Record portfolio value after resolutions
                self.portfolio_history.append((current_timestamp, self.capital))

            # Get all data points for the current timestamp
            current_data_points = self.market_data[self.market_data['Timestamp'] == current_timestamp]

            for _, row in current_data_points.iterrows():
                market_id_tuple = (row['TargetTime'], row['Expiration'])
                
                trade_decision = strategy_instance.decide(row, self.capital)
                
                if trade_decision:
                    # Reject trades at or after expiration
                    if current_timestamp >= row['Expiration']:
                        continue

                    side, quantity, entry_price = trade_decision

                    entry_price = self._apply_slippage(current_timestamp, market_id_tuple, side, entry_price)

                    cost = quantity * entry_price

                    if self.capital >= cost:
                        self.capital -= cost

                        if hasattr(strategy_instance, 'update_portfolio'):
                            strategy_instance.update_portfolio(market_id_tuple, side, quantity, entry_price)

                        self.open_positions.append({
                            'market_id': market_id_tuple,
                            'side': side,
                            'quantity': quantity,
                            'entry_price': entry_price,
                            'expiration': row['Expiration']
                        })
                        self.transactions.append({
                            'Timestamp': current_timestamp,
                            'Type': 'Buy',
                            'MarketID': market_id_tuple,
                            'Side': side,
                            'Quantity': quantity,
                            'EntryPrice': entry_price,
                            'Value': cost,
                            'PnL': -cost
                        })
                    else:
                        # Track liquidity/capital constraint events
                        self.risk_events.append({
                            'timestamp': current_timestamp,
                            'event': 'Insufficient Capital',
                            'details': f"Needed ${cost:.2f}, had ${self.capital:.2f}"
                        })
        
        # After iterating through all timestamps, resolve any remaining open positions
        for position in self.open_positions[:]:
            market_id_tuple = position['market_id']
            resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
            
            if market_id_tuple not in self.pending_market_summaries:
                self.pending_market_summaries[market_id_tuple] = []
            self.pending_market_summaries[market_id_tuple].append(resolved_info)
            self.open_positions.remove(position)

        # Print summaries for any remaining markets in pending_market_summaries
        for market_id_tuple, resolutions_data in self.pending_market_summaries.items():
            self._print_market_summary(market_id_tuple, resolutions_data)
        self.pending_market_summaries.clear()

    def generate_report(self):
        print("\n--- Backtest Report ---")
        print(f"Initial Capital: ${self.initial_capital:.2f}")
        print(f"Final Capital:   ${self.capital:.2f}")
        
        total_pnl = self.capital - self.initial_capital
        roi = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        print(f"Total PnL:       ${total_pnl:.2f} ({roi:+.2f}%)")
        self.max_drawdown = self._calculate_max_drawdown()
        print(f"Max Drawdown:    {self.max_drawdown * 100:.2f}%")
        
        buy_trades = [t for t in self.transactions if t['Type'] == 'Buy']
        resolution_trades = [t for t in self.transactions if t['Type'] == 'Resolution']
        
        total_up_shares = sum(t['Quantity'] for t in buy_trades if t['Side'] == 'Up')
        total_down_shares = sum(t['Quantity'] for t in buy_trades if t['Side'] == 'Down')

        markets_played = set(t['MarketID'] for t in buy_trades)
        num_markets_played = len(markets_played)

        market_pnl = {}
        for t in resolution_trades:
            market_id = t['MarketID']
            pnl = t.get('PnL', 0.0)
            market_pnl.setdefault(market_id, 0.0)
            market_pnl[market_id] += pnl
        
        num_markets_won = sum(1 for pnl in market_pnl.values() if pnl > 0)

        winning_trades_count = 0
        losing_trades_count = 0
        for t in resolution_trades:
            if t['PnL'] > 0:
                winning_trades_count += 1
            else:
                losing_trades_count += 1
        
        print(f"Number of Markets Traded: {num_markets_played}")
        print(f"Number of Markets Won: {num_markets_won}")
        print(f"Number of Trading actions: {len(buy_trades)}")
        print(f"Number of Winning Trades: {winning_trades_count}")
        print(f"Number of Losing Trades: {losing_trades_count}")
        print(f"Total Up Shares: {total_up_shares}")
        print(f"Total Down Shares: {total_down_shares}")
        
        # Risk events summary
        if self.risk_events:
            print(f"\n--- Risk Events ---")
            print(f"Total Risk Events: {len(self.risk_events)}")
            event_types = {}
            for event in self.risk_events:
                event_type = event['event']
                event_types[event_type] = event_types.get(event_type, 0) + 1
            for event_type, count in event_types.items():
                print(f"  {event_type}: {count}")

        # Imbalanced markets analysis
        print("\n--- Imbalanced Market Analysis ---")
        market_shares = {}

        for trade in buy_trades:
            market_id = trade['MarketID']
            side = trade['Side']
            quantity = trade['Quantity']

            if market_id not in market_shares:
                market_shares[market_id] = {'Up': 0, 'Down': 0}
            
            market_shares[market_id][side] += quantity

        imbalanced_count = 0
        for market_id, shares in market_shares.items():
            if shares['Up'] != shares['Down']:
                imbalanced_count += 1
                market_id_formatted = f"({market_id[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id[1].strftime('%Y-%m-%d %H:%M:%S')})"
                print(f"Market {market_id_formatted} is imbalanced: Up={shares['Up']}, Down={shares['Down']}")
        
        if imbalanced_count == 0:
            print("All traded markets are balanced.")
        print("------------------------------------")

if __name__ == "__main__":
    from .strategies.rebalancing_strategy import RebalancingStrategy

    # With slippage
    # backtester = Backtester(initial_capital=INITIAL_CAPITAL, slippage_seconds=2)

    # Without slippage
    backtester = Backtester(initial_capital=INITIAL_CAPITAL)
    
    try:
        backtester.load_data(DATA_FILE)
    except FileNotFoundError as e:
        print(e)
        exit()

    strategy = RebalancingStrategy()
    backtester.run_strategy(strategy)
    backtester.generate_report()
