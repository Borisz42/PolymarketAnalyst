# Polymarket BTC Monitor

A Python-based tool to monitor **Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets**. Features real-time data logging and an interactive dashboard for analyzing market behavior and identifying potential opportunities.

## Features
Recent updates have brought significant improvements to both the backtesting capabilities and the data logging service, enhancing overall analysis and strategy development.

### Data Collection
- **Automated Market Detection**: Automatically finds the currently active 15-minute BTC market
- **Real-time Data Logging**: Continuously fetches and logs market data.
- **CSV Storage**: Historical data stored in date-stamped CSV files in the `data/` directory (e.g., `data/market_data_YYYYMMDD.csv`).
- **Order Book Depth**: Captures comprehensive order book data including bid/ask prices, spreads, and liquidity

### Market Data Format

The enhanced data logger captures comprehensive order book data in date-stamped CSV files (e.g., `data/market_data_YYYYMMDD.csv`) with 14 columns:

#### Column Descriptions

| Column | Description | Example | Notes |
|--------|-------------|---------|-------|
| `Timestamp` | When the data was logged | `2025-12-25 17:00:21` | UTC |
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
| `DownSpread` | Bid-ask spread for DOWN | `0.01` | DownAsk - Bid |
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

### Price Analysis Script
- **`src/analysis/analyze_prices.py`**: A standalone script to perform a detailed analysis of a given day's market data.
- **Resolution Analysis**: Determines and logs which markets resolved "Up" or "Down" based on their final prices.
- **Summary Statistics**: Provides detailed metrics for prices and liquidity across all markets for the analyzed day.
- **Usage**: To run the script for the date specified in your config, use the command:
  ```bash
  python -m src.analysis.analyze_prices
  ```

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

An advanced and modular backtesting script (`src/analysis/backtester.py`) that simulates trading strategies on historical Polymarket data with comprehensive risk management and constraint checking.

The backtester is decoupled from the trading strategies, allowing for easy testing of different algorithms. Strategies are located in the `src/analysis/strategies/` directory and inherit from a base `Strategy` class.

#### Included Strategies

1.  **RebalancingStrategy**: A sophisticated strategy that focuses on accumulating paired positions (buying both UP and DOWN) when profitable opportunities arise, while maintaining balanced positions.
2.  **PredictionStrategy**: A simpler, event-driven strategy that trades based on sharp price movements and liquidity imbalances.

#### Advanced Features

*   **Slippage Simulation**: The backtester can simulate slippage by using the price from a few seconds after the trade decision. This can be configured in the `backtester.py` script.
*   **Comprehensive Reporting**: The backtester provides detailed reports including PnL, ROI, max drawdown, and trade statistics.

#### Configuration

Adjust strategy and analysis parameters in `src/config.py`:

```python
# Set to 0 to use today's date for analysis, or a yyyymmdd integer (e.g., 20231225) for a specific day.
ANALYSIS_DATE = 0
INITIAL_CAPITAL = 1000.0              # Starting capital
# ... other parameters
```
To run the dashboard or backtesters on a specific day's data, simply change the `ANALYSIS_DATE` variable in the config file. The `data_logger.py` will always write to the current day's file, regardless of this setting.

## How to Run

### Step 1: Start the Data Logger
The data logger runs in the background to collect market data. It will always write to a file with the current date.

Open a terminal and run from the root directory:
```bash
python -m src.data_collection.data_logger
```

### Step 2: Configure Your Analysis (Optional)
Before running the dashboard or backtesters, you can choose which day's data to analyze by editing `src/config.py`:
-   Leave `ANALYSIS_DATE = 0` to automatically find and use the **latest available** data file.
-   Set `ANALYSIS_DATE = 20231225` (or any other `yyyymmdd` integer) to analyze a specific day's data.

### Step 3: Run the Dashboard or Backtesters
Open a **new** terminal for each command.

**To Launch the Dashboard:**
```bash
streamlit run src/dashboard/dashboard.py
```

**To Run the Rebalancing Strategy:**
```bash
python -m src.analysis.backtester
```

**To Run the Prediction Strategy:**
```bash
python -m src.analysis.prediction_backtester
```

### Dashboard Tips
- Watch the **Pair Cost chart** (top panel) - green areas show trading opportunities
- Use **Zoom Last 15m** to track the most recent market activity
- Monitor the **Opportunity Indicator** for real-time trading signals
- Check **Liquidity Depth** before planning large trades
- Hover over charts to see exact values with the unified crosshair
- All charts are linked - zooming one automatically zooms all others

## How It Works

The system identifies the **Active Market** by find a 15-minute interval that has started but not yet expired:

- **Start Time**: Beginning of the 15-minute candle
- **Expiration**: End of the 15-minute candle  
- **Contract Prices**: Live "Yes" (Up) and "No" (Down) prices from Polymarket's CLOB

Contracts pay out based on whether the price at **Expiration** is higher ("Up") or lower ("Down") than the **Strike Price**.

## Project Structure

```
PolymarketAnalyst/
├── data/
│   └── market_data_YYYYMMDD.csv # Historical data (auto-generated, date-stamped)
├── src/
│   ├── analysis/
│   │   ├── strategies/
│   │   │   ├── __init__.py
│   │   │   ├── base_strategy.py
│   │   │   ├── rebalancing_strategy.py
│   │   │   └── prediction_strategy.py
│   │   ├── __init__.py
│   │   ├── analyze_prices.py
│   │   ├── backtester.py
│   │   └── prediction_backtester.py
│   ├── config.py                # Centralized configuration file
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
