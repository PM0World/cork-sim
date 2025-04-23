from simulator.agent import Agent
import numpy as np


class DSLongTermAgent(Agent):
    """
    Buys DS when its price is attractive vs. projected yield; sells
    when the LST de-pegs.  Added safety guards so it never tries to
    trade more tokens than it owns (or than the vault can handle).
    """

    def __init__(
        self,
        token_symbol: str,
        buying_pressure: float,
        k: float = 5,
        depeg_threshold: float = 0.98,
        name: str | None = None,
    ):
        agent_name = name or f"DSLongTermAgent for {token_symbol}"
        super().__init__(agent_name)

        self.token_symbol = token_symbol         # e.g. "stETH"
        self.lst_symbol = token_symbol
        self.buying_pressure = buying_pressure   # [0–1] scaling for buys
        self.k = k                               # curvature for exp()
        self.depeg_threshold = depeg_threshold
        self.lst_price_history: list[float] = []

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------
    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        lst_price = vault.lst_eth_amm.price_of_one_token_in_eth()

        lst_yield_per_block = (
            self.blockchain.tokens[self.lst_symbol].get("yield_per_block", 0.0)
            * self.blockchain.num_blocks
        )

        buying_intent = self.calculate_buying_intent(ds_price, lst_yield_per_block)
        amount_eth_to_buy_ds = (
            buying_intent * self.wallet.eth_balance * self.buying_pressure
        )

        # ---------- BUY DS (guarded) ----------
        if amount_eth_to_buy_ds > 0:
            try:
                self.log_action(f"Trying to buy DS with {amount_eth_to_buy_ds:.4f} ETH")
                vault.buy_ds(self.wallet, amount_eth_to_buy_ds)
                self.log_action("   ✔ buy succeeded")
                self.log_trade(
                    {
                        "block": block_number,
                        "agent": self.name,
                        "token": "DS",
                        "volume": amount_eth_to_buy_ds,
                        "action": "buy",
                        "reason": "buying_intent",
                        "additional_info": {
                            "buying_intent": buying_intent,
                            "ds_price": ds_price,
                            "lst_yield_per_block": lst_yield_per_block,
                        },
                    }
                )
            except ValueError as err:
                self.log_action(f"   ✖ buy skipped ({err})")

        # ---------- SELL DS on de-peg (guarded) ----------
        self.lst_price_history.append(lst_price)

        if lst_price <= self.depeg_threshold:
            ds_balance = self.wallet.token_balance(f"DS_{self.token_symbol}")
            extended_depeg_increase = self.count_consecutive_under_threshold(
                self.lst_price_history, self.depeg_threshold
            )
            amount_ds_to_sell = int(ds_balance * extended_depeg_increase * 0.1)
            amount_ds_to_sell = min(amount_ds_to_sell, ds_balance)

            if amount_ds_to_sell > 0:
                try:
                    self.log_action(f"Trying to sell {amount_ds_to_sell:.4f} DS")
                    vault.sell_ds(self.wallet, amount_ds_to_sell)
                    self.log_action("   ✔ sell succeeded")
                    self.log_trade(
                        {
                            "block": block_number,
                            "agent": self.name,
                            "token": "DS",
                            "volume": amount_ds_to_sell,
                            "action": "sell",
                            "reason": "depeg",
                            "additional_info": {
                                "lst_price": lst_price,
                                "depeg_threshold": self.depeg_threshold,
                                "extended_depeg_increase": extended_depeg_increase,
                            },
                        }
                    )
                except ValueError as err:
                    self.log_action(f"   ✖ sell skipped ({err})")

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_buying_intent(ds_price: float, pa_yield: float) -> float:
        if pa_yield == 0:
            return 0.0
        return np.exp(-5 * (ds_price / pa_yield))

    @staticmethod
    def count_consecutive_under_threshold(price_history, threshold=0.95):
        count = 0
        for price in reversed(price_history):
            if price < threshold:
                count += 1
            else:
                break
        return count
