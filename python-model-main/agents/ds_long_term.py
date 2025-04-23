from simulator.agent import Agent
import numpy as np

class DSLongTermAgent(Agent):
    """
    This agent represents a large, long-term investor who aims to accumulate DS (Decoupled Staking) tokens based on favorable yield conditions relative to the pegged asset (PA). The agent's buying decisions are based on the relationship between DS price and the yield received from holding the underlying LST (Liquid Staking Token). Additionally, the agent implements a redemption strategy in case of prolonged depegging events.

    Attributes:
        name (str): The name of the agent.
        token_symbol (str): The symbol of the target token (LST) being compared.
        lst_symbol (str): Alias for token_symbol.
        buying_pressure (float): A multiplier indicating the aggressiveness of the buying strategy.
        k (float): A scaling factor controlling the rate of exponential decay in the buying intent calculation.
        depeg_threshold (float): The price threshold below which the agent starts to consider selling DS tokens.
        lst_price_history (list): A history of LST prices used to evaluate extended depegging events.

    Methods:
        on_block_mined(block_number: int):
            Called when a new block is mined. The agent evaluates the DS price and the full-period LST yield. It calculates buying intent using an exponential decay model, making large, concentrated purchases when intent is strong. Additionally, if the LST price remains below the depeg threshold, the agent progressively exits DS positions based on the duration of the depeg event.

        calculate_buying_intent(ds_price: float, pa_yield: float) -> float:
            Calculates the agent's buying intent using an exponential decay model based on the DS price and the yield of the pegged asset. Returns a value between 0 and 1.

        count_consecutive_under_threshold(price_history: list, threshold: float = 0.95) -> int:
            Counts the number of consecutive periods where the price of the pegged asset remains below a defined threshold. Returns the count of such periods, which is used to scale the redemption volume.

    Context:
        The DSLongTermAgent targets long-term accumulation of DS tokens, concentrating its buying activity when DS prices are significantly lower than the yield of the pegged asset. The agent executes large but infrequent purchases, spreading transactions over time to avoid market impact. During depegging events, a phased redemption strategy is employed where an increasing share of DS holdings is sold as the depeg persists.
    """
    def __init__(self, name, token_symbol: str, buying_pressure: float, k=5, depeg_threshold=0.98):
        super().__init__(name)
        self.token_symbol = token_symbol
        self.lst_symbol = token_symbol
        self.buying_pressure = buying_pressure
        self.k = k
        self.depeg_threshold = depeg_threshold
        self.lst_price_history = []

    def on_block_mined(self, block_number: int):

        vault = self.blockchain.get_vault(self.token_symbol)
        
        # DS Buying Strategy
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()

        # evaluate current yield of LST over full blocks
        # TODO change to remaining blocks?
        lst_yield_per_block = (
            self.blockchain.tokens[self.lst_symbol].get('yield_per_block', 0.0) *
            self.blockchain.num_blocks
        )

        lst_price = vault.lst_eth_amm.price_of_one_token_in_eth()
        
        buying_intent = self.calculate_buying_intent(ds_price, lst_yield_per_block)

        # take buying decision
        # agent buys according to buying intent some share of his ETH balance
        # this is moderated by the buying pressure param (max at 1 or scaling down the amount)
        amount_eth_to_buy_ds = buying_intent * self.wallet.eth_balance * self.buying_pressure
        
        if amount_eth_to_buy_ds > 0:
            # execute buying decision
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

            # Print balance after DS purchase
            ds_balance = self.wallet.token_balance(f'DS_{self.token_symbol}')
            self.log_action(f'Balance after DS purchase: {ds_balance:.4f} DS')

        # Redemption Strategy
        # at depeg “init” some share exits, over a sustained depeg period more and more exit

        # Step 3: Sell DS back, rounded down to a full int for better debugging
        
        # get history of PA price 
        self.lst_price_history.append(lst_price)
        # calculate amount based on current PA price if below a certain threshold
        # and a share of the total DS balance 
        if lst_price <= self.depeg_threshold:
            ds_balance = self.wallet.token_balance(f'DS_{self.token_symbol}')
            # for every last consecutive n days sell a 0.1 share of the total DS balance
            extended_depeg_increase = self.count_consecutive_under_threshold(self.lst_price_history, self.depeg_threshold)
            amount_ds_to_sell = int(ds_balance * extended_depeg_increase * 0.1)
            amount_ds_to_sell = min(amount_ds_to_sell, ds_balance)
            if amount_ds_to_sell > 0:
                self.log_action(f'Starting to sell {amount_ds_to_sell:.4f} DS')
                vault.sell_ds(self.wallet, amount_ds_to_sell)
                self.log_action(f'Sold {amount_ds_to_sell:.4f} DS')

                # Step 4: Print balance after DS sale
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
        """
        Calculates the buying intent based on the DS price and PA yield using an exponential decay model.
        
        Parameters:
        ds_price (float): The current price of the DS token.
        pa_yield (float): The yield of the pegged asset.
        k (float): Scaling factor controlling the rate of decay (default is 5).
        
        Returns:
        float: The buying intent, a value between 0 and 1.
        """
        k = self.k
        return np.exp(-k * (ds_price / pa_yield))

    def count_consecutive_under_threshold(self, price_history, threshold=0.95):
        count = 0
        for price in reversed(price_history):
            if price < threshold:
                count += 1
            else:
                break
        return count

