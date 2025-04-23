from agents.ds_buyer import DSBuyerAgent
from agents.vault_testing_agent import VaultTestingAgent
from simulator.blockchain import Blockchain
from simulator.amm import UniswapV2AMM

# Create the blockchain with 10 blocks and initial ETH balance for each agent
chain = Blockchain(num_blocks=10, initial_eth_balance=100.0, psm_expiry_after_block=10)

# Add CHP token using UniswapV2AMM with a price of 0.1 ETH
chain.add_token(
    # token name
    token='CHP',
    # how much do we want to give each agent to get going
    initial_agent_balance=100.0,
    # the amm implementation for this token, uniV2 has a constant formula so price of LST is just eth/lst
    amm=UniswapV2AMM(token_symbol='CHP', reserve_eth=100 * 1000 * 1000, reserve_token=100 * 1000 * 1000, fee=0.00)
)

# Add some bullish agents that just buy the respective token each round.
chain.add_agents(
    VaultTestingAgent("CHP"),
    DSBuyerAgent("CHP"),
)

# Start a simple mining process
chain.start_mining()
