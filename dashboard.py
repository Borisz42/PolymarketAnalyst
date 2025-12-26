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

st.title("📊 Polymarket 15m BTC Monitor - Historical Analysis")

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
if st.button('🔄 Refresh Data', key='refresh_data_button'):
    st.rerun()

df = load_data()

if df is not None and not df.empty:
    # Calculate derived metrics for strategy analysis
    df['PairCost'] = df['UpAsk'] + df['DownAsk']  # Cost to buy both sides
    df['SpreadTotal'] = df['UpSpread'] + df['DownSpread']  # Total market spread
    def calculate_imbalance(row):
        up_liq = row['UpAskLiquidity']
        down_liq = row['DownAskLiquidity']

        if up_liq > down_liq:
            if down_liq > 0:
                imbalance = up_liq / down_liq
            else:
                imbalance = 10
        elif down_liq > up_liq:
            if up_liq > 0:
                imbalance = - (down_liq / up_liq)
            else:
                imbalance = -10
        else: # up_liq == down_liq
            imbalance = 0

        return max(-10, min(10, imbalance))

    df['LiquidityImbalance'] = df.apply(calculate_imbalance, axis=1)

    # Replace 0 values with NaN for plotting purposes, as 0 ask/liquidity means no data for that side
    df.loc[df['UpAsk'] == 0, 'UpAsk'] = np.nan
    df.loc[df['DownAsk'] == 0, 'DownAsk'] = np.nan
    df.loc[df['UpAskLiquidity'] == 0, 'UpAskLiquidity'] = np.nan
    df.loc[df['DownAskLiquidity'] == 0, 'DownAskLiquidity'] = np.nan
    
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
        for col in ['UpMid', 'DownMid', 'PairCost', 'SpreadTotal', 
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
    
    # Create 3-panel chart
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(
            "💰 Pair Cost (KEY FOR STRATEGY)",
            "📉 Ask Prices (UP vs DOWN)", 
            "💧 Liquidity Depth",
            "⚖️ Liquidity Imbalance"
        ),
        row_heights=[0.3, 0.25, 0.25, 0.2]
    )

    # === CHART 1: PAIR COST (Most Important for Strategy) ===
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

    # === CHART 2: ASK PRICES ===
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['UpAsk'], 
        name="UP Ask",
        line=dict(color='#4ECDC4', width=2),
        mode='lines'
    ), row=2, col=1)
    
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['DownAsk'], 
        name="DOWN Ask",
        line=dict(color='#FF6B9D', width=2, dash='dash'),
        mode='lines'
    ), row=2, col=1)

    # === CHART 3: LIQUIDITY DEPTH ===
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['UpAskLiquidity'], 
        name="UP Ask Liquidity",
        fill='tozeroy',
        fillcolor='rgba(78, 205, 196, 0.3)',
        line=dict(color='#4ECDC4', width=2),
        mode='lines'
    ), row=3, col=1)
    
    fig.add_trace(go.Scatter(
        x=df_chart['Timestamp'], 
        y=df_chart['DownAskLiquidity'], 
        name="DOWN Ask Liquidity",
        fill='tozeroy',
        fillcolor='rgba(255, 107, 157, 0.3)',
        line=dict(color='#FF6B9D', width=2),
        mode='lines'
    ), row=3, col=1)

    # === CHART 4: LIQUIDITY IMBALANCE ===
    fig.add_trace(go.Bar(
        x=df_chart['Timestamp'],
        y=df_chart['LiquidityImbalance'],
        name="Liquidity Imbalance",
        marker_color=np.where(df_chart['LiquidityImbalance'] > 0, '#4ECDC4', '#FF6B9D')
    ), row=4, col=1)

    # Add vertical lines for market transitions
    transitions = df.loc[df['TargetTime'].shift() != df['TargetTime'], 'Timestamp'].iloc[1:]
    for t in transitions:
        for row in range(1, 5):
            fig.add_vline(x=t, line_width=1, line_dash="dot", line_color="gray", row=row, col=1)

    # Update Layout
    fig.update_layout(
        height=1100,
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    # Update y-axis titles
    fig.update_yaxes(title_text="USD", row=1, col=1)
    fig.update_yaxes(title_text="Price", range=[0, 1], row=2, col=1)
    fig.update_yaxes(title_text="Shares", row=3, col=1)
    fig.update_yaxes(title_text="Imbalance Ratio", row=4, col=1)
    fig.update_xaxes(title_text="Time", row=4, col=1)

    # Apply zoom if set
    if current_range:
        for row in range(1, 5):
            fig.update_xaxes(range=current_range, row=row, col=1)

    # Enable crosshair
    fig.update_xaxes(showspikes=True, spikemode='across', spikesnap='cursor', showline=True, spikedash='dash')
    
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})

    # === DATA TABLE ===
    with st.expander("📋 View Recent Data"):
        display_cols = ['Timestamp', 'UpAsk', 'DownAsk', 'PairCost',
                       'SpreadTotal', 'UpAskLiquidity', 'DownAskLiquidity', 'LiquidityImbalance']
        st.dataframe(df[display_cols].tail(20).sort_values('Timestamp', ascending=False),
                    use_container_width=True)
    
else:
    st.warning("No data found yet. Please ensure data_logger.py is running.")