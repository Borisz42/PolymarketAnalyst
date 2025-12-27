# Polymarket BTC Monitor

A Python-based tool to monitor **Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets**. Features real-time data logging and an interactive dashboard for analyzing market behavior and identifying potential opportunities.

## Features
Recent updates have brought significant improvements to both the backtesting capabilities and the data logging service, enhancing overall analysis and strategy development.

### Data Collection
- **Automated Market Detection**: Automatically finds the currently active 15-minute BTC market
- **Real-time Data Logging**: Continuously fetches and logs market data.
- **CSV Storage**: Historical data stored in `data/market_data.csv` for analysis, with optional daily rotation.
- **Order Book Depth**: Captures comprehensive order book data including bid/ask prices, spreads, and liquidity

### Market Data Format

The enhanced data logger captures comprehensive order book data in `data/market_data.csv` with 14 columns:

#### Column Descriptions

| Column | Description | Example | Notes |
|--------|-------------|---------|-------|
| `Timestamp` | When the data was logged | `2025-12-25 17:00:21` | Local time |
| `TargetTime` | Market's target time (start of 15-min window) | `2025-12-25 16:00:00` | UTC |
| `Expiration` | Market expiration time | `2025-12-25 16:15:00` | UTC |
| `UpBid` | Best bid price for UP contracts | `0.57` | Highest price buyers offer |
| `UpAsk` | Best ask price for UP contracts | `0.58` | Lowest price sellers offer |
| `UpMid` | Mid-market price for UP | `0.575` | (UpBid + UpAsk) / 2 |
| `UpSpread` | Bid-ask spread for UP | `0.01` | UpAsk - UpBid |
| `UpBidLiquidity` | Total UP bid liquidity (top 5 levels) | `1224.11` | Shares available to buy |
| `UpAskLiquidity` | Total UP ask liquidity (top 5 levels) | `1357.94` | Shares available to sell |
| `DownBid` | Best bid price for DOWN contracts | `0.4` | Highest price buyers offer |
| `DownAsk` | Best ask price for DOWN contracts | `0.41` | Lowest price sellers offer |
| `DownMid` | Mid-market price for DOWN | `0.405` | (DownBid + DownAsk) / 2 |
| `DownSpread` | Bid-ask spread for DOWN | `0.01` | DownAsk - DownBid |
| `DownBidLiquidity` | Total DOWN bid liquidity (top 5 levels) | `1092.92` | Shares available to buy |
| `DownAskLiquidity` | Total DOWN ask liquidity (top 5 levels) | `1260.11` | Shares available to sell |

#### Understanding the Data

**Prices:**
- All prices are in USD and represent the cost per share
- UP and DOWN prices should theoretically sum to ~$1.00 (e.g., 0.58 + 0.41 = 0.99)
- The difference from $1.00 represents the market's profit margin

**Spreads:**
- Typically 0.01 (1 cent) but can vary from 0.01 to 0.03
- UpSpread and DownSpread are usually similar but can differ based on market conditions
- Tighter spreads indicate more liquid markets
- Example: Row 3 shows UpSpread=0.01 but DownSpread=0.03 (different liquidity on each side)

**Liquidity:**
- Measured in number of shares available at top 5 price levels
- Higher liquidity = easier to enter/exit positions without slippage
- Liquidity can vary significantly between UP and DOWN sides
- Example: Row 7 shows UpAskLiquidity=2477.96 but DownAskLiquidity=924.36

**Why Both UpSpread and DownSpread?**
While spreads are often similar (both 0.01), they can differ when:
- One side has more liquidity than the other
- Market makers adjust pricing based on directional flow
- Volatility affects one side more than the other
Keeping both provides more accurate data for backtesting and analysis.

### Interactive Dashboard
- **Live Auto-Refresh**: Automatically updates periodically (every second) to ensure the latest data is displayed.
- **Advanced Visualization**:
  - Probability trends for Up/Down contracts
  - Market transition indicators (vertical lines)
  - Data point markers for clarity
  - Gaps for zero/missing values
- **Interactive Controls**:
  - Manual refresh button
  - Auto-refresh toggle
  - "Reset Zoom" - view all historical data
  - "Zoom Last 15m" - focus on recent activity (follows new data)
  - Scroll zoom and range slider

### Backtester

An advanced backtesting script (`src/analysis/backtester.py`) that simulates trading strategies on historical Polymarket data with comprehensive risk management and constraint checking.

#### Strategy: RebalancingStrategy

The backtester employs a sophisticated **RebalancingStrategy** that focuses on accumulating paired positions (buying both UP and DOWN) when profitable opportunities arise, while maintaining balanced positions.

**Core Logic:**
- **Paired Position Accumulation**: Buys both UP and DOWN shares when the combined cost is below the safety margin (0.98)
- **Position Rebalancing**: Automatically rebalances when positions become imbalanced
- **Locked Profit Tracking**: Calculates guaranteed profit from paired positions

**Advanced Features:**

1. **State Calculation** (from accumulator.py):
   - Tracks average entry prices for UP and DOWN positions
   - Calculates pair cost (avg_yes + avg_no)
   - Monitors position delta (imbalance between UP and DOWN)
   - Computes locked profit from paired positions

2. **Constraint Checking**:
   - **Liquidity Constraint**: Ensures opposite side has 3x the required liquidity before trading
   - **Delta Constraint**: Prevents position imbalance from exceeding 50 shares
   - **Safety Margin**: Ensures pair cost stays below 0.98

3. **Risk Management** (from risk_engine.py):
   - Tracks maximum drawdown throughout the backtest
   - Monitors peak capital and current capital
   - Logs risk events (insufficient capital, constraint violations)
   - Calculates unrealized P&L using mid-market prices

#### Configuration

Adjust strategy parameters in `src/analysis/backtester.py`:

```python
INITIAL_CAPITAL = 1000.0              # Starting capital
SAFETY_MARGIN_M = 0.98                # Max pair cost (0.98 = 2% profit margin)
MAX_TRADE_SIZE = 500                  # Maximum position size per market
MIN_BALANCE_QTY = 1                   # Minimum imbalance to trigger rebalancing
MAX_UNHEDGED_DELTA = 50               # Maximum position imbalance allowed
MIN_LIQUIDITY_MULTIPLIER = 3.0        # Required liquidity multiplier (3x)
STOP_LOSS_PERCENT = 2.0               # Stop loss threshold (for future use)
```

#### Enhanced Reporting

The backtester provides comprehensive reports including:
- **Performance Metrics**: Total P&L, ROI%, final capital
- **Risk Metrics**: Maximum drawdown percentage
- **Trade Statistics**: Win rate, number of markets traded
- **Position Analysis**: Balanced vs imbalanced markets
- **Risk Events**: Constraint violations, capital shortfalls

**Example Output:**
```
--- Backtest Report ---
Initial Capital: $1000.00
Final Capital:   $1050.00
Total PnL:       $50.00 (+5.00%)
Max Drawdown:    2.34%
Number of Markets Won: 12
--- Risk Events ---
Total Risk Events: 3
  Insufficient Capital: 2
  Liquidity Constraint: 1
```

#### Market Resolution

Markets are resolved using mid-market prices for fairness:
- Uses `UpMid` and `DownMid` from the enhanced CSV data
- Winning side determined by which price is closer to 0
- Each winning share pays out $1.00


#### How to Run Data fetcher and Dashboard

**Step 1: Start the Data Logger**
Open a terminal and run from the root directory:
```bash
python -m src.data_collection.data_logger
```
This will continuously fetch market data every 10 seconds and save it to `data/market_data.csv`.

**Step 2: Launch the Dashboard**
Open a **new** terminal and run:
```bash
streamlit run src/dashboard/dashboard.py
```
The dashboard will open in your browser at `http://localhost:8501`.

#### How to Run backtester

Ensure `data/market_data.csv` contains historical data (generated by running the data logger for a sufficient period). Then, execute the backtester:
```bash
python -m src.analysis.backtester
```
The script will output a report including final capital, total P&L, and the number of winning and losing trades.

### Slippage Backtester
A new script (`src/analysis/slipp_backtester.py`) has been introduced to backtest strategies considering slippage. This backtester focuses on identifying and exploiting price discrepancies between different markets or contracts within Polymarket.

#### How to Run Slippage Backtester
Ensure `data/market_data.csv` contains historical data. Then, execute the slippage backtester:
```bash
python -m src.analysis.slipp_backtester
```
This script will analyze historical data for arbitrage opportunities and report on potential profits.

### Dashboard Tips
- Watch the **Pair Cost chart** (top panel) - green areas show trading opportunities
- Use **Zoom Last 15m** to track the most recent market activity
- Monitor the **Opportunity Indicator** for real-time trading signals
- Check **Liquidity Depth** before planning large trades
- Hover over charts to see exact values with the unified crosshair
- All charts are linked - zooming one automatically zooms all others

## How It Works

The system identifies the **Active Market** by finding the 15-minute interval that has started but not yet expired:

- **Start Time**: Beginning of the 15-minute candle
- **Expiration**: End of the 15-minute candle  
- **Contract Prices**: Live "Yes" (Up) and "No" (Down) prices from Polymarket's CLOB

Contracts pay out based on whether the price at **Expiration** is higher ("Up") or lower ("Down") than the **Strike Price**.

## Project Structure

```
PolymarketAnalyst/
├── data/
│   └── market_data.csv          # Historical data (auto-generated)
├── src/
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── analyze_prices.py
│   │   ├── backtester.py
│   │   └── slipp_backtester.py
│   ├── data_collection/
│   │   ├── __init__.py
│   │   ├── data_logger.py
│   │   ├── fetch_current_polymarket.py
│   │   ├── find_new_market.py
│   │   └── get_current_markets.py
│   ├── dashboard/
│   │   ├── __init__.py
│   │   └── dashboard.py
│   └── __init__.py
├── .gitignore                   # Specifies intentionally untracked files to ignore
└── README.md                    # This file
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

MIT License - feel free to use this project for your own analysis and trading strategies.

## Disclaimer

This tool is for informational and educational purposes only. Trading cryptocurrencies and prediction markets involves risk. Always do your own research and never invest more than you can afford to lose.
