# Steady in-flow/out-flow of the RA into the Liquidity Vault weighted by the attractivity of the current APY of the LV.
# To make it simple the “attractivity” should be parametrized as %  of the current yield of the underlying asset.
# The deposits will translate into DS sell pressure and change the AMM parameters.
# The withdrawals will translate into CT sell pressure and change the AMM parameters.

# If the yield of the LV exceeds the yield of the PA by some margin (maybe 25%) - so 10->12.5%, 
# I would expect there to be inflows - so people deposit the Redemption Asset and receive the LV token
import math
import numpy as np
import pandas as pd

from simulator.agent import Agent

from agents.utils.volume_calculations import buying_intent

class LVDepositorAgent(Agent):
    def __init__(self, name, token_symbol: str, expected_apy=0.05, yield_margin_threshold=0.25):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.yield_margin_threshold = yield_margin_threshold
        self.expected_apy = expected_apy
        
    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        # get LST yield
        lst_info = self.blockchain.tokens[self.token_symbol]
        # yield of underlying token (LST)
        native_yield = lst_info.get('yield_per_block', 0.0)

        annualized_yield = native_yield * self.blockchain.num_blocks

        # calculate yield margin
        yield_margin = (self.expected_apy - annualized_yield)/annualized_yield

        # if yield margin exceeds threshold >> deposit
        if yield_margin > self.yield_margin_threshold:
            # determine amount to be deposited
            deposit_amount = buying_intent(yield_margin, base_volume=1, threshold=0.25, growth_rate=3)
            deposit_amount = min(deposit_amount, self.wallet.eth_balance)
            # deposit LST
            vault.deposit_eth(self.wallet, deposit_amount)
            self.log_action(f'Deposited {deposit_amount} ETH into LV')

        # if the yield decreases below the yield of the PA.
        #  So people will redeem their LV token to get back Redemption Asset.
        if yield_margin < native_yield:
            # determine amount to be redeemed
            # get LP Token balance
            redeem_amount = self.wallet.lpt_balance(self.token_symbol)
            if redeem_amount > 0:
                # redeem LV
                vault.withdraw_lp_tokens(self.wallet, redeem_amount)
                self.log_action(f'Redeemed {redeem_amount} LV tokens')
                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'LV', 
                    'volume': redeem_amount, 
                    'action': 'redeem', 
                    'reason': 'yield margin < native yield',
                    'additional_info': {'yield_margin': yield_margin, 'native_yield': native_yield}
                    })
