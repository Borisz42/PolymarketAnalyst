import pandas as pd
import datetime
import os
from collections import deque

DATA_FILE = "market_data.csv"

# Global Configuration Variables
INITIAL_CAPITAL = 1000.0

class RebalancingStrategy:
    def __init__(self):
        # Parameters from plan
        self.SAFETY_MARGIN_M = 0.99
        self.MAX_TRADE_SIZE = 500
        self.MIN_BALANCE_QTY = 10

        # Portfolio state per market
        self.portfolio_state = {}  # key: market_id, value: {'qty_yes': int, 'qty_no': int, 'cost_yes': float, 'cost_no': float}

    def _get_or_init_portfolio(self, market_id):
        if market_id not in self.portfolio_state:
            self.portfolio_state[market_id] = {'qty_yes': 0, 'qty_no': 0, 'cost_yes': 0.0, 'cost_no': 0.0}
        return self.portfolio_state[market_id]

    def check_safety_margin(self, portfolio, target_side, qty_to_buy, price):
        qty_yes = portfolio['qty_yes']
        qty_no = portfolio['qty_no']
        cost_yes = portfolio['cost_yes']
        cost_no = portfolio['cost_no']

        avg_p_yes = cost_yes / qty_yes if qty_yes > 0 else 0
        avg_p_no = cost_no / qty_no if qty_no > 0 else 0
        
        new_combined_avg_p = -1

        if target_side == 'Up':
            new_cost_yes = cost_yes + qty_to_buy * price
            new_qty_yes = qty_yes + qty_to_buy
            if new_qty_yes == 0: return False
            new_avg_p_yes = new_cost_yes / new_qty_yes
            new_combined_avg_p = new_avg_p_yes + avg_p_no
        elif target_side == 'Down':
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
        price_yes = market_data_point['UpPrice']
        price_no = market_data_point['DownPrice']

        # --- Priority 1: ARBITRAGE on a BALANCED portfolio ---
        if qty_yes == qty_no:
            is_arbitrage_opportunity = price_yes > 0 and price_no > 0 and (price_yes + price_no < self.SAFETY_MARGIN_M)
            if is_arbitrage_opportunity and qty_yes < self.MAX_TRADE_SIZE:
                cost_per_pair = price_yes + price_no
                max_qty_by_capital = int(current_capital / cost_per_pair) if cost_per_pair > 0 else 0
                max_qty_by_size = self.MAX_TRADE_SIZE - qty_yes
                qty_to_buy = min(max_qty_by_capital, max_qty_by_size)

                if qty_to_buy > 0:
                    return ('Arbitrage', qty_to_buy, price_yes, price_no)

        # --- Priority 2: REBALANCING ---
        quantity_delta = abs(qty_yes - qty_no)
        if quantity_delta < self.MIN_BALANCE_QTY:
            return None 

        target_side = 'Down' if qty_yes > qty_no else 'Up'
        target_price = price_no if target_side == 'Down' else price_yes
        
        if target_price <= 0:
            return None

        qty_to_buy = int(min(quantity_delta, self.MAX_TRADE_SIZE))
        while qty_to_buy > 0:
            cost = qty_to_buy * target_price
            if cost > current_capital:
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
        self.transactions = []
        self.open_positions = []
        self.market_data = pd.DataFrame()
        self.market_history = {}
        self.pending_market_summaries = {}

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        self.market_data = pd.read_csv(file_path)
        
        self.market_data['Timestamp'] = pd.to_datetime(self.market_data['Timestamp']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        self.market_data['TargetTime'] = pd.to_datetime(self.market_data['TargetTime']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        self.market_data['Expiration'] = pd.to_datetime(self.market_data['Expiration']).dt.tz_localize('UTC').dt.tz_convert('UTC')
        
        self.market_data.sort_values(by='Timestamp', inplace=True)

        for _, row in self.market_data.iterrows():
            market_id = (row['TargetTime'], row['Expiration'])
            if market_id not in self.market_history:
                self.market_history[market_id] = []
            self.market_history[market_id].append(row)

        print(f"Loaded {len(self.market_data)} data points from {file_path}")

    def _resolve_single_position(self, market_id_tuple, position, current_timestamp):
        if market_id_tuple not in self.market_history:
            return {'pnl': 0, 'winning_side': 'Error'} 

        market_specific_data = self.market_history[market_id_tuple]
        last_dp = market_specific_data[-1]

        winning_side = None
        if last_dp['UpPrice'] == 0:  # If Up price is 0, then Up wins
            winning_side = 'Up'
        elif last_dp['DownPrice'] == 0: # If Down price is 0, then Down wins
            winning_side = 'Down'
        elif last_dp['UpPrice'] > last_dp['DownPrice']:
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
            'Timestamp': current_timestamp, 'Type': 'Resolution', 'MarketID': market_id_tuple,
            'Side': position['side'], 'Quantity': position['quantity'], 'EntryPrice': position['entry_price'],
            'Value': position['quantity'] * position['entry_price'], 'PnL': pnl, 'WinningSide': winning_side
        })
        
        return {
            'market_id': market_id_tuple, 'side': position['side'], 'quantity': position['quantity'],
            'entry_price': position['entry_price'], 'pnl': pnl, 'winning_side': winning_side
        }

    def _print_market_summary(self, market_id_tuple, resolved_positions_data):
        market_id_formatted = f"({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')})"
        total_up_shares, total_up_cost, total_down_shares, total_down_cost, total_market_pnl = 0, 0.0, 0, 0.0, 0.0

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
            
            positions_to_remove_indices = []
            
            for i, position in enumerate(self.open_positions):
                if current_timestamp >= position['expiration']:
                    market_id_tuple = position['market_id']
                    resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
                    if market_id_tuple not in self.pending_market_summaries:
                        self.pending_market_summaries[market_id_tuple] = []
                    self.pending_market_summaries[market_id_tuple].append(resolved_info)
                    positions_to_remove_indices.append(i)
            
            for index in sorted(positions_to_remove_indices, reverse=True):
                del self.open_positions[index]

            current_data_points = self.market_data[self.market_data['Timestamp'] == current_timestamp]

            for _, row in current_data_points.iterrows():
                market_id_tuple = (row['TargetTime'], row['Expiration'])
                trade_decision = strategy_instance.decide(row, self.capital)
                
                if trade_decision:
                    market_id_formatted = f"({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')})"
                    
                    if len(trade_decision) == 4 and trade_decision[0] == 'Arbitrage':
                        _, quantity, up_price, down_price = trade_decision
                        cost = quantity * (up_price + down_price)

                        if self.capital >= cost:
                            portfolio = strategy_instance._get_or_init_portfolio(market_id_tuple)
                            print(f"[{current_timestamp}] STRATEGY: Executing Arbitrage Pair Trade in market {market_id_formatted}.")
                            print(f"  - Reason: Profitable pair price found ({up_price:.2f} + {down_price:.2f} = {up_price+down_price:.2f}) < {strategy_instance.SAFETY_MARGIN_M}.")
                            print(f"  - State: Portfolio=({portfolio['qty_yes']}, {portfolio['qty_no']}), Capital=${self.capital:.2f}")
                            print(f"  - Trade: BUY {quantity} pairs (Up at ${up_price:.2f}, Down at ${down_price:.2f})\n")

                            self.capital -= cost
                            if hasattr(strategy_instance, 'update_portfolio'):
                                strategy_instance.update_portfolio(market_id_tuple, 'Up', quantity, up_price)
                                strategy_instance.update_portfolio(market_id_tuple, 'Down', quantity, down_price)

                            self.open_positions.append({'market_id': market_id_tuple, 'side': 'Up', 'quantity': quantity, 'entry_price': up_price, 'expiration': row['Expiration']})
                            self.transactions.append({'Timestamp': current_timestamp, 'Type': 'Buy', 'MarketID': market_id_tuple, 'Side': 'Up', 'Quantity': quantity, 'EntryPrice': up_price, 'Value': quantity * up_price, 'PnL': -quantity * up_price})
                            
                            self.open_positions.append({'market_id': market_id_tuple, 'side': 'Down', 'quantity': quantity, 'entry_price': down_price, 'expiration': row['Expiration']})
                            self.transactions.append({'Timestamp': current_timestamp, 'Type': 'Buy', 'MarketID': market_id_tuple, 'Side': 'Down', 'Quantity': quantity, 'EntryPrice': down_price, 'Value': quantity * down_price, 'PnL': -quantity * down_price})

                    elif len(trade_decision) == 3:
                        side, quantity, entry_price = trade_decision
                        cost = quantity * entry_price

                        if self.capital >= cost:
                            portfolio = strategy_instance._get_or_init_portfolio(market_id_tuple)
                            quantity_delta = abs(portfolio['qty_yes'] - portfolio['qty_no'])
                            print(f"[{current_timestamp}] STRATEGY: Executing Rebalancing Trade in market {market_id_formatted}.")
                            print(f"  - Reason: Portfolio imbalanced by {quantity_delta} shares.")
                            print(f"  - State: Portfolio=({portfolio['qty_yes']}, {portfolio['qty_no']}), Capital=${self.capital:.2f}")
                            print(f"  - Trade: BUY {quantity} shares of '{side}' at ${entry_price:.2f}\n")

                            self.capital -= cost
                            if hasattr(strategy_instance, 'update_portfolio'):
                                strategy_instance.update_portfolio(market_id_tuple, side, quantity, entry_price)

                            self.open_positions.append({'market_id': market_id_tuple, 'side': side, 'quantity': quantity, 'entry_price': entry_price, 'expiration': row['Expiration']})
                            self.transactions.append({'Timestamp': current_timestamp, 'Type': 'Buy', 'MarketID': market_id_tuple, 'Side': side, 'Quantity': quantity, 'EntryPrice': entry_price, 'Value': cost, 'PnL': -cost})
        
        for position in self.open_positions[:]:
            market_id_tuple = position['market_id']
            resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
            if market_id_tuple not in self.pending_market_summaries:
                self.pending_market_summaries[market_id_tuple] = []
            self.pending_market_summaries[market_id_tuple].append(resolved_info)
            self.open_positions.remove(position)

        for market_id_tuple, resolutions_data in self.pending_market_summaries.items():
            self._print_market_summary(market_id_tuple, resolutions_data)
        self.pending_market_summaries.clear()

    def generate_report(self):
        print("\n--- Backtest Report ---")
        print(f"Initial Capital: ${self.initial_capital:.2f}")
        print(f"Final Capital:   ${self.capital:.2f}")
        
        total_pnl = self.capital - self.initial_capital
        print(f"Total PnL:       ${total_pnl:.2f}")
        
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