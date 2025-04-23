# profiles.py ───────────────────────────────────────────────
"""
High-level participant profiles → ready Agent objects.
Capital is injected after instantiation so one agent = one profile.
"""

from agents import (
    ds_long_term,
    ds_speculation,
    looping,
)

# Earn vault appetite → LoopingAgent params
EARN_APPETITES = {
    "Passive": dict(loop_count=0, max_ltv=0.0),
    "Moderate": dict(loop_count=2, max_ltv=0.60),
    "Max": dict(loop_count=5, max_ltv=0.85),
}

def cautious_fund(token: str):
    return [
        ds_long_term.DSLongTermAgent(
            token_symbol=token,
            buying_pressure=0.2,
            name="Cautious Fund",
        )
    ]

def yield_seeker(token: str):
    return [
        ds_speculation.DSShortTermAgent(
            token_symbol=token,
            threshold=0.03,
            name="Yield Seeker",
        )
    ]

def leverage_whale(token: str):
    # whale uses highest LTV looping
    return [
        looping.LoopingAgent(
            token_symbol=token,
            initial_borrow_rate=0.001,
            borrow_rate_changes={},
            max_ltv=0.85,
            name="Leverage Whale",
        )
    ]

PROFILE_FACTORIES = {
    "Cautious Fund": cautious_fund,
    "Yield Seeker": yield_seeker,
    "Max Leveraged Whale": leverage_whale,
}

# ------------------------------------------------------------------ #
def create_profile(profile_name: str, token: str, capital_eth: float):
    """Return one agent with the requested ETH capital."""
    agent = PROFILE_FACTORIES[profile_name](token)[0]
    agent.wallet.deposit_eth(capital_eth)
    return [agent]

def create_earn_vault(token: str, appetite: str, capital_eth: float):
    """Return a single LoopingAgent matching the Earn appetite."""
    cfg = EARN_APPETITES[appetite]
    ag = looping.LoopingAgent(
        token_symbol=token,
        initial_borrow_rate=0.001,
        borrow_rate_changes={},
        max_ltv=cfg["max_ltv"],
        name=f"Earn ({appetite})",
    )
    ag.wallet.deposit_eth(capital_eth)
    return [ag]
# ───────────────────────────────────────────────────────────
