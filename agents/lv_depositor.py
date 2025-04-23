import math
import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.volume_calculations import buying_intent

class LVDepositorAgent(Agent):
    def __init__(self, token_symbol: str, expected_apy=0.05, yield_margin_threshold=0.25, name: str = None):
        agent_name = name if name else f'LVDepositorAgent for {token_symbol}'
        super().__init__(agent_name)
        self.token_symbol = token_symbol
        self.arp_history = []
        self.yield_margin_threshold = yield_margin_threshold
        self.expected_apy = expected_apy
        
    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        lst_info = self.blockchain.tokens[self.token_symbol]
        native_yield = lst_info.get('yield_per_block', 0.0)

        annualized_yield = native_yield * self.blockchain.num_blocks

        yield_margin = (self.expected_apy - annualized_yield) / annualized_yield

        if yield_margin > self.yield_margin_threshold:
            deposit_amount = buying_intent(yield_margin, base_volume=1, threshold=0.25, growth_rate=3)
            deposit_amount = min(deposit_amount, self.wallet.eth_balance)
            vault.deposit_eth(self.wallet, deposit_amount)
            self.log_action(f'Deposited {deposit_amount} ETH into LV')

        if yield_margin < native_yield:
            redeem_amount = self.wallet.lpt_balance(self.token_symbol)
            if redeem_amount > 0:
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