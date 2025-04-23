import json
import math

from simulator.wallet import Wallet


class EventManager:
    def __init__(self, events):
        """
        Initialize the EventManager with events and a wallet.

        :param events: A list of event dictionaries.
        """
        self.events = events
        self.wallet = Wallet()

    @staticmethod
    def from_json(json_file: str):
        """
        Static method to load events from a JSON file.

        :param json_file: Path to the JSON file containing events.
        :return: An EventManager instance.
        """
        with open(json_file, 'r') as f:
            events = json.load(f)
        return EventManager(events)

    def on_block(self, block_number: int, blockchain):
        """
        Handle events that occur at the current block.

        :param block_number: The current block number.
        :param blockchain: The blockchain instance to interact with.
        """
        # Filter events for the current block
        current_events = [event for event in self.events if event['block'] == block_number]

        for event in current_events:
            token = event['token']

            if token not in blockchain.tokens:
                continue

            if event['type'] == 'depeg':
                percentage = event['percentage']
                self._depeg(block_number, token, percentage, blockchain)

            elif event['type'] == 'repeg':
                self._repeg(block_number, token, blockchain)

            elif event['type'] == 'yield_adjustment':
                percentage = event['percentage']
                self._adjust_yield(block_number, token, percentage, blockchain)

            elif event['type'] == 'eth_yield_adjustment':
                percentage = event['percentage']
                self._adjust_eth_yield(block_number, token, percentage, blockchain)

    def _depeg(self, block_number: int, token: str, percentage: float, blockchain):
        """
        Handles a depeg event by adjusting the price of a token by a given percentage.

        :param block_number: The block number where the event occurs.
        :param token: The token affected by the depeg.
        :param percentage: The depeg percentage (e.g., 0.15 for a 15% depeg).
                           Positive percentage reduces the price.
                           Negative percentage increases the price.
        :param blockchain: The blockchain instance.
        """
        # Step 1: Get current AMM and price
        amm = blockchain.get_amm(token)

        current_price = amm.price_of_one_token_in_eth()

        # Step 2: Calculate target price
        target_price = current_price * (1 - percentage)

        # Step 3: Get current reserves
        x = amm.reserve_eth
        y = amm.reserve_token
        k = x * y

        # Step 4: Calculate new reserves after depeg
        x_new = math.sqrt(k * target_price)
        y_new = math.sqrt(k / target_price)

        # Step 5: Calculate changes in reserves
        delta_x = x_new - x
        delta_y = y_new - y

        # Step 6: Perform swap to adjust reserves
        if delta_y > 0:
            # Need to swap delta_y tokens for ETH (price goes down)
            self.wallet.deposit_token(token, delta_y)
            eth_received = amm.swap_token_for_eth(self.wallet, delta_y)
            action = f"Depegged {token} downwards by {percentage * 100:.2f}%"
        elif delta_x > 0:
            # Need to swap delta_x ETH for tokens (price goes up)
            self.wallet.deposit_eth(delta_x)
            tokens_received = amm.swap_eth_for_token(self.wallet, delta_x)
            action = f"Depegged {token} upwards by {percentage * 100:.2f}%"
        else:
            # No change needed
            return

        # Step 7: Verify new price
        final_price = amm.price_of_one_token_in_eth()
        blockchain.add_action(f"Block {block_number}: {action} from {current_price:.4f} ETH to {final_price:.4f} ETH.")

    def _repeg(self, block_number: int, token: str, blockchain):
        """
        Handles a repeg event by adjusting the reserves to bring the token price back to 1:1 (1 token = 1 ETH).

        :param block_number: The block number where the event occurs.
        :param token: The token affected by the repeg.
        :param blockchain: The blockchain instance.
        """
        # Step 1: Get the current AMM and price
        amm = blockchain.get_amm(token)
        current_price = amm.price_of_one_token_in_eth()

        # Step 2: Ensure the price isn't already at 1:1
        if abs(current_price - 1.0) < 1e-6:
            return

        # Step 3: Get current reserves
        x = amm.reserve_eth  # Current ETH reserve
        y = amm.reserve_token  # Current token reserve
        k = x * y

        # Step 4: Calculate new reserves needed for price = 1.0
        # Since price p = x_new / y_new = 1.0, x_new = y_new
        x_new = math.sqrt(k)
        y_new = math.sqrt(k)

        # Step 5: Calculate changes in reserves
        delta_x = x_new - x
        delta_y = y_new - y

        # Step 6: Adjust reserves accordingly
        if delta_x > 0:
            # Need to add ETH to the pool (swap ETH for tokens)
            self.wallet.deposit_eth(delta_x)
            tokens_received = amm.swap_eth_for_token(self.wallet, delta_x)
            action = f"Repegged {token} upwards by adding {delta_x:.4f} ETH"
        elif delta_y < 0:
            # Need to remove tokens from the pool (swap tokens for ETH)
            delta_y_abs = abs(delta_y)
            self.wallet.deposit_token(token, delta_y_abs)
            eth_received = amm.swap_token_for_eth(self.wallet, delta_y_abs)
            action = f"Repegged {token} upwards by removing {delta_y_abs:.4f} tokens"
        else:
            # No change needed
            return

        # Step 7: Verify new price
        final_price = amm.price_of_one_token_in_eth()

        # Log the successful repeg
        blockchain.add_action(
            f"Block {block_number}: {action}. Price adjusted from {current_price:.4f} ETH to {final_price:.4f} ETH.")

    def _adjust_yield(self, block_number: int, token: str, percentage: float, blockchain):
        """
        Placeholder for handling a yield adjustment event.

        :param block_number: The block number where the event occurs.
        :param token: The token affected by the yield adjustment.
        :param percentage: The percentage adjustment to the yield.
        :param blockchain: The blockchain instance.
        """
        blockchain.tokens[token]['yield_per_block'] = percentage
        blockchain.add_action(f"Adjusted yield for {token} to {percentage * 100:.2f}%.")

    def _adjust_eth_yield(self, block_number, token, percentage, blockchain):
        """
        Placeholder for handling an ETH yield adjustment event.

        :param block_number: The block number where the event occurs.
        :param token: The token affected by the yield adjustment.
        :param percentage: The percentage adjustment to the yield.
        :param blockchain: The blockchain instance.
        """
        blockchain.eth_yield = percentage
        blockchain.add_action(f"Adjusted ETH yield to {percentage * 100:.2f}%.")
