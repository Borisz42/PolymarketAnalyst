import pandas as pd
import datetime
import os
from collections import deque
from decimal import Decimal

DATA_FILE = "market_data.csv"

# Global Configuration Variables
INITIAL_CAPITAL = 1000.0

class RebalancingStrategy:
    def __init__(self):
        # Parameters from plan
        self.SAFETY_MARGIN_M = 0.98
        self.MAX_TRADE_SIZE = 500
        self.MIN_BALANCE_QTY = 1
        
        # Risk management parameters (from risk_engine.py)
        self.MAX_UNHEDGED_DELTA = 50  # Maximum position imbalance
        self.MIN_LIQUIDITY_MULTIPLIER = 3.0  # Opposite side must have 3x liquidity
        self.STOP_LOSS_PERCENT = 2.0  # Stop loss at 2% loss
        
        # Portfolio state per market
        self.portfolio_state = {}  # key: market_id, value: {'qty_yes': int, 'qty_no': int, 'cost_yes': float, 'cost_no': float}

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0}
        return self.portfolio_state[market_id]

    def calculate_state(self, portfolio):
        """
        Calculate current position state (from accumulator.py logic).
        Returns dict with avg_yes, avg_no, pair_cost, delta, locked_profit.
        """
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']
        
        avg_yes = Decimal(str(cost_yes / qty_yes)) if qty_yes > 0 else Decimal('0')
        avg_no = Decimal(str(cost_no / qty_no)) if qty_no > 0 else Decimal('0')
        
        pair_cost = avg_yes + avg_no
        delta = qty_yes - qty_no
        
        # Calculate locked profit (from accumulator.py)
        paired_qty = min(qty_yes, qty_no)
        locked_profit = Decimal('0')
        
        if paired_qty > 0 and pair_cost < Decimal('1.00'):
            locked_profit = Decimal(str(paired_qty)) * (Decimal('1.00') - pair_cost)
        
        return {
            'avg_yes': float(avg_yes),
            'avg_no': float(avg_no),
            'pair_cost': float(pair_cost),
            'delta': delta,
            'locked_profit': float(locked_profit)
        }

    def check_liquidity_constraint(self, market_data_point, target_side, qty_to_buy):
        """
        Check if there's sufficient liquidity on the opposite side (from accumulator.py).
        Returns True if liquidity constraint is met.
        """
        opposite_side = 'Down' if target_side == 'Up' else 'Up'
        required_liquidity = qty_to_buy * self.MIN_LIQUIDITY_MULTIPLIER
        
        # Get available liquidity from order book
        if opposite_side == 'Up':
            available_liquidity = market_data_point.get('UpAskLiquidity', 0)
        else:
            available_liquidity = market_data_point.get('DownAskLiquidity', 0)
        
        return available_liquidity >= required_liquidity

    def check_delta_constraint(self, portfolio, target_side, qty_to_buy):
        """
        Check if trade would violate delta constraint (from risk_engine.py).
        Returns True if delta constraint is met.
        """
        current_delta = portfolio['qty_yes'] - portfolio['qty_no']
        
        if target_side == 'Up':
            new_delta = current_delta + qty_to_buy
        else:
            new_delta = current_delta - qty_to_buy
        
        return abs(new_delta) <= self.MAX_UNHEDGED_DELTA

    def check_safety_margin(self, portfolio, target_side, qty_to_buy, price):
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']

        avg_p_yes = cost_yes / qty_yes if qty_yes > 0 else 0
        avg_p_no = cost_no / qty_no if qty_no > 0 else 0
        
        new_combined_avg_p = -1

        if target_side == 'Up':  # 'Up' is YES
            new_cost_yes = cost_yes + qty_to_buy * price
            new_qty_yes = qty_yes + qty_to_buy
            if new_qty_yes == 0: return False
            new_avg_p_yes = new_cost_yes / new_qty_yes
            new_combined_avg_p = new_avg_p_yes + avg_p_no
        elif target_side == 'Down':  # 'Down' is NO
            new_cost_no = cost_no + qty_to_buy * price
            new_qty_no = qty_no + qty_to_buy
            if new_qty_no == 0: return False
            new_avg_p_no = new_cost_no / new_qty_no
            new_combined_avg_p = avg_p_yes + new_avg_p_no
        else:
            return False

        return new_combined_avg_p < self.SAFETY_MARGIN_M

    def decide(self, market_data_point, current_capital):
        market_id = (market_data_point['TargetTime'], market_data_point['Expiration'])
        portfolio = self._get_or_init_portfolio(market_id)

        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']

        # --- LOGIC FOR BALANCED PORTFOLIO (Increase Position) ---
        if qty_yes == qty_no:
            if qty_yes >= self.MAX_TRADE_SIZE:
                return None

            # Use best ask prices from order book data
            price_yes = market_data_point.get('UpAsk', 0)
            price_no = market_data_point.get('DownAsk', 0)

            # Only increase position if buying a pair is profitable
            if price_yes > 0 and price_no > 0 and (price_yes + price_no < self.SAFETY_MARGIN_M):
                side_to_buy = 'Up'
                price_to_buy = price_yes
                
                # Determine the max quantity we can possibly add
                qty_to_try = self.MAX_TRADE_SIZE - qty_yes
                
                # Search for the largest, safe, and affordable quantity to buy
                while qty_to_try > 0:
                    cost = qty_to_try * price_to_buy
                    if cost > current_capital:
                        qty_to_try -= 1
                        continue

                    # Check all constraints
                    if not self.check_delta_constraint(portfolio, side_to_buy, qty_to_try):
                        qty_to_try -= 1
                        continue
                    
                    if not self.check_liquidity_constraint(market_data_point, side_to_buy, qty_to_try):
                        qty_to_try -= 1
                        continue

                    if self.check_safety_margin(portfolio, side_to_buy, qty_to_try, price_to_buy):
                        # Found the optimal amount, return it
                        return (side_to_buy, qty_to_try, price_to_buy)

                    qty_to_try -= 1
            
            return None # Conditions not met to increase position

        # --- LOGIC FOR UNBALANCED PORTFOLIO (Rebalancing from equalizer.py) ---
        quantity_delta = abs(qty_yes - qty_no)

        if quantity_delta < self.MIN_BALANCE_QTY:
            return None 

        price_yes = market_data_point.get('UpAsk', 0)
        price_no = market_data_point.get('DownAsk', 0)

        target_side = None
        target_price = 0.0

        if qty_yes > qty_no:
            target_side = 'Down'
            target_price = price_no
        else: # qty_no > qty_yes
            target_side = 'Up'
            target_price = price_yes
        
        if target_price <= 0:
            return None

        qty_to_buy = int(min(quantity_delta, self.MAX_TRADE_SIZE))

        while qty_to_buy > 0:
            cost = qty_to_buy * target_price
            if cost > current_capital:
                qty_to_buy -= 1
                continue

            # Check all constraints
            if not self.check_delta_constraint(portfolio, target_side, qty_to_buy):
                qty_to_buy -= 1
                continue
            
            if not self.check_liquidity_constraint(market_data_point, target_side, qty_to_buy):
                qty_to_buy -= 1
                continue

            if self.check_safety_margin(portfolio, target_side, qty_to_buy, target_price):
                return (target_side, qty_to_buy, target_price)

            qty_to_buy -= 1

        return None

    def update_portfolio(self, market_id, side, quantity, price):
        portfolio = self._get_or_init_portfolio(market_id)
        cost = quantity * price
        if side == 'Up':
            portfolio['qty_yes'] += quantity
            portfolio['cost_yes'] += cost
        elif side == 'Down':
            portfolio['qty_no'] += quantity
            portfolio['cost_no'] += cost

class Backtester:
    def __init__(self, initial_capital=INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.transactions = [] # List of (timestamp, type, market_id, side, quantity, price, value, PnL)
        self.open_positions = [] # Changed to a list to allow multiple open positions per market
        self.market_data = pd.DataFrame()
        self.market_history = {} # Stores historical data grouped by market for resolution
        self.pending_market_summaries = {} # Key: market_id_tuple, Value: list of resolved_position_info dictionaries
        
        # Risk tracking (from risk_engine.py)
        self.max_drawdown = 0.0
        self.peak_capital = initial_capital
        self.risk_events = []  # Track risk-related events

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        self.market_data = pd.read_csv(file_path)
        
        # Convert relevant columns to datetime objects
        self.market_data['Timestamp'] = pd.to_datetime(self.market_data['Timestamp']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        self.market_data['TargetTime'] = pd.to_datetime(self.market_data['TargetTime']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        self.market_data['Expiration'] = pd.to_datetime(self.market_data['Expiration']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        
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
        # Use mid prices to determine winner
        up_mid = last_dp.get('UpMid', last_dp.get('UpPrice', 0))
        down_mid = last_dp.get('DownMid', last_dp.get('DownPrice', 0))
        
        if up_mid == 0:  # If Up price is 0, then Up wins
            winning_side = 'Up'
        elif down_mid == 0: # If Down price is 0, then Down wins
            winning_side = 'Down'
        elif down_mid > up_mid:
            winning_side = 'Down'
        else:
            winning_side = 'Up' 
        
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
        print(f"Execution Stats:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Avg Trade Size: {avg_trade_size:.1f} shares")
        print(f"  Avg Time Between Trades: {avg_time_between_trades_str}")
        print("--------------------------------------------------")

    def _update_risk_metrics(self):
        """Update risk metrics including drawdown tracking."""
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        
        current_drawdown = (self.peak_capital - self.capital) / self.peak_capital if self.peak_capital > 0 else 0
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

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
            for index in sorted(positions_to_remove_indices, reverse=True):
                del self.open_positions[index]

            # Update risk metrics
            self._update_risk_metrics()

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
        
        print(f"Number of Buy Trades: {len(buy_trades)}")
        print(f"Number of Markets Traded: {num_markets_played}")
        print(f"Number of Markets Won: {num_markets_won}")
        print(f"Total Up Shares: {total_up_shares}")
        print(f"Total Down Shares: {total_down_shares}")
        print(f"Number of Winning Trades: {winning_trades_count}")
        print(f"Number of Losing Trades: {losing_trades_count}")
        
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
    backtester = Backtester(initial_capital=INITIAL_CAPITAL)
    
    try:
        backtester.load_data(DATA_FILE)
    except FileNotFoundError as e:
        print(e)
        exit()

    strategy = RebalancingStrategy()
    backtester.run_strategy(strategy)
    backtester.generate_report()
