"""Button platform for the Trading 212 integration."""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api.client import Trading212Client
from .api.exceptions import Trading212Error
from .const import (
    CONF_ENVIRONMENT,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DOMAIN,
    ENVIRONMENT_LIVE,
    SCOPE_ORDERS,
)
from .coordinator import Trading212Coordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class Trading212ButtonDescription(ButtonEntityDescription):
    """Describes a Trading 212 button."""

    press_fn: Callable[
        [Trading212Client, Trading212Coordinator], Coroutine[Any, Any, None]
    ]
    required_scope: str | None = None


async def _async_cancel_all_orders(
    client: Trading212Client, coordinator: Trading212Coordinator
) -> None:
    """Cancel all pending orders."""
    orders = await client.get_orders()
    for order in orders:
        order_id = order.get("id")
        if order_id is not None:
            await client.cancel_order(order_id)
    await coordinator.async_request_refresh()


BUTTONS: tuple[Trading212ButtonDescription, ...] = (
    Trading212ButtonDescription(
        key="cancel_all_orders",
        translation_key="cancel_all_orders",
        press_fn=_async_cancel_all_orders,
        required_scope=SCOPE_ORDERS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trading 212 button entities."""
    client: Trading212Client = hass.data[DOMAIN][entry.entry_id][DATA_CLIENT]
    coordinator: Trading212Coordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[Trading212Button] = []
    for description in BUTTONS:
        if description.required_scope and not coordinator.permissions.get(
            description.required_scope, False
        ):
            continue
        entities.append(Trading212Button(client, coordinator, entry, description))

    async_add_entities(entities)


class Trading212Button(ButtonEntity):
    """Button entity for Trading 212 actions."""

    entity_description: Trading212ButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        client: Trading212Client,
        coordinator: Trading212Coordinator,
        entry: ConfigEntry,
        description: Trading212ButtonDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        self._client = client
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        env = entry.data.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE)
        config_url = (
            "https://live.trading212.com/"
            if env == ENVIRONMENT_LIVE
            else "https://demo.trading212.com/"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Trading 212",
            model=f"{env.title()} Trading Account",
            configuration_url=config_url,
        )

    async def async_press(self) -> None:
        """Handle button press."""
        try:
            await self.entity_description.press_fn(self._client, self._coordinator)
        except Trading212Error as err:
            _LOGGER.error(
                "Failed to execute button action %s: %s",
                self.entity_description.key,
                err,
            )
            raise
