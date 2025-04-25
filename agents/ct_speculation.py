import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp


class CTShortTermAgent(Agent):
    """
    CT-Short Term desk with:
    • Profit-adaptive buying_pressure   (your earlier enhancement)
    • MIN_TRADE_ETH                     (skip dust trades)
    • COOLDOWN_BLOCKS                   (1 trade every N blocks max)
    • Auto-borrow + auto-repay CT
    """

    MIN_TRADE_ETH   = 50.0      # skip if < 50 ETH notional
    COOLDOWN_BLOCKS = 5         # trade no more than once / 5 blocks

    # ------------------------------------------------------------------
    def __init__(
        self,
        token_symbol: str,
        buying_pressure: float,
        threshold: float = 0.01,
        name: str | None = None,
    ):
        super().__init__(name or f"CT Short Term for {token_symbol}")

        self.token_symbol = token_symbol
        self.lst_symbol   = token_symbol
        self.arp_history: list[float] = []

        self.buying_pressure = buying_pressure
        self.threshold       = threshold

        self.initial_eth_balance: float | None = None
        self._last_trade_block   = -9999   # for cool-down timing

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def current_profit_eth(self):
        bal = self.wallet.eth_balance
        if self.initial_eth_balance is None:
            self.initial_eth_balance = bal
            return 0.0
        return bal - self.initial_eth_balance

    def adjust_parameters(self):
        profit = self.current_profit_eth()

        # ±10 % aggression tweak
        self.buying_pressure *= 1.10 if profit > 0 else 0.90
        self.buying_pressure  = min(max(self.buying_pressure, 0.1), 5.0)

        self.log_action(
            f"Adj buying_pressure → {self.buying_pressure:.3f} (profit {profit:+.2f} ETH)"
        )

    # ------------------------------------------------------------------
    def on_block_mined(self, block_number: int):
        # --- periodic param re-tune -----------------------------------
        if block_number and block_number % 100 == 0:
            self.adjust_parameters()

        # --- cool-down guard ------------------------------------------
        if block_number - self._last_trade_block < self.COOLDOWN_BLOCKS:
            return

        vault        = self.blockchain.get_vault(self.token_symbol)
        ct_price     = vault.ct_eth_amm.price_of_one_token_in_eth()
        ds_price     = vault.ds_eth_amm.price_of_one_token_in_eth()
        native_yield = self.blockchain.tokens[self.lst_symbol].get(
            "yield_per_block", 0.0
        )

        # ARP + slope
        arp = calculate_arp(
            ds_price, native_yield,
            self.blockchain.num_blocks, self.blockchain.current_block,
        )
        self.arp_history.append(arp)

        if len(self.arp_history) >= 3:
            sharp_decline, sharp_incline, ewa_slope = detect_sharp_decline(
                self.arp_history, n=10, alpha=0.3,
                decline_threshold=-self.threshold,
                incline_threshold= self.threshold,
            )
        else:
            sharp_decline = sharp_incline = False
            ewa_slope     = 0

        # ===== BUY CT (cover) =========================================
        if sharp_incline:
            notional_eth  = self.buying_pressure * ewa_slope
            notional_eth  = max(notional_eth, 0.0)
            if notional_eth < self.MIN_TRADE_ETH:
                return

            volume_to_buy = min(notional_eth, self.wallet.eth_balance)
            vault.ct_eth_amm.swap_eth_for_token(self.wallet, volume_to_buy)
            self.log_action(f"Bought CT for {volume_to_buy:.1f} ETH")

            # repay borrowed CT if any
            borrowed = self.blockchain.borrowed_token.get(
                self.wallet, {}
            ).get(f"CT_{self.token_symbol}", 0.0)
            repay = min(borrowed,
                        self.wallet.token_balance(f"CT_{self.token_symbol}"))
            if repay:
                self.blockchain.repay_token(
                    self.wallet, f"CT_{self.token_symbol}", repay
                )
                self.log_action(f"Repaid {repay:.1f} CT")

            self.log_trade({
                "block":  block_number,
                "agent":  self.name,
                "token":  "CT",
                "volume": volume_to_buy / ct_price,
                "action": "buy",
                "reason": "sharp INcline",
            })
            self._last_trade_block = block_number
            return  # done for this block

        # ===== SELL (short) CT ========================================
        if sharp_decline:
            target_ct   = self.buying_pressure * (-ewa_slope) / ct_price
            target_ct   = max(target_ct, 0.0)
            notional_eth = target_ct * ct_price
            if notional_eth < self.MIN_TRADE_ETH:
                return

            current_ct  = self.wallet.token_balance(f"CT_{self.token_symbol}")
            need_borrow = max(target_ct - current_ct, 0)

            if need_borrow:
                self.blockchain.borrow_token(
                    self.wallet, f"CT_{self.token_symbol}", need_borrow
                )
                self.log_action(f"Borrowed {need_borrow:.1f} CT")

            vault.ct_eth_amm.swap_token_for_eth(self.wallet, target_ct)
            self.log_action(f"Sold {target_ct:.1f} CT")

            self.log_trade({
                "block":  block_number,
                "agent":  self.name,
                "token":  "CT",
                "volume": target_ct,
                "action": "sell",
                "reason": "sharp DEcline",
            })
            self._last_trade_block = block_number
