# scenarios.py ──────────────────────────────────────────────
"""
Neutral stress-test presets.  Each returns a list of event dicts.
"""

def minor_liquidity_shock(depeg, token):
    return [
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Minor {depeg:.0%} depeg",
        }
    ]

def moderate_depeg_pressure(depeg, token):
    ev = []
    # steady liquidity drain for 300 blocks
    for blk in range(1, 301):
        ev.append(
            {
                "block": blk,
                "target": "amm",
                "method": "inject_liquidity",
                "token": token,
                "eth_delta": -3_000,
                "token_delta": -3_000,
                "note": "steady drain",
            }
        )
    ev.append(
        {
            "block": 301,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": "target depeg reached",
        }
    )
    return ev

def severe_depeg_stress(depeg, token):
    return [
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Severe {depeg:.0%} depeg",
        },
        {
            "block": 1,
            "target": "amm",
            "method": "inject_liquidity",
            "token": token,
            "eth_delta": -0.5,  # 50 % pool drained (negative means withdraw fraction)
            "token_delta": -0.5,
            "note": "50 % liquidity withdrawal",
        },
    ]

SCENARIOS = {
    "Minor Liquidity Shock": minor_liquidity_shock,
    "Moderate Depeg Pressure": moderate_depeg_pressure,
    "Severe Depeg Stress": severe_depeg_stress,
}
# ───────────────────────────────────────────────────────────
