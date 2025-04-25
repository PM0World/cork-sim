import io
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt

from runner import run_simulation

# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Cork Depeg Simulator", layout="wide")
st.title("🧮 Cork Scenario Simulator")

# ─────────────────────────────────────────────────────────────
# Scenario + depeg intensity
# ─────────────────────────────────────────────────────────────
scenario = st.selectbox(
    "Scenario preset",
    ["Minor Liquidity Shock", "Moderate Depeg Pressure", "Severe Depeg Stress"],
)
depeg_pct = st.slider("Maximum depeg (%)", 1, 50, 10) / 100  # 0.10 = 10 %

# ─────────────────────────────────────────────────────────────
# Participant capital sliders
# ─────────────────────────────────────────────────────────────
st.subheader("Participant capital (ETH)")
c1, c2, c3 = st.columns(3)
cap_yield = c1.number_input("Yield Seeker (LP)", 0.0, 100_000.0, 5_000.0, 500.0)
cap_hedge = c2.number_input("Hedge Fund",        0.0, 100_000.0, 3_000.0, 500.0)
cap_arb   = c3.number_input("Arbitrage Desk",    0.0, 100_000.0, 2_000.0, 500.0)
capital_map = {k: v for k, v in {
    "Yield Seeker (LP)": cap_yield,
    "Hedge Fund":        cap_hedge,
    "Arbitrage Desk":    cap_arb,
}.items() if v > 0}

# ─────────────────────────────────────────────────────────────
# Market / protocol parameters
# ─────────────────────────────────────────────────────────────
st.subheader("Market conditions")

token = st.text_input("Token symbol", "stETH")
amm_eth = st.number_input("AMM ETH liquidity",   10_000.0, 1_000_000.0, 50_000.0, 5_000.0)
amm_tok = st.number_input("AMM token liquidity", 10_000.0, 1_000_000.0, 50_000.0, 5_000.0)
amm_fee = st.slider("AMM fee", 0.0, 0.1, 0.02)
lst_apr = st.number_input("Staking yield APR (%)", 0.0, 20.0, 4.0)
blocks  = st.slider("Blocks to simulate", 50, 10_000, 500)

# ─────────────────────────────────────────────────────────────
# Run simulation
# ─────────────────────────────────────────────────────────────
if st.button("▶️  Run simulation", type="primary"):
    cfg = dict(
        token       = token,
        initial_eth = 100.0,
        blocks      = blocks,
        eth_yield   = 0.00001,
        lst_yield   = lst_apr / 100 / 365,
        amm_eth     = amm_eth,
        amm_token   = amm_tok,
        amm_fee     = amm_fee,
    )

    res = run_simulation(scenario, depeg_pct, capital_map, cfg)

    # ── headline metrics ────────────────────────────────────────────
    s        = res["summary"]
    min_pct  = s["min_pct"]                     # e.g. 0.12 for −12 %
    minutes  = s["blocks_under_peg"] * 12 / 60  # 12 s per block
    draw_pct = s.get("psm_drawdown_pct", 0.0)   # might be in summary

    m1, m2, m3 = st.columns(3)
    m1.metric("📉 Min price",           f"{1-min_pct:.3f}", f"−{min_pct:.1%}")
    m2.metric("⏱ Time under peg",       f"{minutes:.1f} min")
    m3.metric("🏦 PSM collateral used", f"{draw_pct:.1%}")

    # ── PSM collateral gauge ────────────────────────────────────────
    if "psm_drawdown_pct" in s:
        gauge = pd.DataFrame({
            "label": ["used", "left"],
            "value": [draw_pct, 1-draw_pct]
        })
        arc = (
            alt.Chart(gauge)
            .mark_arc(innerRadius=60, outerRadius=90)
            .encode(theta="value:Q", color="label:N")
            .properties(width=200, height=200)
        )
        st.altair_chart(arc, use_container_width=False)

    # ── price path plot (Matplotlib, also saved to buffer) ──────────
    df_price = pd.DataFrame(res["tokens_stats"]).query("token == @token")
    fig, ax = plt.subplots()
    ax.plot(df_price["block"], df_price["price"])
    ax.set_xlabel("Block"); ax.set_ylabel("Price (ETH)")
    ax.set_title(f"{token} price path")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    st.pyplot(fig)

    # ── expandable data tables ──────────────────────────────────────
    with st.expander("Trades table"):
        st.dataframe(pd.DataFrame(res["all_trades"]))
    with st.expander("Agent stats table"):
        st.dataframe(pd.DataFrame(res["agents_stats"]))

    # ── bar of final wallet face value ──────────────────────────────
    final_bal = (
        pd.DataFrame(res["agents_stats"])
        .groupby("agent")["wallet_face_value"]
        .last()
        .reset_index()
    )
    st.subheader("Final wallet face value (ETH)")
    st.altair_chart(
        alt.Chart(final_bal).mark_bar().encode(
            x="agent:N", y="wallet_face_value:Q"
        ).properties(width=600, height=350),
        use_container_width=True,
    )

    # ── download buttons ────────────────────────────────────────────
    trades_csv = pd.DataFrame(res["all_trades"]).to_csv(index=False).encode()
    st.download_button(
        "Download trades CSV",
        trades_csv,
        file_name="trades.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download price chart PNG",
        buf.getvalue(),
        file_name="price_chart.png",
        mime="image/png",
    )
