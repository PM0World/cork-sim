import io, base64
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt

from runner import run_simulation

# ── global dark theme -------------------------------------------------
st.set_page_config(
    page_title="Cork Depeg Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
    theme={"base": "dark", "primaryColor": "#00E7C5"},
)
st.title("🧮 Cork Scenario Simulator")

# ─────────────────────────────────────────────────────────────
# PARAM INPUTS
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Scenario")
    scenario = st.selectbox(
        "Preset",
        ["Minor Liquidity Shock", "Moderate Depeg Pressure",
         "Severe Depeg Stress", "Three-Minute Demo"],
    )
    depeg_pct = st.slider("Maximum depeg (%)", 1, 50, 10) / 100

    st.header("Participants (ETH)")
    cap_yield = st.number_input("Yield Seeker (LP)", 0.0, 100_000.0, 5_000.0, 500.0)
    cap_hedge = st.number_input("Hedge Fund",        0.0, 100_000.0, 3_000.0, 500.0)
    cap_arb   = st.number_input("Arbitrage Desk",    0.0, 100_000.0, 2_000.0, 500.0)
    capital_map = {k: v for k, v in {
        "Yield Seeker (LP)": cap_yield,
        "Hedge Fund":        cap_hedge,
        "Arbitrage Desk":    cap_arb,
    }.items() if v > 0}

    st.header("Market settings")
    token     = st.text_input("Token symbol", "stETH")
    amm_eth   = st.number_input("AMM ETH liquidity",   10_000.0, 1_000_000.0, 50_000.0, 5_000.0)
    amm_tok   = st.number_input("AMM token liquidity", 10_000.0, 1_000_000.0, 50_000.0, 5_000.0)
    amm_fee   = st.slider("AMM fee", 0.0, 0.1, 0.02)
    lst_apr   = st.number_input("Staking yield APR (%)", 0.0, 20.0, 4.0)
    blocks    = st.slider("Blocks", 50, 10_000, 500)

run = st.button("▶️  Run simulation", type="primary")

# ─────────────────────────────────────────────────────────────
# SIMULATION EXECUTION
# ─────────────────────────────────────────────────────────────
if run:
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

    summary = res["summary"]
    min_pct  = summary["min_pct"]
    minutes  = summary["blocks_under_peg"] * 12 / 60
    draw_pct = summary["psm_drawdown_pct"]

    # ── headline metrics row ----------------------------------------
    m1, m2, m3 = st.columns(3)
    m1.metric("📉 Min price", f"{1-min_pct:.3f}", f"−{min_pct:.1%}")
    m2.metric("⏱ Minutes under peg", f"{minutes:.1f}")
    m3.metric("🏦 PSM used", f"{draw_pct:.1%}")

    # ── charts container -------------------------------------------
    with st.container():
        c_left, c_right = st.columns([2, 1])

        # price chart
        df_price = pd.DataFrame(res["tokens_stats"]).query("token == @token")
        fig, ax = plt.subplots(facecolor="#0E1117")
        ax.plot(df_price["block"], df_price["price"], color="#00E7C5")
        ax.set_xlabel("Block"); ax.set_ylabel("Price (ETH)")
        ax.spines[:].set_color("#BBBBBB")
        ax.tick_params(colors="#BBBBBB")
        c_left.pyplot(fig)

        # save for PNG download
        buf = io.BytesIO()
        fig.savefig(buf, format="png", facecolor="#0E1117")

        # PSM gauge
        gauge_df = pd.DataFrame({
            "label": ["used", "left"],
            "value": [draw_pct, 1-draw_pct]
        })
        arc = (
            alt.Chart(gauge_df)
            .mark_arc(innerRadius=60, outerRadius=90)
            .encode(theta="value:Q", color=alt.Color("label:N",
                    scale=alt.Scale(domain=["used","left"],
                                    range=["#F87171","#374151"])),
                    tooltip=["label:N","value:Q"])
            .properties(width=220, height=220)
        )
        c_right.altair_chart(arc, use_container_width=True)

    # ── final bar chart full width ----------------------------------
    bal = (pd.DataFrame(res["agents_stats"])
           .groupby("agent")["wallet_face_value"].last().reset_index())
    bar = alt.Chart(bal).mark_bar(color="#60A5FA").encode(
        x="agent:N", y="wallet_face_value:Q"
    ).properties(height=300)
    st.subheader("Final wallet face value (ETH)")
    st.altair_chart(bar, use_container_width=True)

    # ── expandable tables ------------------------------------------
    with st.expander("Trades"):
        st.dataframe(pd.DataFrame(res["all_trades"]))
    with st.expander("Agent stats"):
        st.dataframe(pd.DataFrame(res["agents_stats"]))

    # ── download buttons -------------------------------------------
    trades_csv = pd.DataFrame(res["all_trades"]).to_csv(index=False).encode()
    st.download_button("📄 CSV", trades_csv, file_name="trades.csv")
    st.download_button("📈 PNG", buf.getvalue(), file_name="price_chart.png",
                       mime="image/png")
