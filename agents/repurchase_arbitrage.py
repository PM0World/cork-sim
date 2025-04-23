import math
import numpy as np
import pandas as pd

from simulator.agent import Agent

from agents.utils.volume_calculations import buying_intent_increasing_above_1

class RepurchaseArbitrageAgent(Agent):
    def __init__(self, name, token_symbol: str):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.lst_symbol = token_symbol

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)
        
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        # evaluate current price of LST at AMM
        amm = self.blockchain.get_amm(self.lst_symbol)
        lst_price_in_eth = amm.price_of_one_token_in_eth()  

        psm = self.blockchain.get_psm(self.token_symbol)

        repurchase_fee = psm.repurchase_fee

        if (lst_price_in_eth + ds_price) > (1+repurchase_fee):
            # determine buying intent and amount
            buying_intent = buying_intent_increasing_above_1(lst_price_in_eth + ds_price-repurchase_fee)
            
            # calculate potential amount to buy
            potential_amount = buying_intent * self.wallet.eth_balance

            # check availability of tokens in PSM
            token_reserve = psm.token_reserve

            transaction_amount = min(self.wallet.eth_balance, token_reserve)

            if transaction_amount > 0:
                # this agent buys LST & DS directly from the peg stability module PSM
                # price for both together at PSM is always 1
                # get the peg stability module PSM

                transaction_amount = psm.repurchase_token_and_ds(self.wallet, transaction_amount)

                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'LST',
                    'volume': transaction_amount  * lst_price_in_eth,
                    'action': 'Repurchase from PSM',
                    'reason': 'lst_price_in_eth + ds_price > 1',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })

                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'DS', 
                    'volume': transaction_amount * ds_price, 
                    'action': 'Repurchase from PSM', 
                    'reason': 'lst_price_in_eth + ds_price > 1',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })

                # sell both at market rates (expected to be higher than 1 ETH for a pair)
                vault.sell_ds(self.wallet, transaction_amount)
                amm.swap_token_for_eth(self.wallet, transaction_amount)

                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'DS', 
                    'volume': transaction_amount * ds_price, 
                    'action': 'sell', 
                    'reason': 'Immediate Sell at Market after Repurchase',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })
                
                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'LST', 
                    'volume': transaction_amount * lst_price_in_eth, 
                    'action': 'sell', 
                    'reason': 'Immediate Sell at Market after Repurchase',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })
