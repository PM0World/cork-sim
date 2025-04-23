import numpy as np
import pandas as pd

from simulator.agent import Agent

from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp

class CTShortTermAgent(Agent):
    """
    CTShortTermAgent Class

    Speculates on short-term price movements of DS tokens relative to LST yields by reacting to sharp ARP changes.

    Attributes:
        name (str): Optional agent name.
        token_symbol (str): The target token symbol.
        arp_history (list): History of calculated ARPs.
        lst_symbol (str): Alias for token_symbol.
        buying_pressure (float): Multiplier for aggressiveness of buying.
        threshold (float): Threshold for detecting sharp ARP changes.

    Methods:
        on_block_mined(block_number: int):
            Evaluates DS price, calculates ARP, detects sharp ARP changes, and executes trades accordingly.

    Context:
        Reacts dynamically to exploit temporary mispricings by adjusting DS token positions based on sharp ARP trends.
    """

    def __init__(self, token_symbol: str, buying_pressure: float, threshold: float = 0.01, name: str = None):
        agent_name = name if name else f'CT Short Term for {token_symbol}'
        super().__init__(agent_name)
        self.token_symbol = token_symbol
        self.lst_symbol = token_symbol
        self.arp_history = []
        self.buying_pressure = buying_pressure
        self.threshold = threshold

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

        ct_price = vault.ct_eth_amm.price_of_one_token_in_eth()
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        lst_info = self.blockchain.tokens[self.lst_symbol]
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
            sharp_decline = sharp_incline = False
            ewa_slope = 0

        if sharp_incline:
            weighted_volume = self.buying_pressure * ewa_slope
            volume_to_buy = min(weighted_volume, self.wallet.eth_balance)
            vault.ct_eth_amm.swap_eth_for_token(wallet=self.wallet, amount_eth=volume_to_buy)
            self.log_action(f'Bought CT with {volume_to_buy:.4f} ETH')
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'CT', 
                'volume': volume_to_buy, 
                'action': 'buy', 
                'reason': 'sharp INcline',
                'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
            })

        if sharp_decline:
            current_price = ct_price
            weighted_volume = max(self.buying_pressure * (-ewa_slope) / current_price, 0)
            volume_to_sell = min(weighted_volume, self.wallet.token_balances.get(f'CT_{self.token_symbol}', 0))
            vault.ct_eth_amm.swap_token_for_eth(wallet=self.wallet, amount_token=volume_to_sell)
            self.log_action(f'Sold {volume_to_sell:.4f} CT')
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'CT', 
                'volume': volume_to_sell / ct_price, 
                'action': 'sell', 
                'reason': 'sharp DEcline',
                'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
            })