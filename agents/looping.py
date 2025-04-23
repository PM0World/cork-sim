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
    def __init__(self, name, token_symbol: str, initial_borrow_rate=0.01, borrow_rate_changes={}, max_ltv=0.7, lltv=0.915):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.borrow_rate = initial_borrow_rate
        self.borrow_rate_changes = borrow_rate_changes
        self.total_borrowed_eth = 0
        self.max_ltv = max_ltv
        self.total_tokens_as_collateral = 0
        self.lltv = lltv

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        # we see if there is a borrow rate change and update accordings
        # this is done every block to keep the borrow rate up to date
        # regardless of whether a trade happens for this agent
        self.borrow_rate = self.borrow_rate + self.borrow_rate_changes.get(block_number, 0.0)

        # DS Buying Strategy
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        
        # evaluate current yield of LST
        # from the Liquid Staken Token get it's yield
        lst_info = self.blockchain.tokens[self.token_symbol]
        # yield of underlying token (LST)
        native_yield = lst_info.get('yield_per_block', 0.0)
        total_yield = native_yield * (self.blockchain.num_blocks - self.blockchain.current_block)

        amm = self.blockchain.get_amm(self.token_symbol)
        lst_price_in_eth = amm.price_of_one_token_in_eth()    
        
        if (ds_price < (total_yield - self.borrow_rate)) and (self.wallet.eth_balance > 0.1):

            # 1. buy token
            # reserve some ETH for the DS purchase
            token_purchase_volume = (self.wallet.eth_balance / (ds_price + lst_price_in_eth)) * 0.9 # slippage
            token_purchase_volume = round(token_purchase_volume, 0)
            self.blockchain.tokens[self.token_symbol]['amm'].swap_eth_for_token(self.wallet, token_purchase_volume)
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'Token', 
                'volume': token_purchase_volume, 
                'action': 'buy', 
                'reason': 'ds_price < (total_yield - self.borrow_rate)',
                'additional_info': {'ds_price': ds_price, 'total_yield': total_yield, 'borrow_rate': self.borrow_rate}
                })

            # 2. buy respective amount of DS
            vault.buy_ds(self.wallet, token_purchase_volume*ds_price)
            self.log_action(f'Bought DS with {token_purchase_volume:.4f} ETH')
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'DS', 
                'volume': token_purchase_volume, 
                'action': 'buy', 
                'reason': 'ds_price < (total_yield - self.borrow_rate)',
                'additional_info': {'ds_price': ds_price, 'total_yield': total_yield, 'borrow_rate': self.borrow_rate}
                })

            # 3. use token as collateral to borrow more ETH (at the borrow rate)
            # calculate the amount of ETH that can be borrowed
            # based on the current LTV 
            max_borrowable_eth = self.total_tokens_as_collateral * self.max_ltv
            remaining_borrow_eth = max_borrowable_eth - self.total_borrowed_eth

            # calculate the amount of ETH that can be borrowed
            # based on the LLTV and collateral at hand
            max_borrowable_eth_lltv = self.total_tokens_as_collateral * self.lltv

            eth_to_borrow = min(remaining_borrow_eth, max_borrowable_eth_lltv)

            self.wallet.eth_balance += eth_to_borrow
            self.total_borrowed_eth += eth_to_borrow

            self.total_tokens_as_collateral += eth_to_borrow / self.lltv

            # 4 update DS price and yield
            # (not needed here as we do one trade per block)
            # ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
            # native_yield = lst_info.get('yield_per_block', 0.0)

            


