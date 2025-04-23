from agents.ct_long_term import CTLongTermAgent
from agents.ct_speculation import CTShortTermAgent
from agents.ds_long_term import DSLongTermAgent
from agents.ds_speculation import DSShortTermAgent
from agents.insurer import Insurer
from agents.lst_maximalist import LstMaximalist
from agents.redemption_arbitrage import RedemptionArbitrageAgent
from agents.repurchase_arbitrage import RepurchaseArbitrageAgent
from agents.lv_depositor import LVDepositorAgent
from agents.looping import LoopingAgent
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM, YieldSpaceAMM
import pandas as pd


# Simulation parameters
NUM_BLOCKS = 300  # Number of blocks to simulate
INITIAL_ETH_BALANCE = 100.0  # Initial ETH balance for each agent
PSM_EXPIRY_AFTER_BLOCK = 300  # Block after which the Peg Stability Module (PSM) expires

# Token parameters
TOKEN_NAME = 'fraxETH'  # Name of the token to simulate
INITIAL_AGENT_TOKEN_BALANCE = 100.0  # Initial token balance for each agent
AMM_RESERVE_ETH = 1000000.0  # Initial ETH reserve in the AMM
AMM_RESERVE_TOKEN = 1000000.0  # Initial token reserve in the AMM
AMM_FEE = 0.02  # Fee percentage in the AMM, 0.02 = 2%
INITIAL_YIELD_PER_BLOCK = 0.03 / 365  # Yield per block (assuming 3% annual yield)
PSM_REDEMPTION_FEES = 0.001  # Redemption fees for the Peg Stability Module, 0.001 = 0.1%
PSM_REPURCHASE_FEES = 0.05  # Reurchase fees for the Peg Stability Module, 0.05 = 5%


# Agents to include in the simulation
AGENT_NAMES = [
    #'LstMaximalist',
    #'Insurer',
    'DSShortTerm',
    'CTShortTerm',
    'DSLongTerm',
    'CTLongTerm',
    'RedemptionArbitrage',
    'RepurchaseArbitrage',
    #'LVDepositor',
    'LoopingAgent'
    ]

# Create the blockchain
chain = Blockchain(
    num_blocks=NUM_BLOCKS,
    initial_eth_balance=INITIAL_ETH_BALANCE,
    psm_expiry_after_block=PSM_EXPIRY_AFTER_BLOCK,
    initial_eth_yield_per_block=0.00001
)

# Add the token with the specified AMM
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

# Instantiate agents based on AGENT_NAMES
agents = []
for name in AGENT_NAMES:
    #if name == 'LstMaximalist':
    #    agents.append(LstMaximalist(TOKEN_NAME))
    #elif name == 'Insurer':
    #    agents.append(Insurer(TOKEN_NAME))
    if name == 'DSShortTerm':
        agents.append(DSShortTermAgent(name="DS Short Term", token_symbol=TOKEN_NAME, threshold=0.01))
    elif name == 'CTShortTerm':
        agents.append(CTShortTermAgent(name="CT Short Term", token_symbol=TOKEN_NAME, buying_pressure=10))
    elif name == 'DSLongTerm':  
        agents.append(DSLongTermAgent(name="DS Long Term", token_symbol=TOKEN_NAME, buying_pressure=1))
    elif name == 'CTLongTerm':
        agents.append(CTLongTermAgent(name="CT Long Term", token_symbol=TOKEN_NAME, percentage_threshold=0.01))
    elif name == 'RedemptionArbitrage':
        agents.append(RedemptionArbitrageAgent(name="Redemption Arb", token_symbol=TOKEN_NAME))
    elif name == 'RepurchaseArbitrage':
        agents.append(RepurchaseArbitrageAgent(name="Repurchase Arb", token_symbol=TOKEN_NAME))
    elif name == 'LVDepositor':
        agents.append(LVDepositorAgent(name="LV Depositor", token_symbol=TOKEN_NAME, expected_apy=0.05))
    elif name == 'LoopingAgent':
        agents.append(LoopingAgent(
            name="Looping Agent", 
            token_symbol=TOKEN_NAME,
            initial_borrow_rate=0.001, 
            borrow_rate_changes={}, 
            max_ltv=0.7, 
            lltv=0.915))

# Add agents to the blockchain
chain.add_agents(*agents)


# Start a simple mining process
chain.start_mining()

# Access stats dataframes
agents_stats = chain.stats['agents']
tokens_stats = chain.stats['tokens']
vaults_stats = chain.stats['vaults']
amms_stats = chain.stats['amms']
borrowed_eth_stats = chain.stats['borrowed_eth']
borrowed_tokens_stats = chain.stats['borrowed_tokens']


agents = ['DS Short Term']
all_trades = pd.DataFrame(chain.all_trades)
print(all_trades.query("agent in @agents"))
# we have several trades for DS Short Term agent (all Buying)

ds_short_term = agents_stats.query("agent in @agents")["wallet_token_balances"].apply(pd.Series)
print((ds_short_term["DS_fraxETH"] > 0.0).sum())
# but the agent never holds any DS_stETH tokens

