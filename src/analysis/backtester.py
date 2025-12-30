import src.config as config
import pandas as pd
import pandas_ta as ta
import datetime
import os
import time
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
        self.transactions = []
        self.open_positions = []
        self.market_data = pd.DataFrame()
        self.market_history = {}
        self.pending_market_summaries = {}
        
        # Risk tracking
        self.max_drawdown = 0.0
        self.portfolio_history = []
        self.risk_events = []

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data file not found at {file_path}")
        
        date_columns = ['Timestamp', 'TargetTime', 'Expiration']
        self.market_data = pd.read_csv(file_path, parse_dates=date_columns)

        for col in date_columns:
            self.market_data[col] = self.market_data[col].dt.tz_localize('UTC')
        
        self.market_data.sort_values(by='Timestamp', inplace=True)

        # Calculate Volatility and RSI for each market
        self.market_data['Volatility'] = self.market_data.groupby(['TargetTime', 'Expiration'])['UpMid'].transform(lambda x: x.pct_change().rolling(window=14).std())
        self.market_data['RSI'] = self.market_data.groupby(['TargetTime', 'Expiration'])['UpMid'].transform(lambda x: ta.rsi(x, length=14))

        grouped_by_market = self.market_data.groupby(['TargetTime', 'Expiration'])
        self.market_history = {market_id: group for market_id, group in grouped_by_market}

        print(f"Loaded {len(self.market_data)} data points from {file_path}")

    def _resolve_single_position(self, market_id_tuple, position, current_timestamp):
        if market_id_tuple not in self.market_history:
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

        # Calculate MAE
        trade_data = market_specific_data[
            (market_specific_data['Timestamp'] >= position['timestamp']) &
            (market_specific_data['Timestamp'] <= current_timestamp)
        ]

        mae = 0
        if not trade_data.empty:
            if position['side'] == 'Up':
                worst_price = trade_data['UpMid'].min()
                mae = position['entry_price'] - worst_price
            else:
                worst_price = trade_data['DownMid'].max()
                mae = worst_price - position['entry_price']

        time_in_trade = (current_timestamp - position['timestamp']).total_seconds()

        self.transactions.append({
            'Timestamp': current_timestamp,
            'Type': 'Resolution',
            'MarketID': market_id_tuple,
            'Side': position['side'],
            'Quantity': position['quantity'],
            'EntryPrice': position['entry_price'],
            'Value': position['quantity'] * position['entry_price'],
            'PnL': pnl,
            'WinningSide': winning_side,
            'MAE': mae,
            'TimeInTrade': time_in_trade
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
        market_id_formatted = f"({market_id_tuple[0].strftime('%Y-%m-%d %H:%M:%S')}, {market_id_tuple[1].strftime('%Y-%m-%d %H:%M:%S')})"
        total_market_pnl = sum(res['pnl'] for res in resolved_positions_data)
        print(f"\\n--- Market Resolution Summary for {market_id_formatted} ---")
        print(f"Total PnL for market: ${total_market_pnl:.2f}")

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
        if self.slippage_seconds <= 0:
            return entry_price
        slippage_timestamp = current_timestamp + pd.Timedelta(seconds=self.slippage_seconds)
        future_data = self.market_data[
            (self.market_data['Timestamp'] >= slippage_timestamp) &
            (self.market_data['TargetTime'] == market_id_tuple[0]) &
            (self.market_data['Expiration'] == market_id_tuple[1])
        ]
        if not future_data.empty:
            slippage_row = future_data.iloc[0]
            if side == 'Up':
                slipped_price = slippage_row.get('UpAsk', entry_price)
            else: # side == 'Down'
                slipped_price = slippage_row.get('DownAsk', entry_price)
            if slipped_price > 0:
                return slipped_price
        return entry_price

    def run_strategy(self, strategy_instance):
        current_timestamp = None
        unique_timestamps = self.market_data['Timestamp'].unique()
        for ts_np in unique_timestamps:
            current_timestamp = pd.to_datetime(ts_np)
            
            positions_to_remove = []
            for position in self.open_positions:
                if current_timestamp >= position['expiration']:
                    market_id_tuple = position['market_id']
                    resolved_info = self._resolve_single_position(market_id_tuple, position, current_timestamp)
                    
                    if market_id_tuple not in self.pending_market_summaries:
                        self.pending_market_summaries[market_id_tuple] = []
                    self.pending_market_summaries[market_id_tuple].append(resolved_info)
                    
                    positions_to_remove.append(position)
            
            if positions_to_remove:
                self.open_positions = [p for p in self.open_positions if p not in positions_to_remove]
                self.portfolio_history.append((current_timestamp, self.capital))

            current_data_points = self.market_data[self.market_data['Timestamp'] == current_timestamp]
            for _, row in current_data_points.iterrows():
                market_id_tuple = (row['TargetTime'], row['Expiration'])
                trade_decision = strategy_instance.decide(row, self.capital)
                
                if trade_decision:
                    if current_timestamp >= row['Expiration']:
                        continue

                    side, quantity, entry_price, _ = trade_decision
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
                            'expiration': row['Expiration'],
                            'timestamp': current_timestamp
                        })
                        self.transactions.append({
                            'Timestamp': current_timestamp,
                            'Type': 'Buy',
                            'MarketID': market_id_tuple,
                            'Side': side,
                            'Quantity': quantity,
                            'EntryPrice': entry_price,
                            'Value': cost,
                            'PnL': -cost,
                            'Volatility': row['Volatility'],
                            'RSI': row['RSI']
                        })
        
        # Resolve any remaining open positions
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
        print("\\n--- Backtest Report ---")
        print(f"Initial Capital: ${self.initial_capital:.2f}")
        print(f"Final Capital:   ${self.capital:.2f}")
        total_pnl = self.capital - self.initial_capital
        roi = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        print(f"Total PnL:       ${total_pnl:.2f} ({roi:+.2f}%)")
        self.max_drawdown = self._calculate_max_drawdown()
        print(f"Max Drawdown:    {self.max_drawdown * 100:.2f}%")
