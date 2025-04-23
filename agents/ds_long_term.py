from simulator.agent import Agent
import numpy as np

class DSLongTermAgent(Agent):
    def __init__(self, token_symbol: str, buying_pressure: float, k=5, depeg_threshold=0.98, name: str = None):
        agent_name = name if name else f'DSLongTermAgent for {token_symbol}'
        super().__init__(agent_name)
        self.token_symbol = token_symbol
        self.lst_symbol = token_symbol
        self.buying_pressure = buying_pressure
        self.k = k
        self.depeg_threshold = depeg_threshold
        self.lst_price_history = []

    def on_block_mined(self, block_number: int):

        vault = self.blockchain.get_vault(self.token_symbol)
        
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()

        lst_yield_per_block = (
            self.blockchain.tokens[self.lst_symbol].get('yield_per_block', 0.0) *
            self.blockchain.num_blocks
        )

        lst_price = vault.lst_eth_amm.price_of_one_token_in_eth()
        
        buying_intent = self.calculate_buying_intent(ds_price, lst_yield_per_block)

        amount_eth_to_buy_ds = buying_intent * self.wallet.eth_balance * self.buying_pressure
        
        if amount_eth_to_buy_ds > 0:
            self.log_action(f'Starting to buy DS with {amount_eth_to_buy_ds:.4f} ETH')
            vault.buy_ds(self.wallet, amount_eth_to_buy_ds)
            self.log_action(f'Bought DS with {amount_eth_to_buy_ds:.4f} ETH')
            self.log_trade({
                'block': block_number,
                'agent': self.name,
                'token': 'DS', 
                'volume': amount_eth_to_buy_ds, 
                'action': 'buy', 
                'reason': 'buying_intent',
                'additional_info': {'buying_intent': buying_intent, 'ds_price': ds_price, 'lst_yield_per_block': lst_yield_per_block},
            })

            ds_balance = self.wallet.token_balance(f'DS_{self.token_symbol}')
            self.log_action(f'Balance after DS purchase: {ds_balance:.4f} DS')

        self.lst_price_history.append(lst_price)

        if lst_price <= self.depeg_threshold:
            ds_balance = self.wallet.token_balance(f'DS_{self.token_symbol}')
            extended_depeg_increase = self.count_consecutive_under_threshold(self.lst_price_history, self.depeg_threshold)
            amount_ds_to_sell = int(ds_balance * extended_depeg_increase * 0.1)
            amount_ds_to_sell = min(amount_ds_to_sell, ds_balance)
            if amount_ds_to_sell > 0:
                self.log_action(f'Starting to sell {amount_ds_to_sell:.4f} DS')
                vault.sell_ds(self.wallet, amount_ds_to_sell)
                self.log_action(f'Sold {amount_ds_to_sell:.4f} DS')

                eth_balance_after_sale = self.wallet.eth_balance
                self.log_action(f'Balance after DS sale: {eth_balance_after_sale:.4f} ETH')
                self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'DS', 
                    'volume': amount_ds_to_sell, 
                    'action': 'sell', 
                    'reason': 'lst_price <= self.depeg_threshold',
                    'additional_info': {'lst_price': lst_price, 'depeg_threshold': self.depeg_threshold, 'extended_depeg_increase': extended_depeg_increase},
                })

    def calculate_buying_intent(self, ds_price, pa_yield):
        return np.exp(-self.k * (ds_price / pa_yield))

    def count_consecutive_under_threshold(self, price_history, threshold=0.95):
        count = 0
        for price in reversed(price_history):
            if price < threshold:
                count += 1
            else:
                break
        return count