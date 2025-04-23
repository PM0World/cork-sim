from simulator.agent import Agent

class DSBuyerAgent(Agent):

    def __init__(self, token_symbol: str):
        self.token_symbol = token_symbol
        super().__init__(f'DSBuyerAgent for {token_symbol}')

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)
        # Step 1: Buy DS with 1 ETH
        amount_eth_to_buy_ds = 1.0
        self.log_action(f'Starting to buy DS with {amount_eth_to_buy_ds:.4f} ETH')
        vault.buy_ds(self.wallet, amount_eth_to_buy_ds)
        self.log_action(f'Bought DS with {amount_eth_to_buy_ds:.4f} ETH')

        # Step 2: Print balance after DS purchase
        ds_balance = self.wallet.token_balance(f'DS_{self.token_symbol}')
        self.log_action(f'Balance after DS purchase: {ds_balance:.4f} DS')

        # Step 3: Sell DS back, rounded down to a full int for better debugging
        amount_ds_to_sell = int(ds_balance)
        self.log_action(f'Starting to sell {amount_ds_to_sell:.4f} DS')
        vault.sell_ds(self.wallet, amount_ds_to_sell)
        self.log_action(f'Sold {amount_ds_to_sell:.4f} DS')

        # Step 4: Print balance after DS sale
        eth_balance_after_sale = self.wallet.eth_balance
        self.log_action(f'Balance after DS sale: {eth_balance_after_sale:.4f} ETH')
