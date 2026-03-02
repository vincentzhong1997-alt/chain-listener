"""Listen for WBTC events on Ethereum, Tron, and Solana using their token ABIs."""

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
SOL_ABI_PATH = Path(__file__).with_name("sol_wbtc.json")

CHAIN_SETUPS = {
    "ethereum": {
        "enabled": False,
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
                "api_key_header": os.environ.get("ETH_API_KEY_HEADER"),
            }
        ],
        "confirmation_blocks": 12,
        "polling_interval": 15000,
        "start_block": 24038340,
    },
    "tron": {
        "enabled": False,
        "chain_type": "tron",
        "contract_address": "TYhWwKpw43ENFWBTGpzLHn3882f2au7SMi",
        "abi_path": TRON_ABI_PATH,
        "endpoints": [
            {
                "url": os.environ.get("TRON_RPC_URL", "https://api.trongrid.io"),
                "api_key": os.environ.get("TRON_API_KEY", "d320f1de-30a2-4be7-a4b0-8151681e7bd9"),
                "api_key_header": os.environ.get("TRON_API_KEY_HEADER", "TRON-PRO-API-KEY"),
            }
        ],
        "confirmation_blocks": 20,
        "polling_interval": 10000,
        "start_block": 78553867,
    },
    "solana": {
        "chain_type": "solana",
        "contract_address": "Fii8GURTsfPZrpBZNd99BRPMDztUUGm7Th1XfoANDHVh",
        "abi_path": SOL_ABI_PATH,
        "endpoints": [
            {
                "url": os.environ.get("SOLANA_RPC_URL", "https://solana-mainnet.gateway.tatum.io"),
                "api_key": "t-694ad531445c47886798c086-e30b86fa1dd2449594e7d6bc",
                "api_key_header": "x-api-key",
            }
        ],
        "confirmation_blocks": 0,
        "polling_interval": 15000,
        "start_block": 336608407,
        "allowed_events": ["burn", "add_mint_request"],
    },
}


def _load_event_names(abi_path: Path, allowed: List[str] | None = None) -> List[str]:
    """Read an ABI/IDL file and return the list of unique event (or instruction) names.

    Args:
        abi_path: Path to the ABI/IDL file
        allowed: Optional whitelist of event names to include
    """
    with abi_path.open("r", encoding="utf-8") as f:
        abi = json.load(f)

    allowed_set = set(allowed) if allowed else None
    event_names: List[str] = []

    def _should_keep(name: str) -> bool:
        if not name:
            return False
        if allowed_set is not None and name not in allowed_set:
            return False
        return name not in event_names

    # Ethereum-style ABI (list of entries)
    if isinstance(abi, list):
        for entry in abi:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "event":
                continue
            name = entry.get("name")
            if _should_keep(name):
                event_names.append(name)
        return event_names

    # Anchor/IDL-style (dict with "events" or "instructions")
    if isinstance(abi, dict):
        # Prefer "events" if present
        for entry in abi.get("events", []) or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if _should_keep(name):
                event_names.append(name)

        # Fallback to instructions (Solana programs often expose via instructions)
        for entry in abi.get("instructions", []) or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if _should_keep(name):
                event_names.append(name)

    return event_names


def _build_config() -> Tuple[ChainListenerConfig, Dict[str, Dict[str, List[str]]]]:
    """Create the ChainListener configuration for Ethereum + Tron + Solana."""
    chains: Dict[str, Dict[str, object]] = {}
    callbacks: Dict[str, Dict[str, List[str]]] = {}

    for chain_name, settings in CHAIN_SETUPS.items():
        event_names = _load_event_names(
            settings["abi_path"], settings.get("allowed_events")
        )

        chain_config: Dict[str, object] = {
            "enabled": settings.get("enabled", True),
            "chain_type": settings["chain_type"],
            "confirmation_blocks": settings["confirmation_blocks"],
            "polling_interval": settings["polling_interval"],
            "rpc": {
                "endpoints": settings["endpoints"],
                "timeout": 30,
                "retries": 3,
                "rate_limit": {"requests_per_second": 1, "burst_size": 1},
                "max_block_batch": 10
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

        chains[chain_name] = chain_config
        callbacks[chain_name] = {
            "contract_address": settings["contract_address"],
            "events": event_names,
        }

    config_data = {
        "global_config": {
            "max_concurrent_processing": 10,
            "event_batch_size": 10,
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

    print("Listening for WBTC events on Ethereum, Tron, and Solana")
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
