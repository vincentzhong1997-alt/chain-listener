import json
import pytest
from unittest.mock import AsyncMock, patch

from chain_listener.adapters.tron import TronAdapter
from chain_listener.models.events import RawEvent, ChainType


def _build_config():
    return {
        "name": "tron",
        "network": "mainnet",
        "rpc": {
            "urls": ["https://api.trongrid.io"],
            "timeout": 30,
            "retries": 2,
            "rate_limit": {
                "requests_per_second": 5,
                "burst_size": 10,
            },
        },
    }


@pytest.mark.asyncio
async def test_get_latest_block_number_uses_tron_client():
    adapter = TronAdapter(_build_config())
    with patch.object(
        adapter,
        "_execute_with_client",
        AsyncMock(return_value=123456),
    ) as mock_exec:
        latest = await adapter.get_latest_block_number()

    assert latest == 123456
    mock_exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_logs_invokes_contract_event_fetch_and_aggregates():
    adapter = TronAdapter(_build_config())

    # mock timestamp lookup
    adapter._block_to_timestamp = AsyncMock(side_effect=[1000, 2000])

    first_contract_events = [
        {
            "block_number": 1,
            "transaction_hash": "0x1",
            "event_name": "Transfer",
            "contract_address": "TXXX",
            "result": {"value": "1"},
        }
    ]
    second_contract_events = []

    with patch.object(
        adapter,
        "_fetch_contract_events",
        AsyncMock(side_effect=[first_contract_events, second_contract_events]),
    ) as mock_fetch:
        logs = await adapter.get_logs(
            address=["TXXX", "TYYY"],
            topics=["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"],
            from_block=10,
            to_block=20,
        )

    assert len(logs) == 1
    mock_fetch.assert_awaited()
    # called once per address
    assert mock_fetch.await_count == 2
    first_call = mock_fetch.await_args_list[0]
    assert first_call.kwargs["event_name"] == "Transfer"
    assert first_call.kwargs["min_timestamp"] == 1000
    assert first_call.kwargs["max_timestamp"] == 2000


def test_decode_event_returns_decoded_event_dataclass():
    adapter = TronAdapter(_build_config())
    raw_event = RawEvent(
        chain_type=adapter.chain_type,
        block_number=123,
        block_hash="0xabc",
        transaction_hash="0xdef",
        log_index=0,
        contract_address="TXYZ",
        raw_data={
            "event_name": "Transfer",
            "result": {"from": "TA", "to": "TB", "value": "1"},
            "timestamp": 1730000000,
        },
        timestamp=0,
    )

    decoded = adapter.decode_event(raw_event)

    assert decoded.event_name == "Transfer"
    assert decoded.parameters["value"] == "1"
    assert decoded.timestamp == 1730000000


def test_decode_event_uses_loaded_abi(tmp_path):
    abi_path = tmp_path / "tron_erc20.json"
    abi_definition = [
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
                {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
                {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        }
    ]
    abi_path.write_text(json.dumps(abi_definition))

    contract_address = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    config = _build_config()
    config["contracts"] = [
        {
            "name": "TronToken",
            "address": contract_address,
            "abi_path": str(abi_path),
            "events": ["Transfer"],
        }
    ]

    adapter = TronAdapter(config)

    def pad_address(addr: str) -> str:
        return "0x" + ("0" * 24) + addr[2:]

    sender = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    recipient = "0xcccccccccccccccccccccccccccccccccccccccc"
    raw_event = RawEvent(
        chain_type=ChainType.TRON,
        block_number=987,
        block_hash="ff" * 32,
        transaction_hash="11" * 32,  # intentionally missing 0x prefix
        log_index=2,
        contract_address=contract_address,
        raw_data={
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                pad_address(sender),
                pad_address(recipient),
            ],
            "data": "0x" + "0" * 60 + "007b",
            "timestamp": 1700001111,
        },
        timestamp=0,
    )

    decoded = adapter.decode_event(raw_event)

    assert decoded.event_name == "Transfer"
    assert decoded.parameters["value"] == 123
    assert decoded.parameters["from"].lower() == sender.lower()
    assert decoded.parameters["to"].lower() == recipient.lower()


@pytest.mark.asyncio
async def test_get_logs_uses_event_filters_for_tron():
    adapter = TronAdapter(_build_config())

    adapter._fetch_contract_events = AsyncMock(return_value=[])
    adapter._block_to_timestamp = AsyncMock(return_value=None)

    await adapter.get_logs(
        address="TXYZ",
        from_block=0,
        to_block=10,
        event_filters={"TXYZ": ["Transfer", "Approval"]},
    )

    assert adapter._fetch_contract_events.await_count == 2
