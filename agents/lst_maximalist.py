# A sample actor that is very bullish on a specific lst and just buys one more per round.
import random

from simulator.agent import Agent


class LstMaximalist(Agent):

    def __init__(self, lst_symbol: str, name: str = None):
        agent_name = name if name else f'LST Maximalist for {lst_symbol}'
        super().__init__(agent_name)
        self.lst_symbol = lst_symbol

    def on_block_mined(self, block_number: int):
        amm = self.blockchain.get_amm(self.lst_symbol)

        lst_price_in_eth = amm.price_of_one_token_in_eth()

        try:
            amm.swap_eth_for_token(self.wallet, lst_price_in_eth)
            self.log_action(f'bought one {self.lst_symbol} with {lst_price_in_eth:.4f} ETH')

            amm.add_liquidity(self.wallet, 1, lst_price_in_eth)
            self.log_action(f'added liquidity to ETH/{self.lst_symbol} with 1 ETH and {lst_price_in_eth:.4f} LST')

        except ValueError:
            self.log_action(f'no more ETH, would ❤️ to buy more.')