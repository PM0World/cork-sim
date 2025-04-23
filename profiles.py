# profiles.py ───────────────────────────────────────────────
"""
Cork-aligned participant categories:

• Yield Seeker (LP)  – seeks staking & LP yield
• Hedge Fund         – buys DS for downside hedge
• Arbitrage Desk     – redemption / repurchase / CT-short

Each create_* function returns ONE agent.  The UI lets user size each
category in ETH; the runner deposits that ETH in the agent's wallet.
"""

from agents import (
    lst_maximalist,
    lv_depositor,
    ds_long_term,
    redemption_arbitrage,
    repurchase_arbitrage,
    ct_speculation,
    looping,
)

# ------------------------------------------------------------------ #
# Safe looping variant: skips DS buy if vault has no liquidity
class SafeLoopingAgent(looping.LoopingAgent):
    def on_block_mined(self, block_number: int):
        try:
            super().on_block_mined(block_number)
        except ValueError as e:
            if "Not enough liquidity to buy DS" in str(e):
                # graceful skip
                self.log_action("Skipped DS buy – vault empty")
            else:
                raise

# ------------------------------------------------------------------ #
def create_yield_seeker(token: str, capital_eth: float):
    """LP + moderate looping."""
    agent = SafeLoopingAgent(
        token_symbol=token,
        initial_borrow_rate=0.001,
        borrow_rate_changes={},
        max_ltv=0.60,
        name="Yield Seeker",
    )
    agent.wallet.deposit_eth(capital_eth)
    return [agent]


def create_hedge_fund(token: str, capital_eth: float):
    agent = ds_long_term.DSLongTermAgent(
        token_symbol=token,
        buying_pressure=0.3,
        name="Hedge Fund",
    )
    agent.wallet.deposit_eth(capital_eth)
    return [agent]


def create_arb_desk(token: str, capital_eth: float):
    """Bundle three arbitrage strategies into one desk."""
    arb1 = redemption_arbitrage.RedemptionArbitrageAgent(
        token_symbol=token, name="Redemption Arb"
    )
    arb2 = repurchase_arbitrage.RepurchaseArbitrageAgent(
        token_symbol=token, name="Repurchase Arb"
    )
    arb3 = ct_speculation.CTShortTermAgent(
        token_symbol=token, buying_pressure=8, name="CT Short"
    )
    for ag in (arb1, arb2, arb3):
        ag.wallet.deposit_eth(capital_eth / 3)
    return [arb1, arb2, arb3]


PROFILE_CREATORS = {
    "Yield Seeker (LP)": create_yield_seeker,
    "Hedge Fund": create_hedge_fund,
    "Arbitrage Desk": create_arb_desk,
}

# helper used by runner ------------------------------------------------
def make_agents(profile_name: str, token: str, capital_eth: float):
    return PROFILE_CREATORS[profile_name](token, capital_eth)
# ───────────────────────────────────────────────────────────
