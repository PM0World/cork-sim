from exceptiongroup import catch

from simulator.wallet import Wallet


class Vault:

    def __init__(self, token_symbol: str, blockchain, psm, lst_eth_amm, ct_eth_amm, ds_eth_amm, reserve_ct=0.4, debug=False):
        """
        Initialize the Vault.

        :param blockchain: The blockchain object.
        :param token_symbol: The token tied to the vault (e.g., LST).
        :param psm: The Peg Stability Module (PSM) associated with the token.
        :param lst_eth_amm: The AMM for LST/ETH pool.
        :param ct_eth_amm: The AMM for CT/ETH pool.
        :param ds_eth_amm: The AMM for DS/ETH pool.
        :param reserve_ct: The reserve ratio for CT tokens in the vault.
        """
        self.blockchain = blockchain
        self.token_symbol = token_symbol  # Token (LST) associated with the vault
        self.psm = psm  # Peg Stability Module for CT/DS tokens
        self.lst_eth_amm = lst_eth_amm  # AMM for LST/ETH
        self.ct_eth_amm = ct_eth_amm  # AMM for CT/ETH
        self.ds_eth_amm = ds_eth_amm  # AMM for DS/ETH
        self.reserve_ct = reserve_ct # Reserve ratio for CT tokens in the vault

        # Vault will have its own wallet to manage ETH, LST, CT, and DS
        self.wallet = Wallet(owner='Vault Wallet')  # A wallet object for holding ETH and tokens
        self.lp_token_supply = 0.0  # Total supply of LP tokens issued by the vault
        self.lp_holders = {}  # Track LP tokens for each wallet
        self.debug = debug

    def _log(self, message):
        if self.debug:
            print(message)

    def deposit_eth(self, wallet, amount_eth: float):
        """
        Deposit ETH into the vault and perform the recursive conversion.

        :param wallet: The wallet of the agent depositing ETH.
        :param amount_eth: The amount of ETH being deposited.
        """
        # Step 1: Withdraw ETH from the agent's wallet
        wallet.withdraw_eth(amount_eth)

        # Step 2: Deposit ETH into the vault's wallet
        self.wallet.deposit_eth(amount_eth)
        self._log(
            f"Vault received {amount_eth:.4f} ETH from {wallet}. Total ETH in vault: {self.wallet.eth_balance:.4f} ETH")

        # Step 3: Perform the recursive conversion with the deposited ETH
        self._recursive_conversion(amount_eth)

        # Step 4: Issue LP tokens to the wallet based on the deposited ETH
        self._issue_lp_tokens(wallet, amount_eth)

    def withdraw_lp_tokens(self, wallet, amount_lp: float):
        """
        Withdraw LP tokens and return the equivalent value in ETH by withdrawing from the vault's CT/ETH LP tokens
        and selling the CT for ETH.

        :param wallet: The wallet requesting withdrawal.
        :param amount_lp: The amount of LP tokens to withdraw.
        """
        if amount_lp <= 0:
            raise ValueError("Withdrawal amount must be greater than zero")

        if amount_lp > self.lp_holders.get(wallet, 0):
            raise ValueError("Not enough LP tokens in wallet to withdraw")

        # Step 1: Calculate the user's share of the vault's total value in ETH
        share_of_assets = amount_lp / self.lp_token_supply
        total_vault_value = self._get_total_vault_value()  # Get total value of the vault in ETH
        user_share_value_in_eth = share_of_assets * total_vault_value

        # Log the user's share in terms of ETH
        self._log(f"User's LP token share is equivalent to {user_share_value_in_eth:.4f} ETH.")

        # Step 2: Calculate the CT/ETH price ratio (i.e., how much 1 CT is worth in ETH)
        ct_to_eth_price_ratio = self.ct_eth_amm.price_of_one_token_in_eth()

        # Step 3: Calculate how much CT and ETH to withdraw based on the price of CT in ETH
        # Withdraw as much ETH as possible directly from the pool
        eth_to_withdraw_directly = user_share_value_in_eth / (1 + ct_to_eth_price_ratio)

        # Calculate the remaining amount of value that needs to be withdrawn in CT
        ct_to_withdraw = user_share_value_in_eth - eth_to_withdraw_directly

        # Step 4: Remove liquidity from the CT/ETH pool to get back CT tokens and ETH
        ct_received, eth_from_ct_lp = self.ct_eth_amm.remove_liquidity(self.wallet, ct_to_withdraw)

        # Step 5: Sell the withdrawn CT tokens for ETH using the CT/ETH AMM
        eth_from_ct = self.ct_eth_amm.swap_token_for_eth(self.wallet, ct_received)

        # Step 6: Add up the total ETH to return to the user
        total_eth_to_return = eth_from_ct + eth_from_ct_lp

        # Step 7: Withdraw the total ETH from the vault's wallet and deposit it into the user's wallet
        self.wallet.withdraw_eth(total_eth_to_return)
        wallet.deposit_eth(total_eth_to_return)

        # Step 8: Burn the LP tokens being withdrawn
        self.lp_token_supply -= amount_lp
        self.lp_holders[wallet] -= amount_lp
        wallet.withdraw_lpt('V_' + self.token_symbol, amount_lp)

        # Log the withdrawal
        self._log(f"Withdrew {total_eth_to_return:.4f} ETH after converting CT. Burned {amount_lp:.4f} LP tokens.")


    def _deposit_ct_eth(self, amount_ct: float, amount_eth: float):
        """
        Deposit CT and ETH into the CT/ETH AMM.

        :param amount_ct: The amount of CT to deposit into the CT/ETH pool.
        :param amount_eth: The amount of ETH to deposit into the CT/ETH pool.
        """
        # Step 1: Deposit CT and ETH into the CT/ETH AMM
        if amount_ct > 0 and amount_eth > 0:
            # Deposit both CT tokens and ETH into the CT/ETH pool
            self.ct_eth_amm.add_liquidity(self.wallet, amount_eth=amount_eth, amount_token=amount_ct)
            self._log(f"Deposited {amount_ct:.4f} CT and {amount_eth:.4f} ETH into the CT/ETH pool")

    def _recursive_conversion(self, amount_eth: float):
        """
        Perform the recursive ETH to LST, CT/DS split, and DS sale until the returned ETH becomes negligible.



        :param amount_eth: The initial amount of ETH to start the recursion with.
        """
        threshold = 0.01  # Stop the recursion when ETH becomes smaller than this threshold

        while amount_eth >= threshold:
            reserve_ct = amount_eth * self.reserve_ct
            self.psm.deposit_eth(self.wallet, reserve_ct)
            ds_tokens = reserve_ct

            remainder_eth = amount_eth - reserve_ct

            share_of_ct_in_the_pool = self.ct_eth_amm.reserve_token / (self.ct_eth_amm.reserve_token + self.ct_eth_amm.reserve_eth)
            share_of_eth_in_the_pool = 1 - share_of_ct_in_the_pool

            eth_for_amm = remainder_eth * share_of_eth_in_the_pool  # Amount of ETH to send to the PSM for CT and DS
            ct_for_amm = remainder_eth - eth_for_amm  # Amount of CT to keep in the vault

            self.psm.deposit_eth(self.wallet, ct_for_amm)  # PSM gives back CT and DS tokens
            self.ct_eth_amm.add_liquidity(self.wallet, eth_for_amm, ct_for_amm)

            ds_tokens += ct_for_amm

            if ds_tokens > 0:
                amount_eth = self.ds_eth_amm.swap_token_for_eth(self.wallet, ds_tokens)
            else:
                amount_eth = 0

    def _issue_lp_tokens(self, wallet, amount_eth: float):
        """
        Issue LP tokens to the wallet based on the ETH deposited.

        :param wallet: The wallet to receive LP tokens.
        :param amount_eth: The amount of ETH deposited (used to calculate LP tokens).
        """
        # Step 1: Calculate the total value of the vault (ETH + DS + CT/ETH LP tokens)
        total_vault_value = self._get_total_vault_value()

        # Step 2: If this is the first liquidity provision, mint LP tokens based on the initial ETH deposit
        if self.lp_token_supply == 0:
            # Mint LP tokens equal to the initial ETH deposit (1:1 ratio)
            lp_tokens_to_mint = amount_eth
        else:
            # Mint LP tokens proportional to the ETH deposit relative to the vault's total value
            lp_tokens_to_mint = (amount_eth / total_vault_value) * self.lp_token_supply

        # Step 3: Update the LP token supply
        self.lp_token_supply += lp_tokens_to_mint

        # Step 4: Track the LP tokens in the wallet
        self.lp_holders[wallet] = self.lp_holders.get(wallet, 0) + lp_tokens_to_mint
        wallet.deposit_lpt(f'V_' + self.token_symbol, lp_tokens_to_mint)

        # Log the issuance of LP tokens
        self._log(f"Issued {lp_tokens_to_mint:.4f} LP tokens to {wallet}. Total LP supply: {self.lp_token_supply:.4f}")

    def _get_total_vault_value(self) -> float:
        """
        Calculate the total value of the vault (ETH + DS + CT/ETH LP tokens) in terms of ETH.

        :return: The total value of the vault in ETH.
        """
        # ETH value held in the vault
        eth_value = self.wallet.eth_balance

        # Convert DS tokens to their ETH equivalent using the DS/ETH AMM
        ds_value_in_eth = self.ds_eth_amm.price_of_one_token_in_eth() * self.wallet.token_balance(
            f'DS_{self.token_symbol}')

        # Calculate the value of the CT/ETH LP tokens
        # Assuming the value of LP tokens is proportional to the total reserves in the CT/ETH AMM
        ct_eth_lp_value_in_eth = (
                                             self.ct_eth_amm.reserve_eth / self.ct_eth_amm.total_lpt_supply) * self.wallet.lpt_balance(
            self.token_symbol)

        # Total value of the vault is the sum of ETH, DS (in ETH terms), and CT/ETH LP tokens (in ETH terms)
        total_value = eth_value + ds_value_in_eth + ct_eth_lp_value_in_eth

        return total_value

    def get_lp_token_price(self) -> float:
        """
        Get the price of one LP token in terms of ETH.

        :return: The price of one LP token in ETH.
        """
        # If no LP tokens have been issued yet, the price is undefined (we can assume it's 0)
        if self.lp_token_supply == 0:
            return 0.0

        # Calculate the total value of the vault
        total_vault_value = self._get_total_vault_value()

        # Calculate the price of one LP token
        lp_token_price = total_vault_value / self.lp_token_supply

        return lp_token_price

    def calculate_sell_ds_outcome(self, amount_ds):
        # Get current prices and fees
        ct_eth_price = self.ct_eth_amm.price_of_one_token_in_eth()
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()
        ct_fee = self.ct_eth_amm.fee
        ds_fee = self.ds_eth_amm.fee

        # Limit amount_ds based on available CT and ETH in AMMs
        ct_available = self.ct_eth_amm.reserve_token
        eth_available = self.ds_eth_amm.reserve_eth
        max_ds_sellable = min(amount_ds, ct_available, eth_available / ds_price)
        if amount_ds > max_ds_sellable:
            amount_ds = max_ds_sellable

        # ETH from PSM redemption (assuming 1:1 ratio)
        eth_from_psm = amount_ds  # 1 DS + 1 CT redeem for 1 ETH

        # ETH needed to repay CT loan
        eth_needed_for_repayment = amount_ds * ct_eth_price

        # Calculate slippage and adjusted ETH to swap for CT
        ct_slippage = self.ct_eth_amm.calculate_slippage(eth_needed_for_repayment, 'eth_to_token')
        eth_to_swap_for_ct = eth_needed_for_repayment / ((1 - ct_fee) * (1 - ct_slippage))

        # Remaining ETH for investor
        remaining_eth = eth_from_psm - eth_to_swap_for_ct
        if remaining_eth < 0:
            remaining_eth = 0  # Investor receives nothing

        return remaining_eth

    def calculate_buy_ds_outcome(self, amount_eth):
        # Get current prices and fees
        ct_eth_price = self.ct_eth_amm.price_of_one_token_in_eth()
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()
        ct_fee = self.ct_eth_amm.fee
        ds_fee = self.ds_eth_amm.fee

        # Calculate DS tokens to give investor
        ds_to_give_investor = amount_eth / ds_price

        # Borrow ETH to acquire CT
        eth_to_borrow = ds_to_give_investor * ct_eth_price

        # Total ETH to deposit into PSM
        total_eth = amount_eth + eth_to_borrow

        # Receive CT and DS from PSM
        ct_received = total_eth
        ds_received = total_eth

        # Estimate ETH from selling CT
        ct_slippage = self.ct_eth_amm.calculate_slippage(ct_received, 'token_to_eth')
        expected_eth_from_ct = ct_received * ct_eth_price * (1 - ct_fee) * (1 - ct_slippage)

        # Calculate shortfall in ETH for loan repayment
        eth_needed_for_repayment = eth_to_borrow
        shortfall_eth = eth_needed_for_repayment - expected_eth_from_ct

        # Sell DS to cover shortfall if necessary
        if shortfall_eth > 0:
            ds_slippage = self.ds_eth_amm.calculate_slippage(shortfall_eth / ds_price, 'token_to_eth')
            ds_to_sell = shortfall_eth / (ds_price * (1 - ds_fee) * (1 - ds_slippage))
            remaining_ds = ds_received - ds_to_sell
        else:
            remaining_ds = ds_received

        # Ensure remaining_ds is not negative
        if remaining_ds < 0:
            remaining_ds = 0

        return remaining_ds

    def buy_ds(self, wallet, amount_eth: float):
        """
        Buy DS tokens via the vault by borrowing ETH, acquiring CT/DS via the PSM,
        selling CT for ETH, and returning the remainder DS tokens to the investor.

        :param wallet: The wallet of the investor buying DS.
        :param amount_eth: The amount of ETH being used to buy DS.
        """

        if self.calculate_buy_ds_outcome(amount_eth) <= 0:
            self._log(f"Not enough liquidity to buy DS with {amount_eth:.4f} ETH.")
            raise ValueError("Not enough liquidity to buy DS with {amount_eth:.4f} ETH.")

        # Step 0: Calculate the CT/ETH price and DS price
        ct_eth_price = self.ct_eth_amm.price_of_one_token_in_eth()
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()
        self._log(f"CT price: {ct_eth_price:.4f} ETH, DS price: {ds_price:.4f} ETH")

        # Step 1: Cap Purchase if too much DS is being bought
        ds_available = self.ds_eth_amm.reserve_token
        ds_available_in_eth = ds_available * ds_price

        if amount_eth > ds_available_in_eth:
            amount_eth = ds_available_in_eth
            self._log(f"Cap Purchase: Only {amount_eth:.4f} ETH worth of DS available for purchase.")

        # Step 2: Investor deposits ETH into the vault
        wallet.withdraw_eth(amount_eth)
        self.wallet.deposit_eth(amount_eth)
        self._log(f"Investor deposited {amount_eth:.4f} ETH into the vault.")

        # Step 3: Calculate how many DS the user will receive
        ds_to_give_investor = amount_eth / ds_price
        self._log(f"Investor will receive {ds_to_give_investor:.4f} DS tokens.")

        # Step 4: Borrow ETH from the blockchain to match the ETH required for CT
        eth_to_borrow = (amount_eth / ds_price) * ct_eth_price  # e.g., borrow 9 ETH
        self.blockchain.borrow_eth(self.wallet, eth_to_borrow)
        self._log(f"Vault borrowed {eth_to_borrow:.4f} ETH from the blockchain.")

        # Step 5: Total ETH now held by vault (deposited + borrowed)
        total_eth = amount_eth + eth_to_borrow
        self._log(f"Total ETH in vault: {total_eth:.4f}")

        # Step 6: Use PSM to acquire CT and DS tokens
        self.psm.deposit_eth(self.wallet, total_eth)  # e.g., 10 CT and 10 DS
        ct_received = total_eth
        ds_received = total_eth
        self._log(f"Acquired {ct_received:.4f} CT and {ds_received:.4f} DS via PSM.")

        # Step 7: Sell CT for ETH
        slippage = self.ct_eth_amm.calculate_slippage(ct_received, 'token_to_eth')
        eth_from_ct = self.ct_eth_amm.swap_token_for_eth(self.wallet, ct_received)
        self._log(f"Sold {ct_received:.4f} CT for {eth_from_ct:.4f} ETH.")

        # Step 8: Calculate how much DS needs to be sold to repay the loan, considering the fee with a 20% premium
        ds_amm_fee = self.ds_eth_amm.fee
        eth_needed_for_repayment = eth_to_borrow - eth_from_ct
        if eth_needed_for_repayment < 0:
            # rare condition: Slippage works in our favour
            eth_needed_for_repayment = 0
        ds_to_sell = (eth_needed_for_repayment / ds_price) / (1 - ds_amm_fee)   # Adjust for premium fee, 1.05 is to be on the safe side
        self._log(f"Need to sell {ds_to_sell:.4f} DS (with fee premium) to repay the loan.")

        if ds_to_sell > self.wallet.token_balances[f'DS_{self.token_symbol}']:
            ds_to_sell = self.wallet.token_balances[f'DS_{self.token_symbol}']
        # Step 9: Sell DS to repay the borrowed ETH
        eth_from_ds = self.ds_eth_amm.swap_token_for_eth(self.wallet, ds_to_sell)

        eth_accumulated_for_repay = eth_from_ct + eth_from_ds
        while eth_accumulated_for_repay < eth_to_borrow:
            # Ui, we need to swap more ds for eth
            # this may happen if the liquidity isn't deep enough
            new_ds_price = self.ds_eth_amm.price_of_one_token_in_eth()
            more_ds_to_sell = ((eth_to_borrow - eth_accumulated_for_repay) / new_ds_price) / (1 + ds_amm_fee)
            new_eth_from_ds = self.ds_eth_amm.swap_token_for_eth(self.wallet, more_ds_to_sell)
            eth_accumulated_for_repay += new_eth_from_ds
            ds_to_sell += more_ds_to_sell
            eth_from_ds += new_eth_from_ds

        self._log(f"Sold {ds_to_sell:.4f} DS for {eth_from_ds:.4f} ETH.")

        # Step 10: Repay the loan to the blockchain
        self.blockchain.repay_eth(self.wallet, eth_to_borrow)
        self._log(f"Repaid {eth_from_ds:.4f} ETH to the blockchain to settle the loan.")

        # Step 11: Give the investor the remaining DS tokens
        remaining_ds = ds_received - ds_to_sell

        if remaining_ds > self.wallet.token_balances[f'DS_{self.token_symbol}']:
            remaining_ds = self.wallet.token_balances[f'DS_{self.token_symbol}']

        assert remaining_ds > 0, f"Remaining DS should be positive, but got {remaining_ds}"

        self.wallet.withdraw_token(f'DS_{self.token_symbol}', remaining_ds)
        wallet.deposit_token(f'DS_{self.token_symbol}', remaining_ds)
        self._log(f"Investor received {remaining_ds:.4f} DS tokens as their final share.")

    def sell_ds(self, wallet, amount_ds: float):
        """
        Sell DS tokens via the vault by borrowing CT, redeeming both CT and DS for ETH via the PSM,
        and returning the equivalent ETH (minus fees) to the investor.

        :param wallet: The wallet of the investor selling DS.
        :param amount_ds: The amount of DS being sold.
        """
        if self.calculate_sell_ds_outcome(amount_ds) <= 0:
            self._log(f"Not enough liquidity to sell DS for {amount_ds:.4f} DS.")
            raise ValueError(f"Not enough liquidity to sell DS for {amount_ds:.4f} DS.")

        # Step 0: Calculate the CT/ETH price and DS/ETH price
        ct_eth_price = self.ct_eth_amm.price_of_one_token_in_eth()  # e.g., 0.9 ETH
        ds_price = self.ds_eth_amm.price_of_one_token_in_eth()  # e.g., 0.8 ETH
        self._log(f"CT price: {ct_eth_price:.4f} ETH, DS price: {ds_price:.4f} ETH")

        # Step 1: Cap Sale if too much DS is being sold
        ct_available = self.ct_eth_amm.reserve_token
        eth_available = self.ds_eth_amm.reserve_eth

        if (amount_ds > ct_available) or (amount_ds * ds_price > eth_available):
            amount_ds = min(ct_available, eth_available / ds_price)
            self._log(f"Cap Sale: Only {amount_ds:.4f} CT available for matching the sale.")

        # Step 2: Investor sends DS tokens to the vault
        wallet.withdraw_token(f'DS_{self.token_symbol}', amount_ds)
        self.wallet.deposit_token(f'DS_{self.token_symbol}', amount_ds)
        self._log(f"Investor deposited {amount_ds:.4f} DS into the vault.")

        # Step 3: Borrow CT from the blockchain to match the amount of DS being sold
        ct_to_borrow = amount_ds
        self.blockchain.borrow_token(self.wallet, f'CT_{self.token_symbol}', ct_to_borrow)
        self._log(f"Vault borrowed {ct_to_borrow:.4f} CT from the blockchain.")

        eth_from_ds   =self.psm.redeem_with_ct_and_ds(self.wallet, ct_to_borrow, self.blockchain.current_block)
        self._log(f"Redeemed {eth_from_ds:.4f} ETH from PSM after redeeming CT and DS.")

        # Step 6: Swap ETH back for CT to repay the blockchain, applying fee premium
        eth_needed_for_repayment = eth_from_ds * ct_eth_price
        ct_amm_fee = self.ct_eth_amm.fee
        eth_to_swap_for_ct = eth_needed_for_repayment / (1 - ct_amm_fee)
        self._log(f"Need to swap {eth_to_swap_for_ct:.4f} ETH (with fee premium) to repay the CT loan.")

        # Step 7: Swap some ETH for CT and repay the loan
        ct_from_eth = self.ct_eth_amm.swap_eth_for_token(self.wallet, eth_to_swap_for_ct)

        remaining_eth_to_return = eth_from_ds - eth_to_swap_for_ct
        while ct_from_eth < ct_to_borrow:
            # Ui, we need to swap more eth for ct
            # this may happen if the liquidity isn't deep enough
            new_ct_eth_price = self.ct_eth_amm.price_of_one_token_in_eth()
            eth_to_swap_for_ct = ((ct_to_borrow - ct_from_eth) / new_ct_eth_price) * (1 + ct_amm_fee)
            ct_from_eth += self.ct_eth_amm.swap_eth_for_token(self.wallet, eth_to_swap_for_ct)
            remaining_eth_to_return -= eth_to_swap_for_ct

        self.blockchain.repay_token(self.wallet, f'CT_{self.token_symbol}', ct_to_borrow)
        self._log(f"Repaid {ct_from_eth:.4f} CT to the blockchain.")

        # Step 8: Calculate the remaining ETH to return to the investor (after repaying the borrowed CT)
        self._log(f"Remaining ETH to return to the investor: {remaining_eth_to_return:.4f}")

        # Step 9: Pay out the remaining ETH to the investor
        self.wallet.withdraw_eth(remaining_eth_to_return)
        if remaining_eth_to_return > 0:
            wallet.deposit_eth(remaining_eth_to_return)
        self._log(f"Investor received {remaining_eth_to_return:.4f} ETH after selling {amount_ds:.4f} DS.")