# Dashboard Module

This module provides an interactive web-based dashboard for visualizing and analyzing the market data collected by the data logger. It is built using the Streamlit library.

To run the dashboard, use the following command from the project's root directory:
```bash
streamlit run src/dashboard/dashboard.py
```

## Key Features

-   **Live Auto-Refresh**: The dashboard can be configured to automatically refresh its data, allowing for near real-time monitoring of the market.
-   **Interactive Charts**: All charts are built with Plotly, providing interactive features like zooming, panning, and hovering to inspect data points.
-   **Unified Crosshair**: Hovering over any chart will display a synchronized crosshair across all charts, making it easy to correlate data points at a specific timestamp.
-   **Zoom Controls**: Dedicated buttons allow you to quickly "Reset Zoom" to view the entire day's data or "Zoom Last 15m" to focus on the most recent market activity.

## Chart Explanations

The dashboard consists of four main charts, arranged vertically and sharing a common timeline.

### 1. Pair Cost

-   **Purpose**: This chart is critical for identifying arbitrage opportunities.
-   **What it Shows**: It plots the combined cost of buying one "Up" contract and one "Down" contract at their current ask prices (`UpAsk + DownAsk`).
-   **How to Interpret**: A contract pair will always resolve to be worth exactly $1.00. Therefore, any time the `PairCost` drops below $1.00, it represents a potential trading opportunity. The dashboard includes a horizontal line at the `$0.98` level to highlight these entry points.

### 2. Ask Prices (UP vs DOWN)

-   **Purpose**: This chart shows the individual ask prices for the "Up" and "Down" contracts.
-   **What it Shows**: It plots the `UpAsk` and `DownAsk` prices over time.
-   **How to Interpret**: This chart provides a clear visualization of the market's sentiment. When the "Up" price is high (e.g., > $0.60) and the "Down" price is low, it indicates the market expects the price of BTC to go up, and vice versa.

### 3. Liquidity Depth

-   **Purpose**: This chart helps in assessing the market's stability and the feasibility of executing large trades.
-   **What it Shows**: It displays the total number of shares available at the top 5 ask levels for both "Up" and "Down" contracts (`UpAskLiquidity` and `DownAskLiquidity`).
-   **How to Interpret**: Higher liquidity means it is easier to enter and exit large positions without causing significant price slippage. A sudden drop in liquidity can be a sign of increased market volatility or risk.

### 4. Liquidity Imbalance

-   **Purpose**: This chart highlights potential short-term price movements by showing imbalances in market liquidity.
-   **What it Shows**: It displays a bar chart representing the ratio of "Up" to "Down" ask liquidity. A positive bar indicates more liquidity on the "Up" side, while a negative bar indicates more liquidity on the "Down" side.
-   **How to Interpret**: A significant imbalance can signal that market makers are trying to encourage trading in a particular direction. For example, a large negative bar (high "Down" liquidity) might suggest that a sharp move upwards is anticipated, and vice versa.
