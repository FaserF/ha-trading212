"""Services for Trading 212."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api.client import Trading212Client
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN
from .coordinator import Trading212Coordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_CANCEL_ORDER = "cancel_order"
SERVICE_CANCEL_ALL_ORDERS = "cancel_all_orders"

SCHEMA_CANCEL_ORDER = vol.Schema(
    {
        vol.Required("order_id"): vol.Any(cv.positive_int, cv.string),
        vol.Optional("entry_id"): cv.string,
    }
)

SCHEMA_CANCEL_ALL_ORDERS = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
    }
)


def _get_entry_id(hass: HomeAssistant, call: ServiceCall) -> str:
    """Retrieve entry_id from call or pick first active entry."""
    entry_id = call.data.get("entry_id")
    if entry_id and entry_id in hass.data[DOMAIN]:
        return entry_id
    entries = list(hass.data[DOMAIN].keys())
    # Exclude internal session keys if any
    valid_entries = [
        e
        for e in entries
        if isinstance(hass.data[DOMAIN][e], dict)
        and DATA_CLIENT in hass.data[DOMAIN][e]
    ]
    if not valid_entries:
        raise ValueError("No configured Trading 212 integration found.")
    return valid_entries[0]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Trading 212 services."""

    async def handle_cancel_order(call: ServiceCall) -> None:
        """Handle cancelling a specific order."""
        entry_id = _get_entry_id(hass, call)
        client: Trading212Client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
        coordinator: Trading212Coordinator = hass.data[DOMAIN][entry_id][
            DATA_COORDINATOR
        ]
        order_id = call.data["order_id"]
        _LOGGER.info("Cancelling Trading 212 order %s", order_id)
        await client.cancel_order(order_id)
        await coordinator.async_request_refresh()

    async def handle_cancel_all_orders(call: ServiceCall) -> None:
        """Handle cancelling all open orders."""
        entry_id = _get_entry_id(hass, call)
        client: Trading212Client = hass.data[DOMAIN][entry_id][DATA_CLIENT]
        coordinator: Trading212Coordinator = hass.data[DOMAIN][entry_id][
            DATA_COORDINATOR
        ]
        orders = await client.get_orders()
        for o in orders:
            o_id = o.get("id")
            if o_id is not None:
                await client.cancel_order(o_id)
        await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_ORDER,
        handle_cancel_order,
        schema=SCHEMA_CANCEL_ORDER,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_ALL_ORDERS,
        handle_cancel_all_orders,
        schema=SCHEMA_CANCEL_ALL_ORDERS,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Trading 212 services."""
    hass.services.async_remove(DOMAIN, SERVICE_CANCEL_ORDER)
    hass.services.async_remove(DOMAIN, SERVICE_CANCEL_ALL_ORDERS)
