from simulator.wallet import Wallet


class PegStabilityModule:
    def __init__(self, token_symbol: str, expiry_block: int, redemption_fee: float = 0.001, repurchase_fee: float = 0.05):
        """
        Initialize the Peg Stability Module.

        :param token_symbol: The token tied to the PSM (e.g., LST).
        :param expiry_block: The block number after which only CT is required for redemption.
        :param redemption_fee: The fee applied on redemption (e.g., 0.001 for 0.1%).
        :param repurchase_fee: The fee applied on repurchase (e.g., 0.05 for 5%).
        """
        self.token_symbol = token_symbol
        self.expiry_block = expiry_block
        self.eth_reserve = 0.0
        self.token_reserve = 0.0
        self.redemption_fee = redemption_fee
        self.repurchase_fee = repurchase_fee
        self.total_redemption_fee = 0.0
        self.total_repurchase_fee = 0.0

    def deposit_eth(self, wallet: Wallet, amount_eth: float):
        """Deposit ETH into the PSM and receive CT and DS tokens."""
        if amount_eth <= 0:
            raise ValueError("Deposit amount must be positive")

        # Withdraw ETH from wallet
        wallet.withdraw_eth(amount_eth)

        # Mint equivalent amount of CT and DS tokens
        wallet.deposit_token(f'CT_{self.token_symbol}', amount_eth)
        wallet.deposit_token(f'DS_{self.token_symbol}', amount_eth)

        # Increase PSM ETH reserve
        self.eth_reserve += amount_eth

    def redeem_with_ct_and_ds(self, wallet: Wallet, amount_tokens: float, current_block: int) -> float:
        """
        Redeem ETH by returning CT and DS tokens before expiry.

        :param wallet: The wallet of the user redeeming ETH.
        :param amount_tokens: The amount of CT and DS tokens provided.
        :param current_block: The current block number.
        :return: Net ETH redeemed after applying the fee.
        """
        if current_block > self.expiry_block:
            raise ValueError("Cannot redeem with CT and DS after expiry")

        if amount_tokens <= 0:
            raise ValueError("Redemption amount must be positive")

        # Check if the wallet has enough CT and DS tokens
        if wallet.token_balance(f'CT_{self.token_symbol}') < amount_tokens or \
           wallet.token_balance(f'DS_{self.token_symbol}') < amount_tokens:
            raise ValueError("Not enough CT or DS tokens in wallet to cover redemption")

        # Withdraw CT and DS tokens from the wallet
        wallet.withdraw_token(f'CT_{self.token_symbol}', amount_tokens)
        wallet.withdraw_token(f'DS_{self.token_symbol}', amount_tokens)

        # Calculate the fee
        fee_eth = amount_tokens * self.redemption_fee

        # Net ETH after fee
        net_eth = amount_tokens - fee_eth

        if net_eth > self.eth_reserve:
            raise ValueError("Not enough ETH in PSM reserve to cover redemption")

        # Transfer net ETH to the wallet
        wallet.deposit_eth(net_eth)

        # Update PSM reserves
        self.eth_reserve -= net_eth
        self.token_reserve += amount_tokens  # Increase the PSM's token reserve by the full amount of tokens provided

        self.total_redemption_fee += fee_eth  # Update total redemption fee
        return net_eth  # Return net ETH redeemed after fees

    def redeem_with_token_and_ds(self, wallet: Wallet, amount_tokens: float, current_block: int) -> float:
        """
        Redeem ETH by returning the underlying token and DS tokens before expiry.

        :param wallet: The wallet of the user redeeming ETH.
        :param amount_tokens: The amount of underlying token and DS tokens provided.
        :param current_block: The current block number.
        :return: Net ETH redeemed after applying the fee.
        """
        # Same logic as redeem_with_ct_and_ds
        if current_block > self.expiry_block:
            raise ValueError("Cannot redeem with token and DS after expiry")

        if amount_tokens <= 0:
            raise ValueError("Redemption amount must be positive")

        # Check if the wallet has enough tokens and DS tokens
        if wallet.token_balance(self.token_symbol) < amount_tokens or \
           wallet.token_balance(f'DS_{self.token_symbol}') < amount_tokens:
            raise ValueError("Not enough tokens or DS tokens in wallet to cover redemption")

        # Withdraw tokens and DS tokens from the wallet
        wallet.withdraw_token(self.token_symbol, amount_tokens)
        wallet.withdraw_token(f'DS_{self.token_symbol}', amount_tokens)

        # Calculate the fee
        fee_eth = amount_tokens * self.redemption_fee

        # Net ETH after fee
        net_eth = amount_tokens - fee_eth

        if net_eth > self.eth_reserve:
            raise ValueError("Not enough ETH in PSM reserve to cover redemption")

        # Transfer net ETH to the wallet
        wallet.deposit_eth(net_eth)

        # Update PSM reserves
        self.eth_reserve -= net_eth
        self.token_reserve += amount_tokens

        self.total_redemption_fee += fee_eth  # Update total redemption fee

        return net_eth  # Return net ETH redeemed after fees

    def redeem_with_ct_post_expiry(self, wallet: Wallet, amount_tokens: float, current_block: int) -> float:
        """
        Redeem ETH by returning only CT tokens after expiry.

        :param wallet: The wallet of the user redeeming ETH.
        :param amount_tokens: The amount of CT tokens provided.
        :param current_block: The current block number.
        :return: Net ETH redeemed after applying the fee.
        """
        if current_block < self.expiry_block:
            raise ValueError("Cannot redeem with only CT before expiry")

        if amount_tokens <= 0:
            raise ValueError("Redemption amount must be positive")

        # Check if the wallet has enough CT tokens
        if wallet.token_balance(f'CT_{self.token_symbol}') < amount_tokens:
            raise ValueError("Not enough CT tokens in wallet to cover redemption")

        # Withdraw CT tokens from the wallet
        wallet.withdraw_token(f'CT_{self.token_symbol}', amount_tokens)

        # Calculate the fee
        fee_eth = amount_tokens * self.redemption_fee

        # Net ETH after fee
        net_eth = amount_tokens - fee_eth

        if net_eth > self.eth_reserve:
            raise ValueError("Not enough ETH in PSM reserve to cover redemption")

        # Transfer net ETH to the wallet
        wallet.deposit_eth(net_eth)

        # Update PSM reserves
        self.eth_reserve -= net_eth
        self.token_reserve += amount_tokens

        self.total_redemption_fee += fee_eth  # Update total redemption fee

        return net_eth  # Return net ETH redeemed after fees

    def repurchase_token_and_ds(self, wallet: Wallet, amount_eth: float) -> float:
        """
        After a redemption, users can repurchase the underlying token & DS in a bundle from the PSM.
        The fee is applied by deducting from the given ETH amount.

        :param wallet: The wallet of the user repurchasing tokens.
        :param amount_eth: The amount of ETH the user wants to spend.
        :return: Net tokens received after fee.
        """
        if amount_eth <= 0:
            raise ValueError("Repurchase amount must be positive")

        # Calculate the fee
        fee_eth = amount_eth * self.repurchase_fee

        # Net ETH after fee
        net_eth = amount_eth - fee_eth

        # Tokens received are equivalent to net ETH (since token price is 1 ETH per token)
        amount_tokens = net_eth

        # Ensure PSM has enough tokens
        if amount_tokens > self.token_reserve:
            raise ValueError("Not enough tokens in PSM reserve to cover repurchase")

        # Withdraw ETH from the wallet
        wallet.withdraw_eth(amount_eth)

        # Increase PSM ETH reserve by amount_eth
        self.eth_reserve += amount_eth

        # Decrease PSM token reserve by amount_tokens
        self.token_reserve -= amount_tokens

        # Transfer tokens to the wallet
        wallet.deposit_token(self.token_symbol, amount_tokens)
        wallet.deposit_token(f'DS_{self.token_symbol}', amount_tokens)

        self.total_repurchase_fee += fee_eth

        return amount_tokens  # Return net tokens received after fees
