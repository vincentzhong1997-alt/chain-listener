"""Listen for WBTC Mint/Burn events on BSC testnet with config-driven SDK setup."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from chain_listener import ChainListener
from chain_listener.models.events import DecodedEvent

DEFAULT_CHAIN_NAME = "bsc_testnet"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


async def on_wbtc_event(event: DecodedEvent) -> None:
    """Print monitored event details."""
    params = event.parameters or {}

    print("\n[WBTC Event @ BSC Testnet]")
    print(f"Event: {event.event_name}")
    print(f"Contract: {event.contract_address}")
    if "requester" in params:
        print(f"Requester: {params.get('requester')}")
    if "to" in params:
        print(f"To: {params.get('to')}")
    if "burner" in params:
        print(f"Burner: {params.get('burner')}")
    if "nonce" in params:
        print(f"Nonce: {params.get('nonce')}")

    amount = params.get("amount", params.get("value"))
    if amount is not None:
        print(f"Amount (raw): {amount}")
    if "btcTxid" in params:
        print(f"BTC Txid: {params.get('btcTxid')}")
    if "requestHash" in params:
        print(f"Request Hash: {params.get('requestHash')}")
    print(f"Block: {event.block_number}")
    print(f"Tx: {event.transaction_hash}")
    print("-" * 60)


def _get_config_path() -> Path:
    """Get config file path from env or default path in current directory."""
    config_path = os.environ.get("BSC_TESTNET_LISTENER_CONFIG")
    if config_path:
        return Path(config_path).expanduser()
    return DEFAULT_CONFIG_PATH


def _register_callbacks_from_config(listener: ChainListener, chain_name: str) -> None:
    """Register callbacks for all configured contracts/events on target chain."""
    chain_config = listener.config.chains.get(chain_name)
    if chain_config is None:
        raise ValueError(f"Chain '{chain_name}' not found in config")

    for contract in chain_config.contracts:
        for event_name in contract.events:
            listener.on_event(
                chain_name,
                contract.address,
                event_name,
                on_wbtc_event,
            )


async def main() -> None:
    """Start listener and stream configured events with config file."""
    logging.basicConfig(level=logging.INFO)

    config_path = _get_config_path()
    listener = ChainListener.from_config_file(str(config_path))
    _register_callbacks_from_config(listener, DEFAULT_CHAIN_NAME)

    print("Listening for WBTC Mint/Burn events from config file...")
    print(f"Config: {config_path}")
    print(
        "Set BSC_TESTNET_LISTENER_CONFIG to use another config file.\n"
    )

    try:
        await listener.start_listening()
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping listener...")
    finally:
        await listener.stop_listening()


if __name__ == "__main__":
    asyncio.run(main())
