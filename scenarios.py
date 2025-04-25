# scenarios.py ─────────────────────────────────────────────────────────
"""
Deterministic stress-test presets for the Cork simulator.

All events target the AMM only; schema:

    { "block": <int>,
      "target": "amm",
      "method": "set_price" | "inject_liquidity",
      ... }

Rules
-----
• Negative eth_delta / token_delta ≥ |1| = absolute units.
• −1 < value < 0  → fraction of *current* reserves (e.g. −0.5 = −50 %).

Colour markers (“color” key) are ignored by core logic but the UI can
use them to paint chart annotations.
"""

# ------------------------------------------------------------------ #
# 1. Minor Liquidity Shock  • quick dip then full recovery
# ------------------------------------------------------------------ #
def minor_liquidity_shock(depeg: float, token: str):
    return [
        # ↓ peg dip
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Minor {depeg:.0%} depeg",
            "color": "red",
        },
        # ↑ full restoration
        {
            "block": 200,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1.00,
            "note": "Peg restored",
            "color": "green",
        },
    ]


# ------------------------------------------------------------------ #
# 2. Moderate Depeg Pressure  • slow drain, dip, rebound
# ------------------------------------------------------------------ #
def moderate_depeg_pressure(depeg: float, token: str):
    events = []

    # steady drain 300 blocks
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

    # ↓ depeg hit
    events.append(
        {
            "block": 301,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": "target depeg reached",
            "color": "red",
        }
    )

    # ↑ rebound
    events.append(
        {
            "block": 450,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1.00,
            "note": "market confidence returns",
            "color": "green",
        }
    )

    return events


# ------------------------------------------------------------------ #
# 3. Severe Depeg Stress  • deep dip + 50 % yank + late recovery
# ------------------------------------------------------------------ #
def severe_depeg_stress(depeg: float, token: str):
    return [
        # ↓ instant crash
        {
            "block": 1,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg,
            "note": f"Severe {depeg:.0%} depeg",
            "color": "red",
        },
        # yank 50 % liquidity
        {
            "block": 1,
            "target": "amm",
            "method": "inject_liquidity",
            "token": token,
            "eth_delta": -0.5,       # −50 % reserves
            "token_delta": -0.5,
            "note": "50 % liquidity withdrawal",
        },
        # ↑ partial re-peg
        {
            "block": 600,
            "target": "amm",
            "method": "set_price",
            "token": token,
            "new_price": 1 - depeg / 3,   # e.g. −10 % → −3.33 %
            "note": "partial recovery",
            "color": "orange",
        },
    ]


# ------------------------------------------------------------------ #
# 4. Three-Minute Demo Arc  • dip → panic → overshoot → settle
# ------------------------------------------------------------------ #
def demo_arc(token: str):
    return [
        {"block": 50,  "target": "amm", "method": "set_price",
         "token": token, "new_price": 0.97, "note": "early wobble", "color": "orange"},
        {"block": 120, "target": "amm", "method": "set_price",
         "token": token, "new_price": 0.90, "note": "panic low",    "color": "red"},
        {"block": 240, "target": "amm", "method": "set_price",
         "token": token, "new_price": 1.05, "note": "overshoot ↑",  "color": "green"},
        {"block": 300, "target": "amm", "method": "set_price",
         "token": token, "new_price": 1.00, "note": "settle 1:1",   "color": "green"},
    ]


# ------------------------------------------------------------------ #
# Registry
# ------------------------------------------------------------------ #
SCENARIOS = {
    "Minor Liquidity Shock":   minor_liquidity_shock,
    "Moderate Depeg Pressure": moderate_depeg_pressure,
    "Severe Depeg Stress":     severe_depeg_stress,
    "Three-Minute Demo":       lambda pct, t: demo_arc(t),  # pct ignored
}
# ───────────────────────────────────────────────────────────
