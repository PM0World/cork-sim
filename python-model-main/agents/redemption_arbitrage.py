# buying DS
# buys in case of depeg when  LST+DS < 1

# redemption
#immediately after purchase

import math
import numpy as np
import pandas as pd

from simulator.agent import Agent

class RedemptionArbitrageAgent(Agent):
    """
    RedemptionArbitrageAgent is an arbitrage agent that executes trades when the combined price of DS and LST tokens
    falls below 1 (indicating a depeg situation). The agent buys DS and LST tokens in equal amounts using available ETH
    balance and immediately redeems them for ETH on the Peg Stability Module (PSM).

    Attributes:
    -----------
    token_symbol : str
        The symbol of the DS token being traded.
    lst_symbol : str
        The symbol of the LST token being traded.
    liquidity : float
        The liquidity available to the agent for executing trades.

    Methods:
    --------
    on_block_mined():
        This method is called when a new block is mined. The agent evaluates the current prices of DS and LST tokens.
        If the combined price of DS and LST is less than 1, it initiates the buy and redeem process.

        - Evaluates the price of DS and LST on the AMM.
        - Calculates the buying intent based on the depeg margin (i.e., how far DS + LST is from 1).
        - Executes balanced buys of DS and LST tokens using the ETH wallet balance.
        - Immediately redeems the purchased DS and LST tokens for 1 ETH through the Peg Stability Module.

    buying_intent_increasing_below_1(margin, base_volume=1, threshold=1, growth_rate=3):
        Calculates the agent's buying intent based on the margin below 1. The closer DS + LST is to zero,
        the stronger the intent, but the value is normalized to stay between 0 and 1.

        Parameters:
        ----------
        margin : float
            The margin as a decimal representing how far the combined price of DS and LST is from 1 (e.g., 0.2 for 20%).
        base_volume : float, optional
            The base volume of buying intent (default is 1).
        threshold : float, optional
            The margin threshold where buying intent is maximized (default is 1).
        growth_rate : float, optional
            The rate at which the buying intent grows as the margin decreases (default is 3).

        Returns:
        -------
        float
            The normalized buying intent, a value between 0 and 1.

    calculate_ds_lst_amount(balance_in_eth, ds_price, lst_price, spending_percentage):
        Calculates the amounts of DS and LST tokens to buy using a specified percentage of the ETH balance.

        Parameters:
        ----------
        balance_in_eth : float
            The current ETH balance available in the wallet.
        ds_price : float
            The price of one DS token in ETH.
        lst_price : float
            The price of one LST token in ETH.
        spending_percentage : float
            The percentage of the ETH balance to spend on buying DS and LST tokens (between 0 and 100).

        Returns:
        -------
        tuple
            A tuple containing the amounts of DS and LST tokens to be bought.
    """
    def __init__(self, name, token_symbol: str):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.lst_symbol = token_symbol

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)
        # buys in case of depeg when  LST+DS < 1
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        # evaluate current price of LST at AMM
        amm = self.blockchain.get_amm(self.lst_symbol)
        lst_price_in_eth = amm.price_of_one_token_in_eth()    

        # get psm 
        psm = self.blockchain.get_psm(self.token_symbol)

        # get redemption fee from psm
        redemption_fee = psm.redemption_fee
        
        if (lst_price_in_eth + ds_price + redemption_fee) < 1:
            # determine buying intent 
            # buying intent is scaled between 0 and 1
            buying_intent = self.buying_intent_increasing_below_1(lst_price_in_eth + ds_price + redemption_fee)

            # we need to balance the available ETH in wallet
            # in order for the trade to work the agents needs to buy the same amount of DS & LST
            # also we need to consider wallet balance
            token_count = self.calculate_ds_lst_amount(self.wallet.eth_balance, ds_price, lst_price_in_eth, buying_intent*100)

            ds_amount_in_eth = token_count * ds_price

            if vault.calculate_buy_ds_outcome(ds_amount_in_eth) == 0:
                return

            vault.buy_ds(self.wallet, ds_amount_in_eth)

            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'DS', 
                    'volume': ds_amount_in_eth, 
                    'action': 'buy', 
                    'reason': 'lst_price_in_eth + ds_price < 1',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })

            # buys LST in the background to redeem
            lst_amount_in_eth = token_count * lst_price_in_eth
            amm.swap_eth_for_token(self.wallet, lst_amount_in_eth)

            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'LST', 
                    'volume': lst_amount_in_eth, 
                    'action': 'buy', 
                    'reason': 'Match DS buy',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })

            # immediately redeem LST+DS for 1 ETH
            # this is happening on the Peg Stability Module
            # get the peg stability module PSM
            psm = self.blockchain.get_psm(self.token_symbol)
            # get the current block number
            block = self.blockchain.current_block

            # we lose on fees and slippage when doing the above trades
            # so we determine resulting amounts in wallet and sell all

            lst_balance = self.wallet.token_balances[self.token_symbol]
            ds_balance = self.wallet.token_balances[f"DS_{self.token_symbol}"]

            redemption_amount = min(
                lst_balance,
                ds_balance
            )

            psm.redeem_with_token_and_ds(
                self.wallet, 
                redemption_amount,
                block)
            
            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'ETH', 
                    'volume': redemption_amount, 
                    'action': 'redeem', 
                    'reason': 'Immediate Redeem after purchase',
                    'additional_info': {'lst_price_in_eth': lst_price_in_eth, 'ds_price': ds_price}
                    })


    def buying_intent_increasing_below_1(self, margin, base_volume=1, threshold=1, growth_rate=3):
        """
        Calculate normalized buying intent (between 0 and 1) based on a percentage margin using an exponential function.
        The intent increases as the margin goes below the threshold (1), but will not exceed 1.
        
        Parameters:
        margin (float): The margin as a decimal (e.g., 0.2 for 20%).
        base_volume (float): The baseline volume of buying intent (default is 1).
        threshold (float): The margin threshold where buying intent is maximized (default is 1).
        growth_rate (float): The rate at which the intent grows exponentially below the threshold (default is 3).

        Returns:
        float: Normalized buying intent between 0 and 1.
        """
        if margin >= threshold:
            return 0
        else:
            # Use a logistic function or similar to scale the output between 0 and 1
            intent = base_volume * math.exp(growth_rate * (threshold - margin))
            # Normalize the intent to be between 0 and 1
            return 1 - (1 / (1 + intent))

        
    def calculate_ds_lst_amount(self, balance_in_eth, ds_price, lst_price, spending_percentage):
        amount_to_spend = (spending_percentage / 100) * balance_in_eth
        combined_price = ds_price + lst_price
        token_count = amount_to_spend // combined_price
        return token_count