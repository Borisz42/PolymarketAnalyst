# Polymarket BTC Monitor

A Python-based tool to monitor **Polymarket's 15-minute Bitcoin (BTC) Up/Down prediction markets**. Features real-time data logging and an interactive dashboard for analyzing market behavior and identifying potential opportunities.

## Features

### Data Collection
- **Automated Market Detection**: Automatically finds the currently active 15-minute BTC market
- **Real-time Data Logging**: Continuously fetches and logs market data.
- **Configurable**: The dashboard's data file path is now determined automatically and hardcoded.
- **Robust Error Handling**: Gracefully handles incomplete data and API failures with a retry mechanism.
- **CSV Storage**: Historical data stored in `market_data.csv` for analysis, with optional daily rotation.
- **Data Validation**: Validates price ranges and detects anomalies.
- **Market Transition Handling**: Detects market transitions and adds a separator to the CSV file.
- **Monitoring & Statistics**: Tracks and displays statistics such as uptime, success rate, and average logging latency.

### Interactive Dashboard
- **Live Auto-Refresh**: Automatically updates periodically (every second) to ensure the latest data is displayed.
- **Dual Chart View**: Synchronized price and probability charts with linked zoom
- **Advanced Visualization**:
  - Price history vs. strike price comparison
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
  - Unified hover mode with crosshair across both charts
- **Real-time Metrics**: Current strike price, BTC price, and contract costs

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Borisz42/PolymarketAnalyst.git
   cd PolymarketAnalyst
   ```

2. Install dependencies:
   ```bash
   pip install requests pytz streamlit pandas plotly
   ```

## Usage

### Quick Start: Console Monitor
Run the simple console bot to see current market data:
```bash
python arbitrage_bot.py
```

### Full Dashboard Experience

**Step 1: Start the Data Logger**
Open a terminal and run:
```bash
python data_logger.py
```
This will continuously fetch market data every 10 seconds and save it to `market_data.csv`.

**Step 2: Launch the Dashboard**
Open a **new** terminal and run:
```bash
python -m streamlit run dashboard.py
```
The dashboard will open in your browser at `http://localhost:8501`.

### Dashboard Tips
- Enable **Auto-refresh** to see updates in real-time as data is logged
- Use **Zoom Last 15m** to track the most recent market activity
- Hover over the charts to see exact values with the unified crosshair
- The charts are linked - zooming one automatically zooms the other

## How It Works

The system identifies the **Active Market** by finding the 15-minute interval that has started but not yet expired:

- **Start Time**: Beginning of the 15-minute candle
- **Expiration**: End of the 15-minute candle  
- **Strike Price**: BTC price at the Start Time (from Binance)
- **Current Price**: Real-time BTC price from Binance
- **Contract Prices**: Live "Yes" (Up) and "No" (Down) prices from Polymarket's CLOB

Contracts pay out based on whether the price at **Expiration** is higher ("Up") or lower ("Down") than the **Strike Price**.

## Project Structure

```
PolymarketAnalyst/
├── __pycache__/                 # Python compiled bytecode cache
├── dashboard.py                  # Streamlit dashboard application
├── data_logger.py               # Background data collection service
├── fetch_current_polymarket.py  # Core market data fetching logic
├── find_new_market.py           # Script to find new markets
├── get_current_markets.py       # Script to get current markets
├── .gitignore                   # Specifies intentionally untracked files to ignore
├── README.md                    # This file
└── market_data.csv              # Historical data (auto-generated and used by dashboard)
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

MIT License - feel free to use this project for your own analysis and trading strategies.

## Disclaimer

This tool is for informational and educational purposes only. Trading cryptocurrencies and prediction markets involves risk. Always do your own research and never invest more than you can afford to lose.
