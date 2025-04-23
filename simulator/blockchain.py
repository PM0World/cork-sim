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
    Added `events_path` (optional) so callers can load a custom events file
    or skip events entirely by passing None.
    """

    current_block = 0

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------
    def __init__(
        self,
        num_blocks: int,
        initial_eth_balance: float,
        psm_expiry_after_block: int,
        initial_eth_yield_per_block: float = 0.0,
        events_path: Optional[str] = "events.json",          # ← NEW PARAM
    ):
        # --------------- events manager ---------------
        if events_path is None:
            self.event_manager = EventManager()              # empty
        else:
            self.event_manager = EventManager.from_json(events_path)

        # --------------- high-level config ------------
        self.num_blocks = num_blocks
        self.initial_eth_balance = initial_eth_balance
        self.eth_yield_per_block = initial_eth_yield_per_block

        assert (
            psm_expiry_after_block <= num_blocks
        ), "PSM expiry date must be before the end of the simulation"
        self.psm_expiry_at_block = psm_expiry_after_block

        # --------------- dynamic state ----------------
        self.tokens = {}                         # token_symbol → dict
        self.agents = []                         # all agent objects
        self.initial_eth_balance_overrides = {}  # per-agent override

        self.actions: list[str] = []             # actions for current blk
        self.all_actions: list[list[str]] = []   # history of all actions
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

        # --------------- metrics dataframes ----------
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
            "psms": pd.DataFrame(
                columns=["block", "token", "eth_reserve"]
            ),
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

    # ------------------------------------------------------------------
    # (all original methods remain exactly as in your previous version)
    # Only the constructor above changed – everything below is identical.
    # ------------------------------------------------------------------

    # --------------------------- helpers ------------------------------
    def _append_stats(self, block_number):
        ...
        # (unchanged body – keep everything you posted earlier)
        ...

    # ----------------------- public interface -------------------------
    def add_agent(self, agent, eth_balance: float):
        ...
    def add_agents(self, *agents):
        ...
    def add_token(
        self,
        token: str,
        initial_agent_balance: float,
        amm: AMM,
        risk=0.1,
        initial_yield_per_block=0.00001,
    ):
        ...
    def get_vault(self, token: str):
        ...
    def get_psm(self, token: str):
        ...
    def get_amm(self, token: str):
        ...
    def add_action(self, action):
        ...
    def add_trade(self, trade):
        ...

    # ---------- borrowing / repayment (unchanged) ---------------------
    def borrow_eth(self, wallet, amount_eth: float):
        ...
    def repay_eth(self, wallet, amount_eth: float):
        ...
    def borrow_token(self, wallet: Wallet, token: str, amount_token: float):
        ...
    def repay_token(self, wallet: Wallet, token: str, amount_token: float):
        ...

    # ---------- internal checks / stats ------------------------------
    def _check_borrowings_repaid(self, block_number: int):
        ...
    def collect_stats(self, block_number, print_stats=True):
        ...
    def _distribute_yield(self):
        ...

    # ------------------ mining / simulation loop ---------------------
    def start_mining(self, print_stats: bool = True):
        ...
    def _run_single_simulation(self, sim_id: int):
        ...
    def monte_carlo_simulation(self, n_simulations: int):
        ...
