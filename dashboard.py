import numpy as np
import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import datetime


# Get the directory of the current script
SCRIPT_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(SCRIPT_DIR, "market_data.csv")


st.set_page_config(page_title="Polymarket BTC Monitor", layout="wide")

st.title("📊 Polymarket 15m BTC Monitor - Enhanced")

def load_data():
    try:
        df = pd.read_csv(DATA_FILE)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        return df
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Auto-refresh logic (Top of page)
col_top1, col_top2 = st.columns([1, 4])
with col_top1:
    if st.button('🔄 Refresh Data', key='refresh_data_button'):
        st.rerun()
with col_top2:
    auto_refresh = st.checkbox("Auto-refresh", value=True)

df = load_data()

if df is not None and not df.empty:
    # Calculate derived metrics for strategy analysis
    df['PairCost'] = df['UpAsk'] + df['DownAsk']  # Cost to buy both sides
    df['PairCostMid'] = df['UpMid'] + df['DownMid']  # Mid-market pair cost
    df['Opportunity'] = 0.98 - df['PairCost']  # Profit opportunity (positive = good)
    df['SpreadTotal'] = df['UpSpread'] + df['DownSpread']  # Total market spread
    df['LiquidityImbalance'] = (df['UpAskLiquidity'] - df['DownAskLiquidity']) / (df['UpAskLiquidity'] + df['DownAskLiquidity'])
    
    # Get latest from raw data
    latest = df.iloc[-1]
    
    # === KEY METRICS ===
    st.subheader("📈 Current Market State")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("UP Ask", f"${latest['UpAsk']:.3f}", 
                 help="Best ask price for UP contracts")
    with col2:
        st.metric("DOWN Ask", f"${latest['DownAsk']:.3f}",
                 help="Best ask price for DOWN contracts")
    with col3:
        pair_cost = latest['PairCost']
        opportunity = latest['Opportunity']
        st.metric("Pair Cost", f"${pair_cost:.3f}", 
                 f"{opportunity:+.3f}",
                 delta_color="inverse",
                 help="Cost to buy both UP and DOWN. Target: <$0.98")
    with col4:
        st.metric("Total Spread", f"${latest['SpreadTotal']:.3f}",
                 help="Combined bid-ask spread (lower = more liquid)")
    with col5:
        liq_imb = latest['LiquidityImbalance']
        st.metric("Liq. Imbalance", f"{liq_imb:+.2%}",
                 help="Liquidity imbalance (+ = more UP liquidity)")

    # === TRADING OPPORTUNITY INDICATOR ===
    if opportunity > 0:
        st.success(f"✅ **OPPORTUNITY**: Pair cost ${pair_cost:.3f} is below $0.98 target! Potential profit: ${opportunity:.3f} per pair")
    elif opportunity > -0.01:
        st.warning(f"⚠️ **MARGINAL**: Pair cost ${pair_cost:.3f} is close to target")
    else:
        st.info(f"ℹ️ **NO OPPORTUNITY**: Pair cost ${pair_cost:.3f} exceeds $0.98 target")

    # Process data for charts (add gaps between different markets)
    df_chart = df.copy().sort_values('Timestamp')
    df_chart['group'] = (df_chart['TargetTime'] != df_chart['TargetTime'].shift()).cumsum()
    
    segments = []
    for _, group in df_chart.groupby('group'):
        segments.append(group)
        # Add gap row
        gap_row = group.iloc[[-1]].copy()
        gap_row['Timestamp'] += pd.Timedelta(seconds=1) 
        # Set values to NaN to break the line
        for col in ['UpMid', 'DownMid', 'PairCost', 'Opportunity', 'SpreadTotal', 
                    'UpAskLiquidity', 'DownAskLiquidity', 'LiquidityImbalance']:
            gap_row[col] = np.nan
        segments.append(gap_row)
    
    df_chart = pd.concat(segments).reset_index(drop=True)

    # Initialize zoom mode
    if 'zoom_mode' not in st.session_state:
        st.session_state.zoom_mode = None

    # Zoom Controls
    col_z1, col_z2 = st.columns([1, 10])
    with col_z1:
        if st.button("Reset Zoom", key='reset_zoom_button'):
            st.session_state.zoom_mode = None
            st.rerun()
    with col_z2:
        if st.button("Zoom Last 15m", key='zoom_15m_button'):
            st.session_state.zoom_mode = 'last_15m'
            st.rerun()

    # Calculate range based on mode
    current_range = None
    if st.session_state.zoom_mode == 'last_15m':
        end_time = df['Timestamp'].max()
        start_time = end_time - pd.Timedelta(minutes=15)
        current_range = [start_time, end_time]

    # === MAIN CHARTS ===
    st.subheader("📊 Market Analysis")
    
    # Create 4-panel chart
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            "💰 Pair Cost & Opportunity (KEY FOR STRATEGY)",
            "📉 Mid Prices (UP vs DOWN)", 
            "📊 Spread Analysis",
            "💧 Liquidity Depth"
        ),
        row_heights=[0.3, 0.25, 0.2, 0.25]
    )

    # === CHART 1: PAIR COST & OPPORTUNITY (Most Important for Strategy) ===
    # Pair cost line
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['PairCost'], 
        name="Pair Cost (Ask)",
        line=dict(color='#FF6B6B', width=3),
        mode='lines'
    ), row=1, col=1)
    
    # Target line at 0.98
    fig.add_hline(y=0.98, line_dash="dash", line_color="green", 
                  annotation_text="Target: $0.98", row=1, col=1)
    
    # Opportunity area (when pair cost < 0.98)
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'],
        y=df_chart['Opportunity'],
        name="Profit Opportunity",
        fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.2)',
        line=dict(color='#00FF00', width=2),
        mode='lines'
    ), row=1, col=1)

    # === CHART 2: MID PRICES ===
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['UpMid'], 
        name="UP Mid",
        line=dict(color='#4ECDC4', width=2),
        mode='lines'
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['DownMid'], 
        name="DOWN Mid",
        line=dict(color='#FF6B9D', width=2, dash='dash'),
        mode='lines'
    ), row=2, col=1)

    # === CHART 3: SPREAD ANALYSIS ===
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['UpSpread'], 
        name="UP Spread",
        line=dict(color='#95E1D3', width=2),
        mode='lines'
    ), row=3, col=1)
    
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['DownSpread'], 
        name="DOWN Spread",
        line=dict(color='#F38181', width=2),
        mode='lines'
    ), row=3, col=1)

    # === CHART 4: LIQUIDITY DEPTH ===
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['UpAskLiquidity'], 
        name="UP Ask Liquidity",
        fill='tozeroy',
        fillcolor='rgba(78, 205, 196, 0.3)',
        line=dict(color='#4ECDC4', width=2),
        mode='lines'
    ), row=4, col=1)
    
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['DownAskLiquidity'], 
        name="DOWN Ask Liquidity",
        fill='tozeroy',
        fillcolor='rgba(255, 107, 157, 0.3)',
        line=dict(color='#FF6B9D', width=2),
        mode='lines'
    ), row=4, col=1)

    # Add vertical lines for market transitions
    transitions = df.loc[df['TargetTime'].shift() != df['TargetTime'], 'Timestamp'].iloc[1:]
    for t in transitions:
        for row in range(1, 5):
            fig.add_vline(x=t, line_width=1, line_dash="dot", line_color="gray", row=row, col=1)

    # Update Layout
    fig.update_layout(
        height=1200,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Update y-axis titles
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="Price", range=[0, 1], row=2, col=1)
    fig.update_yaxes(title_text="Spread", row=3, col=1)
    fig.update_yaxes(title_text="Shares", row=4, col=1)
    fig.update_xaxes(title_text="Time", row=4, col=1)

    # Apply zoom if set
    if current_range:
        for row in range(1, 5):
            fig.update_xaxes(range=current_range, row=row, col=1)

    # Enable crosshair
    fig.update_xaxes(showspikes=True, spikemode='across', spikesnap='cursor', showline=True, spikedash='dash')
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

    # === CORRELATION INSIGHTS ===
    st.subheader("🔍 Strategy Insights")
    
    col_i1, col_i2 = st.columns(2)
    
    with col_i1:
        st.markdown("**📊 Key Correlations to Watch:**")
        st.markdown("""
        - **Pair Cost < $0.98** → Trading opportunity (green area in chart 1)
        - **Low Total Spread** → More liquid market, easier to enter/exit
        - **High Liquidity** → Can execute larger trades without slippage
        - **Liquidity Imbalance** → May indicate directional pressure
        """)
    
    with col_i2:
        st.markdown("**⚡ Current Conditions:**")
        recent = df.tail(10)
        avg_opportunity = recent['Opportunity'].mean()
        avg_spread = recent['SpreadTotal'].mean()
        avg_liquidity = (recent['UpAskLiquidity'].mean() + recent['DownAskLiquidity'].mean()) / 2
        
        st.markdown(f"""
        - Avg Opportunity (last 10): **${avg_opportunity:+.4f}**
        - Avg Total Spread: **${avg_spread:.4f}**
        - Avg Liquidity: **{avg_liquidity:.1f} shares**
        - Opportunities in last 10: **{(recent['Opportunity'] > 0).sum()}/10**
        """)

    # === DATA TABLE ===
    with st.expander("📋 View Recent Data"):
        display_cols = ['Timestamp', 'UpAsk', 'DownAsk', 'PairCost', 'Opportunity', 
                       'SpreadTotal', 'UpAskLiquidity', 'DownAskLiquidity']
        st.dataframe(df[display_cols].tail(20).sort_values('Timestamp', ascending=False),
                    use_container_width=True)
    
    st.caption(f"Last updated: {latest['Timestamp']}")

else:
    st.warning("No data found yet. Please ensure data_logger.py is running.")
    
# --- Auto-refresh logic (periodic check) ---
if auto_refresh:
    time.sleep(1)  # Refresh every 1 second
    st.rerun()