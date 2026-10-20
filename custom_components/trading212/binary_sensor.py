"""Binary sensor platform for Trading 212."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENVIRONMENT,
    DATA_COORDINATOR,
    DOMAIN,
    ENVIRONMENT_LIVE,
    SCOPE_ORDERS,
    SCOPE_PORTFOLIO,
)
from .coordinator import CoordinatorData, Trading212Coordinator


@dataclass(frozen=True, kw_only=True)
class Trading212BinarySensorDescription(BinarySensorEntityDescription):
    """Describes a Trading 212 binary sensor."""

    is_on_fn: Callable[[CoordinatorData], bool]
    required_scope: str | None = None


BINARY_SENSORS: tuple[Trading212BinarySensorDescription, ...] = (
    Trading212BinarySensorDescription(
        key="has_active_orders",
        translation_key="has_active_orders",
        is_on_fn=lambda d: d.active_orders_count > 0,
        required_scope=SCOPE_ORDERS,
    ),
    Trading212BinarySensorDescription(
        key="has_open_positions",
        translation_key="has_open_positions",
        is_on_fn=lambda d: d.open_positions_count > 0,
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212BinarySensorDescription(
        key="profitable_today",
        translation_key="profitable_today",
        is_on_fn=lambda d: d.daily_gain_loss >= 0,
        required_scope=SCOPE_PORTFOLIO,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trading 212 binary sensors."""
    coordinator: Trading212Coordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    entities: list[Trading212BinarySensor] = []
    for description in BINARY_SENSORS:
        if description.required_scope and not coordinator.permissions.get(
            description.required_scope, False
        ):
            continue
        entities.append(Trading212BinarySensor(coordinator, entry, description))

    async_add_entities(entities)


class Trading212BinarySensor(
    CoordinatorEntity[Trading212Coordinator], BinarySensorEntity
):
    """Binary sensor for Trading 212."""

    entity_description: Trading212BinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Trading212Coordinator,
        entry: ConfigEntry,
        description: Trading212BinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
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

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return False
        return self.entity_description.is_on_fn(self.coordinator.data)
