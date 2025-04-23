# Cork Trading Engine

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ethereum](https://img.shields.io/badge/Ethereum-3C3C3D?style=for-the-badge&logo=ethereum&logoColor=white)

## Trading Simulation Engine for Cork Tech Protocol

This project is a trading simulation engine designed for the Cork Tech Protocol. It allows users to simulate trading activities, manage liquidity, and perform various operations related to the Cork Tech Protocol.

### Features

- **Liquidity Management**: Add and remove liquidity from the Automated Market Maker (AMM).
- **Trading**: Swap ETH for LST and vice versa.
- **Price Calculation**: Calculate the current price of LST in terms of ETH.
- **Simulation**: Run multiple simulations in parallel to analyze different scenarios.

### Requirements

- Python 3.7+
- pip (Python package installer)

### Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/deep-ink-ventures/trading-simulation-engine.git
    cd trading-simulation-engine
    ```

2. Create a virtual environment:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

### Usage

1. Run the simulation:
    ```sh
    python main.py
    ```

2. View the results in the console.

### Project Structure

- `simulator/`: Contains the core simulation logic.
- `agents/`: Contains the different types of agents that participate in the simulation.
- `main.py`: Entry point for running the simulation.
- `.gitignore`: Specifies files and directories to be ignored by git.
- `requirements.txt`: Lists the dependencies required for the project.
