"""Listen for USDC Transfer events on BSC."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from chain_listener import ChainListener, ChainListenerConfig
from chain_listener.models.events import DecodedEvent

USDC_CONTRACT_ADDRESS = "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d"
USDC_ABI_PATH = Path(__file__).with_name("usdc_erc20_abi.json")


def _parse_start_block(raw_value: Optional[str]) -> Optional[int]:
    """Parse optional start block from environment variable."""
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
        return parsed if parsed >= 0 else None
    except ValueError:
        return None


def _parse_positive_int(raw_value: Optional[str], default: int) -> int:
    """Parse positive integer from environment variable."""
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


def build_config() -> ChainListenerConfig:
    """Build listener config for BSC USDC transfer monitoring."""
    rpc_url = os.environ.get("BSC_RPC_URL", "https://bsc-dataseed.binance.org")
    start_block = _parse_start_block(os.environ.get("BSC_START_BLOCK"))
    polling_interval_ms = _parse_positive_int(
        os.environ.get("BSC_POLLING_INTERVAL_MS"), 10000
    )
    requests_per_second = _parse_positive_int(
        os.environ.get("BSC_REQUESTS_PER_SECOND"), 1
    )
    burst_size = _parse_positive_int(os.environ.get("BSC_BURST_SIZE"), 1)

    bsc_chain_config = {
        "enabled": True,
        "chain_type": "bsc",
        "confirmation_blocks": 12,
        "polling_interval": polling_interval_ms,
        "rpc": {
            "urls": [rpc_url],
            "timeout": 30,
            "retries": 3,
            "rate_limit": {
                "requests_per_second": requests_per_second,
                "burst_size": burst_size,
            },
        },
        "contracts": [
            {
                "name": "USDC",
                "address": USDC_CONTRACT_ADDRESS,
                "abi_path": str(USDC_ABI_PATH),
                "events": ["Transfer"],
            }
        ],
    }

    if start_block is not None:
        bsc_chain_config["start_block"] = start_block

    return ChainListenerConfig(
        global_config={
            "max_concurrent_processing": 10,
            "event_batch_size": 100,
            "log_level": "INFO",
        },
        chains={"bsc": bsc_chain_config},
    )


async def on_transfer(event: DecodedEvent) -> None:
    """Handle USDC transfer events."""
    params = event.parameters or {}
    sender = params.get("from", "unknown")
    recipient = params.get("to", "unknown")
    amount = params.get("value", "unknown")

    print("\n[USDC Transfer @ BSC]")
    print(f"From: {sender}")
    print(f"To: {recipient}")
    print(f"Value (raw): {amount}")
    print(f"Block: {event.block_number}")
    print(f"Tx: {event.transaction_hash}")
    print("-" * 60)


async def main() -> None:
    """Start listener and stream BSC USDC Transfer events."""
    logging.basicConfig(level=logging.INFO)

    listener = ChainListener(build_config())
    listener.on_event("bsc", USDC_CONTRACT_ADDRESS, "Transfer", on_transfer)

    print("Listening for BSC USDC Transfer events...")
    print(f"Contract: {USDC_CONTRACT_ADDRESS}")
    print("Environment variables:")
    print("  BSC_RPC_URL      Optional, default https://bsc-dataseed.binance.org")
    print("  BSC_START_BLOCK  Optional, if unset listens from latest confirmed block")
    print("  BSC_POLLING_INTERVAL_MS  Optional, default 10000 (10s)")
    print("  BSC_REQUESTS_PER_SECOND  Optional, default 1")
    print("  BSC_BURST_SIZE           Optional, default 1")
    print("Press Ctrl+C to stop.\n")

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
