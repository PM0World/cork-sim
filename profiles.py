# profiles.py  ─────────────────────────────────────────────────────────
from agents import (
    ds_long_term,
    redemption_arbitrage,
    repurchase_arbitrage,
    ct_speculation,
    looping,
)

SEED_CT = 1_000   # starter CT per arb agent
SEED_DS = 1_000   # starter DS for hedge funds

# ── Safe looping agent (skips if vault dry) ──────────────────────────
class SafeLoopingAgent(looping.LoopingAgent):
    def on_block_mined(self, block_number: int):
        try:
            super().on_block_mined(block_number)
        except ValueError as e:
            if "Not enough liquidity" in str(e):
                self.log_action("Skipped DS buy (vault empty)")
            else:
                raise

# ── Profile builders ─────────────────────────────────────────────────
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
        buying_pressure=0.3,
        name="Hedge Fund",
    )
    ag.wallet.deposit_eth(capital_eth)
    ag.wallet.deposit_token(f"DS_{token}", SEED_DS)
    return [ag]

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
    for ag in (arb1, arb2, arb3):
        ag.wallet.deposit_eth(capital_eth / 3)
        ag.wallet.deposit_token(f"CT_{token}", SEED_CT)
    return [arb1, arb2, arb3]

PROFILE_CREATORS = {
    "Yield Seeker (LP)": create_yield_seeker,
    "Hedge Fund":        create_hedge_fund,
    "Arbitrage Desk":    create_arb_desk,
}

def make_agents(profile: str, token: str, capital_eth: float):
    return PROFILE_CREATORS[profile](token, capital_eth)
# ─────────────────────────────────────────────────────────────────────
