# scenarios.py ─────────────────────────────────────────────────────────
"""
Deterministic stress-test presets for the Cork simulator.

Each function returns a *list of event dictionaries* understood by
EventManager.  We only touch the AMM, so `target` is always "amm".

Supported event schema
----------------------
{
    "block":  <int>,                  # 1-based block height
    "target": "amm",

    # --- price jump ---
    "method":     "set_price",        # override token price instantly
    "token":      <symbol>,           # e.g. "stETH"
    "new_price":  <float>,            # price in redemption asset

    # OR
    # --- liquidity change ---
    "method":      "inject_liquidity",
    "token":       <symbol>,
    "eth_delta":   <float>,           # +ve add, −ve withdraw
    "token_delta": <float>,           # same unit as token
                                      # if abs(value) < 1 treat as *fraction*
    "note":        <str>,             # human-readable description
}
"""

# ---------------------------------------------------------------------
# 1. Minor Liquidity Shock → quick dip then full recovery
# ---------------------------------------------------------------------
def minor_liquidity_shock(depeg: float, token: str):
    """
    • Block 1   : small 1-off depeg
    • Block 200 : peg fully restored
    """
    return [
        # ↓ 1-off depeg
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Minor {depeg:.0%} depeg",
        },
        # ↑ recovery
        {
            "block": 200,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1.00,
            "note": "Peg restored",
        },
    ]


# ---------------------------------------------------------------------
# 2. Moderate Depeg Pressure → slow drain, dip, rebound
# ---------------------------------------------------------------------
def moderate_depeg_pressure(depeg: float, token: str):
    """
    • Blocks 1-300 : linear liquidity drain (simulates steady selling)
    • Block 301    : target depeg hit
    • Block 450    : full re-peg (positive shock)
    """
    events = []

    # steady liquidity removal
    for blk in range(1, 301):
        events.append(
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

    # ↓ reach depeg price
    events.append(
        {
            "block": 301,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": "target depeg reached",
        }
    )

    # ↑ rebound / re-peg
    events.append(
        {
            "block": 450,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1.00,
            "note": "market confidence returns",
        }
    )

    return events


# ---------------------------------------------------------------------
# 3. Severe Depeg Stress → big dip + 50 % liquidity yank + late recovery
# ---------------------------------------------------------------------
def severe_depeg_stress(depeg: float, token: str):
    """
    • Block 1   : instant deep depeg + half of liquidity yanked
    • Block 600 : partial recovery (back to 1 – depeg/3)
    """
    return [
        # ↓ crash
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Severe {depeg:.0%} depeg",
        },
        # 50 % liquidity removal
        {
            "block": 1,
            "target": "amm",
            "method": "inject_liquidity",
            "token": token,
            "eth_delta": -0.5,          # interpreted as −50 %
            "token_delta": -0.5,
            "note": "50 % liquidity withdrawal",
        },
        # ↑ late partial recovery
        {
            "block": 600,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg / 3,  # e.g. −10 % → −3.33 % residual
            "note": "partial re-peg",
        },
    ]


# ---------------------------------------------------------------------
# Scenario registry
# ---------------------------------------------------------------------
SCENARIOS = {
    "Minor Liquidity Shock":   minor_liquidity_shock,
    "Moderate Depeg Pressure": moderate_depeg_pressure,
    "Severe Depeg Stress":     severe_depeg_stress,
}
# ───────────────────────────────────────────────────────────
