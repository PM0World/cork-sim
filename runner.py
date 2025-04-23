# runner.py  ─────────────────────────────────────────────────
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM
from profiles import make_agents
from scenarios import SCENARIOS
from analysis import summarize

def run_simulation(
    scenario_name: str,
    depeg_pct: float,
    capital_map: dict[str, float],   # {"Yield Seeker (LP)":5000, ...}
    cfg: dict,
):
    # ── 1. chain ------------------------------------------------------
    chain = Blockchain(
        num_blocks=cfg["blocks"],
        initial_eth_balance=cfg["initial_eth"],
        psm_expiry_after_block=cfg["blocks"],
        initial_eth_yield_per_block=cfg["eth_yield"],
        events_path=None,
    )

    token = cfg["token"]
    amm = UniswapV2AMM(
        token_symbol=token,
        reserve_eth=cfg["amm_eth"],
        reserve_token=cfg["amm_token"],
        fee=cfg["amm_fee"],
    )
    # bigger DS reserve (risk 0.30)
    chain.add_token(
        token=token,
        initial_agent_balance=0,
        amm=amm,
        risk=0.30,
        initial_yield_per_block=cfg["lst_yield"],
    )

    # ── 2. add agents -------------------------------------------------
    for name, cap in capital_map.items():
        chain.add_agents(*make_agents(name, token, cap))

    # ── 3. inject scenario events ------------------------------------
    events = SCENARIOS[scenario_name](depeg_pct, token)
    for ev in events:
        ev.setdefault("type", "action")
    chain.event_manager.events.extend(events)
    chain.event_manager.events.sort(key=lambda ev: ev["block"])

    # ── 4. run & collect results -------------------------------------
    chain.start_mining(print_stats=False)
    return {
        "tokens_stats": chain.stats["tokens"],
        "agents_stats": chain.stats["agents"],
        "all_trades": chain.all_trades,
        "summary": summarize(chain.stats["tokens"]),
    }
# ───────────────────────────────────────────────────────────
