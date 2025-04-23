# analysis.py ───────────────────────────────────────────────
import pandas as pd

def summarize(tokens_df: pd.DataFrame, peg=1.0):
    price = tokens_df["price"].values
    min_p  = price.min()
    min_pct = 1 - min_p / peg
    under = (price < peg * 0.99).sum()
    return dict(
        min_price=float(min_p),
        min_pct=float(min_pct),
        blocks_under_peg=int(under),
    )
# ───────────────────────────────────────────────────────────
