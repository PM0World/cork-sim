# profiles.py ───────────────────────────────────────────────
from agents import (
    ds_long_term,
    redemption_arbitrage,
    repurchase_arbitrage,
    ct_speculation,
    looping,
)

# starter inventories – tweak anytime
SEED_CT = 1_000     # CT tokens the desk can sell immediately
SEED_DS = 1_000     # DS tokens the hedge fund can redeem

# ------------------------------------------------------------------ #
class SafeLoopingAgent(looping.LoopingAgent):
    def on_block_mined(self, block_number: int):
        try:
            super().on_block_mined(block_number)
        except ValueError as e:
            if "Not enough liquidity" in str(e):
                self.log_action("Skipped DS buy (vault empty)")
            else:
                raise

# YIELD SEEKER (LP) --------------------------------------------------
def create_yield_seeker(token: str, capital_eth: float):
    agent = SafeLoopingAgent(
        token_symbol=token,
        initial_borrow_rate=0.001,
        borrow_rate_changes={},
        max_ltv=0.60,
        name="Yield Seeker",
    )
    agent.wallet.deposit_eth(capital_eth)
    return [agent]

# HEDGE FUND ---------------------------------------------------------
def create_hedge_fund(token: str, capital_eth: float):
    ag = ds_long_term.DSLongTermAgent(
        token_symbol=token,
        buying_pressure=0.3,
        name="Hedge Fund",
    )
    ag.wallet.deposit_eth(capital_eth)
    # seed DS inventory so it can redeem on first dip
    ag.wallet.deposit_token(f"DS_{token}", SEED_DS)
    return [ag]

# ARBITRAGE DESK -----------------------------------------------------
def create_arb_desk(token: str, capital_eth: float):
    arb1 = redemption_arbitrage.RedemptionArbitrageAgent(
        token_symbol=token, name="Redemption Arb"
    )
    arb2 = repurchase_arbitrage.RepurchaseArbitrageAgent(
        token_symbol=token, name="Repurchase Arb"
    )
    arb3 = ct_speculation.CTShortTermAgent(
        token_symbol=token, buying_pressure=8, name="CT Short"
    )
    # split capital three ways
    for ag in (arb1, arb2, arb3):
        ag.wallet.deposit_eth(capital_eth / 3)
        ag.wallet.deposit_token(f"CT_{token}", SEED_CT)
    return [arb1, arb2, arb3]

# mapping ------------------------------------------------------------
PROFILE_CREATORS = {
    "Yield Seeker (LP)": create_yield_seeker,
    "Hedge Fund": create_hedge_fund,
    "Arbitrage Desk": create_arb_desk,
}

def make_agents(profile_name: str, token: str, capital_eth: float):
    return PROFILE_CREATORS[profile_name](token, capital_eth)
# ───────────────────────────────────────────────────────────
