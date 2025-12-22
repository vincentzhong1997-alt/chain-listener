import pytest
from unittest.mock import AsyncMock, patch

from chain_listener.adapters.solana import SolanaAdapter
from chain_listener.models.events import ChainType, RawEvent


def _build_config():
    return {
        "name": "solana",
        "network": "mainnet",
        "rpc": {
            "urls": ["https://api.mainnet-beta.solana.com"],
            "timeout": 30,
            "retries": 2,
            "rate_limit": {
                "requests_per_second": 5,
                "burst_size": 10,
            },
        },
        "contracts": [],
    }


@pytest.mark.asyncio
async def test_get_latest_block_number_uses_client():
    adapter = SolanaAdapter(_build_config())
    async_mock = AsyncMock(return_value={"result": 123456})

    with patch.object(adapter, "_execute_with_client", async_mock):
        latest = await adapter.get_latest_block_number()

    assert latest == 123456
    async_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_logs_fetches_signatures_and_events():
    adapter = SolanaAdapter(_build_config())

    with patch.object(
        adapter,
        "_fetch_signatures_for_program",
        AsyncMock(side_effect=[[{"signature": "sig1"}], [{"signature": "sig2"}]]),
    ) as fetch_mock, patch.object(
        adapter,
        "_build_events_from_signatures",
        AsyncMock(
            side_effect=[
                [
                    {
                        "event_name": "MintRequest",
                        "block_number": 1,
                        "block_hash": "hash1",
                        "transaction_hash": "sig1",
                        "log_index": 0,
                        "address": "ProgramA",
                        "timestamp": 111,
                        "event_data": {"amount": 10},
                    }
                ],
                [
                    {
                        "event_name": "BurnRequest",
                        "block_number": 2,
                        "block_hash": "hash2",
                        "transaction_hash": "sig2",
                        "log_index": 0,
                        "address": "ProgramB",
                        "timestamp": 222,
                        "event_data": {"amount": 3},
                    }
                ],
            ]
        ),
    ) as events_mock:
        logs = await adapter.get_logs(
            address=["ProgramA", "ProgramB"],
            topics=["MintRequest"],
            from_block=1,
            to_block=100,
        )

    # Only one event matches the topic filter
    assert len(logs) == 1
    assert logs[0]["event_name"] == "MintRequest"
    fetch_mock.assert_awaited()
    events_mock.assert_awaited()


def test_decode_event_returns_decoded_event():
    adapter = SolanaAdapter(_build_config())
    raw_event = RawEvent(
        chain_type=ChainType.SOLANA,
        block_number=42,
        block_hash="recent-hash",
        transaction_hash="sig123",
        log_index=0,
        contract_address="ProgramC",
        raw_data={
            "event_name": "MintConfirm",
            "event_data": {"amount": 99},
            "timestamp": 99123,
        },
        timestamp=0,
    )

    decoded = adapter.decode_event(raw_event)

    assert decoded.chain_type == ChainType.SOLANA
    assert decoded.event_name == "MintConfirm"
    assert decoded.parameters["amount"] == 99
    assert decoded.timestamp == 99123
