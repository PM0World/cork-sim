import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
from runner import run_simulation

# ── Layout & inputs ───────────────────────────────────────────
st.set_page_config(page_title="Cork Depeg Simulator", layout="wide")
st.title("🧮  Cork Protocol – Depeg Scenario Simulator")

scenario = st.selectbox(
    "Scenario Preset",
    ["Flash Crash", "Liquidity Drain"],
    index=0,
)

depeg_pct = st.slider("Max depeg (%)", 1, 50, 10) / 100.0

st.subheader("Agent Mix")
col1, col2, col3 = st.columns(3)
profiles = {
    "Cautious Fund": col1.number_input("Cautious Fund (count)", 0, 10, 1),
    "Yield Seeker":  col2.number_input("Yield Seeker (count)", 0, 10, 2),
    "Max Leveraged Whale": col3.number_input("Whales (count)", 0, 5, 1),
}
# strip zeros
profiles = {k: v for k, v in profiles.items() if v > 0}

st.subheader("Market Conditions")
token      = st.text_input("Token symbol", "stETH")
amm_eth    = st.number_input("AMM ETH Liquidity",   1_000.0, value=1_000_000.0)
amm_token  = st.number_input("AMM Token Liquidity", 1_000.0, value=1_000_000.0)
amm_fee    = st.slider("AMM fee", 0.0, 0.1, 0.02)
lst_yield  = st.number_input("LST yield (APR %)", 0.0, 10.0, 4.0) / 100 / 365
blocks     = st.slider("Blocks to simulate", 10, 10_000, 300)
eth_yield  = st.number_input("ETH yield per block", 0.0, 0.01, 0.00001, format="%.6f")

if st.button("▶️  Run simulation"):
    cfg = dict(
        token=token,
        initial_eth=100.0,
        blocks=blocks,
        eth_yield=eth_yield,
        lst_yield=lst_yield,
        amm_eth=amm_eth,
        amm_token=amm_token,
        amm_fee=amm_fee,
    )
    res = run_simulation(scenario, depeg_pct, profiles, cfg)

    # ── Results tables ─────────────────────────────
    st.success(
        f"Sim finished · min price "
        f"{res['summary']['min_price']:.3f} "
        f"({res['summary']['min_pct']:.1%} below peg), "
        f"time under peg {res['summary']['blocks_under_peg']} blocks"
    )

    st.subheader("Trades")
    st.dataframe(pd.DataFrame(res["all_trades"]))

    st.subheader("Agent Stats")
    st.dataframe(pd.DataFrame(res["agents_stats"]))

    # ── Charts ─────────────────────────────────────
    prices = pd.DataFrame(res["tokens_stats"]).query("token == @token")
    st.subheader(f"{token} price path")
    fig, ax = plt.subplots()
    ax.plot(prices["block"], prices["price"])
    ax.set_xlabel("Block"); ax.set_ylabel("Price")
    st.pyplot(fig)

    st.subheader("Final wallet value per agent")
    final = (
        pd.DataFrame(res["agents_stats"])
          .groupby("agent")["wallet_face_value"]
          .last().reset_index()
    )
    chart = alt.Chart(final).mark_bar().encode(
        x="agent:N", y="wallet_face_value:Q"
    ).properties(width=600, height=350)
    st.altair_chart(chart, use_container_width=True)

    # ── Downloads ──────────────────────────────────
    st.download_button(
        "Download trades CSV",
        pd.DataFrame(res["all_trades"]).to_csv(index=False),
        file_name="trades.csv",
    )
    st.download_button(
        "Download agent stats CSV",
        pd.DataFrame(res["agents_stats"]).to_csv(index=False),
        file_name="agents_stats.csv",
    )
