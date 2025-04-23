from simulator.agent import Agent

from agents.utils.volume_calculations import buying_intent

class CTLongTermAgent(Agent):
    """
    CTLongTermAgent Class

    This agent represents a long-term buyer of "CT" tokens, seeking to lock in a higher fixed yield compared to holding a native asset (Liquid Staking Token, LST). The agent monitors the annualized risk premium (ARP) of CT relative to the native LST yield. When the ARP exceeds a predefined threshold, the agent executes a purchase of CT tokens weighted by the price difference.

    Attributes:
        name (str): The name of the agent.
        token_symbol (str): The symbol of the target token (LST) being compared.
        percentage_threshold (float): The ARP threshold percentage above the native yield to trigger a CT purchase.
        lst_symbol (str): Alias for token_symbol.

    Methods:
        on_block_mined(block_number: int):
            Called when a new block is mined. The method checks the yield of the native LST and the corresponding CT token. If the ARP of CT exceeds the defined threshold, the agent calculates a weighted purchase volume based on the price difference and executes the purchase using ETH. The purchase action and details are logged. This agent does not handle CT selling, as the goal is to lock in yields for maturity.

    Context:
        Generally, a CT long-term buyer aims to achieve a higher risk-adjusted yield on their redemption asset (CT) compared to simply holding the underlying pegged asset (LST). The comparison benchmark is providing liquidity in a Pendle pool of the same maturity due to similar depeg risks. By continuously buying CT when conditions are favorable, the agent drives up the CT price, reducing ARP over time.
    """
    def __init__(self, name, token_symbol: str, percentage_threshold):
        super().__init__(name)
        self.percentage_threshold = percentage_threshold
        self.token_symbol = token_symbol
        self.lst_symbol = token_symbol


    def on_block_mined(self, block_number: int):
        vault = self.blockchain.get_vault(self.lst_symbol)

        # from the Liquid Staken Token get it's yield
        lst_info = self.blockchain.tokens[self.lst_symbol]
        # yield of underlying token (LST)
        lst_yield = lst_info.get('yield_per_block', 0.0)

        expected_lst_yield = lst_yield * self.blockchain.num_blocks
        # current fixed yield
        # 1-CT price (as CT will sell for 1 PA at maturity)

        ct_price = self.blockchain.get_amm(f'CT_{self.lst_symbol}').price_of_one_token_in_eth()
        fixed_yield = 1 - ct_price

        risk_premium = fixed_yield - expected_lst_yield
        
        if risk_premium > self.percentage_threshold:
            # caculate volume
            weighted_volume = buying_intent(risk_premium, base_volume=1, threshold=self.percentage_threshold, growth_rate=3)
            volume_to_buy = min(weighted_volume, self.wallet.eth_balance)
            vault.ct_eth_amm.swap_eth_for_token(wallet=self.wallet, amount_eth=volume_to_buy)
            self.log_action(f'Bought CT with {weighted_volume:.4f} ETH')
            self.log_trade({
                    'block': block_number,
                    'agent': self.name,
                    'token': 'CT', 
                    'volume': weighted_volume, 
                    'action': 'buy', 
                    'reason': 'arp > self.percentage_threshold',
                    'additional_info': {'arp': risk_premium, 'self.percentage_threshold': self.percentage_threshold},
                    })

        # CT selling not happening for this agent
        # I would abstract away from selling for this agent role. 
        # For sure in the real world there would be some, but I think 
        # it will be reasonably captured in the CT speculation side. 
        # The CT long-term buyer is fixing the yield that will be realized at maturity.





