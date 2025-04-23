import multiprocessing
import copy
import random
from typing import Optional

import pandas as pd
from colorama import Fore, Style, init

from simulator.amm import AMM, YieldSpaceAMM, UniswapV2AMM
from simulator.event_manager import EventManager
from simulator.psm import PegStabilityModule
from simulator.vault import Vault
from simulator.wallet import Wallet

init(autoreset=True)


class Blockchain:
    """
    Core chain state-machine.
    `events_path` is optional – pass None to start with an empty
    EventManager.
    """

    current_block = 0

    # ──────────────────────────────────────────────────────────
    # Constructor
    # ──────────────────────────────────────────────────────────
    def __init__(
        self,
        num_blocks: int,
        initial_eth_balance: float,
        psm_expiry_after_block: int,
        initial_eth_yield_per_block: float = 0.0,
        events_path: Optional[str] = "events.json",
    ):
        # -------- event manager --------
        if events_path is None:
            self.event_manager = EventManager([])          # ← FIX: pass empty list
        else:
            self.event_manager = EventManager.from_json(events_path)

        # -------- high-level config ----
        self.num_blocks = num_blocks
        self.initial_eth_balance = initial_eth_balance
        self.eth_yield_per_block = initial_eth_yield_per_block

        assert psm_expiry_after_block <= num_blocks, (
            "PSM expiry date must be before the end of the simulation"
        )
        self.psm_expiry_at_block = psm_expiry_after_block

        # -------- dynamic state -------
        self.tokens = {}                         # token_symbol → dict
        self.agents = []                         # all agent objects
        self.initial_eth_balance_overrides = {}  # per-agent overrides

        self.actions: list[str] = []             # actions in current block
        self.all_actions: list[list[str]] = []   # history of actions
        self.all_trades: list[dict] = []         # structured trade log

        self.genesis_wallet = Wallet()
        self.genesis_wallet.set_initial_balances(1000)

        # borrowing trackers
        self.borrowed_eth = {}
        self.total_borrowed_eth = 0.0
        self.borrowed_token = {}
        self.total_borrowed_token = {}

        Blockchain.current_block = 0
        self.current_block = 0

        # -------- metrics dataframes ---
        self.stats = {
            "agents": pd.DataFrame(
                columns=[
                    "block",
                    "agent",
                    "wallet_face_value",
                    "wallet_eth_balance",
                    "wallet_token_balances",
                    "wallet_lpt_balances",
                ]
            ),
            "tokens": pd.DataFrame(columns=["block", "token", "price"]),
            "vaults": pd.DataFrame(
                columns=[
                    "block",
                    "token",
                    "lp_token_price_eth",
                    "eth_balance",
                    "ds_balance_eth",
                ]
            ),
            "psms": pd.DataFrame(columns=["block", "token", "eth_reserve"]),
            "amms": pd.DataFrame(
                columns=[
                    "block",
                    "token",
                    "total_lpt_supply",
                    "total_eth_reserve",
                    "total_token_reserve",
                ]
            ),
            "borrowed_eth": pd.DataFrame(columns=["block", "wallet", "amount"]),
            "borrowed_tokens": pd.DataFrame(
                columns=["block", "wallet", "token", "amount"]
            ),
        }

    # (everything below this point is unchanged – keep your existing
    #  _append_stats, add_token, borrow/repay, mining loop, etc.)


    # ------------------------------------------------------------------
    # Helpers – stats aggregation
    # ------------------------------------------------------------------
    def _append_stats(self, block_number):
        def is_valid_dataframe(df):
            return not df.empty and not df.isna().all(axis=None)

        # -------- agents --------
        agent_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "agent": str(agent),
                    "wallet_face_value": agent.get_wallet_face_value(),
                    "wallet_eth_balance": copy.deepcopy(agent.wallet.eth_balance),
                    "wallet_token_balances": copy.deepcopy(
                        agent.wallet.token_balances
                    ),
                    "wallet_lpt_balances": copy.deepcopy(agent.wallet.lpt_balances),
                }
                for agent in self.agents
            ]
        )
        if is_valid_dataframe(agent_stats):
            if is_valid_dataframe(self.stats["agents"]):
                self.stats["agents"] = pd.concat(
                    [self.stats["agents"], agent_stats], ignore_index=True
                )
            else:
                self.stats["agents"] = agent_stats.copy()

        # -------- tokens --------
        token_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "token": token,
                    "price": lst_info["amm"].price_of_one_token_in_eth(),
                }
                for token, lst_info in self.tokens.items()
                if "amm" in lst_info
            ]
        )
        if is_valid_dataframe(token_stats):
            if is_valid_dataframe(self.stats["tokens"]):
                self.stats["tokens"] = pd.concat(
                    [self.stats["tokens"], token_stats], ignore_index=True
                )
            else:
                self.stats["tokens"] = token_stats.copy()

        # -------- vaults --------
        vault_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "token": token,
                    "lp_token_price_eth": vault.get_lp_token_price(),
                    "eth_balance": vault.wallet.eth_balance,
                    "ds_balance_eth": vault.ds_eth_amm.price_of_one_token_in_eth()
                    * vault.wallet.token_balance(f"DS_{token}"),
                }
                for token, lst_info in self.tokens.items()
                if "vault" in lst_info
                for vault in [lst_info["vault"]]
            ]
        )
        if is_valid_dataframe(vault_stats):
            if is_valid_dataframe(self.stats["vaults"]):
                self.stats["vaults"] = pd.concat(
                    [self.stats["vaults"], vault_stats], ignore_index=True
                )
            else:
                self.stats["vaults"] = vault_stats.copy()

        # -------- psms --------
        psm_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "token": token,
                    "eth_reserve": lst_info["psm"].eth_reserve,
                }
                for token, lst_info in self.tokens.items()
                if "psm" in lst_info
            ]
        )
        if is_valid_dataframe(psm_stats):
            if is_valid_dataframe(self.stats["psms"]):
                self.stats["psms"] = pd.concat(
                    [self.stats["psms"], psm_stats], ignore_index=True
                )
            else:
                self.stats["psms"] = psm_stats.copy()

        # -------- amms --------
        amm_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "token": token,
                    "total_lpt_supply": lst_info["amm"].total_lpt_supply,
                    "total_eth_reserve": lst_info["amm"].reserve_eth,
                    "total_token_reserve": lst_info["amm"].reserve_token,
                }
                for token, lst_info in self.tokens.items()
                if "amm" in lst_info
            ]
        )
        if is_valid_dataframe(amm_stats):
            if is_valid_dataframe(self.stats["amms"]):
                self.stats["amms"] = pd.concat(
                    [self.stats["amms"], amm_stats], ignore_index=True
                )
            else:
                self.stats["amms"] = amm_stats.copy()

        # -------- borrowed ETH --------
        borrowed_eth_stats = pd.DataFrame(
            [
                {"block": block_number, "wallet": str(wallet), "amount": amount}
                for wallet, amount in self.borrowed_eth.items()
            ]
        )
        if is_valid_dataframe(borrowed_eth_stats):
            if is_valid_dataframe(self.stats["borrowed_eth"]):
                self.stats["borrowed_eth"] = pd.concat(
                    [self.stats["borrowed_eth"], borrowed_eth_stats], ignore_index=True
                )
            else:
                self.stats["borrowed_eth"] = borrowed_eth_stats.copy()

        # -------- borrowed tokens --------
        borrowed_token_stats = pd.DataFrame(
            [
                {
                    "block": block_number,
                    "wallet": str(wallet),
                    "token": token,
                    "amount": amount,
                }
                for wallet, token_amounts in self.borrowed_token.items()
                for token, amount in token_amounts.items()
            ]
        )
        if is_valid_dataframe(borrowed_token_stats):
            if is_valid_dataframe(self.stats["borrowed_tokens"]):
                self.stats["borrowed_tokens"] = pd.concat(
                    [self.stats["borrowed_tokens"], borrowed_token_stats],
                    ignore_index=True,
                )
            else:
                self.stats["borrowed_tokens"] = borrowed_token_stats.copy()

    # ------------------------------------------------------------------
    # Public interface – token / agent management
    # ------------------------------------------------------------------
    def add_agent(self, agent, eth_balance: float):
        self.agents.append(agent)
        self.initial_eth_balance_overrides[agent] = eth_balance

    def add_agents(self, *agents):
        for agent in agents:
            self.agents.append(agent)

    def add_token(
        self,
        token: str,
        initial_agent_balance: float,
        amm: AMM,
        risk: float = 0.1,
        initial_yield_per_block: float = 0.00001,
    ):
        psm = PegStabilityModule(
            token_symbol=token,
            expiry_block=self.psm_expiry_at_block,
            redemption_fee=0.001,
            repurchase_fee=0.05,
        )
        psm.deposit_eth(self.genesis_wallet, 100)

        base_reserve = self.genesis_wallet.eth_balance * 10000
        reserve_ct_eth = base_reserve * (1 - risk)
        reserve_ds_eth = base_reserve * risk

        ct_amm = YieldSpaceAMM(
            token_symbol=f"CT_{token}",
            reserve_eth=reserve_ct_eth,
            reserve_token=base_reserve,
            discount_rate=1 / self.psm_expiry_at_block,
        )
        ds_amm = YieldSpaceAMM(
            token_symbol=f"DS_{token}",
            reserve_eth=reserve_ds_eth,
            reserve_token=base_reserve,
            discount_rate=1 / self.psm_expiry_at_block,
        )

        vault = Vault(
            blockchain=self,
            token_symbol=token,
            psm=psm,
            lst_eth_amm=amm,
            ct_eth_amm=ct_amm,
            ds_eth_amm=ds_amm,
        )

        self.tokens[token] = {
            "initial_agent_balance": initial_agent_balance,
            "amm": amm,
            "psm": psm,
            "vault": vault,
            "yield_per_block": initial_yield_per_block,
        }
        self.tokens[f"CT_{token}"] = {
            "initial_agent_balance": 0,
            "amm": ct_amm,
        }
        self.tokens[f"DS_{token}"] = {
            "initial_agent_balance": 0,
            "amm": ds_amm,
        }

    def get_vault(self, token: str):
        return self.tokens[token].get("vault")

    def get_psm(self, token: str):
        return self.tokens[token].get("psm")

    def get_amm(self, token: str):
        return self.tokens[token]["amm"]

    def add_action(self, action: str):
        self.actions.append(f"  - {action}")

    def add_trade(self, trade: dict):
        self.all_trades.append(trade)

    # ------------------------------------------------------------------
    # Borrowing / repayment
    # ------------------------------------------------------------------
    def borrow_eth(self, wallet, amount_eth: float):
        if amount_eth <= 0:
            raise ValueError("Borrow amount must be positive")
        self.total_borrowed_eth += amount_eth
        self.borrowed_eth[wallet] = self.borrowed_eth.get(wallet, 0.0) + amount_eth
        wallet.deposit_eth(amount_eth)
        self.add_action(f"borrowed {amount_eth:.4f} ETH")

    def repay_eth(self, wallet, amount_eth: float):
        if wallet not in self.borrowed_eth or self.borrowed_eth[wallet] == 0:
            raise ValueError(f"{wallet} has no ETH to repay")
        if amount_eth > self.borrowed_eth[wallet]:
            raise ValueError(
                f"Cannot repay more than borrowed. Borrowed: {self.borrowed_eth[wallet]:.4f} ETH"
            )
        self.total_borrowed_eth -= amount_eth
        self.borrowed_eth[wallet] -= amount_eth
        wallet.withdraw_eth(amount_eth)
        self.add_action(f"repaid {amount_eth:.4f} ETH")

    def borrow_token(self, wallet: Wallet, token: str, amount_token: float):
        if amount_token <= 0:
            raise ValueError("Borrow amount must be positive")
        if token not in self.tokens:
            raise ValueError(f"Token {token} does not exist")

        self.borrowed_token.setdefault(wallet, {})
        self.borrowed_token[wallet][token] = (
            self.borrowed_token[wallet].get(token, 0.0) + amount_token
        )
        self.total_borrowed_token[token] = self.total_borrowed_token.get(token, 0.0) + amount_token

        wallet.deposit_token(token, amount_token)
        self.add_action(f"borrowed {amount_token:.4f} {token}")

    def repay_token(self, wallet: Wallet, token: str, amount_token: float):
        if amount_token <= 0:
            raise ValueError("Repayment amount must be positive")
        if wallet not in self.borrowed_token or token not in self.borrowed_token[wallet]:
            raise ValueError(f"{wallet} has no borrowed {token} to repay")
        if amount_token > self.borrowed_token[wallet][token]:
            raise ValueError(
                f"Cannot repay more than borrowed. Borrowed: {self.borrowed_token[wallet][token]:.4f} {token}"
            )

        self.borrowed_token[wallet][token] -= amount_token
        self.total_borrowed_token[token] -= amount_token
        if self.borrowed_token[wallet][token] == 0:
            del self.borrowed_token[wallet][token]

        wallet.withdraw_token(token, amount_token)
        self.add_action(f"repaid {amount_token:.4f} {token}")

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------
    def _check_borrowings_repaid(self, block_number: int):
        if self.total_borrowed_eth > 0:
            raise ValueError(
                f"Block {block_number}: Not all borrowed ETH has been repaid. "
                f"Total outstanding: {self.total_borrowed_eth:.4f} ETH"
            )
        for token, total_borrowed in self.total_borrowed_token.items():
            if total_borrowed > 0:
                raise ValueError(
                    f"Block {block_number}: Not all borrowed {token} tokens have been repaid. "
                    f"Total outstanding: {total_borrowed:.4f} {token}"
                )

    # ------------------------------------------------------------------
    # Stats + logging at each block
    # ------------------------------------------------------------------
    def collect_stats(self, block_number: int, print_stats: bool = True):
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
                print(
                    Fore.GREEN
                    + f"Agent: {agent} | Wallet face value: {agent.get_wallet_face_value():.4f} ETH"
                )

            for lst_info in self.tokens.values():
                amm = lst_info["amm"]
                print(
                    Fore.MAGENTA
                    + f"LST: {amm.name} | Price: {amm.price_of_one_token_in_eth():.4f} ETH"
                )

            print(Style.BRIGHT + Fore.CYAN + "-" * 100)
            print()

        self.actions.clear()

    # ------------------------------------------------------------------
    # Yield distribution
    # ------------------------------------------------------------------
    def _distribute_yield(self):
        for wallet in Wallet.all_wallets():
            for token, lst_info in self.tokens.items():
                yield_per_block = lst_info.get("yield_per_block", 0.0)
                balance = wallet.token_balance(token)
                accrued_yield = balance * yield_per_block
                if accrued_yield > 0:
                    wallet.deposit_token(token, accrued_yield)
                    self.add_action(f"{wallet} received {accrued_yield:.4f} {token} as yield")

            if self.eth_yield_per_block > 0:
                accrued_eth_yield = wallet.eth_balance * self.eth_yield_per_block
                if accrued_eth_yield > 0:
                    wallet.deposit_eth(accrued_eth_yield)
                    self.add_action(f"{wallet} received {accrued_eth_yield:.4f} ETH as yield")

    # ------------------------------------------------------------------
    # Mining loop
    # ------------------------------------------------------------------
    def start_mining(self, print_stats: bool = True):
        # distribute genesis balances
        for agent in self.agents:
            if agent in self.initial_eth_balance_overrides:
                agent.wallet.deposit_eth(self.initial_eth_balance_overrides[agent])
            else:
                agent.wallet.deposit_eth(self.initial_eth_balance)
            for token, lst_info in self.tokens.items():
                agent.wallet.deposit_token(token, lst_info["initial_agent_balance"])
            agent.on_after_genesis(self)

        self.collect_stats(0, print_stats)

        for block_number in range(1, self.num_blocks + 1):
            self.current_block = block_number
            Blockchain.current_block = block_number

            self.actions.append("Protocol actions ...")
            self._distribute_yield()
            self.event_manager.on_block(block_number, self)

            self.actions.append("")

            random.shuffle(self.agents)
            for agent in self.agents:
                self.actions.append(f"It's {agent}'s turn now ...")
                agent.on_block_mined(block_number)
                self.actions.append("")

            self.actions.append("All agents took action.")
            self._check_borrowings_repaid(block_number)

            self.collect_stats(block_number, print_stats)

        if print_stats:
            print("Mining completed!")

    # ------------------------------------------------------------------
    # Parallel Monte-Carlo
    # ------------------------------------------------------------------
    def _run_single_simulation(self, sim_id: int):
        blockchain_copy = copy.deepcopy(self)
        blockchain_copy.start_mining(print_stats=False)
        return {
            "simulation_id": sim_id,
            "final_prices": {
                token: blockchain_copy.get_amm(token).price_of_one_token_in_eth()
                for token in blockchain_copy.tokens
            },
            "agent_balances": {
                agent: agent.get_wallet_face_value() for agent in blockchain_copy.agents
            },
            "chain": blockchain_copy,
        }

    def monte_carlo_simulation(self, n_simulations: int):
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            results = pool.map(self._run_single_simulation, range(n_simulations))
        return results
