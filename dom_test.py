from agents.ct_long_term import CTLongTermAgent
from agents.ct_speculation import CTShortTermAgent
from agents.ds_long_term import DSLongTermAgent
from agents.ds_speculation import DSShortTermAgent
from agents.redemption_arbitrage import RedemptionArbitrageAgent
from agents.repurchase_arbitrage import RepurchaseArbitrageAgent
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM


# Simulation parameters
NUM_BLOCKS = 300  # Number of blocks to simulate
INITIAL_ETH_BALANCE = 100.0  # Initial ETH balance for each agent
PSM_EXPIRY_AFTER_BLOCK = 300  # Block after which the Peg Stability Module (PSM) expires

# Token parameters
TOKEN_NAME = 'stETH'  # Name of the token to simulate
INITIAL_AGENT_TOKEN_BALANCE = 100.0  # Initial token balance for each agent
AMM_RESERVE_ETH = 10.0  # Initial ETH reserve in the AMM
AMM_RESERVE_TOKEN = 100.0  # Initial token reserve in the AMM
AMM_FEE = 0.00  # Fee percentage in the AMM
INITIAL_YIELD_PER_BLOCK = 0.03 / 365  # Yield per block (assuming 3% annual yield)

# Agents to include in the simulation
AGENT_NAMES = [
    #'LstMaximalist', 
    #'Insurer',
    #'DSShortTerm',
    #'CTShortTerm',
    'DSLongTerm',
    #'DSShortTerm',
    #'RedemptionArbitrage',
    #'RepurchaseArbitrage'
    ]

# Create the blockchain
chain = Blockchain(
    num_blocks=NUM_BLOCKS,
    initial_eth_balance=INITIAL_ETH_BALANCE,
    psm_expiry_after_block=PSM_EXPIRY_AFTER_BLOCK
)

# Add the token with the specified AMM
chain.add_token(
    token=TOKEN_NAME,
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
    if name == 'LstMaximalist':
        agents.append(LstMaximalist(TOKEN_NAME))
    elif name == 'Insurer':
        agents.append(Insurer(TOKEN_NAME))
    elif name == 'DSShortTerm':
        agents.append(DSShortTermAgent(name="DS Short Term", token_symbol=TOKEN_NAME))
    elif name == 'CTShortTerm':
        agents.append(CTShortTermAgent(name="CT Short Term", token_symbol=TOKEN_NAME, buying_pressure=10))
    elif name == 'DSLongTerm':  
        agents.append(DSLongTermAgent(name="DS Long Term", token_symbol=TOKEN_NAME, buying_pressure=1))
    elif name == 'CTLongTerm':
        agents.append(CTLongTermAgent(name="CT Long Term", token_symbol=TOKEN_NAME), percentage_threshold=0.01)
    elif name == 'RedemptionArbitrage':
        agents.append(RedemptionArbitrageAgent(name="Redemption Arb", token_symbol=TOKEN_NAME))
    elif name == 'RepurchaseArbitrage':
        agents.append(RepurchaseArbitrageAgent(name="Repurchase Arb", token_symbol=TOKEN_NAME))

# Add agents to the blockchain
chain.add_agents(*agents)


# Start a simple mining process
chain.start_mining()

# also no wallet changes for any agent (even the Maximalist blindly buying)
agents_stats.query("agent == 'LST Maximalist for stETH'")["wallet_token_balances"].apply(pd.Series)

# BUG? this is empty
chain.all_actions