from simulator.wallet import Wallet


class Agent:

    def __init__(self, name: str):
        self.name = name
        self.blockchain = None
        self.wallet = Wallet(self.name)

    def on_after_genesis(self, blockchain):
        self.blockchain = blockchain

    def on_block_mined(self, block_number: int):
        pass

    def log_action(self, action):
        self.blockchain.add_action( action)
    
    def log_trade(self, trade):
        self.blockchain.add_trade(trade)

    def get_wallet_face_value(self):
        # Start with the agent's ETH balance
        total_eth_value = self.wallet.eth_balance

        # Add the ETH equivalent of all LST balances
        for token, token_balance in self.wallet.token_balances.items():
            amm = self.blockchain.get_amm(token)
            token_price_in_eth = amm.price_of_one_token_in_eth()
            total_eth_value += token_balance * token_price_in_eth

        # Add the agent's share of ETH and LST in each liquidity pool based on their LPT balance
        for pool_name, lpt_balance in self.wallet.lpt_balances.items():
            if pool_name.startswith('V_'):
                token = pool_name[2:]
                vault = self.blockchain.get_vault(token)
                price = vault.get_lp_token_price()
                total_eth_value += lpt_balance * price
                continue
            amm = self.blockchain.get_amm(pool_name)
            if amm.total_lpt_supply == 0:
                continue  # Avoid division by zero if there's no liquidity in the pool

            # Calculate the agent's share of the ETH and LST in the pool based on their LPT holdings
            eth_share = (lpt_balance / amm.total_lpt_supply) * amm.reserve_eth
            token_share = (lpt_balance / amm.total_lpt_supply) * amm.reserve_token
            token_price_in_eth = amm.price_of_one_token_in_eth()

            # Convert the LST share to ETH equivalent
            token_share_in_eth = token_share * token_price_in_eth

            # Add the agent's share of ETH and the ETH equivalent of their LST share to the total value
            total_eth_value += eth_share + token_share_in_eth

        return total_eth_value

    def __str__(self):
        return self.name
