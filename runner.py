# runner.py  ─────────────────────────────────────────────────────────
"""
High-level wrapper that:
1. Builds a Blockchain instance with given market config
2. Adds an Earn-vault agent plus other profile agents
3. Injects scenario events
4. Runs the chain and returns tidy results
"""

from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM
from profiles import create_profile, create_earn_vault
from scenarios import SCENARIOS
from analysis import summarize


def run_simulation(
    scenario_name: str,
    depeg_pct: float,
    profile_capital: dict[str, float],
    earn_appetite: str,
    earn_capital: float,
    cfg: dict,
):
    """
    Parameters
    ----------
    scenario_name : str
        Key in SCENARIOS, e.g. "Minor Liquidity Shock"
    depeg_pct : float
        0 → 1, so 0.1 == 10 % depeg
    profile_capital : dict[str, float]
        e.g. {"Cautious Fund": 500, "Max Leveraged Whale": 10000}
    earn_appetite : str
        "Passive" | "Moderate" | "Max"
    earn_capital : float
        ETH notional for the Earn vault agent
    cfg : dict
        {
            token, initial_eth, blocks, eth_yield,
            lst_yield, amm_eth, amm_token, amm_fee
        }
    """

    # ── 1. Build chain ──────────────────────────────────────────────
    chain = Blockchain(
        num_blocks=cfg["blocks"],
        initial_eth_balance=cfg["initial_eth"],
        psm_expiry_after_block=cfg["blocks"],
        initial_eth_yield_per_block=cfg["eth_yield"],
        events_path=None,  # we inject events manually
    )

    token = cfg["token"]
    amm = UniswapV2AMM(
        token_symbol=token,
        reserve_eth=cfg["amm_eth"],
        reserve_token=cfg["amm_token"],
        fee=cfg["amm_fee"],
    )
    chain.add_token(
        token=token,
        initial_agent_balance=0,
        amm=amm,
        risk=0.02,
        initial_yield_per_block=cfg["lst_yield"],
    )

    # ── 2. Earn vault agent ─────────────────────────────────────────
    chain.add_agents(*create_earn_vault(token, earn_appetite, earn_capital))

    # ── 3. Other participant profiles ──────────────────────────────
    for name, capital in profile_capital.items():
        chain.add_agents(*create_profile(name, token, capital))

    # ── 4. Scenario events ─────────────────────────────────────────
    scenario_events = SCENARIOS[scenario_name](depeg_pct, token)
    for ev in scenario_events:
        ev.setdefault("type", "action")  # ensure EventManager has this key
    chain.event_manager.events.extend(scenario_events)
    chain.event_manager.events.sort(key=lambda ev: ev["block"])

    # ── 5. Run chain ───────────────────────────────────────────────
    chain.start_mining(print_stats=False)

    # ── 6. Collect & return results ────────────────────────────────
    return {
        "tokens_stats": chain.stats["tokens"],
        "agents_stats": chain.stats["agents"],
        "all_trades": chain.all_trades,
        "summary": summarize(chain.stats["tokens"]),
        "final_block": chain.current_block,
    }
# ────────────────────────────────────────────────────────────────────
