"""Tests for Trading 212 diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.trading212.const import DATA_COORDINATOR, DOMAIN
from custom_components.trading212.coordinator import CoordinatorData
from custom_components.trading212.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redaction(hass: MagicMock) -> None:
    """Test diagnostics export and credential redaction."""
    entry = MagicMock()
    entry.entry_id = "test_entry_diag"
    entry.title = "Trading 212 (Live)"
    entry.data = {
        "api_key": "SUPER_SECRET_KEY",
        "api_secret": "SUPER_SECRET_SECRET",
        "environment": "live",
    }
    entry.options = {}
    entry.version = 2

    coordinator = MagicMock()
    coordinator.permissions = {"account": True, "portfolio": True}
    coordinator.data = CoordinatorData(
        total_value=1234.56,
        cash_available=100.0,
        currency="EUR",
    )

    hass.data = {
        DOMAIN: {
            entry.entry_id: {
                DATA_COORDINATOR: coordinator,
            }
        }
    }

    result = await async_get_config_entry_diagnostics(hass, entry)
    assert result["entry"]["data"]["api_key"] == "**REDACTED**"
    assert result["entry"]["data"]["api_secret"] == "**REDACTED**"
    assert result["coordinator_data"]["total_value"] == 1234.56
    assert result["coordinator_data"]["currency"] == "EUR"
