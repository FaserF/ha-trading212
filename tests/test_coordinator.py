"""Tests for Trading 212 coordinator and models."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from custom_components.trading212.const import (
    DEFAULT_POLL_INTERVAL,
    ENVIRONMENT_LIVE,
    SCOPE_ACCOUNT,
    SCOPE_HISTORY,
    SCOPE_METADATA,
    SCOPE_ORDERS,
    SCOPE_PIES,
    SCOPE_PORTFOLIO,
)
from custom_components.trading212.coordinator import (
    Trading212Coordinator,
    ticker_to_slug,
)


def test_ticker_to_slug() -> None:
    """Test converting tickers to valid entity slug IDs."""
    assert ticker_to_slug("AAPL_US_EQ") == "aapl_us_eq"
    assert ticker_to_slug("BPl_EQ") == "bpl_eq"
    assert ticker_to_slug("BRK.B") == "brk_b"


async def test_coordinator_fetch(hass: MagicMock, mock_trading212_client) -> None:
    """Test coordinator data fetch with mocked API client."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_123"
    config_entry.data = {
        "api_key": "dummy_key",
        "environment": ENVIRONMENT_LIVE,
    }
    config_entry.options = {}

    permissions = {
        SCOPE_ACCOUNT: True,
        SCOPE_PORTFOLIO: True,
        SCOPE_METADATA: True,
        SCOPE_PIES: True,
        SCOPE_ORDERS: True,
        SCOPE_HISTORY: True,
    }

    coordinator = Trading212Coordinator(
        hass,
        mock_trading212_client,
        DEFAULT_POLL_INTERVAL,
        config_entry,
        permissions,
    )

    coordinator._store = MagicMock()
    coordinator._store.async_load = AsyncMock(return_value=None)
    coordinator._store.async_save = AsyncMock(return_value=None)
    data = await coordinator._fetch_data()
    assert data.total_value == 61.28
    assert data.cash_available == 40.0
    assert data.currency == "EUR"
    assert "bpl_eq" in data.positions
    pos = data.positions["bpl_eq"]
    assert pos.ticker == "BPl_EQ"
    assert pos.instrument_name == "BP"
    assert pos.quantity == 2.92396
    assert pos.average_price == 618.00093025
