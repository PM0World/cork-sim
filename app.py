import streamlit as st
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM
from agents.ds_speculation import DSShortTermAgent
from agents.ct_speculation import CTShortTermAgent
from agents.ds_long_term import DSLongTermAgent
from agents.ct_long_term import CTLongTermAgent
from agents.redemption_arbitrage import RedemptionArbitrageAgent
from agents.repurchase_arbitrage import RepurchaseArbitrageAgent
from agents.looping import LoopingAgent
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Cork Protocol Trading Engine", layout="wide")

# Explicitly enforced Dark Mode & IBM Plex Mono Font
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&display=swap');

html, body, .stApp, .css-18e3th9, .css-1d391kg, .st-emotion-cache-18ni7ap {
    font-family: 'IBM Plex Mono', monospace !important;
    background-color: #0E1117 !important;
    color: #FFFFFF !important;
}

section.main, .block-container {
    background-color: #0E1117 !important;
}

.css-1d391kg, .css-1y4p8pa, .stSidebar, .sidebar-content {
    background-color: #161B22 !important;
}

button, .stButton>button {
    background-color: #21262D !important;
    color: #FFFFFF !important;
    border: none !important;
}

input, .stNumberInput input, .stTextInput input {
    background-color: #21262D !important;
    color: #FFFFFF !important;
}

.stSlider div {
    color: #FFFFFF !important;
}

.stMarkdown, .dataframe, table, td, th {
    color: #FFFFFF !important;
}
</style>
""", unsafe_allow_html=True)

st.title("Cork Protocol Trading Engine")

# Sidebar Parameters
st.sidebar.header("Simulation Settings")
num_blocks = st.sidebar.slider("Simulation Blocks", 100, 2000, 300, 50)
initial_eth_balance = st.sidebar.number_input("Initial ETH Balance", 50.0, 10000.0, 5000.0, 50.0)
amm_reserve = st.sidebar.number_input("AMM Initial Reserve", 1e6, 2e7, 1e7, 1e5)
volatility = st.sidebar.slider("Volatility", 0.0, 1.0, 0.02, 0.01)
yield_rate = st.sidebar.slider("Annual Yield (%)", 0.0, 20.0, 3.0, 0.1) / 365

# Simulation Execution
if st.sidebar.button("Run Simulation"):
    with st.spinner('Simulating...'):
        chain = Blockchain(
            num_blocks=num_blocks,
            initial_eth_balance=initial_eth_balance,
            psm_expiry_after_block=num_blocks,
            initial_eth_yield_per_block=yield_rate
        )

        chain.add_token(
            token='stETH',
            risk=volatility,
            initial_agent_balance=100.0,
            amm=UniswapV2AMM('stETH', amm_reserve, amm_reserve, 0.02),
            initial_yield_per_block=yield_rate
        )

        agents = [
            DSShortTermAgent("DS Short Term", "stETH", 0.01),
            CTShortTermAgent("CT Short Term", "stETH", 10),
            DSLongTermAgent("DS Long Term", "stETH", 1),
            CTLongTermAgent("CT Long Term", "stETH", 0.01),
            RedemptionArbitrageAgent("Redemption Arb", "stETH"),
            RepurchaseArbitrageAgent("Repurchase Arb", "stETH"),
            LoopingAgent("Looping Agent", "stETH", 0.001, {}, 0.7, 0.915)
        ]

        chain.add_agents(*agents)
        chain.start_mining()

        agents_stats = chain.stats['agents']
        trades = pd.DataFrame(chain.all_trades)

    wallet_df = agents_stats[['agent', 'wallet_face_value']].copy()
    wallet_df.columns = ['Agent', 'Wallet Value (ETH)']

    st.subheader("Agent Wallet Summary")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=wallet_df, y='Agent', x='Wallet Value (ETH)', palette="coolwarm_r", ax=ax)
    ax.set_xlabel("Wallet Value (ETH)")
    ax.set_ylabel("Agent")
    st.pyplot(fig)
    st.dataframe(wallet_df, use_container_width=True)

    st.subheader("Trade Volumes")
    trade_volumes = trades.groupby('agent')['volume'].sum().reset_index().rename(columns={'agent':'Agent', 'volume':'Total Volume'})
    fig2, ax2 = plt.subplots(figsize=(10, 5))
    sns.barplot(data=trade_volumes, y='Agent', x='Total Volume', palette="mako_r", ax=ax2)
    ax2.set_xlabel("Total Volume")
    ax2.set_ylabel("Agent")
    st.pyplot(fig2)
    st.dataframe(trade_volumes, use_container_width=True)

    st.subheader("Predictive Price Simulation")
    forecast_blocks = st.slider("Predictive Blocks", 50, 500, 100, 10)
    predicted_prices = np.cumsum(np.random.normal(loc=0, scale=volatility, size=forecast_blocks)) + amm_reserve/1e6

    fig3, ax3 = plt.subplots(figsize=(10, 4))
    ax3.plot(range(forecast_blocks), predicted_prices, color="#58A6FF")
    ax3.set_xlabel("Blocks Ahead")
    ax3.set_ylabel("Predicted stETH Price (ETH)")
    st.pyplot(fig3)

    csv = trades.to_csv(index=False).encode('utf-8')
    st.download_button("Download Trade Data", csv, "trades.csv", "text/csv")


