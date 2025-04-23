# buying DS
# varying investment horizon
# sharp decline of annualized premium drives buying

# sell DS
# sharp decline of premium (expontential decay)
import numpy as np
import pandas as pd

from simulator.agent import Agent

from agents.utils.trigger_calculations import detect_sharp_decline, calculate_arp

class CTShortTermAgent(Agent):
    """
    CTShortTermAgent Class

    This agent speculates on the short-term price movements of DS tokens relative to LST (Liquid Staking Token) yields. The agent monitors annualized risk premium (ARP) trends and responds to sharp increases or declines in premium, adjusting its trading strategy accordingly. The aim is to exploit temporary market inefficiencies by dynamically buying or selling DS tokens.

    Attributes:
        name (str): The name of the agent.
        token_symbol (str): The symbol of the target token (LST) being compared.
        arp_history (list): A history of calculated ARPs for the DS token.
        lst_symbol (str): Alias for token_symbol.
        buying_pressure (float): A multiplier indicating the aggressiveness of the buying strategy.

    Methods:
        on_block_mined(block_number: int):
            Called when a new block is mined. This method evaluates the current DS price at the AMM and computes the projected full-expiry DS price and the yield of the native LST token. It calculates the ARP and detects sharp price movements based on historical data. The agent buys CT tokens when a sharp ARP incline is detected and sells CT tokens in the event of a sharp decline. Each action is logged with volume details.

        detect_sharp_decline(prices: list, n: int = 10, alpha: float = 0.3, decline_threshold: float = -0.05, incline_threshold: float = 0.05):
            Analyzes a series of ARP data points to detect sharp declines or inclines using an exponentially weighted average (EWA) slope. Returns a boolean indicating a sharp decline or incline, along with the calculated slope.

    Context:
        This agent employs a speculative trading strategy that reacts to changes in the annualized premium between DS and LST tokens. The buying pressure is weighted by the detected price trend, with DS tokens being acquired during sharp inclines and sold during sharp declines. The goal is to capitalize on temporary mispricings while accommodating varying investment horizons and market volatility.
    """
    def __init__(self, name, token_symbol: str, buying_pressure: float, threshold=0.01):
        super().__init__(name) 
        self.token_symbol = token_symbol
        self.arp_history = []
        self.lst_symbol = token_symbol
        self.buying_pressure = buying_pressure
        self.threshold = threshold

    def on_block_mined(self, block_number: int):
        """
        very similar as for the DS Speculation Agent, just inverse incentives
        all decisions and ARP calculation are based on DS price
        """
        vault = self.blockchain.get_vault(self.token_symbol)

        ct_price = vault.ct_eth_amm.price_of_one_token_in_eth()

         # DS Buying Strategy
        # evaluate current price of DS at AMM
        ds_price = vault.ds_eth_amm.price_of_one_token_in_eth()
        
        # evaluate current yield of LST
        # from the Liquid Staken Token get it's yield
        lst_info = self.blockchain.tokens[self.lst_symbol]
        # yield of underlying token (LST)
        native_yield = lst_info.get('yield_per_block', 0.0)
  
        arp = calculate_arp(ds_price, native_yield, self.blockchain.num_blocks, self.blockchain.current_block)
        
        self.arp_history.append(arp)

        if len(self.arp_history) >= 3:
            sharp_decline, sharp_incline, ewa_slope = detect_sharp_decline(
                self.arp_history, 
                n=10, 
                alpha=0.3,
                decline_threshold=-self.threshold, 
                incline_threshold=self.threshold
                )
        else:
            sharp_decline = False
            sharp_incline = False
            ewa_slope = 0
        
        # all volume calcs are done in ETH and for sell converted to CT
        # Possible Improvement add a smoother volume calculation
        if sharp_incline:
            weighted_volume = self.buying_pressure * ewa_slope
            volume_to_buy = min(weighted_volume, self.wallet.eth_balance)
            # amount in ETH to buy CT
            vault.ct_eth_amm.swap_eth_for_token(wallet=self.wallet, amount_eth=volume_to_buy)
            self.log_action(f'Bought CT with {volume_to_buy:.4f} ETH')
            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'CT', 
                    'volume': volume_to_buy, 
                    'action': 'buy', 
                    'reason': 'sharp INcline',
                    'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
                    })

        # Sell CT
        if sharp_decline:
            current_price = vault.ct_eth_amm.price_of_one_token_in_eth()
            weighted_volume = max(self.buying_pressure * ewa_slope *-1 / current_price, 0)
            volume_to_sell = min(weighted_volume, self.wallet.token_balances[f'CT_{self.token_symbol}'])
            # amount denominated in CT to sell
            vault.ct_eth_amm.swap_token_for_eth(wallet=self.wallet, amount_token=volume_to_sell)
            self.log_action(f'Sold {volume_to_sell:.4f} CT')
            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'CT', 
                    'volume': volume_to_sell / ct_price, 
                    'action': 'sell', 
                    'reason': 'sharp DEcline',
                    'additional_info': {'arp': arp, 'ewa_slope': ewa_slope, 'arp_history': self.arp_history}
                    })

