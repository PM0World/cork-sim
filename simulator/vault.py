# simulator/vault.py  ─────────────────────────────────────────────────
from simulator.wallet import Wallet


class Vault:
    def __init__(
        self,
        token_symbol: str,
        blockchain,
        psm,
        lst_eth_amm,
        ct_eth_amm,
        ds_eth_amm,
        reserve_ct=0.4,
        debug=False,
    ):
        self.blockchain   = blockchain
        self.token_symbol = token_symbol
        self.psm          = psm
        self.lst_eth_amm  = lst_eth_amm
        self.ct_eth_amm   = ct_eth_amm
        self.ds_eth_amm   = ds_eth_amm
        self.reserve_ct   = reserve_ct

        self.wallet       = Wallet(owner="Vault Wallet")
        self.lp_token_supply = 0.0
        self.lp_holders      = {}
        self.debug = debug

    # ------------------------------------------------------------------
    def _log(self, msg):                     # helper
        if self.debug:
            print(msg)

    # ──────────────────────────────────────────────────────────────────
    # deposit / withdraw (unchanged)
    # …  ▶▶  all methods up to calculate_sell_ds_outcome stay the same
    # ──────────────────────────────────────────────────────────────────

    # ------------------------------------------------------------------
    # simplified outcome calc – PSM first, then AMM
    # ------------------------------------------------------------------
    def calculate_sell_ds_outcome(self, amount_ds):
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()

        # ETH obtainable from PSM (1 : 1)
        eth_from_psm = min(amount_ds, self.psm.eth_reserve)

        # Remaining DS that must hit AMM
        remaining_ds = amount_ds - eth_from_psm
        eth_from_amm = remaining_ds * ds_price * (1 - self.ds_eth_amm.fee)

        return eth_from_psm + eth_from_amm

    # ------------------------------------------------------------------
    # NEW  PSM-first redemption path
    # ------------------------------------------------------------------
    def sell_ds(self, wallet, amount_ds: float):
        """
        User sells DS for ETH.
        1. Redeem via PSM as much as collateral allows (1:1).
        2. Any leftover DS is swapped through the DS/ETH AMM.
        3. No CT borrowing, no circular swaps – collateral draw-down now
           visible in the PSM gauge.
        """
        if amount_ds <= 0:
            raise ValueError("amount_ds must be positive")

        # Cap sale to available DS in wallet
        amount_ds = min(
            amount_ds,
            wallet.token_balance(f"DS_{self.token_symbol}")
        )

        # -------- user transfers DS into vault ------------------------
        wallet.withdraw_token(f"DS_{self.token_symbol}", amount_ds)
        self.wallet.deposit_token(f"DS_{self.token_symbol}", amount_ds)
        self._log(f"Vault received {amount_ds:.1f} DS from {wallet}")

        # -------- step 1 : redeem via PSM -----------------------------
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()
        redeemable_ds = min(amount_ds, self.psm.eth_reserve)  # ETH reserve == DS cap
        eth_from_psm  = 0.0
        if redeemable_ds > 0:
            eth_from_psm = self.psm.redeem_ds(self.wallet, redeemable_ds)
            self.wallet.withdraw_token(f"DS_{self.token_symbol}", redeemable_ds)
            amount_ds -= redeemable_ds
            self._log(
                f"Redeemed {redeemable_ds:.1f} DS via PSM → {eth_from_psm:.1f} ETH"
            )
            self.blockchain.add_action(
                f"PSM redeemed {redeemable_ds:.1f} DS for {eth_from_psm:.1f} ETH"
            )

        # -------- step 2 : any remainder hits AMM ---------------------
        eth_from_amm = 0.0
        if amount_ds > 0:
            eth_from_amm = self.ds_eth_amm.swap_token_for_eth(
                self.wallet, amount_ds
            )
            self._log(f"Swapped {amount_ds:.1f} DS on AMM → {eth_from_amm:.1f} ETH")

        # -------- payout ----------------------------------------------
        total_eth = eth_from_psm + eth_from_amm
        self.wallet.withdraw_eth(total_eth)
        wallet.deposit_eth(total_eth)
        self._log(f"Investor received {total_eth:.1f} ETH for DS sale")
