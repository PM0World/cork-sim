# profiles.py ───────────────────────────────────────────────────────────
"""
Defines ready-made participant mixes that map 1-to-1 to Cork’s product
primitives:

* Yield Seeker (LP)    →  Earn / Loop vaults
* Hedge Fund           →  Hedge (holds DS, redeems in panic)
* Arbitrage Desk       →  Trade (CT short, redemption + repurchase arb)

Starter CT / DS / ETH inventories are sized so that every run, even at
small capital levels, shows *all* trade types (buy, sell, redeem, repay).
"""

from agents import (
    ds_long_term,
    redemption_arbitrage,
    repurchase_arbitrage,
    ct_speculation,
    looping,
)

# Seed inventory per agent
SEED_CT = 2_000     # enough to short > one block
SEED_DS = 2_000     # enough to redeem during panic


# ───────────────────────────────────────────────────────────
# SafeLoopingAgent: skips on-vault-empty instead of error
# ───────────────────────────────────────────────────────────
class SafeLoopingAgent(looping.LoopingAgent):
    def on_block_mined(self, block_number: int):
        try:
            super().on_block_mined(block_number)
        except ValueError as e:
            if "Not enough liquidity" in str(e):
                self.log_action("Skipped DS buy (vault empty)")
            else:
                raise


# ───────────────────────────────────────────────────────────
# Profile builders
# ───────────────────────────────────────────────────────────
def create_yield_seeker(token: str, capital_eth: float):
    ag = SafeLoopingAgent(
        token_symbol=token,
        initial_borrow_rate=0.001,
        borrow_rate_changes={},
        max_ltv=0.60,
        name="Yield Seeker (LP)",
    )
    ag.wallet.deposit_eth(capital_eth)
    return [ag]


def create_hedge_fund(token: str, capital_eth: float):
    ag = ds_long_term.DSLongTermAgent(
        token_symbol=token,
        buying_pressure=0.30,
        name="Hedge Fund",
    )
    ag.wallet.deposit_eth(capital_eth)
    ag.wallet.deposit_token(f"DS_{token}", SEED_DS)
    return [ag]


def create_arb_desk(token: str, capital_eth: float):
    # three distinct desks under one “Arbitrage Desk” umbrella
    arb_red = redemption_arbitrage.RedemptionArbitrageAgent(
        token_symbol=token, name="Redemption Arb"
    )
    arb_rep = repurchase_arbitrage.RepurchaseArbitrageAgent(
        token_symbol=token, name="Repurchase Arb"
    )
    arb_ct  = ct_speculation.CTShortTermAgent(
        token_symbol=token, buying_pressure=8, name="CT Short"
    )

    for ag in (arb_red, arb_rep, arb_ct):
        ag.wallet.deposit_eth(capital_eth / 3)
        ag.wallet.deposit_token(f"CT_{token}", SEED_CT)

    return [arb_red, arb_rep, arb_ct]


# Registry
PROFILE_CREATORS = {
    "Yield Seeker (LP)": create_yield_seeker,
    "Hedge Fund":        create_hedge_fund,
    "Arbitrage Desk":    create_arb_desk,
}


def make_agents(profile: str, token: str, capital_eth: float):
    return PROFILE_CREATORS[profile](token, capital_eth)
# ───────────────────────────────────────────────────────────
