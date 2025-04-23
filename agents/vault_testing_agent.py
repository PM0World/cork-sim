from simulator.agent import Agent

class VaultTestingAgent(Agent):

    def __init__(self, token_symbol: str):
        self.token_symbol = token_symbol
        super().__init__(f'VaultTestingAgent for {token_symbol}')

    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.token_symbol)
        # Deposit 10 LP tokens into the vault

        # Step 1: Deposit 1 ETH into the vault
        amount_eth_to_deposit = 1.0
        vault.deposit_eth(self.wallet, amount_eth_to_deposit)
        self.log_action(f'deposited {amount_eth_to_deposit:.4f} ETH into the vault')

        # Step 2: Print balance of the depositor and the vault after deposit
        depositor_balance = self.wallet.eth_balance
        vault_balance = vault.wallet.eth_balance
        self.log_action(f'Balance after deposit: Depositor: {depositor_balance:.4f} ETH | Vault: {vault_balance:.4f} ETH')

        # Step 3: Withdraw the LP tokens and print the new balance
        amount_lp_to_withdraw = 1.0  # Withdraw exactly 1 LP tokens back
        vault.withdraw_lp_tokens(self.wallet, amount_lp_to_withdraw)
        self.log_action(f'Withdrew {amount_lp_to_withdraw:.4f} LP tokens from the vault')

        # Step 4: Print balance of the depositor and vault after withdrawal
        depositor_balance_after = self.wallet.eth_balance
        vault_balance_after = vault.wallet.eth_balance
        self.log_action(f'Balance after withdrawal: Depositor: {depositor_balance_after:.4f} ETH | Vault: {vault_balance_after:.4f} ETH')

