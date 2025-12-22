"""Listen for WBTC events on both Ethereum and Tron using their token ABIs."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

from chain_listener import ChainListener, ChainListenerConfig
from chain_listener.models.events import DecodedEvent

ETH_ABI_PATH = Path(__file__).with_name("eth_wbtc.json")
TRON_ABI_PATH = Path(__file__).with_name("trx_wbtc.json")

CHAIN_SETUPS = {
    "ethereum": {
        "chain_type": "ethereum",
        "contract_address": "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",
        "abi_path": ETH_ABI_PATH,
        "endpoints": [
            {
                "url": os.environ.get(
                    "ETHEREUM_RPC_URL",
                    "https://eth-mainnet.g.alchemy.com/v2/8kg5BVMw4kdwNLo0bMkA6",
                ),
                "api_key": os.environ.get("ETHEREUM_API_KEY"),
            }
        ],
        "confirmation_blocks": 12,
        "polling_interval": 15000,
        "start_block": 24038340,
    },
    "tron": {
        "chain_type": "tron",
        "contract_address": "TYhWwKpw43ENFWBTGpzLHn3882f2au7SMi",
        "abi_path": TRON_ABI_PATH,
        "endpoints": [
            {
                "url": os.environ.get("TRON_RPC_URL", "https://api.trongrid.io"),
                "api_key": os.environ.get("TRON_API_KEY"),
            }
        ],
        "confirmation_blocks": 20,
        "polling_interval": 10000,
        "start_block": None,
    },
}


def _load_event_names(abi_path: Path) -> List[str]:
    """Read an ABI file and return the list of unique event names."""
    with abi_path.open("r", encoding="utf-8") as f:
        abi = json.load(f)

    event_names: List[str] = []
    for entry in abi:
        if entry.get("type") != "event":
            continue
        name = entry.get("name")
        if name and name not in event_names:
            event_names.append(name)
    return event_names


def _build_config() -> Tuple[ChainListenerConfig, Dict[str, Dict[str, List[str]]]]:
    """Create the ChainListener configuration for Ethereum + Tron."""
    chains: Dict[str, Dict[str, object]] = {}
    callbacks: Dict[str, Dict[str, List[str]]] = {}

    for chain_name, settings in CHAIN_SETUPS.items():
        event_names = _load_event_names(settings["abi_path"])

        urls: List[str] = []
        headers: Dict[str, str] = {}
        for ep in settings["endpoints"]:
            url = ep.get("url")
            if not url:
                continue
            urls.append(url)
            api_key = ep.get("api_key")
            if api_key and settings["chain_type"] == "tron":
                headers["TRON-PRO-API-KEY"] = api_key

        chain_config: Dict[str, object] = {
            "enabled": True,
            "chain_type": settings["chain_type"],
            "confirmation_blocks": settings["confirmation_blocks"],
            "polling_interval": settings["polling_interval"],
            "rpc": {
                "urls": urls,
                "timeout": 30,
                "retries": 3,
            },
            "contracts": [
                {
                    "name": "WBTC",
                    "address": settings["contract_address"],
                    "abi_path": str(settings["abi_path"]),
                    "events": event_names,
                }
            ],
        }

        if settings.get("start_block") is not None:
            chain_config["start_block"] = settings["start_block"]

        if headers:
            chain_config["adapter_config"] = {
                "rpc": {
                    "headers": headers
                }
            }

        chains[chain_name] = chain_config
        callbacks[chain_name] = {
            "contract_address": settings["contract_address"],
            "events": event_names,
        }

    config_data = {
        "global_config": {
            "max_concurrent_processing": 10,
            "event_batch_size": 100,
            "log_level": "INFO",
        },
        "chains": chains,
    }
    return ChainListenerConfig(**config_data), callbacks


async def log_event(event: DecodedEvent) -> None:
    """Print the decoded event details."""
    chain_value = event.chain_type.value if hasattr(event.chain_type, "value") else event.chain_type
    print(f"\n[WBTC:{chain_value}] Event detected")
    print(f"Event:        {event.event_name}")
    print(f"Block:        {event.block_number}")
    print(f"Tx Hash:      {event.transaction_hash}")
    print(f"Log Index:    {event.log_index}")
    print("Parameters:")
    if event.parameters:
        for key, value in event.parameters.items():
            print(f"  - {key}: {value}")
    else:
        print("  (no parameters)")
    print("-" * 60)


async def main() -> None:
    """Bootstrap the listener and keep it running."""
    logging.basicConfig(level=logging.INFO)

    config, callback_map = _build_config()
    listener = ChainListener(config)

    for chain_name, info in callback_map.items():
        for event_name in info["events"]:
            listener.on_event(
                chain_name,
                info["contract_address"],
                event_name,
                log_event,
            )

    print("Listening for WBTC events on Ethereum and Tron")
    for chain_name, info in callback_map.items():
        print(f"- {chain_name}: {info['contract_address']} ({len(info['events'])} events)")
    print("Press Ctrl+C to stop\n")

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
