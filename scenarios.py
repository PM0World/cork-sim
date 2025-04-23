# scenarios.py  ─────────────────────────────────────────────
"""
Scenario presets → a function that yields EventManager-ready dicts.
Each scenario returns a list[dict] generated from the requested depeg %.
"""

def flash_crash(depeg_pct: float, token: str):
    """
    Instant sell wall that drops price by `depeg_pct` at block 1,
    AMM fee raised to slow recovery at block 5.
    """
    return [
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg_pct,
            "note": f"Flash crash {depeg_pct:.0%} depeg",
        },
        {
            "block": 5,
            "target": "amm",
            "method": "update_fee",
            "token": token,
            "new_fee": 0.03,
            "note": "Temporary fee hike to dampen arb",
        },
    ]


def liquidity_drain(depeg_pct: float, token: str):
    """
    Gradual liquidity removal over 100 blocks → price slides `depeg_pct`.
    """
    events = []
    # remove 1% liquidity each block for 100 blocks
    for blk in range(1, 101):
        events.append(
            {
                "block": blk,
                "target": "amm",
                "method": "inject_liquidity",
                "token": token,
                "eth_delta": -10_000,   # negative = withdraw
                "token_delta": -10_000,
                "note": "slow drain",
            }
        )
    # At the end force price to min level
    events.append(
        {
            "block": 101,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg_pct,
            "note": "Reached target depeg",
        }
    )
    return events


SCENARIOS = {
    "Flash Crash": flash_crash,
    "Liquidity Drain": liquidity_drain,
}
# ────────────────────────────────────────────────────────────────────
