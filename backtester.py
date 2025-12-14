import pandas as pd
import datetime
import os
from collections import deque

DATA_FILE = "market_data.csv"

# Global Configuration Variables
INITIAL_CAPITAL = 1000.0
SHARE_SIZE = 2
# New global parameters for the derivative moving average strategy
DERIVATIVE_MA_PERIOD = 10 # Number of periods for the moving average of the derivative
DERIVATIVE_THRESHOLD = 0.005 # A small threshold to act as a buffer around zero for derivative MA
N_TICK_POINT = 1 # Trade on every N-th data point for a given market

class DerivativeMovingAverageStrategy:
    def __init__(self):
        # self.traded_markets = set() # Removed to allow multiple trades per market
        self.investment_amount = SHARE_SIZE # Use global SHARE_SIZE
        # Store price history for each market to calculate derivative moving average
        # Key: (TargetTime, Expiration)
        # Value: deque of (UpPrice, DownPrice) tuples for DERIVATIVE_MA_PERIOD + 1 entries
        self.market_price_history = {} 
        self.market_tick_counts = {} # To track the number of data points processed for each market

    def decide(self, market_data_point, current_capital):
        market_identifier = (market_data_point['TargetTime'], market_data_point['Expiration'])
        
        # Increment tick count for this market
        self.market_tick_counts[market_identifier] = self.market_tick_counts.get(market_identifier, 0) + 1

        # Only consider trading on every N_TICK_POINT-th data point
        if self.market_tick_counts[market_identifier] % N_TICK_POINT != 0:
            return None # Skip trade decision for this tick

        current_up_price = market_data_point['UpPrice']
        current_down_price = market_data_point['DownPrice']

        # Get/create price history for this market
        if market_identifier not in self.market_price_history:
            self.market_price_history[market_identifier] = deque(maxlen=DERIVATIVE_MA_PERIOD + 1)
        
        # Append current prices to history
        self.market_price_history[market_identifier].append((current_up_price, current_down_price))

        price_history = self.market_price_history[market_identifier]

        # Ensure we have enough data points to calculate the MA of derivatives
        if len(price_history) < DERIVATIVE_MA_PERIOD + 1:
            return None # Not enough history yet

        # Calculate the derivative moving average for UpPrice
        # Simplified: (Current Price - Price from DERIVATIVE_MA_PERIOD ago) / DERIVATIVE_MA_PERIOD
        ma_up_derivative = (price_history[-1][0] - price_history[0][0]) / DERIVATIVE_MA_PERIOD
        
        # Calculate the derivative moving average for DownPrice
        ma_down_derivative = (price_history[-1][1] - price_history[0][1]) / DERIVATIVE_MA_PERIOD

        side = None
        entry_price = 0.0

        if ma_up_derivative > DERIVATIVE_THRESHOLD:
            side = 'Up'
            entry_price = current_up_price
        elif ma_down_derivative < -DERIVATIVE_THRESHOLD: # Negative derivative for Down means price is decreasing
            side = 'Down'
            entry_price = current_down_price
        
        if side and (self.investment_amount * entry_price) <= current_capital:
            # self.traded_markets.add(market_identifier) # Removed to allow multiple trades
            return (side, self.investment_amount, entry_price)
        
        return None

class Backtester:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.transactions = [] # List of (timestamp, type, market_id, side, quantity, price, value, PnL)
        self.open_positions = [] # Changed to a list to allow multiple open positions per market
        self.market_data = pd.DataFrame()
        self.market_history = {} # Stores historical data grouped by market for resolution

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        self.market_data = pd.read_csv(file_path)
        
        # Convert relevant columns to datetime objects
        self.market_data['Timestamp'] = pd.to_datetime(self.market_data['Timestamp']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        # TargetTime and Expiration are now output as naive strings by data_logger.py,
        # but they represent UTC times, so localize them to UTC after parsing.
        self.market_data['TargetTime'] = pd.to_datetime(self.market_data['TargetTime']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        self.market_data['Expiration'] = pd.to_datetime(self.market_data['Expiration']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        
        # Sort data by timestamp to ensure chronological processing
        self.market_data.sort_values(by='Timestamp', inplace=True)

        # Group data by market identifier for easier lookup during resolution
        # A market is uniquely identified by its TargetTime and Expiration
        for _, row in self.market_data.iterrows():
            market_id = (row['TargetTime'], row['Expiration'])
            if market_id not in self.market_history:
                self.market_history[market_id] = []
            self.market_history[market_id].append(row)

        print(f"Loaded {len(self.market_data)} data points from {file_path}")

    def _resolve_single_position(self, market_id_tuple, position, current_timestamp):
        """Resolves a single expired market position and returns its PnL details."""
        if market_id_tuple not in self.market_history:
            # This should ideally not happen if data is loaded correctly
            # and market_id_tuple comes from an existing position
            return {'pnl': 0, 'winning_side': 'Error'} 

        market_specific_data = self.market_history[market_id_tuple]
        last_dp = market_specific_data[-1] # The final state of the market

        winning_side = None
        if last_dp['UpPrice'] == 0:  # If Up price is 0, then Up wins
            winning_side = 'Up'
        elif last_dp['DownPrice'] == 0: # If Down price is 0, then Down wins
            winning_side = 'Down'
        else:
            winning_side = 'Neither' # Effectively a loss for any held position
        
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
        
        # Return details for aggregation
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

        print(f"\n--- Market Resolution Summary for {market_id_formatted} ---")
        print(f"Total PnL for market: ${total_market_pnl:.2f}")
        print(f"Up Shares: {total_up_shares}, Avg Entry Price: ${avg_up_price:.2f}")
        print(f"Down Shares: {total_down_shares}, Avg Entry Price: ${avg_down_price:.2f}")
        print("--------------------------------------------------")


    def run_strategy(self, strategy_instance):
        current_timestamp = None
        unique_timestamps = self.market_data['Timestamp'].unique()
        
        for ts_np in unique_timestamps:
            current_timestamp = pd.to_datetime(ts_np)
            
            # Use a list to hold positions to remove to avoid modifying list during iteration
            positions_to_remove_indices = []
            
            # Collect all resolved positions at this timestamp, grouped by market_id_tuple
            resolved_positions_collector = {} # Key: market_id_tuple, Value: list of individual position resolution details

            # Process open positions for expiration at current_timestamp or earlier
            for i, position in enumerate(self.open_positions):
                if current_timestamp >= position['expiration']:
                    market_id_tuple = position['market_id']
                    
                    resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
                    
                    if market_id_tuple not in resolved_positions_collector:
                        resolved_positions_collector[market_id_tuple] = []
                    resolved_positions_collector[market_id_tuple].append(resolved_info)
                    
                    positions_to_remove_indices.append(i)
            
            # Remove resolved positions from self.open_positions (iterate in reverse to avoid index issues)
            for index in sorted(positions_to_remove_indices, reverse=True):
                del self.open_positions[index]

            # Print summary for markets that are fully resolved at this timestamp
            for market_id_tuple, resolutions_data in resolved_positions_collector.items():
                # A market is fully resolved at this timestamp if all its positions expired
                # and none are remaining in self.open_positions. Given that we delete positions
                # from open_positions for which current_timestamp >= expiration,
                # any market_id_tuple in resolved_positions_collector means all its positions
                # with this expiration have been resolved.
                self._print_market_summary(market_id_tuple, resolutions_data)

            # Get all data points for the current timestamp
            current_data_points = self.market_data[self.market_data['Timestamp'] == current_timestamp]

            for _, row in current_data_points.iterrows():
                market_id_tuple = (row['TargetTime'], row['Expiration'])
                
                trade_decision = strategy_instance.decide(row, self.capital)
                
                if trade_decision:
                    side, quantity, entry_price = trade_decision
                    cost = quantity * entry_price

                    if self.capital >= cost:

                        self.capital -= cost

                        self.open_positions.append({ # Append to list
                            'market_id': market_id_tuple, # Store market_id explicitly
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
                            'PnL': -cost # Initial PnL is the cost of investment
                        })
                        print(f"[{current_timestamp.strftime('%Y-%m-%d %H:%M:%S')}] BOUGHT {quantity} shares of {side} in market ({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')}) at ${entry_price:.2f}. Capital: ${self.capital:.2f}")
                    else:
                        print(f"[{current_timestamp.strftime('%Y-%m-%d %H:%M:%S')}] Insufficient capital to buy {quantity} shares of {side} in market ({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')}) (Cost: ${cost:.2f}, Capital: ${self.capital:.2f})")
        
        # After iterating through all timestamps, resolve any remaining open positions
        # Iterate over a copy of the list for final resolution
        final_resolved_positions_collector = {}
        for position in self.open_positions[:]: # Use a copy to allow modification
            market_id_tuple = position['market_id']
            resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp) # Use last current_timestamp or position['expiration']
            
            if market_id_tuple not in final_resolved_positions_collector:
                final_resolved_positions_collector[market_id_tuple] = []
            final_resolved_positions_collector[market_id_tuple].append(resolved_info)
            self.open_positions.remove(position) # Remove from original list

        for market_id_tuple, resolutions_data in final_resolved_positions_collector.items():
            self._print_market_summary(market_id_tuple, resolutions_data)
            
    def generate_report(self):
        print("\n--- Backtest Report ---")
        print(f"Initial Capital: ${self.initial_capital:.2f}")
        print(f"Final Capital:   ${self.capital:.2f}")
        
        total_pnl = self.capital - self.initial_capital
        print(f"Total PnL:       ${total_pnl:.2f}")
        
        buy_trades = [t for t in self.transactions if t['Type'] == 'Buy']
        resolution_trades = [t for t in self.transactions if t['Type'] == 'Resolution']
        
        print(f"Number of Buy Trades: {len(buy_trades)}")
        print(f"Number of Resolutions: {len(resolution_trades)}")

        winning_trades_count = 0
        losing_trades_count = 0
        for t in resolution_trades:
            if t['PnL'] > 0:
                winning_trades_count += 1
            else: # PnL <= 0, includes exact 0 and negative PnL. "Neither" implies loss of investment.
                losing_trades_count += 1
        
        print(f"Number of Winning Trades: {winning_trades_count}")
        print(f"Number of Losing Trades: {losing_trades_count}")

        # Optional: Print transaction history
        # print("\n--- Transaction History ---")
        # for t in self.transactions:
        #     print(t)


if __name__ == "__main__":
    # The user has indicated that data_logger.py is running in a separate process
    # and market_data.csv already contains data.
    # Therefore, we skip automatic data generation.


    backtester = Backtester(initial_capital=INITIAL_CAPITAL)
    
    try:
        backtester.load_data(DATA_FILE)
    except FileNotFoundError as e:
        print(e)
        exit()

    strategy = DerivativeMovingAverageStrategy() # Use the new strategy
    backtester.run_strategy(strategy)
    backtester.generate_report()

    # Clean up generated data file (optional)
    # os.remove(DATA_FILE)
    # print(f"Removed {DATA_FILE}")