"""
main.py – Cork Protocol Simulation entry point
• Can be imported as a function `main()` by Streamlit.
• Run directly for CLI testing: `python main.py`
"""

from typing import List, Dict, Optional
import pandas as pd

from agents.ct_long_term import CTLongTermAgent
from agents.ct_speculation import CTShortTermAgent
from agents.ds_long_term import DSLongTermAgent
from agents.ds_speculation import DSShortTermAgent
from agents.insurer import Insurer
from agents.lst_maximalist import LstMaximalist
from agents.redemption_arbitrage import RedemptionArbitrageAgent
from agents.repurchase_arbitrage import RepurchaseArbitrageAgent
from agents.lv_depositor import LVDepositorAgent
from agents.looping import LoopingAgent
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM

# ------------------------------------------------------------------
# Default constants (kept from the original file)
# ------------------------------------------------------------------
NUM_BLOCKS = 300
INITIAL_ETH_BALANCE = 100.0
TOKEN_NAME = "stETH"

INITIAL_AGENT_TOKEN_BALANCE = 100.0
AMM_RESERVE_ETH = 1_000_000.0
AMM_RESERVE_TOKEN = 1_000_000.0
AMM_FEE = 0.02
INITIAL_YIELD_PER_BLOCK = 0.03 / 365

PSM_EXPIRY_AFTER_BLOCK = NUM_BLOCKS
INITIAL_ETH_YIELD_PER_BLOCK = 0.00001

DEFAULT_AGENT_NAMES = [
    # "LstMaximalist",
    # "Insurer",
    "DSShortTerm",
    "CTShortTerm",
    "DSLongTerm",
    "CTLongTerm",
    "RedemptionArbitrage",
    "RepurchaseArbitrage",
    # "LVDepositor",
    # "LoopingAgent",
]

# ------------------------------------------------------------------
# Internal helper: map agent name → instance with given params
# ------------------------------------------------------------------
def _build_agent(name: str, token: str, params: Dict) -> object:
    if name == "DSShortTerm":
        return DSShortTermAgent(
            name="DS Short Term",
            token_symbol=token,
            threshold=params.get("threshold", 0.01),
        )
    if name == "CTShortTerm":
        return CTShortTermAgent(
            name="CT Short Term",
            token_symbol=token,
            buying_pressure=params.get("buying_pressure", 10),
        )
    if name == "DSLongTerm":
        return DSLongTermAgent(
            name="DS Long Term",
            token_symbol=token,
            buying_pressure=params.get("buying_pressure", 1),
        )
    if name == "CTLongTerm":
        return CTLongTermAgent(
            name="CT Long Term",
            token_symbol=token,
            percentage_threshold=params.get("percentage_threshold", 0.01),
        )
    if name == "RedemptionArbitrage":
        return RedemptionArbitrageAgent(name="Redemption Arb", token_symbol=token)
    if name == "RepurchaseArbitrage":
        return RepurchaseArbitrageAgent(name="Repurchase Arb", token_symbol=token)
    if name == "LstMaximalist":
        return LstMaximalist(token_symbol=token)
    if name == "Insurer":
        return Insurer(token_symbol=token)
    if name == "LVDepositor":
        return LVDepositorAgent(
            name="LV Depositor",
            token_symbol=token,
            expected_apy=params.get("expected_apy", 0.05),
        )
    if name == "LoopingAgent":
        return LoopingAgent(
            name="Looping Agent",
            token_symbol=token,
            initial_borrow_rate=params.get("initial_borrow_rate", 0.001),
            borrow_rate_changes=params.get("borrow_rate_changes", {}),
            max_ltv=params.get("max_ltv", 0.7),
            lltv=params.get("lltv", 0.915),
        )
    raise ValueError(f"Unknown agent name '{name}'")


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
def main(
    *,
    num_blocks: int = NUM_BLOCKS,
    initial_eth_balance: float = INITIAL_ETH_BALANCE,
    token_name: str = TOKEN_NAME,
    initial_agent_token_balance: float = INITIAL_AGENT_TOKEN_BALANCE,
    amm_kwargs: Optional[Dict] = None,
    initial_yield_per_block: float = INITIAL_YIELD_PER_BLOCK,
    initial_eth_yield_per_block: float = INITIAL_ETH_YIELD_PER_BLOCK,
    psm_expiry_after_block: Optional[int] = None,
    agent_names: Optional[List[str]] = None,
    agent_params: Optional[Dict[str, Dict]] = None,
    events_path: str = "events.json",
    agents_override: Optional[List[object]] = None,
):
    """
    Run a single simulation and return a dict of Pandas DataFrames.
    GUI or tests can override any argument.
    """
    amm_kwargs = amm_kwargs or {}
    psm_expiry_after_block = psm_expiry_after_block or num_blocks
    agent_names = agent_names or DEFAULT_AGENT_NAMES
    agent_params = agent_params or {}

    # ---------------- blockchain + token -----------------
    chain = Blockchain(
        num_blocks=num_blocks,
        initial_eth_balance=initial_eth_balance,
        psm_expiry_after_block=psm_expiry_after_block,
        initial_eth_yield_per_block=initial_eth_yield_per_block,
        events_path=events_path,
    )

    chain.add_token(
        token=token_name,
        risk=0.02,
        initial_agent_balance=initial_agent_token_balance,
        amm=UniswapV2AMM(
            token_symbol=token_name,
            reserve_eth=amm_kwargs.get("reserve_eth", AMM_RESERVE_ETH),
            reserve_token=amm_kwargs.get("reserve_token", AMM_RESERVE_TOKEN),
            fee=amm_kwargs.get("fee", AMM_FEE),
        ),
        initial_yield_per_block=initial_yield_per_block,
    )

    # ---------------- agents -----------------------------
    if agents_override is not None:
        agents = agents_override
    else:
        agents = [
            _build_agent(name, token_name, agent_params.get(name, {}))
            for name in agent_names
        ]
    chain.add_agents(*agents)

    # ---------------- run simulation ---------------------
    chain.start_mining()

    # ---------------- results ----------------------------
    return {
        "agents_stats": chain.stats["agents"],
        "tokens_stats": chain.stats["tokens"],
        "vaults_stats": chain.stats["vaults"],
        "amms_stats": chain.stats["amms"],
        "borrowed_eth_stats": chain.stats["borrowed_eth"],
        "borrowed_tokens_stats": chain.stats["borrowed_tokens"],
        "all_trades": pd.DataFrame(chain.all_trades),
        "final_block": num_blocks,
    }


# ------------------------------------------------------------------
# CLI test
# ------------------------------------------------------------------
if __name__ == "__main__":
    res = main()
    print("Simulation completed.")
    print(f"Trades executed: {len(res['all_trades'])}")
