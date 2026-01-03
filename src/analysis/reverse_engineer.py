
import pandas as pd
import argparse
import os
import logging
from decimal import Decimal, getcontext

# Set precision for Decimal calculations
getcontext().prec = 28

# --- Setup Logging ---
LOG_DIR = 'logs'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Summary logger
summary_logger = logging.getLogger('summary_logger')
summary_logger.setLevel(logging.INFO)
if summary_logger.hasHandlers():
    summary_logger.handlers.clear()
summary_handler = logging.FileHandler(os.path.join(LOG_DIR, 'reverse_engineering_summary.txt'), mode='w')
summary_formatter = logging.Formatter('%(asctime)s - %(message)s')
summary_handler.setFormatter(summary_formatter)
summary_logger.addHandler(summary_handler)
summary_logger.addHandler(logging.StreamHandler())

def analyze(market_data_path, user_data_path):
    """
    Analyzes user trades against market data to reverse engineer a strategy.
    """
    summary_logger.info(f"Starting analysis for market data: {market_data_path} and user data: {user_data_path}")

    # --- Load Data ---
    try:
        market_df = pd.read_csv(market_data_path, parse_dates=['Timestamp', 'TargetTime'])
        user_df = pd.read_csv(user_data_path, parse_dates=['timestamp', 'TargetTime'])
    except FileNotFoundError as e:
        summary_logger.error(f"Error loading data files: {e}")
        return

    # --- Preprocessing and Merging ---
    market_df.sort_values('Timestamp', inplace=True)
    user_df.sort_values('timestamp', inplace=True)

    merged_df = pd.merge_asof(
        user_df,
        market_df,
        left_on='timestamp',
        right_on='Timestamp',
        by='TargetTime',
        direction='backward'
    )
    merged_df.dropna(subset=['Timestamp'], inplace=True)
    summary_logger.info(f"Successfully merged {len(merged_df)} user trades with market data.")

    # --- Portfolio State Calculation ---
    merged_df['quantity_dec'] = merged_df['quantity'].apply(lambda x: Decimal(str(x)))
    merged_df['price_dec'] = merged_df['price'].apply(lambda x: Decimal(str(x)))
    merged_df['cost'] = merged_df['quantity_dec'] * merged_df['price_dec']
    merged_df['is_up'] = (merged_df['trade_side'] == 'Up')
    merged_df['is_down'] = (merged_df['trade_side'] == 'Down')
    grouped = merged_df.groupby('TargetTime')
    all_markets_df = []

    for name, group in grouped:
        group = group.copy()
        group['cum_qty_up'] = (group['quantity_dec'] * group['is_up']).cumsum()
        group['cum_cost_up'] = (group['cost'] * group['is_up']).cumsum()
        group['cum_qty_down'] = (group['quantity_dec'] * group['is_down']).cumsum()
        group['cum_cost_down'] = (group['cost'] * group['is_down']).cumsum()
        group['PortfolioQtyUp'] = group['cum_qty_up'].shift(1).fillna(Decimal('0'))
        group['PortfolioCostUp'] = group['cum_cost_up'].shift(1).fillna(Decimal('0'))
        group['PortfolioQtyDown'] = group['cum_qty_down'].shift(1).fillna(Decimal('0'))
        group['PortfolioCostDown'] = group['cum_cost_down'].shift(1).fillna(Decimal('0'))
        all_markets_df.append(group)

    if not all_markets_df:
        summary_logger.warning("No data to process after grouping. Exiting.")
        return

    result_df = pd.concat(all_markets_df)

    result_df['PortfolioAvgPriceUp'] = result_df.apply(
        lambda row: row['PortfolioCostUp'] / row['PortfolioQtyUp'] if row['PortfolioQtyUp'] > 0 else Decimal('0'),
        axis=1
    )
    result_df['PortfolioAvgPriceDown'] = result_df.apply(
        lambda row: row['PortfolioCostDown'] / row['PortfolioQtyDown'] if row['PortfolioQtyDown'] > 0 else Decimal('0'),
        axis=1
    )
    result_df['PortfolioUnhedgedDelta'] = result_df['PortfolioQtyUp'] - result_df['PortfolioQtyDown']

    # --- Finalize and Log CSV ---
    result_df.rename(columns={
        'TargetTime': 'MarketTargetTime',
        'timestamp': 'TradeTimestamp',
        'trade_side': 'TradeSide',
        'quantity': 'TradeQuantity',
        'price': 'TradePrice',
        'Timestamp': 'MarketDataTimestamp'
    }, inplace=True)

    market_data_columns = [col for col in market_df.columns if col not in ['Timestamp', 'TargetTime']]
    portfolio_columns = ['PortfolioQtyUp', 'PortfolioAvgPriceUp', 'PortfolioQtyDown', 'PortfolioAvgPriceDown', 'PortfolioUnhedgedDelta']
    trade_columns = ['TradeTimestamp', 'TradeSide', 'TradeQuantity', 'TradePrice']

    final_columns = ['MarketTargetTime'] + trade_columns + ['MarketDataTimestamp'] + portfolio_columns + market_data_columns

    # Use .copy() to avoid SettingWithCopyWarning
    output_df = result_df[final_columns].copy()

    # Convert Decimal columns to float for CSV writing
    for col in portfolio_columns:
        output_df[col] = output_df[col].astype(float)

    # Use a direct to_csv call for clarity and performance
    output_csv_path = os.path.join(LOG_DIR, 'reverse_engineering_log.csv')
    output_df.to_csv(output_csv_path, index=False, lineterminator='\n')

    summary_logger.info(f"Analysis complete. Logged {len(output_df)} trades to {output_csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reverse engineer a trading strategy by analyzing historical data.")
    parser.add_argument("--market-data", required=True, help="Path to the market data CSV file.")
    parser.add_argument("--user-data", required=True, help="Path to the user trades data CSV file.")
    args = parser.parse_args()

    analyze(args.market_data, args.user_data)
