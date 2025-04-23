# analysis.py  ──────────────────────────────────────────────
import pandas as pd

def summarize(tokens_df: pd.DataFrame, peg=1.0):
    """Return dict with min pct and time under peg."""
    price = tokens_df["price"].values
    min_price = price.min()
    min_pct   = 1 - min_price / peg
    under_idx = (price < peg * 0.99).nonzero()[0]   # >1% off-peg
    duration  = len(under_idx)
    return {
        "min_price": float(min_price),
        "min_pct":  float(min_pct),
        "blocks_under_peg": int(duration),
    }
# ──────────────────────────────────────────────────────────
