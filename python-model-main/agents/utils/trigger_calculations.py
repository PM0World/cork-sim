import numpy as np
import pandas as pd

def calculate_arp(token_price, lst_yield, num_blocks, current_block):
    """
    Calculate the ARP (Annualized Risk Premium) based on the current Token price, LST yield, and block numbers.

    :param token_price: Current price of Token.
    :param lst_yield: Current yield of LST.
    :param num_blocks: Total number of blocks.
    :param current_block: Current block number.
    :return: ARP value.
    """
    full_expiry_token_price = token_price * (num_blocks / (num_blocks - current_block + 1))
    full_expiry_yield = lst_yield * num_blocks
    arp = full_expiry_yield - full_expiry_token_price
    return arp

def detect_sharp_decline(prices, n=3, alpha=0.3, decline_threshold=-0.05, incline_threshold=0.05):
    """
    Detects a sharp decline in a price series using an exponentially weighted average slope.

    :param prices: List of prices (time series).
    :param n: Number of recent points to consider for slope calculation.
    :param alpha: Smoothing factor for the exponentially weighted average.
    :param threshold: Threshold for detecting a sharp decline (e.g., slope threshold).
    :return: Boolean indicating if a sharp decline is detected.
    """
    if len(prices) < n:
        False, False, 0.0

    # Calculate slopes of the last n points
    slopes = np.diff(prices[-n:])

    # Compute the exponentially weighted average of the slopes
    ewa_slope = pd.Series(slopes).ewm(alpha=alpha).mean().iloc[-1]

    # Check if the EWA slope indicates a sharp decline
    sharp_decline = ewa_slope < decline_threshold
    sharp_incline = ewa_slope > incline_threshold

    return sharp_decline, sharp_incline, ewa_slope