# runner.py  ────────────────────────────────────────────────
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM
from profiles import create_profile
from scenarios import SCENARIOS
from analysis import summarize

def run_simulation(
    scenario_name: str,
    depeg_pct: float,
    profile_config: dict[str, int],
    market_cfg: dict,
):
    """
    scenario_name: key in SCENARIOS
    depeg_pct    : 0-1 float (e.g. 0.1 == 10 %)
    profile_config: {"Cautious Fund":2, "Max Leveraged Whale":1}
    market_cfg: {
        token, initial_eth, blocks, eth_yield,
        amm_eth, amm_token, amm_fee
    }
    """

    # 1. chain
    chain = Blockchain(
        num_blocks=market_cfg["blocks"],
        initial_eth_balance=market_cfg["initial_eth"],
        psm_expiry_after_block=market_cfg["blocks"],
        initial_eth_yield_per_block=market_cfg["eth_yield"],
        events_path=None,
    )

    token = market_cfg["token"]
    amm = UniswapV2AMM(
        token_symbol=token,
        reserve_eth=market_cfg["amm_eth"],
        reserve_token=market_cfg["amm_token"],
        fee=market_cfg["amm_fee"],
    )
    chain.add_token(
        token=token,
        initial_agent_balance=0,
        amm=amm,
        risk=0.02,
        initial_yield_per_block=market_cfg["lst_yield"],
    )

    # 2. agents
    for prof, cnt in profile_config.items():
        agents = create_profile(prof, token, cnt)
        chain.add_agents(*agents)

    # 3. scenario events
    events = SCENARIOS[scenario_name](depeg_pct, token)
    for ev in events:
        chain.event_manager.add(ev)

    # 4. run
    chain.start_mining(print_stats=False)

    return {
        "tokens_stats": chain.stats["tokens"],
        "agents_stats": chain.stats["agents"],
        "all_trades": chain.all_trades,
        "summary": summarize(chain.stats["tokens"]),
        "final_block": chain.current_block,
    }
# ──────────────────────────────────────────────────────────
