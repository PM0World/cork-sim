#!/usr/bin/env python3

import argparse
import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import sys
import time


def fetch_historical_prices(coin_id, vs_currency, from_timestamp, to_timestamp, api_key=None):
    """
    Fetch historical market data for a given coin from CoinGecko.

    :param coin_id: CoinGecko ID of the coin (e.g., 'ethereum', 'steth').
    :param vs_currency: The target currency to compare against (e.g., 'usd', 'eth').
    :param from_timestamp: UNIX timestamp for the start date.
    :param to_timestamp: UNIX timestamp for the end date.
    :param api_key: Optional API key for paid CoinGecko plan.
    :return: DataFrame with 'date' and 'price' columns.
    """
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    params = {
        'vs_currency': vs_currency,
        'from': from_timestamp,
        'to': to_timestamp
    }

    headers = {}
    if api_key:
        headers['X-CoinGecko-API-Key'] = api_key

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                prices = data.get('prices', [])
                if not prices:
                    print(f"No price data found for {coin_id} between the specified dates.")
                    return pd.DataFrame(columns=['date', 'price'])
                df = pd.DataFrame(prices, columns=['timestamp', 'price'])
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
                df = df[['date', 'price']].drop_duplicates(subset='date')
                return df
            elif response.status_code == 429:
                # Rate limit exceeded
                wait_time = 60  # Wait for 60 seconds before retrying
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Error fetching data for {coin_id}: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception occurred while fetching data for {coin_id}: {e}")

        wait_time = 2 ** attempt
        print(f"Retrying in {wait_time} seconds...")
        time.sleep(wait_time)

    print(f"Failed to fetch data for {coin_id} after {max_retries} attempts.")
    sys.exit(1)


def generate_events(steth_df, eth_df, threshold, token_symbol):
    """
    Generate depeg and repeg events based on stETH/ETH ratio.

    :param steth_df: DataFrame containing stETH prices.
    :param eth_df: DataFrame containing ETH prices.
    :param threshold: Threshold percentage for depeg detection (e.g., 0.05 for 5%).
    :param token_symbol: Symbol of the token (e.g., 'stETH').
    :return: List of event dictionaries.
    """
    # Merge on date
    merged_df = pd.merge(steth_df, eth_df, on='date', suffixes=('_steth', '_eth'))

    # Calculate the stETH/ETH ratio
    merged_df['ratio'] = merged_df['price_steth'] / merged_df['price_eth']

    # Initialize variables
    events = []
    is_depegged = False
    block_number = 0  # Each day is one block

    for index, row in merged_df.iterrows():
        block_number += 1  # Increment block number
        ratio = row['ratio']
        date = row['date']

        # Check for depeg
        if not is_depegged and ratio < (1 - threshold):
            depeg_percentage = 1 - ratio
            event = {
                "type": "depeg",
                "block": block_number,
                "percentage": round(depeg_percentage, 4),  # Round for readability
                "token": token_symbol
            }
            events.append(event)
            is_depegged = True
            print(f"Depeg event on {date}: ratio={ratio:.4f}, depeg by {depeg_percentage * 100:.2f}%")

        # Check for repeg
        elif is_depegged and ratio >= (1 - threshold):
            event = {
                "type": "repeg",
                "block": block_number,
                "token": token_symbol
            }
            events.append(event)
            is_depegged = False
            print(f"Repeg event on {date}: ratio={ratio:.4f}")

    return events


def parse_arguments():
    """
    Parse command-line arguments.

    :return: Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Generate events.json based on stETH/ETH price data.')

    parser.add_argument('--output', type=str, default='events.json',
                        help='Output JSON file name (default: events.json)')
    parser.add_argument('--threshold', type=float, default=0.05,
                        help='Depeg threshold as a decimal (e.g., 0.05 for 5%%) (default: 0.05)')
    parser.add_argument('--start-date', type=str, required=True,
                        help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, required=True,
                        help='End date in YYYY-MM-DD format')
    parser.add_argument('--token-symbol', type=str, default='stETH',
                        help='Symbol of the token (default: stETH)')
    parser.add_argument('--coin-gecko-id', type=str, default='steth',
                        help='CoinGecko ID for stETH (default: steth)')
    parser.add_argument('--vs-currency', type=str, default='eth',
                        help='Currency to compare against (default: eth)')
    parser.add_argument('--api-key', type=str, default=None,
                        help='Optional API key for paid CoinGecko plan')

    return parser.parse_args()


def main():
    args = parse_arguments()

    # Convert dates to UNIX timestamps
    try:
        start_dt = datetime.strptime(args.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end_date, '%Y-%m-%d')
        if end_dt < start_dt:
            print("End date must be after start date.")
            sys.exit(1)
    except ValueError:
        print("Incorrect date format. Please use YYYY-MM-DD.")
        sys.exit(1)

    from_timestamp = int(start_dt.timestamp())
    to_timestamp = int((end_dt + timedelta(days=1)).timestamp())  # Include end date

    print(f"Fetching historical prices from {args.start_date} to {args.end_date}...")

    # Fetch stETH prices
    steth_df = fetch_historical_prices(
        coin_id=args.coin_gecko_id,
        vs_currency=args.vs_currency,
        from_timestamp=from_timestamp,
        to_timestamp=to_timestamp,
        api_key=args.api_key
    )

    if steth_df.empty:
        print("No stETH price data available for the specified date range.")
        sys.exit(1)

    # Fetch ETH prices
    # If vs_currency is 'eth', ETH price in 'eth' is always 1
    if args.vs_currency.lower() == 'eth':
        eth_df = steth_df[['date']].copy()
        eth_df['price'] = 1.0
    else:
        eth_df = fetch_historical_prices(
            coin_id='ethereum',
            vs_currency=args.vs_currency,
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            api_key=args.api_key
        )
        if eth_df.empty:
            print("No ETH price data available for the specified date range.")
            sys.exit(1)

    # Generate events
    events = generate_events(
        steth_df=steth_df,
        eth_df=eth_df,
        threshold=args.threshold,
        token_symbol=args.token_symbol
    )

    # Save events to JSON file
    with open(args.output, 'w') as f:
        json.dump(events, f, indent=2)

    print(f"\nEvents have been saved to {args.output}")


if __name__ == "__main__":
    main()
