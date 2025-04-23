from abc import ABC, abstractmethod
from collections import defaultdict

from simulator.wallet import Wallet


# Base AMM class (abstract)
class AMM(ABC):
    def __init__(self, token_symbol: str, reserve_eth: float, reserve_token: float, fee: float = 0.003):
        self.name = token_symbol  # Token symbol tied to the AMM (e.g., LST, any other token)
        self.reserve_eth = reserve_eth
        self.reserve_token = reserve_token
        self.total_lpt_supply = 0  # Total supply of Liquidity Pool Tokens (LPTs)
        self.fee = fee  # Swap fee (default: 0.3%)
        self.lpt_holders = {}  # Track how many LPTs each wallet holds
        self.fee_accumulated_eth = defaultdict(float)
        self.fee_accumulated_token = defaultdict(float)

    def add_liquidity(self, wallet: Wallet, amount_eth: float, amount_token: float):
        """Add liquidity to the pool and mint LPTs."""
        wallet.withdraw_eth(amount_eth)
        wallet.withdraw_token(self.name, amount_token)

        # Calculate the amount of LPT tokens to mint
        lpt_to_mint = self._calculate_lpt_mint(amount_eth, amount_token)
        wallet.deposit_lpt(self.name, lpt_to_mint)
        self.total_lpt_supply += lpt_to_mint
        self.lpt_holders[wallet] = self.lpt_holders.get(wallet, 0) + lpt_to_mint

        self.reserve_eth += amount_eth
        self.reserve_token += amount_token

    def remove_liquidity(self, wallet: Wallet, lpt_amount: float):
        """Remove liquidity from the pool and burn LPTs.

        :returns: The amount of token and ETH withdrawn from the pool.
        """
        # Calculate the share of the reserves to withdraw
        share_eth = (lpt_amount / self.total_lpt_supply) * self.reserve_eth
        share_token = (lpt_amount / self.total_lpt_supply) * self.reserve_token

        self.reserve_eth -= share_eth
        self.reserve_token -= share_token
        self.total_lpt_supply -= lpt_amount

        wallet.deposit_eth(share_eth)
        wallet.deposit_token(self.name, share_token)
        wallet.withdraw_lpt(self.name, lpt_amount)
        self.lpt_holders[wallet] -= lpt_amount
        return share_token, share_eth

    def swap_eth_for_token(self, wallet: Wallet, amount_eth: float) -> float:
        """Common ETH to Token swap logic with fee deduction."""
        from simulator.blockchain import Blockchain

        # Apply the fee
        fee_deducted_eth = amount_eth * (1 - self.fee)
        amount_token = self._calculate_swap_out_amount(fee_deducted_eth, self.reserve_eth, self.reserve_token)

        wallet.withdraw_eth(amount_eth)  # Withdraw full amount (including the fee)
        wallet.deposit_token(self.name, amount_token)

        self.reserve_eth += amount_eth
        self.reserve_token -= amount_token
        self.fee_accumulated_eth[Blockchain.current_block] += amount_eth * self.fee
        return amount_token

    def swap_token_for_eth(self, wallet: Wallet, amount_token: float) -> float:
        """Common Token to ETH swap logic with fee deduction."""
        from simulator.blockchain import Blockchain

        # Apply the fee
        fee_deducted_token = amount_token * (1 - self.fee)
        amount_eth = self._calculate_swap_out_amount(fee_deducted_token, self.reserve_token, self.reserve_eth)

        wallet.withdraw_token(self.name, amount_token)  # Withdraw full amount (including the fee)
        wallet.deposit_eth(amount_eth)

        self.reserve_token += amount_token
        self.reserve_eth -= amount_eth
        self.fee_accumulated_token[Blockchain.current_block] += amount_token * self.fee
        return amount_eth

    def get_fee_accumulated_eth_between_blocks(self, start_block: int, end_block: int) -> float:
        """Get the total fee accumulated in ETH between two blocks."""
        return sum(self.fee_accumulated_eth[block] for block in range(start_block, end_block + 1))

    def get_fee_accumulated_token_between_blocks(self, start_block: int, end_block: int) -> float:
        """Get the total fee accumulated in tokens between two blocks."""
        return sum(self.fee_accumulated_token[block] for block in range(start_block, end_block + 1))

    def get_total_fee_value_between_blocks_in_eth(self, start_block: int, end_block: int) -> float:
        """Get the total fee value (in ETH) accumulated between two blocks."""
        eth_fee = self.get_fee_accumulated_eth_between_blocks(start_block, end_block)
        token_fee = self.get_fee_accumulated_token_between_blocks(start_block, end_block)
        token_fee_in_eth = token_fee * self.price_of_one_token_in_eth()
        return eth_fee + token_fee_in_eth

    @abstractmethod
    def price_of_one_token_in_eth(self) -> float:
        """Calculate the price of 1 token in ETH."""
        pass

    @abstractmethod
    def _calculate_swap_out_amount(self, amount_in: float, reserve_in: float, reserve_out: float) -> float:
        """Abstract method to calculate swap output amount based on AMM formula."""
        pass

    def _calculate_lpt_mint(self, amount_eth: float, amount_token: float) -> float:
        """Calculate how many LPT tokens to mint based on the added liquidity."""
        if self.total_lpt_supply == 0:
            # When there's no liquidity yet, use the geometric mean of reserves
            return (amount_eth * amount_token) ** 0.5
        else:
            # Otherwise, mint LPT proportional to existing reserves
            return min(
                (amount_eth / self.reserve_eth) * self.total_lpt_supply,
                (amount_token / self.reserve_token) * self.total_lpt_supply
            )

    # Added Slippage Calculation Methods
    def calculate_slippage(self, amount_in: float, swap_direction: str) -> float:
        """
        Calculate the slippage for a given swap.

        :param amount_in: The amount of input asset being swapped.
        :param swap_direction: 'eth_to_token' or 'token_to_eth'
        :return: The slippage as a fraction (e.g., 0.05 for 5% slippage).
        """
        if swap_direction == 'eth_to_token':
            reserve_in = self.reserve_eth
            reserve_out = self.reserve_token
        elif swap_direction == 'token_to_eth':
            reserve_in = self.reserve_token
            reserve_out = self.reserve_eth
        else:
            raise ValueError("swap_direction must be 'eth_to_token' or 'token_to_eth'")

        price_before = reserve_out / reserve_in
        amount_out_expected = amount_in * (1 - self.fee) * price_before

        amount_out_actual = self._calculate_swap_out_amount(
            amount_in * (1 - self.fee),
            reserve_in,
            reserve_out
        )

        slippage = (amount_out_expected - amount_out_actual) / amount_out_expected

        return slippage

    def get_expected_output_amount(self, amount_in: float, swap_direction: str) -> float:
        """
        Get the expected output amount for a given input amount and swap direction.

        :param amount_in: The amount of input asset.
        :param swap_direction: 'eth_to_token' or 'token_to_eth'
        :return: The expected output amount.
        """
        if swap_direction == 'eth_to_token':
            reserve_in = self.reserve_eth
            reserve_out = self.reserve_token
        elif swap_direction == 'token_to_eth':
            reserve_in = self.reserve_token
            reserve_out = self.reserve_eth
        else:
            raise ValueError("swap_direction must be 'eth_to_token' or 'token_to_eth'")

        amount_in_with_fee = amount_in * (1 - self.fee)
        amount_out = self._calculate_swap_out_amount(amount_in_with_fee, reserve_in, reserve_out)
        return amount_out


# UniswapV2 style AMM (constant product formula)
class UniswapV2AMM(AMM):
    def _calculate_swap_out_amount(self, amount_in: float, reserve_in: float, reserve_out: float) -> float:
        """
        UniswapV2 constant product formula: x * y = k
        Calculates how much of the output token you get for a given input.
        """
        numerator = amount_in * reserve_out
        denominator = reserve_in + amount_in
        return numerator / denominator

    def price_of_one_token_in_eth(self) -> float:
        """Calculate the price of 1 token in ETH (UniswapV2 logic)."""
        if self.reserve_token == 0:
            return float('inf')
        return self.reserve_eth / self.reserve_token


# Yield Space AMM
class YieldSpaceAMM(AMM):
    def __init__(self, token_symbol: str, reserve_eth: float, reserve_token: float, discount_rate: float,
                 fee: float = 0.003):
        super().__init__(token_symbol, reserve_eth, reserve_token, fee)
        self.discount_rate = discount_rate  # Discount rate for time decay or yield factor

    def _calculate_swap_out_amount(self, amount_in: float, reserve_in: float, reserve_out: float) -> float:
        """Yield Space formula adjusted for discount rate."""
        # Adjusted reserves
        adjusted_reserve_in = reserve_in ** (1 - self.discount_rate)
        adjusted_reserve_out = reserve_out ** (1 + self.discount_rate)
        amount_out = adjusted_reserve_out - ((adjusted_reserve_in * adjusted_reserve_out) / (adjusted_reserve_in + amount_in))
        return amount_out

    def price_of_one_token_in_eth(self) -> float:
        """
        The price of one token in ETH with the YieldSpace formula.
        """
        if self.reserve_eth == 0 or self.reserve_token == 0:
            raise ValueError("Reserves must be greater than zero to calculate price")

        base_price = self.reserve_eth / self.reserve_token
        adjusted_price = base_price * (1 - self.discount_rate)

        if adjusted_price <= 0:
            raise ValueError("Price calculation error: adjusted price is negative or zero.")

        return adjusted_price

    # Override the slippage calculation for YieldSpace
    def calculate_slippage(self, amount_in: float, swap_direction: str) -> float:
        """
        Calculate the slippage for a given swap in YieldSpace AMM.

        :param amount_in: The amount of input asset being swapped.
        :param swap_direction: 'eth_to_token' or 'token_to_eth'
        :return: The slippage as a fraction.
        """
        if swap_direction == 'eth_to_token':
            reserve_in = self.reserve_eth
            reserve_out = self.reserve_token
        elif swap_direction == 'token_to_eth':
            reserve_in = self.reserve_token
            reserve_out = self.reserve_eth
        else:
            raise ValueError("swap_direction must be 'eth_to_token' or 'token_to_eth'")

        price_before = reserve_out / reserve_in
        amount_out_expected = amount_in * (1 - self.fee) * price_before

        # Adjusted reserves
        adjusted_reserve_in = reserve_in ** (1 - self.discount_rate)
        adjusted_reserve_out = reserve_out ** (1 + self.discount_rate)
        amount_in_with_fee = amount_in * (1 - self.fee)
        amount_out_actual = adjusted_reserve_out - ((adjusted_reserve_in * adjusted_reserve_out) / (adjusted_reserve_in + amount_in_with_fee))

        slippage = (amount_out_expected - amount_out_actual) / amount_out_expected

        return slippage
