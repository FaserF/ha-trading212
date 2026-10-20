"""Fixtures for Trading 212 tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_SUMMARY = {
    "free": 40.0,
    "total": 61.28,
    "ppl": -0.20,
    "result": 0.0,
    "invested": 21.48,
    "pieCash": 0.0,
    "blocked": 0.0,
}

MOCK_ACCOUNT_INFO = {
    "id": 51958397,
    "currencyCode": "EUR",
}

MOCK_POSITIONS = [
    {
        "ticker": "BPl_EQ",
        "quantity": 2.92396,
        "averagePrice": 618.00093025,
        "currentPrice": 616.3,
        "ppl": -0.20,
        "fxPpl": -0.14,
        "initialFillDate": "2026-10-20T10:45:17.038+03:00",
        "frontend": "SYSTEM",
        "maxBuy": 1267859.07604,
        "maxSell": None,
        "pieQuantity": 0,
    }
]

MOCK_INSTRUMENTS = [
    {
        "ticker": "BPl_EQ",
        "type": "STOCK",
        "workingScheduleId": 55,
        "isin": "GB0007980591",
        "currencyCode": "GBX",
        "name": "BP",
        "shortName": "BP",
        "maxOpenQuantity": 1267862.0,
        "extendedHours": False,
        "addedOn": "2018-07-12T07:10:05.000+03:00",
    }
]

MOCK_PIES = []

MOCK_ORDERS = []

MOCK_DIVIDENDS = {
    "items": [],
    "nextPagePath": None,
}

MOCK_PERMISSIONS = {
    "account": True,
    "portfolio": True,
    "metadata": True,
    "pies": True,
    "orders": True,
    "history": True,
}


@pytest.fixture
def hass():
    """Mock HomeAssistant instance."""
    mock_hass = MagicMock()
    mock_hass.bus.async_fire = MagicMock()
    return mock_hass


@pytest.fixture
def mock_trading212_client():
    """Mock Trading 212 API client."""
    with patch(
        "custom_components.trading212.api.client.Trading212Client",
        autospec=True,
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.get_account_summary = AsyncMock(return_value=MOCK_SUMMARY)
        client.get_account_cash = AsyncMock(return_value=MOCK_SUMMARY)
        client.get_account_info = AsyncMock(return_value=MOCK_ACCOUNT_INFO)
        client.get_positions = AsyncMock(return_value=MOCK_POSITIONS)
        client.get_portfolio = AsyncMock(return_value=MOCK_POSITIONS)
        client.get_instruments = AsyncMock(return_value=MOCK_INSTRUMENTS)
        client.get_exchanges = AsyncMock(return_value=[])
        client.get_pies = AsyncMock(return_value=MOCK_PIES)
        client.get_orders = AsyncMock(return_value=MOCK_ORDERS)
        client.get_dividends = AsyncMock(return_value=MOCK_DIVIDENDS)
        client.get_historical_orders = AsyncMock(return_value={"items": []})
        client.get_historical_transactions = AsyncMock(return_value={"items": []})
        client.get_historical_exports = AsyncMock(return_value=[])
        client.cancel_order = AsyncMock(return_value=None)
        client.test_permissions = AsyncMock(return_value=MOCK_PERMISSIONS)
        yield client
