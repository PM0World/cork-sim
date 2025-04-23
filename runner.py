# runner.py ─────────────────────────────────────────────────
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
    profile_capital example:
        {"Cautious Fund": 500, "Max Leveraged Whale": 10_000}
    """

    # 1. chain ----------------------------------------------------------------
    chain = Blockchain(
        num_blocks=cfg["blocks"],
        initial_eth_balance=cfg["initial_eth"],
        psm_expiry_after_block=cfg["blocks"],
        initial_eth_yield_per_block=cfg["eth_yield"],
        events_path=None,                      # we'll inject manually
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

    # 2. Earn vault agent ------------------------------------------------------
    chain.add_agents(*create_earn_vault(token, earn_appetite, earn_capital))

    # 3. other participant profiles -------------------------------------------
    for name, cap in profile_capital.items():
        chain.add_agents(*create_profile(name, token, cap))

    # 4. scenario events -------------------------------------------------------
    scenario_events = SCENARIOS[scenario_name](depeg_pct, token)
    chain.event_manager.events.extend(scenario_events)
    # keep them ordered by block just in case
    chain.event_manager.events.sort(key=lambda ev: ev["block"])

    # 5. run -------------------------------------------------------------------
    chain.start_mining(print_stats=False)

    # 6. pack results ----------------------------------------------------------
    return dict(
        tokens_stats=chain.stats["tokens"],
        agents_stats=chain.stats["agents"],
        all_trades=chain.all_trades,
        summary=summarize(chain.stats["tokens"]),
        final_block=chain.current_block,
    )
# ───────────────────────────────────────────────────────────
