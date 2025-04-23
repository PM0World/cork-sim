# profiles.py  ─────────────────────────────────────────────
"""
Map friendly profile names → ready-made Agent objects.
Edit values here to tune behaviour without touching UI or core logic.
"""

from agents import (
    ds_long_term,
    ds_speculation,
    ct_speculation,
    looping,
)

def cautious_fund(token):
    """Small buyer of DS that exits early."""
    return [
        ds_long_term.DSLongTermAgent(
            token_symbol=token,
            buying_pressure=0.2,
            name="Cautious Fund"
        )
    ]

def yield_seeker(token):
    """Buys DS for yield, trades around small depegs."""
    return [
        ds_speculation.DSShortTermAgent(
            token_symbol=token,
            threshold=0.03,
            name="Yield Seeker"
        )
    ]

def max_leveraged_whale(token):
    """Aggressive looping whale with high LTV."""
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
    "Max Leveraged Whale": max_leveraged_whale,
}

# public helper -------------------------------------------------------
def create_profile(profile_name: str, token: str, count: int = 1):
    """Return *count* agent objects for a profile."""
    agents = []
    for _ in range(count):
        agents.extend(PROFILE_FACTORIES[profile_name](token))
    return agents
# ────────────────────────────────────────────────────────────────────
