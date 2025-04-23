# main.py

from agents.ct_long_term import CTLongTermAgent
from agents.ct_speculation import CTShortTermAgent
from agents.ds_long_term import DSLongTermAgent
from agents.ds_speculation import DSShortTermAgent
from agents.redemption_arbitrage import RedemptionArbitrageAgent
from agents.repurchase_arbitrage import RepurchaseArbitrageAgent
from agents.looping import LoopingAgent
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM
import pandas as pd

def main(num_blocks=300, initial_eth_balance=100.0):
    # Simulation parameters
    TOKEN_NAME = 'stETH'
    AMM_RESERVE_ETH = 1000000.0
    AMM_RESERVE_TOKEN = 1000000.0
    AMM_FEE = 0.02
    INITIAL_AGENT_TOKEN_BALANCE = 100.0
    INITIAL_YIELD_PER_BLOCK = 0.03 / 365
    PSM_EXPIRY_AFTER_BLOCK = num_blocks

    chain = Blockchain(
        num_blocks=num_blocks,
        initial_eth_balance=initial_eth_balance,
        psm_expiry_after_block=PSM_EXPIRY_AFTER_BLOCK,
        initial_eth_yield_per_block=0.00001
    )

    chain.add_token(
        token=TOKEN_NAME,
        risk=0.02,
        initial_agent_balance=INITIAL_AGENT_TOKEN_BALANCE,
        amm=UniswapV2AMM(
            token_symbol=TOKEN_NAME,
            reserve_eth=AMM_RESERVE_ETH,
            reserve_token=AMM_RESERVE_TOKEN,
            fee=AMM_FEE
        ),
        initial_yield_per_block=INITIAL_YIELD_PER_BLOCK
    )

    agents = [
        DSShortTermAgent(name="DS Short Term", token_symbol=TOKEN_NAME, threshold=0.01),
        CTShortTermAgent(name="CT Short Term", token_symbol=TOKEN_NAME, buying_pressure=10),
        DSLongTermAgent(name="DS Long Term", token_symbol=TOKEN_NAME, buying_pressure=1),
        CTLongTermAgent(name="CT Long Term", token_symbol=TOKEN_NAME, percentage_threshold=0.01),
        RedemptionArbitrageAgent(name="Redemption Arb", token_symbol=TOKEN_NAME),
        RepurchaseArbitrageAgent(name="Repurchase Arb", token_symbol=TOKEN_NAME),
        LoopingAgent(
            name="Looping Agent",
            token_symbol=TOKEN_NAME,
            initial_borrow_rate=0.001,
            borrow_rate_changes={},
            max_ltv=0.7,
            lltv=0.915
        )
    ]

    chain.add_agents(*agents)
    chain.start_mining()

    agents_stats = chain.stats['agents']
    all_trades = pd.DataFrame(chain.all_trades)

    results = {
        "agents_stats": agents_stats,
        "all_trades": all_trades,
        "final_block": num_blocks
    }

    return results

