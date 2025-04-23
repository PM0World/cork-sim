import multiprocessing
import copy
import random

import pandas as pd
from colorama import Fore, Style, init
from simulator.amm import AMM, YieldSpaceAMM, UniswapV2AMM
from simulator.event_manager import EventManager
from simulator.psm import PegStabilityModule
from simulator.vault import Vault
from simulator.wallet import Wallet

init(autoreset=True)


class Blockchain:

    current_block = 0

    def __init__(
            self, num_blocks: int,
            initial_eth_balance: float,
            psm_expiry_after_block: int,
            initial_eth_yield_per_block: float = 0):
        self.event_manager = EventManager.from_json('events.json')
        self.num_blocks = num_blocks
        self.tokens = {}  # Stores tokens and their AMM instances
        self.agents = []  # List of agents participating in the blockchain
        self.initial_eth_balance = initial_eth_balance
        self.initial_eth_balance_overrides = {}
        self.actions = []  # List to store actions taken during mining
        self.all_actions = []  # List to store all actions taken during mining
        self.all_trades = []  # List to store all trades in a structured format executed during mining
        self.genesis_wallet = Wallet()
        self.genesis_wallet.set_initial_balances(1000)
        self.eth_yield_per_block = initial_eth_yield_per_block # The yield in eth per block

        assert psm_expiry_after_block <= num_blocks, "PSM expiry date must be before the end of the simulation"
        self.psm_expiry_at_block = psm_expiry_after_block

        self.borrowed_eth = {}  # Tracks borrowed ETH and the block at which it was borrowed
        self.total_borrowed_eth = 0.0  # Total amount of ETH currently borrowed

        self.borrowed_token = {}  # Tracks borrowed tokens (e.g., LST, CT, DS) per wallet
        self.total_borrowed_token = {}  # Tracks total borrowed tokens by token type

        self.current_block = 0

        self.stats = {
            'agents': pd.DataFrame(columns=['block', 'agent', 'wallet_face_value']),
            'tokens': pd.DataFrame(columns=['block', 'token', 'price']),
            'vaults': pd.DataFrame(columns=['block', 'token', 'total_lpt_supply', 'total_eth_reserve', 'total_token_reserve']),
            'psms': pd.DataFrame(columns=['block', 'token', 'eth_reserve']),
            'amms': pd.DataFrame(columns=['block', 'token', 'total_lpt_supply', 'total_eth_reserve', 'total_token_reserve']),
            'borrowed_eth': pd.DataFrame(columns=['block', 'wallet', 'amount']),
            'borrowed_tokens': pd.DataFrame(columns=['block', 'wallet', 'token', 'amount']),
        }

    def _append_stats(self, block_number):
        # Utility function to check if DataFrame is non-empty and has valid data
        def is_valid_dataframe(df):
            return not df.empty and not df.isna().all(axis=None)

        # Collect stats for each agent
        agent_stats = pd.DataFrame([{
            'block': block_number,
            'agent': str(agent),
            'wallet_face_value': agent.get_wallet_face_value(),
            'wallet_eth_balance': copy.deepcopy(agent.wallet.eth_balance),
            'wallet_token_balances': copy.deepcopy(agent.wallet.token_balances),
            'wallet_lpt_balances': copy.deepcopy(agent.wallet.lpt_balances)
        } for agent in self.agents])

        if is_valid_dataframe(agent_stats):
            if is_valid_dataframe(self.stats['agents']):
                self.stats['agents'] = pd.concat([self.stats['agents'], agent_stats], ignore_index=True)
            else:
                self.stats['agents'] = agent_stats.copy()

        # Collect stats for each token
        token_stats = pd.DataFrame([{
            'block': block_number,
            'token': token,
            'price': lst_info['amm'].price_of_one_token_in_eth()
        } for token, lst_info in self.tokens.items() if 'amm' in lst_info])

        if is_valid_dataframe(token_stats):
            if is_valid_dataframe(self.stats['tokens']):
                self.stats['tokens'] = pd.concat([self.stats['tokens'], token_stats], ignore_index=True)
            else:
                self.stats['tokens'] = token_stats.copy()

        # Collect stats for each vault
        vault_stats = pd.DataFrame([{
            'block': block_number,
            'token': token,
            'lp_token_price_eth': vault.get_lp_token_price(),
            'eth_balance': vault.wallet.eth_balance,
            'ds_balance_eth': vault.ds_eth_amm.price_of_one_token_in_eth() * vault.wallet.token_balance(f'DS_{token}')
        } for token, lst_info in self.tokens.items() if 'vault' in lst_info for vault in [lst_info['vault']]])

        if is_valid_dataframe(vault_stats):
            if is_valid_dataframe(self.stats['vaults']):
                self.stats['vaults'] = pd.concat([self.stats['vaults'], vault_stats], ignore_index=True)
            else:
                self.stats['vaults'] = vault_stats.copy()

        # Collect stats for each PSM
        psm_stats = pd.DataFrame([{
            'block': block_number,
            'token': token,
            'eth_reserve': lst_info['psm'].eth_reserve
        } for token, lst_info in self.tokens.items() if 'psm' in lst_info])

        if is_valid_dataframe(psm_stats):
            if is_valid_dataframe(self.stats['psms']):
                self.stats['psms'] = pd.concat([self.stats['psms'], psm_stats], ignore_index=True)
            else:
                self.stats['psms'] = psm_stats.copy()

        # Collect stats for each AMM
        amm_stats = pd.DataFrame([{
            'block': block_number,
            'token': token,
            'total_lpt_supply': lst_info['amm'].total_lpt_supply,
            'total_eth_reserve': lst_info['amm'].reserve_eth,
            'total_token_reserve': lst_info['amm'].reserve_token
        } for token, lst_info in self.tokens.items() if 'amm' in lst_info])

        if is_valid_dataframe(amm_stats):
            if is_valid_dataframe(self.stats['amms']):
                self.stats['amms'] = pd.concat([self.stats['amms'], amm_stats], ignore_index=True)
            else:
                self.stats['amms'] = amm_stats.copy()

        # Collect stats for each borrowed ETH amount
        borrowed_eth_stats = pd.DataFrame([{
            'block': block_number,
            'wallet': str(wallet),
            'amount': amount
        } for wallet, amount in self.borrowed_eth.items()])

        if is_valid_dataframe(borrowed_eth_stats):
            if is_valid_dataframe(self.stats['borrowed_eth']):
                self.stats['borrowed_eth'] = pd.concat([self.stats['borrowed_eth'], borrowed_eth_stats],
                                                       ignore_index=True)
            else:
                self.stats['borrowed_eth'] = borrowed_eth_stats.copy()

        # Collect stats for each borrowed token amount
        borrowed_token_stats = pd.DataFrame([{
            'block': block_number,
            'wallet': str(wallet),
            'token': token,
            'amount': amount
        } for wallet, token_amounts in self.borrowed_token.items() for token, amount in token_amounts.items()])

        if is_valid_dataframe(borrowed_token_stats):
            if is_valid_dataframe(self.stats['borrowed_tokens']):
                self.stats['borrowed_tokens'] = pd.concat([self.stats['borrowed_tokens'], borrowed_token_stats],
                                                          ignore_index=True)
            else:
                self.stats['borrowed_tokens'] = borrowed_token_stats.copy()

    def __str__(self):
        return f"Blockchain with {len(self.agents)} agents and {len(self.tokens)} tokens at block {self.num_blocks}"

    def add_agent(self, agent, eth_balance: float):
        self.agents.append(agent)
        self.initial_eth_balance_overrides[agent] = eth_balance

    def add_agents(self, *agents):
        for agent in agents:
            self.agents.append(agent)

    def add_token(self, token: str, initial_agent_balance: float, amm: AMM, risk=0.1, initial_yield_per_block=0.00001):
        psm = PegStabilityModule(
            token_symbol=token, expiry_block=self.psm_expiry_at_block, redemption_fee=0.001, repurchase_fee=0.05
        )
        psm.deposit_eth(self.genesis_wallet, 100)

        base_reserve = self.genesis_wallet.eth_balance * 10000
        reserve_ct_eth = base_reserve * (1 - risk)
        reserve_ds_eth = base_reserve * risk

        ct_amm = YieldSpaceAMM(token_symbol=f'CT_{token}', reserve_eth=reserve_ct_eth, reserve_token=base_reserve, discount_rate=1/self.psm_expiry_at_block)
        ds_amm = YieldSpaceAMM(token_symbol=f'DS_{token}', reserve_eth=reserve_ds_eth, reserve_token=base_reserve, discount_rate=1/self.psm_expiry_at_block)

        vault = Vault(
            blockchain=self, token_symbol=token, psm=psm, lst_eth_amm=amm, ct_eth_amm=ct_amm, ds_eth_amm=ds_amm
        )

        self.tokens[token] = {
            'initial_agent_balance': initial_agent_balance,
            'amm': amm,
            'psm': psm,
            'vault': vault,
            'yield_per_block': initial_yield_per_block
        }
        self.tokens[f'CT_{token}'] = {
            'initial_agent_balance': 0,
            'amm': ct_amm
        }
        self.tokens[f'DS_{token}'] = {
            'initial_agent_balance': 0,
            'amm': ds_amm
        }

    def get_vault(self, token: str):
        return self.tokens[token].get('vault')

    def get_psm(self, token: str):
        return self.tokens[token].get('psm')

    def get_amm(self, token: str):
        return self.tokens[token]['amm']

    def add_action(self, action):
        self.actions.append(f'  - {action}')
    
    def add_trade(self, trade):
        self.all_trades.append(trade)

    def borrow_eth(self, wallet, amount_eth: float):
        """Allow an agent to borrow ETH from the blockchain."""
        if amount_eth <= 0:
            raise ValueError("Borrow amount must be positive")

        self.total_borrowed_eth += amount_eth
        self.borrowed_eth[wallet] = self.borrowed_eth.get(wallet, 0.0) + amount_eth
        wallet.deposit_eth(amount_eth)
        self.add_action(f"borrowed {amount_eth:.4f} ETH")

    def repay_eth(self, wallet, amount_eth: float):
        """Allow an agent to repay borrowed ETH to the blockchain."""
        if wallet not in self.borrowed_eth or self.borrowed_eth[wallet] == 0:
            raise ValueError(f"{wallet} has no ETH to repay")

        if amount_eth > self.borrowed_eth[wallet]:
            raise ValueError(f"Cannot repay more than borrowed. Borrowed: {self.borrowed_eth[wallet]:.4f} ETH")

        self.total_borrowed_eth -= amount_eth
        self.borrowed_eth[wallet] -= amount_eth
        wallet.withdraw_eth(amount_eth)
        self.add_action(f"repaid {amount_eth:.4f} ETH")

    def borrow_token(self, wallet: Wallet, token: str, amount_token: float):
        """
        Allow an agent to borrow tokens from the blockchain.

        :param wallet: The wallet borrowing tokens.
        :param token: The token to borrow.
        :param amount_token: The amount of tokens to borrow.
        """
        if amount_token <= 0:
            raise ValueError("Borrow amount must be positive")

        if token not in self.tokens:
            raise ValueError(f"Token {token} does not exist")

        # Track borrowed tokens for this wallet and the total borrowed tokens by type
        self.borrowed_token[wallet] = self.borrowed_token.get(wallet, {})
        self.borrowed_token[wallet][token] = self.borrowed_token[wallet].get(token, 0.0) + amount_token

        self.total_borrowed_token[token] = self.total_borrowed_token.get(token, 0.0) + amount_token

        wallet.deposit_token(token, amount_token)
        self.add_action(f"borrowed {amount_token:.4f} {token}")

    def repay_token(self, wallet: Wallet, token: str, amount_token: float):
        """
        Allow an agent to repay borrowed tokens to the blockchain.

        :param wallet: The wallet repaying tokens.
        :param token: The token being repaid.
        :param amount_token: The amount of tokens to repay.
        """
        if amount_token <= 0:
            raise ValueError("Repayment amount must be positive")

        if wallet not in self.borrowed_token or token not in self.borrowed_token[wallet]:
            raise ValueError(f"{wallet} has no borrowed {token} to repay")

        if amount_token > self.borrowed_token[wallet][token]:
            raise ValueError(
                f"Cannot repay more than borrowed. Borrowed: {self.borrowed_token[wallet][token]:.4f} {token}")

        # Update borrowed token amounts
        self.borrowed_token[wallet][token] -= amount_token
        self.total_borrowed_token[token] -= amount_token

        # Remove token entry from wallet if fully repaid
        if self.borrowed_token[wallet][token] == 0:
            del self.borrowed_token[wallet][token]

        wallet.withdraw_token(token, amount_token)
        self.add_action(f"repaid {amount_token:.4f} {token}")

    def _check_borrowings_repaid(self, block_number: int):
        """Ensure all borrowed ETH and tokens have been repaid at the end of the block."""
        # Check if all borrowed ETH has been repaid
        if self.total_borrowed_eth > 0:
            raise ValueError(
                f"Block {block_number}: Not all borrowed ETH has been repaid. Total outstanding: {self.total_borrowed_eth:.4f} ETH"
            )

        # Check if all borrowed tokens have been repaid
        for token, total_borrowed in self.total_borrowed_token.items():
            if total_borrowed > 0:
                raise ValueError(
                    f"Block {block_number}: Not all borrowed {token} tokens have been repaid. Total outstanding: {total_borrowed:.4f} {token}"
                )

    def collect_stats(self, block_number, print_stats=True):

        self._append_stats(block_number)
        self.all_actions.append(self.actions.copy())

        if print_stats:
            print(Style.BRIGHT + Fore.CYAN + "-" * 100)

            if block_number == 0:
                print(Fore.YELLOW + "*** AND SO IT BEGINS ... ***")
            else:
                print(Fore.YELLOW + f"*** Block number {block_number} mined! ***")

            for action in self.actions:
                print(Fore.BLUE + action)

            for agent in self.agents:
                print(Fore.GREEN + f"Agent: {agent} | Wallet face value: {agent.get_wallet_face_value():.4f} ETH")

            for lst_info in self.tokens.values():
                amm = lst_info['amm']
                print(Fore.MAGENTA + f"LST: {amm.name} | Price: {amm.price_of_one_token_in_eth():.4f} ETH")

            print(Style.BRIGHT + Fore.CYAN + "-" * 100)
            print()
        self.actions.clear()

    def _distribute_yield(self):
        """
        Distribute yield to all agents at the end of the block based on the yield_per_block for each token.
        Yield is distributed as new tokens added to the respective LST balance in each agent's wallet.
        """
        for wallet in Wallet.all_wallets():
            for token, lst_info in self.tokens.items():
                yield_per_block = lst_info.get('yield_per_block', 0.0)

                balance = wallet.token_balance(token)
                accrued_yield = balance * yield_per_block

                if accrued_yield > 0:
                    wallet.deposit_token(token, accrued_yield)
                    self.add_action(f"{wallet} received {accrued_yield:.4f} {token} as yield")

            if self.eth_yield_per_block > 0:
                    accrued_yield = wallet.eth_balance * self.eth_yield_per_block
                    if accrued_yield > 0:
                        wallet.deposit_eth(accrued_yield)
                        self.add_action(f"{wallet} received {accrued_yield:.4f} ETH as yield")

    def start_mining(self, print_stats=True):
        for agent in self.agents:
            if agent in self.initial_eth_balance_overrides:
                agent.wallet.deposit_eth(self.initial_eth_balance_overrides[agent])
            else:
                agent.wallet.deposit_eth(self.initial_eth_balance)
            for token, lst_info in self.tokens.items():
                agent.wallet.deposit_token(token, lst_info['initial_agent_balance'])
            agent.on_after_genesis(self)

        self.collect_stats(0, print_stats)

        for block_number in range(1, self.num_blocks + 1):
            self.current_block = block_number
            Blockchain.current_block = block_number
            self.actions.append(f"Protocol actions ...")
            self._distribute_yield()
            self.event_manager.on_block(block_number, self)

            self.actions.append("")

            random.shuffle(self.agents)
            for agent in self.agents:
                self.actions.append(f"It's {agent}'s turn now ...")
                agent.on_block_mined(block_number)
                self.actions.append("")

            self.actions.append(f"All agents took action.")
            self._check_borrowings_repaid(block_number)

            self.collect_stats(block_number, print_stats)


        if print_stats:
            print("Mining completed!")
                    

    def _run_single_simulation(self, sim_id: int):
        """
        Run a single simulation by creating a deep copy of the current blockchain instance.
        :param sim_id: Simulation ID to differentiate between simulations.
        :return: Simulation result (e.g., final agent balances or other metrics).
        """
        # Create a deep copy of the blockchain to ensure independence
        blockchain_copy = copy.deepcopy(self)

        # Start mining for this simulation (without printing stats to minimize output)
        blockchain_copy.start_mining(print_stats=False)

        # Collect relevant results (e.g., final token prices or agent balances)
        results = {
            'simulation_id': sim_id,
            'final_prices': {token: blockchain_copy.get_amm(token).price_of_one_token_in_eth() for token in blockchain_copy.tokens},
            'agent_balances': {agent: agent.get_wallet_face_value() for agent in blockchain_copy.agents},
            'chain': blockchain_copy
        }

        return results

    def monte_carlo_simulation(self, n_simulations: int):
        """
        Run n simulations in parallel using multiprocessing, with each simulation being independent.
        :param n_simulations: Number of simulations to run in parallel.
        :return: List of results from all simulations.
        """
        # Use multiprocessing to run simulations in parallel
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            # Run the `_run_single_simulation` method in parallel, passing different simulation IDs
            results = pool.map(self._run_single_simulation, range(n_simulations))

        return results
