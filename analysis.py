# analysis.py ─────────────────────────────────────────────────────────
import pandas as pd

def summarize(tokens_df: pd.DataFrame, psms_df: pd.DataFrame | None, peg=1.0):
    """
    tokens_df : chain.stats['tokens']
    psms_df   : chain.stats['psms']   (may be None)
    """
    price = tokens_df["price"].values
    min_p = price.min()
    min_pct = 1 - min_p / peg
    under = int((price < peg * 0.99).sum())

    draw_pct = 0.0
    if psms_df is not None and not psms_df.empty:
        start = psms_df.iloc[0]["eth_reserve"]
        min_reserve = psms_df["eth_reserve"].min()
        draw_pct = (start - min_reserve) / start if start else 0.0

    return dict(
        min_price=float(min_p),
        min_pct=float(min_pct),
        blocks_under_peg=under,
        psm_drawdown_pct=float(draw_pct),
    )
