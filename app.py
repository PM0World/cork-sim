import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
from runner import run_simulation

st.set_page_config(page_title="Cork Depeg Simulator", layout="wide")
st.title("🧮 Cork Protocol – Scenario Simulator")

# ── Scenario & depeg ───────────────────────────────────────
scenario = st.selectbox(
    "Scenario preset",
    ["Minor Liquidity Shock", "Moderate Depeg Pressure", "Severe Depeg Stress"],
)
depeg_pct = st.slider("Maximum depeg (%)", 1, 50, 10) / 100.0

# ── Earn appetite ──────────────────────────────────────────
earn_appetite = st.radio(
    "Earn vault appetite",
    ["Passive", "Moderate", "Max"],
    help="Passive = no leverage, Max = highest LTV looping",
)
earn_capital = st.number_input("Earn capital (ETH)", 0.0, 50_000.0, 5_000.0, step=500.0)

# ── Other participants: capital sliders ────────────────────
st.subheader("Market participants (capital in ETH)")
c1, c2, c3 = st.columns(3)
cap_cf   = c1.number_input("Cautious Fund",        0.0, 20_000.0, 500.0, step=100.0)
cap_ys   = c2.number_input("Yield Seeker",         0.0, 20_000.0, 3_000.0, step=100.0)
cap_whale= c3.number_input("Max Leveraged Whale",  0.0, 50_000.0, 10_000.0, step=1_000.0)
profile_capital = {k:v for k,v in {
    "Cautious Fund":cap_cf,
    "Yield Seeker":cap_ys,
    "Max Leveraged Whale":cap_whale}.items() if v>0}

# ── Market conditions ──────────────────────────────────────
st.subheader("Market conditions")
token      = st.text_input("Token symbol", "stETH")
amm_eth    = st.number_input("AMM ETH liquidity",   1_000.0, value=1_000_000.0, step=1_000.0)
amm_token  = st.number_input("AMM token liquidity", 1_000.0, value=1_000_000.0, step=1_000.0)
amm_fee    = st.slider("AMM fee", 0.0, 0.1, 0.02)
lst_apr    = st.number_input("Staking yield APR (%)", 0.0, 20.0, 4.0)
blocks     = st.slider("Blocks to simulate", 50, 10_000, 500)

if st.button("▶️ Run simulation"):
    cfg = dict(
        token=token,
        initial_eth=100.0,
        blocks=blocks,
        eth_yield=0.00001,
        lst_yield=lst_apr/100/365,
        amm_eth=amm_eth,
        amm_token=amm_token,
        amm_fee=amm_fee,
    )
    res = run_simulation(
        scenario,
        depeg_pct,
        profile_capital,
        earn_appetite,
        earn_capital,
        cfg,
    )

    # ── Summary ────────────────────────────
    min_pct = res["summary"]["min_pct"]
    mins = res["summary"]["blocks_under_peg"]*12/60
    st.success(
        f"Min price {1-min_pct:.3f} (−{min_pct:.1%}); "
        f"time under peg ≈ {mins:.1f} min"
    )

    # ── Tables ─────────────────────────────
    st.subheader("Trades")
    st.dataframe(pd.DataFrame(res["all_trades"]))
    st.subheader("Agent stats")
    st.dataframe(pd.DataFrame(res["agents_stats"]))

    # ── Price chart ────────────────────────
    st.subheader(f"{token} price path")
    df_prices = pd.DataFrame(res["tokens_stats"]).query("token==@token")
    fig, ax = plt.subplots()
    ax.plot(df_prices["block"], df_prices["price"])
    ax.set_xlabel("Block"); ax.set_ylabel("Price")
    st.pyplot(fig)

    # ── Wallet bar chart ───────────────────
    final_bal = (
        pd.DataFrame(res["agents_stats"])
          .groupby("agent")["wallet_face_value"].last().reset_index())
    chart = alt.Chart(final_bal).mark_bar().encode(
        x="agent:N", y="wallet_face_value:Q"
    ).properties(width=600, height=350)
    st.altair_chart(chart, use_container_width=True)

    # ── Downloads ──────────────────────────
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
