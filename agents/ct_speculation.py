import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp


class CTShortTermAgent(Agent):
    """
    Enhanced CTShortTermAgent

    Speculates on short-term moves of CT relative to LST yields.
    • Buys CT on sharp upward ARP trends  (= cheap DS, risk subsiding).
    • Shorts CT on sharp downward ARP trends (= panic, DS expensive).

    Enhancements:
    • Historical state and profit tracking.
    • Dynamic adjustment of buying_pressure based on historical profitability.
    • Automatic CT borrowing and repayment logic preserved.
    """

    def __init__(
        self,
        token_symbol: str,
        buying_pressure: float,
        threshold: float = 0.01,
        name: str | None = None,
    ):
        super().__init__(name or f"CT Short Term for {token_symbol}")

        self.token_symbol = token_symbol
        self.lst_symbol = token_symbol
        self.arp_history: list[float] = []

        self.buying_pressure = buying_pressure
        self.threshold = threshold

    def adjust_parameters(self):
        profit = self.current_profit_eth()

        # Adjust buying pressure based on profitability
        if profit > 0:
            self.buying_pressure *= 1.1  # Increase aggressiveness by 10%
        else:
            self.buying_pressure *= 0.9  # Decrease aggressiveness by 10%

        # Clamp within sensible bounds
        self.buying_pressure = min(max(self.buying_pressure, 0.1), 5.0)

        # Log parameter adjustment
        self.log_action(
            f"Adjusted buying pressure to {self.buying_pressure:.4f} based on profit of {profit:.4f} ETH"
        )

    def on_block_mined(self, block_number: int):
        # Adjust parameters periodically every 100 blocks
        if block_number % 100 == 0 and block_number > 0:
            self.adjust_parameters()

        vault = self.blockchain.get_vault(self.token_symbol)
        ct_price = vault.ct_eth_amm.price_of_one_token_in_eth()
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        native_yield = self.blockchain.tokens[self.lst_symbol].get("yield_per_block", 0.0)

        arp = calculate_arp(
            ds_price, native_yield,
            self.blockchain.num_blocks,
            self.blockchain.current_block,
        )
        self.arp_history.append(arp)

        if len(self.arp_history) >= 3:
            sharp_decline, sharp_incline, ewa_slope = detect_sharp_decline(
                self.arp_history, n=10, alpha=0.3,
                decline_threshold=-self.threshold, incline_threshold=self.threshold,
            )
        else:
            sharp_decline = sharp_incline = False
            ewa_slope = 0

        # ===== BUY CT on sharp incline ================================
        if sharp_incline:
            notional_eth = self.buying_pressure * ewa_slope
            volume_to_buy = min(notional_eth, self.wallet.eth_balance)

            if volume_to_buy > 0:
                vault.ct_eth_amm.swap_eth_for_token(self.wallet, volume_to_buy)
                self.log_action(f"Bought CT with {volume_to_buy:.4f} ETH")

                borrowed = (
                    self.blockchain.borrowed_token
                    .get(self.wallet, {})
                    .get(f"CT_{self.token_symbol}", 0.0)
                )
                repay_amt = min(
                    borrowed,
                    self.wallet.token_balance(f"CT_{self.token_symbol}")
                )
                if repay_amt > 0:
                    self.blockchain.repay_token(
                        self.wallet, f"CT_{self.token_symbol}", repay_amt
                    )
                    self.log_action(f"Repaid {repay_amt:.4f} borrowed CT")

                self.log_trade({
                    "block": block_number,
                    "agent": self.name,
                    "token": "CT",
                    "volume": volume_to_buy / ct_price,
                    "action": "buy",
                    "reason": "sharp INcline",
                    "additional_info": {
                        "arp": arp,
                        "ewa_slope": ewa_slope,
                        "arp_history": self.arp_history[-12:],
                    },
                })

        # ===== SELL (short) CT on sharp decline =======================
        if sharp_decline:
            target_ct = max(
                self.buying_pressure * (-ewa_slope) / ct_price, 0,
            )
            current_ct = self.wallet.token_balance(f"CT_{self.token_symbol}")
            need_borrow = max(target_ct - current_ct, 0)

            if need_borrow > 0:
                self.blockchain.borrow_token(
                    self.wallet, f"CT_{self.token_symbol}", need_borrow
                )
                self.log_action(f"Borrowed {need_borrow:.4f} CT for short")

            volume_to_sell = target_ct
            if volume_to_sell > 0:
                vault.ct_eth_amm.swap_token_for_eth(self.wallet, volume_to_sell)
                self.log_action(f"Sold {volume_to_sell:.4f} CT")

                self.log_trade({
                    "block": block_number,
                    "agent": self.name,
                    "token": "CT",
                    "volume": volume_to_sell,
                    "action": "sell",
                    "reason": "sharp DEcline",
                    "additional_info": {
                        "arp": arp,
                        "ewa_slope": ewa_slope,
                        "arp_history": self.arp_history[-12:],
                    },
                })
