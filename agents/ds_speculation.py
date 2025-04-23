import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp


class DSShortTermAgent(Agent):
    """
    DSShortTermAgent Class

    This agent focuses on short-term trading of DS tokens based on the fluctuations in annualized risk premium (ARP) relative to the underlying LST (Liquid Staking Token). The agent's strategy is to capitalize on sharp declines or increases in ARP by dynamically adjusting its buying or selling volume, reacting to market trends and opportunities.

    Attributes:
        name (str): The name of the agent.
        token_symbol (str): The symbol of the target token (LST) being compared.
        arp_history (list): A history of calculated ARPs for the DS token.
        lst_symbol (str): Alias for token_symbol.
        threshold (float): The sensitivity threshold for detecting sharp changes in ARP slope.

    Methods:
        on_block_mined(block_number: int):
            Called when a new block is mined. This method evaluates the DS price relative to the full expiry period and calculates ARP. The agent monitors ARP history to detect sharp changes using an exponentially weighted average (EWA) slope. A sharp decline prompts the agent to buy DS tokens, while a sharp incline triggers a selling action. Each action is logged with transaction details.

        detect_sharp_decline(prices: list, n: int = 10, alpha: float = 0.3, decline_threshold: float = -0.05, incline_threshold: float = 0.05) -> tuple:
            Analyzes a series of ARP data points to detect sharp declines or inclines using an exponentially weighted average slope. Returns a tuple with booleans indicating sharp decline and incline, as well as the calculated slope.

    Context:
        The DSShortTermAgent aims to exploit temporary mispricings by responding quickly to changes in the ARP between DS and LST tokens. By using an EWA-based detection method, the agent makes swift trading decisions based on detected market trends. This strategy is designed for short-term speculation, adapting dynamically to sharp changes in ARP.
    """
    def __init__(self, name, token_symbol: str, threshold=0.01):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.lst_symbol = token_symbol
        self.threshold = threshold

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        # DS Buying Strategy
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        
        # evaluate current yield of LST
        # from the Liquid Staken Token get it's yield
        lst_info = self.blockchain.tokens[self.lst_symbol]
        # yield of underlying token (LST)
        native_yield = lst_info.get('yield_per_block', 0.0)
  
        arp = calculate_arp(ds_price, native_yield, self.blockchain.num_blocks, self.blockchain.current_block)
        
        self.arp_history.append(arp)

        if len(self.arp_history) >= 3:
            sharp_decline, sharp_incline, ewa_slope = detect_sharp_decline(
                self.arp_history, 
                n=10, 
                alpha=0.3,
                decline_threshold=-self.threshold, 
                incline_threshold=self.threshold
                )
        else:
            sharp_decline = False
            sharp_incline = False
            ewa_slope = 0

        # buy DS
        if sharp_decline:
            weighted_volume = 100 * ewa_slope * (-1)
            # limit to available ETH balance 
            potential_eth_spending = weighted_volume / ds_price
            corrected_volume = min(self.wallet.eth_balance, potential_eth_spending)
            if corrected_volume > 0:
                try:
                    vault.buy_ds(self.wallet, corrected_volume)
                    self.log_action(f'Bought DS with {corrected_volume:.4f} ETH')
                    self.log_trade({
                        'block': block_number,
                        'agent': self.name,
                        'token': 'DS',
                        'volume': corrected_volume,
                        'action': 'buy',
                        'reason': 'sharp decline',
                        'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
                        })
                except ValueError:
                    # not enough liquidity to buy DS
                    pass


        # Sell DS 
        if sharp_incline:
            weighted_volume = 100 * ewa_slope / ds_price # same formula but this time we denote in DS
            corrected_volume = min(weighted_volume, self.wallet.token_balances[f'DS_{self.token_symbol}'])
            if corrected_volume > 0:
                try:
                    vault.sell_ds(self.wallet, corrected_volume)
                    self.log_action(f'Sold {corrected_volume:.4f} DS')
                    self.log_trade({
                        'block': block_number,
                        'agent': self.name,
                        'token': 'DS',
                        'volume': corrected_volume / ds_price, # denoted in ETH
                        'action': 'sell',
                        'reason': 'sharp incline',
                        'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
                        })
                except ValueError:
                    # not enough liquidity to sell DS
                    pass

