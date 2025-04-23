class Wallet:

    @classmethod
    def all_wallets(cls):
        return cls.wallets or []

    @classmethod
    def add_wallet(cls, wallet):
        if not hasattr(cls, 'wallets'):
            cls.wallets = []

        cls.wallets.append(wallet)

    def __init__(self, owner: str = None):
        self.owner = 'Unknown wallet' if owner is None else owner
        self.eth_balance = 0.0
        self.token_balances = {}  # Tracks balances of any tokens (LST, CT, DS, etc.)
        self.lpt_balances = {}  # Tracks balances of Liquidity Pool Tokens (LPTs)

        Wallet.add_wallet(self)


    def set_initial_balances(self, eth_balance: float, token_balances: dict = None):
        token_balances = token_balances or {}
        if eth_balance < 0:
            raise ValueError("ETH balance must be non-negative")
        if any(amount < 0 for amount in token_balances.values()):
            raise ValueError("Token balances must be non-negative")
        self.eth_balance = eth_balance
        self.token_balances = token_balances

    # ETH deposit and withdrawal
    def deposit_eth(self, amount: float):
        if amount < 0:
            raise ValueError("Deposit amount must be positive")
        self.eth_balance += amount

    def withdraw_eth(self, amount: float):
        if amount > self.eth_balance:
            raise ValueError("Not enough ETH balance")
        self.eth_balance -= amount

    # Token deposit and withdrawal (general for all token types: LST, CT, DS, etc.)
    def deposit_token(self, token: str, amount: float):
        if amount < 0:
            raise ValueError("Deposit amount must be positive")
        if token not in self.token_balances:
            self.token_balances[token] = 0.0
        self.token_balances[token] += amount

    def withdraw_token(self, token: str, amount: float):
        if token not in self.token_balances or amount > self.token_balances[token]:
            raise ValueError(f"Not enough {token} balance")
        self.token_balances[token] -= amount

    def token_balance(self, token: str) -> float:
        """Returns the balance of a specific token (LST, CT, DS, etc.)."""
        return self.token_balances.get(token, 0.0)

    # LPT deposit and withdrawal
    def deposit_lpt(self, pool_name: str, amount: float):
        """Deposit Liquidity Pool Tokens (LPTs) for a given pool."""
        if amount < 0:
            raise ValueError("Deposit amount must be positive")
        if pool_name not in self.lpt_balances:
            self.lpt_balances[pool_name] = 0.0
        self.lpt_balances[pool_name] += amount

    def withdraw_lpt(self, pool_name: str, amount: float):
        """Withdraw Liquidity Pool Tokens (LPTs) for a given pool."""
        if pool_name not in self.lpt_balances or amount > self.lpt_balances[pool_name]:
            raise ValueError("Not enough LPT balance")
        self.lpt_balances[pool_name] -= amount

    def lpt_balance(self, pool_name: str) -> float:
        """Returns the LPT balance for a specific pool."""
        return self.lpt_balances.get(pool_name, 0.0)

    def __str__(self):
        return f'{self.owner}'
