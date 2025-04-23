import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp


class LoopingAgent(Agent):
    """
    The price of the DS must be lower than the delta between Pegged Asset yield and the borrow rate in the lending market, 
    otherwise the loop is not profitable

    Caution: The agent will hold both the borrowed ETH and the token used as collateral in the wallet.
    This will inflate the face value of the wallet
    """
    def __init__(self, token_symbol: str, initial_borrow_rate=0.01, borrow_rate_changes=None, max_ltv=0.7, lltv=0.915, name: str = None):
        agent_name = name if name else f'LoopingAgent for {token_symbol}'
        super().__init__(agent_name)
        self.token_symbol = token_symbol
        self.arp_history = []
        self.borrow_rate = initial_borrow_rate
        self.borrow_rate_changes = borrow_rate_changes if borrow_rate_changes else {}
        self.total_borrowed_eth = 0
        self.max_ltv = max_ltv
        self.total_tokens_as_collateral = 0
        self.lltv = lltv

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        self.borrow_rate += self.borrow_rate_changes.get(block_number, 0.0)

        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        lst_info = self.blockchain.tokens[self.token_symbol]
        native_yield = lst_info.get('yield_per_block', 0.0)
        total_yield = native_yield * (self.blockchain.num_blocks - self.blockchain.current_block)

        amm = self.blockchain.get_amm(self.token_symbol)
        lst_price_in_eth = amm.price_of_one_token_in_eth()    
        
        if (ds_price < (total_yield - self.borrow_rate)) and (self.wallet.eth_balance > 0.1):
            token_purchase_volume = (self.wallet.eth_balance / (ds_price + lst_price_in_eth)) * 0.9
            token_purchase_volume = round(token_purchase_volume, 0)
            amm.swap_eth_for_token(self.wallet, token_purchase_volume)
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'Token', 
                'volume': token_purchase_volume, 
                'action': 'buy', 
                'reason': 'ds_price < (total_yield - borrow_rate)',
                'additional_info': {'ds_price': ds_price, 'total_yield': total_yield, 'borrow_rate': self.borrow_rate}
            })

            vault.buy_ds(self.wallet, token_purchase_volume * ds_price)
            self.log_action(f'Bought DS with {token_purchase_volume:.4f} ETH')
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'DS', 
                'volume': token_purchase_volume, 
                'action': 'buy', 
                'reason': 'ds_price < (total_yield - borrow_rate)',
                'additional_info': {'ds_price': ds_price, 'total_yield': total_yield, 'borrow_rate': self.borrow_rate}
            })

            max_borrowable_eth = self.total_tokens_as_collateral * self.max_ltv
            remaining_borrow_eth = max_borrowable_eth - self.total_borrowed_eth
            max_borrowable_eth_lltv = self.total_tokens_as_collateral * self.lltv
            eth_to_borrow = min(remaining_borrow_eth, max_borrowable_eth_lltv)

            self.wallet.eth_balance += eth_to_borrow
            self.total_borrowed_eth += eth_to_borrow
            self.total_tokens_as_collateral += eth_to_borrow / self.lltv
