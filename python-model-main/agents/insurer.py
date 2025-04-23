from simulator.agent import Agent


class Insurer(Agent):

    def __init__(self, lst_symbol: str):
        super().__init__(f'Insurer for {lst_symbol}')
        self.lst_symbol = lst_symbol

    def on_block_mined(self, block_number: int):
        # Access the AMM for the token and the PSM
        amm = self.blockchain.get_amm(self.lst_symbol)
        psm = self.blockchain.get_psm(self.lst_symbol)

        # Attempt to buy some ETH by swapping LST tokens
        try:
            # Buy 1 ETH worth of LST (can adjust to any desired amount)
            lst_price_in_eth = amm.price_of_one_token_in_eth()
            amount_lst_to_swap = 1 / lst_price_in_eth
            amm.swap_token_for_eth(self.wallet, amount_lst_to_swap)
            self.log_action(f'bought 1 ETH by swapping {amount_lst_to_swap:.4f} {self.lst_symbol}')

            # Deposit the ETH into the PSM
            eth_balance = self.wallet.eth_balance
            psm.deposit_eth(self.wallet, eth_balance)
            self.log_action(f'deposited {eth_balance:.4f} ETH into the PSM for {self.lst_symbol}')
        except ValueError:
            self.log_action(f'no more {self.lst_symbol}, would ❤️ insure more')
