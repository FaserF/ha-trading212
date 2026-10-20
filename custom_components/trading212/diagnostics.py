"""Diagnostics support for Trading 212."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_API_SECRET, DATA_COORDINATOR, DOMAIN
from .coordinator import Trading212Coordinator

TO_REDACT = {
    CONF_API_KEY,
    CONF_API_SECRET,
    "api_key",
    "api_secret",
    "id",
    "reference",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: Trading212Coordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    data = coordinator.data
    coord_data_dict: dict[str, Any] = {}
    if data:
        coord_data_dict = {
            "total_value": data.total_value,
            "cash_available": data.cash_available,
            "cash_in_pies": data.cash_in_pies,
            "invested": data.invested,
            "unrealized_pnl": data.unrealized_pnl,
            "realized_pnl": data.realized_pnl,
            "result_percent": data.result_percent,
            "currency": data.currency,
            "open_positions_count": data.open_positions_count,
            "active_orders_count": data.active_orders_count,
            "total_dividends": data.total_dividends,
            "daily_gain_loss": data.daily_gain_loss,
            "daily_gain_loss_percent": data.daily_gain_loss_percent,
            "last_updated": data.last_updated.isoformat()
            if data.last_updated
            else None,
            "account_info": data.account_info_raw,
            "positions_count": len(data.positions),
            "pies_count": len(data.pies),
            "orders_count": len(data.orders_raw),
        }

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
            "version": entry.version,
        },
        "permissions": coordinator.permissions,
        "coordinator_data": async_redact_data(coord_data_dict, TO_REDACT),
    }
