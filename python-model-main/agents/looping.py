import numpy as np
import pandas as pd

from simulator.agent import Agent
from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp

class LoopingAgent(Agent):
    def __init__(self, name, token_symbol: str, initial_borrow_rate=0.01, borrow_rate_changes=None, max_ltv=0.7, lltv=0.915):
        super().__init__(name)
        self.token_symbol = token_symbol
        self.borrow_rate = initial_borrow_rate
        self.borrow_rate_changes = borrow_rate_changes or {}
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
            total_eth_needed_per_unit = ds_price + lst_price_in_eth
            max_affordable_volume = self.wallet.eth_balance / total_eth_needed_per_unit * 0.9
            token_purchase_volume = np.floor(max_affordable_volume)

            eth_for_token = token_purchase_volume
            eth_for_ds = token_purchase_volume * ds_price
            total_eth_needed = eth_for_token + eth_for_ds

            # Explicit safeguard
            if total_eth_needed > self.wallet.eth_balance:
                token_purchase_volume = np.floor(self.wallet.eth_balance / (1 + ds_price))
                eth_for_token = token_purchase_volume
                eth_for_ds = token_purchase_volume * ds_price
                total_eth_needed = eth_for_token + eth_for_ds

            # Final safety check before any transactions
            if token_purchase_volume > 0 and total_eth_needed <= self.wallet.eth_balance:
                # Buy Token
                self.blockchain.tokens[self.token_symbol]['amm'].swap_eth_for_token(
                    self.wallet, eth_for_token
                )
                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'Token',
                    'volume': eth_for_token,
                    'action': 'buy',
                    'reason': 'profitable arbitrage',
                    'additional_info': {
                        'ds_price': ds_price,
                        'total_yield': total_yield,
                        'borrow_rate': self.borrow_rate
                    }
                })

                # Buy DS explicitly safely
                vault.buy_ds(self.wallet, eth_for_ds)
                self.log_action(f'Bought DS with {eth_for_ds:.4f} ETH')
                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'DS',
                    'volume': eth_for_ds,
                    'action': 'buy',
                    'reason': 'profitable arbitrage',
                    'additional_info': {
                        'ds_price': ds_price,
                        'total_yield': total_yield,
                        'borrow_rate': self.borrow_rate
                    }
                })

                # Use tokens as collateral safely
                max_borrowable_eth = self.total_tokens_as_collateral * self.max_ltv
                remaining_borrow_eth = max_borrowable_eth - self.total_borrowed_eth
                max_borrowable_eth_lltv = self.total_tokens_as_collateral * self.lltv
                eth_to_borrow = min(remaining_borrow_eth, max_borrowable_eth_lltv)

                if eth_to_borrow > 0:
                    self.wallet.eth_balance += eth_to_borrow
                    self.total_borrowed_eth += eth_to_borrow
                    self.total_tokens_as_collateral += eth_to_borrow / self.lltv
                    self.log_action(f'Borrowed {eth_to_borrow:.4f} ETH using collateral')
                    self.log_trade({
                        'block': block_number,
                        'agent': self.name,
                        'token': 'ETH',
                        'volume': eth_to_borrow,
                        'action': 'borrow',
                        'reason': 'collateralized borrowing',
                        'additional_info': {
                            'collateral_tokens': self.total_tokens_as_collateral,
                            'borrow_rate': self.borrow_rate
                        }
                    })


