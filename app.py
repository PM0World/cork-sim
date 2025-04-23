import streamlit as st
import pandas as pd
from main import main as run_sim

from agents import (
    ds_speculation,
    ct_speculation,
    ds_long_term,
    ct_long_term,
    looping,
    redemption_arbitrage,
    repurchase_arbitrage,
    lst_maximalist,
    insurer,
    lv_depositor,
)

# ---------- helper to build agent objects dynamically ----------
def build_agent(name, params, token):
    mapping = {
        "DS Short Term": lambda p: ds_speculation.DSShortTermAgent(
            name=name, token_symbol=token, threshold=p.get("threshold", 0.01)
        ),
        "CT Short Term": lambda p: ct_speculation.CTShortTermAgent(
            name=name, token_symbol=token, buying_pressure=p.get("buying_pressure", 10)
        ),
        "DS Long Term": lambda p: ds_long_term.DSLongTermAgent(
            name=name, token_symbol=token, buying_pressure=p.get("buying_pressure", 1)
        ),
        "CT Long Term": lambda p: ct_long_term.CTLongTermAgent(
            name=name, token_symbol=token, percentage_threshold=p.get("pct_thr", 0.01)
        ),
        "Looping Agent": lambda p: looping.LoopingAgent(
            name=name,
            token_symbol=token,
            initial_borrow_rate=p.get("init_rate", 0.001),
            borrow_rate_changes={},
            max_ltv=p.get("max_ltv", 0.7),
        ),
        "Redemption Arb": lambda p: redemption_arbitrage.RedemptionArbitrageAgent(
            name=name, token_symbol=token
        ),
        "Repurchase Arb": lambda p: repurchase_arbitrage.RepurchaseArbitrageAgent(
            name=name, token_symbol=token
        ),
        # --- FIXED: no name= kwarg, only token_symbol ---
        "Lst Maximalist": lambda p: lst_maximalist.LstMaximalist(
            token_symbol=token
        ),
        "Insurer": lambda p: insurer.Insurer(name=name, token_symbol=token),
        "LV Depositor": lambda p: lv_depositor.LVDepositorAgent(
            name=name, token_symbol=token
        ),
    }
    return mapping[name](params)


# ---------- Streamlit UI --------------------------------------
st.set_page_config(page_title="Cork Simulator", layout="wide")
st.title("🧮 Cork Protocol Trading Simulator")

# ---- Step 1 core ----
with st.sidebar.expander("Step 1 · Core simulation", expanded=True):
    num_blocks = st.slider("Blocks to mine", 10, 10_000, 300)
    init_eth = st.number_input("Initial ETH balance", 1.0, value=100.0)
    token_name = st.text_input("TOKEN_NAME", "stETH")
    events_file = st.file_uploader("Custom events.json (optional)")

# ---- Step 2 AMM ----
with st.sidebar.expander("Step 2 · AMM parameters", expanded=False):
    reserve_eth = st.number_input("AMM reserve ETH", 1000.0, value=1_000_000.0)
    reserve_token = st.number_input(
        "AMM reserve TOKEN", 1000.0, value=1_000_000.0
    )
    amm_fee = st.slider("AMM fee", 0.0, 0.1, 0.02)

# ---- Step 3 agents ----
all_agent_names = [
    "DS Short Term",
    "CT Short Term",
    "DS Long Term",
    "CT Long Term",
    "Looping Agent",
    "Redemption Arb",
    "Repurchase Arb",
    "Lst Maximalist",
    "Insurer",
    "LV Depositor",
]
chosen = st.sidebar.multiselect(
    "Step 3 · Choose agents",
    all_agent_names,
    default=[n for n in all_agent_names if n != "Looping Agent"],
)

# per-agent parameter forms
agent_params = {}
for name in chosen:
    with st.sidebar.expander(f"{name} settings"):
        if name == "DS Short Term":
            agent_params[name] = {
                "threshold": st.number_input(
                    "threshold", 0.0, 0.5, 0.01, key=name
                )
            }
        elif name == "CT Short Term":
            agent_params[name] = {
                "buying_pressure": st.number_input(
                    "buying pressure", 1, 100, 10, key=name
                )
            }
        elif name == "DS Long Term":
            agent_params[name] = {
                "buying_pressure": st.number_input(
                    "buying pressure", 1, 10, 1, key=name
                )
            }
        elif name == "CT Long Term":
            agent_params[name] = {
                "pct_thr": st.number_input(
                    "% threshold", 0.0, 0.5, 0.01, key=name
                )
            }
        elif name == "Looping Agent":
            agent_params[name] = {
                "init_rate": st.number_input(
                    "initial borrow rate", 0.0, 0.01, 0.001, key=name
                ),
                "max_ltv": st.slider("max LTV", 0.1, 0.9, 0.7, key=name),
            }
        else:
            agent_params[name] = {}

# ---- Step 4 advanced ----
with st.sidebar.expander("Step 4 · Advanced / Monte-Carlo", expanded=False):
    n_sims = st.selectbox("How many simulations?", list(range(1, 11)), index=0)
    eth_yield = st.number_input(
        "initial_eth_yield_per_block", 0.0, 0.01, 0.00001, format="%.6f"
    )
    psm_expiry = st.number_input(
        "PSM expiry block (0 = same as num_blocks)", 0, num_blocks, num_blocks
    )

run = st.sidebar.button("▶️  Run simulation")

# ---------- run logic ----------
if run:
    agents = [
        build_agent(name, agent_params.get(name, {}), token_name)
        for name in chosen
    ]

    res = run_sim(
        num_blocks=num_blocks,
        initial_eth_balance=init_eth,
        agents_override=agents,
        amm_kwargs={
            "reserve_eth": reserve_eth,
            "reserve_token": reserve_token,
            "fee": amm_fee,
        },
        initial_eth_yield_per_block=eth_yield,
        psm_expiry_after_block=psm_expiry or num_blocks,
        events_path=None if events_file is None else "/tmp/upload.json",
    )

    st.success(
        f"Completed {res['final_block']} blocks · {len(res['all_trades'])} trades"
    )
    st.subheader("Trades")
    st.dataframe(res["all_trades"])
    st.subheader("Agent Stats")
    st.dataframe(pd.DataFrame(res["agents_stats"]))
