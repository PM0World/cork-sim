import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp


class DSShortTermAgent(Agent):
    def __init__(self, token_symbol: str, threshold=0.01, name: str = None):
        agent_name = name if name else f'DSShortTermAgent for {token_symbol}'
        super().__init__(agent_name)
        self.token_symbol = token_symbol
        self.arp_history = []
        self.lst_symbol = token_symbol
        self.threshold = threshold

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)

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

        if sharp_decline:
            weighted_volume = 100 * ewa_slope * (-1)
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
                    pass

        if sharp_incline:
            weighted_volume = 100 * ewa_slope / ds_price
            corrected_volume = min(weighted_volume, self.wallet.token_balances.get(f'DS_{self.token_symbol}', 0))
            if corrected_volume > 0:
                try:
                    vault.sell_ds(self.wallet, corrected_volume)
                    self.log_action(f'Sold {corrected_volume:.4f} DS')
                    self.log_trade({
                        'block': block_number,
                        'agent': self.name,
                        'token': 'DS',
                        'volume': corrected_volume / ds_price,
                        'action': 'sell',
                        'reason': 'sharp incline',
                        'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
                    })
                except ValueError:
                    pass