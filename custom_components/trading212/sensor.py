"""Sensor platform for Trading 212."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALL_PIE_SENSORS,
    ALL_POSITION_SENSORS,
    CONF_ENVIRONMENT,
    CONF_LABEL,
    CONF_PIE_SENSORS,
    CONF_POSITION_SENSORS,
    DATA_COORDINATOR,
    DOMAIN,
    ENVIRONMENT_LIVE,
    SCOPE_ACCOUNT,
    SCOPE_HISTORY,
    SCOPE_ORDERS,
    SCOPE_PIES,
    SCOPE_PORTFOLIO,
)
from .coordinator import CoordinatorData, Pie, Position, Trading212Coordinator
from .util import combined_config, get_enabled_sensor_list


def _label_slug(coordinator: Trading212Coordinator) -> str:
    label = combined_config(coordinator.config_entry).get(CONF_LABEL, "").strip()
    if not label:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def _entity_id(label_slug: str, *parts: str) -> str:
    prefix = f"trading212_{label_slug}" if label_slug else "trading212"
    return "_".join([prefix, *parts])


@dataclass(frozen=True, kw_only=True)
class Trading212SensorDescription(SensorEntityDescription):
    """Describes a Trading 212 account sensor."""

    value_fn: Callable[[CoordinatorData], Any] | None = None
    attrs_fn: Callable[[CoordinatorData], dict[str, Any]] | None = None
    unit_fn: Callable[[CoordinatorData], str] | None = None
    required_scope: str | None = None


ACCOUNT_SENSOR_DESCRIPTIONS: tuple[Trading212SensorDescription, ...] = (
    Trading212SensorDescription(
        key="total_value",
        name="Total Value",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.total_value,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="cash_available",
        name="Cash Available",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.cash_available,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="cash_in_pies",
        name="Cash in Pies",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.cash_in_pies,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="invested",
        name="Invested",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.invested,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="unrealized_pnl",
        name="Unrealized P&L",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: d.unrealized_pnl,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="realized_pnl",
        name="Realized P&L",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: d.realized_pnl,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="result_percent",
        name="Overall Return",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: round(d.result_percent, 2),
        required_scope=SCOPE_ACCOUNT,
    ),
    Trading212SensorDescription(
        key="open_positions_count",
        name="Open Positions",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.open_positions_count,
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="active_orders_count",
        name="Active Orders",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.active_orders_count,
        required_scope=SCOPE_ORDERS,
    ),
    Trading212SensorDescription(
        key="total_dividends",
        name="Total Dividends",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda d: d.total_dividends,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_HISTORY,
    ),
    Trading212SensorDescription(
        key="daily_gain_loss",
        name="Daily Gain/Loss",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: d.daily_gain_loss,
        unit_fn=lambda d: d.currency,
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="daily_gain_loss_percent",
        name="Daily Gain/Loss %",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: round(d.daily_gain_loss_percent, 2),
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="top_daily_mover",
        name="Top Daily Mover",
        value_fn=lambda d: d.top_daily_mover.name if d.top_daily_mover else None,
        attrs_fn=lambda d: (
            {
                "ticker": d.top_daily_mover.ticker,
                "change_value": d.top_daily_mover.change_value,
                "change_pct": d.top_daily_mover.change_pct,
            }
            if d.top_daily_mover
            else {}
        ),
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="bottom_daily_mover",
        name="Bottom Daily Mover",
        value_fn=lambda d: d.bottom_daily_mover.name if d.bottom_daily_mover else None,
        attrs_fn=lambda d: (
            {
                "ticker": d.bottom_daily_mover.ticker,
                "change_value": d.bottom_daily_mover.change_value,
                "change_pct": d.bottom_daily_mover.change_pct,
            }
            if d.bottom_daily_mover
            else {}
        ),
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="biggest_daily_gain",
        name="Biggest Daily Gain",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: (
            d.biggest_daily_gain.change_value if d.biggest_daily_gain else None
        ),
        unit_fn=lambda d: d.currency,
        attrs_fn=lambda d: (
            {
                "ticker": d.biggest_daily_gain.ticker,
                "name": d.biggest_daily_gain.name,
            }
            if d.biggest_daily_gain
            else {}
        ),
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="biggest_daily_loss",
        name="Biggest Daily Loss",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda d: (
            d.biggest_daily_loss.change_value if d.biggest_daily_loss else None
        ),
        unit_fn=lambda d: d.currency,
        attrs_fn=lambda d: (
            {
                "ticker": d.biggest_daily_loss.ticker,
                "name": d.biggest_daily_loss.name,
            }
            if d.biggest_daily_loss
            else {}
        ),
        required_scope=SCOPE_PORTFOLIO,
    ),
    Trading212SensorDescription(
        key="last_updated",
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.last_updated,
        required_scope=None,
    ),
)

_POSITION_ENTITY_SLUG: dict[str, str] = {
    "average_price": "avg_price",
}

POSITION_ATTRS: tuple[
    tuple[str, str, SensorDeviceClass | None, str | None, SensorStateClass | None], ...
] = (
    ("value", "Value", SensorDeviceClass.MONETARY, None, SensorStateClass.TOTAL),
    ("pnl", "P&L", SensorDeviceClass.MONETARY, None, None),
    ("pnl_percent", "P&L %", None, PERCENTAGE, SensorStateClass.MEASUREMENT),
    ("quantity", "Quantity", None, None, SensorStateClass.MEASUREMENT),
    (
        "average_price",
        "Avg Price",
        SensorDeviceClass.MONETARY,
        None,
        SensorStateClass.TOTAL,
    ),
    (
        "current_price",
        "Current Price",
        SensorDeviceClass.MONETARY,
        None,
        SensorStateClass.TOTAL,
    ),
    ("daily_gain_loss", "Daily Gain/Loss", SensorDeviceClass.MONETARY, None, None),
    (
        "daily_gain_loss_percent",
        "Daily Gain/Loss %",
        None,
        PERCENTAGE,
        SensorStateClass.MEASUREMENT,
    ),
)

PIE_ATTRS: tuple[
    tuple[str, str, SensorDeviceClass | None, str | None, SensorStateClass | None], ...
] = (
    ("value", "Value", SensorDeviceClass.MONETARY, None, SensorStateClass.TOTAL),
    ("invested", "Invested", SensorDeviceClass.MONETARY, None, SensorStateClass.TOTAL),
    ("pnl", "P&L", SensorDeviceClass.MONETARY, None, None),
    ("pnl_percent", "P&L %", None, PERCENTAGE, SensorStateClass.MEASUREMENT),
    ("cash", "Cash", SensorDeviceClass.MONETARY, None, SensorStateClass.TOTAL),
    ("progress", "Progress", None, PERCENTAGE, SensorStateClass.MEASUREMENT),
    ("goal", "Goal", SensorDeviceClass.MONETARY, None, SensorStateClass.TOTAL),
    (
        "dividends_gained",
        "Dividends Gained",
        SensorDeviceClass.MONETARY,
        None,
        SensorStateClass.TOTAL,
    ),
    (
        "dividends_in_cash",
        "Dividends Cash",
        SensorDeviceClass.MONETARY,
        None,
        SensorStateClass.TOTAL,
    ),
    (
        "dividends_reinvested",
        "Dividends Reinvested",
        SensorDeviceClass.MONETARY,
        None,
        SensorStateClass.TOTAL,
    ),
)


def _enabled_position_attrs(
    coordinator: Trading212Coordinator,
) -> tuple[
    tuple[str, str, SensorDeviceClass | None, str | None, SensorStateClass | None], ...
]:
    if not coordinator.permissions.get(SCOPE_PORTFOLIO, True):
        return ()
    enabled = set(
        get_enabled_sensor_list(
            coordinator.config_entry,
            CONF_POSITION_SENSORS,
            ALL_POSITION_SENSORS,
        )
    )
    return tuple(a for a in POSITION_ATTRS if a[0] in enabled)


def _enabled_pie_attrs(
    coordinator: Trading212Coordinator,
) -> tuple[
    tuple[str, str, SensorDeviceClass | None, str | None, SensorStateClass | None], ...
]:
    if not coordinator.permissions.get(SCOPE_PIES, True):
        return ()
    enabled = set(
        get_enabled_sensor_list(
            coordinator.config_entry, CONF_PIE_SENSORS, ALL_PIE_SENSORS
        )
    )
    return tuple(a for a in PIE_ATTRS if a[0] in enabled)


def _remove_disabled_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    enabled_unique_ids: set[str],
) -> None:
    registry = er.async_get(hass)
    stale = [
        entity.entity_id
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if entity.unique_id not in enabled_unique_ids and entity.platform == DOMAIN
    ]
    for entity_id in stale:
        registry.async_remove(entity_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trading 212 sensors."""
    coordinator: Trading212Coordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    account_entities: list[Trading212AccountSensor] = []
    for description in ACCOUNT_SENSOR_DESCRIPTIONS:
        if description.required_scope and not coordinator.permissions.get(
            description.required_scope, True
        ):
            continue
        account_entities.append(Trading212AccountSensor(coordinator, description))

    async_add_entities(account_entities)

    position_attrs = _enabled_position_attrs(coordinator)
    pie_attrs = _enabled_pie_attrs(coordinator)

    if coordinator.data is not None:
        enabled_unique_ids: set[str] = (
            {
                f"{entry.entry_id}_{desc.key}"
                for desc in ACCOUNT_SENSOR_DESCRIPTIONS
                if not desc.required_scope
                or coordinator.permissions.get(desc.required_scope, True)
            }
            | {
                f"{entry.entry_id}_{slug}_{attr_key}"
                for slug in coordinator.data.positions
                for attr_key, _suffix, _dc, _unit, _sc in position_attrs
            }
            | {
                f"{entry.entry_id}_{slug}_{attr_key}"
                for slug in coordinator.data.pies
                for attr_key, _suffix, _dc, _unit, _sc in pie_attrs
            }
        )
        _remove_disabled_entities(hass, entry, enabled_unique_ids)

    known_slugs: set[str] = set()

    @callback
    def _add_new_position_sensors() -> None:
        if coordinator.data is None:
            return
        new_slugs = set(coordinator.data.positions.keys()) - known_slugs
        if not new_slugs:
            return
        known_slugs.update(new_slugs)
        async_add_entities(
            Trading212PositionSensor(coordinator, slug, attr_key, suffix, dc, unit, sc)
            for slug in new_slugs
            for attr_key, suffix, dc, unit, sc in position_attrs
        )

    _add_new_position_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_position_sensors))

    known_pie_slugs: set[str] = set()

    @callback
    def _add_new_pie_sensors() -> None:
        if coordinator.data is None:
            return
        new_slugs = set(coordinator.data.pies.keys()) - known_pie_slugs
        if not new_slugs:
            return
        known_pie_slugs.update(new_slugs)
        async_add_entities(
            Trading212PieSensor(coordinator, slug, attr_key, suffix, dc, unit, sc)
            for slug in new_slugs
            for attr_key, suffix, dc, unit, sc in pie_attrs
        )

    _add_new_pie_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_pie_sensors))


class Trading212AccountSensor(CoordinatorEntity[Trading212Coordinator], SensorEntity):
    """Account level sensor for Trading 212."""

    def __init__(
        self,
        coordinator: Trading212Coordinator,
        description: Trading212SensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = _entity_id(
            _label_slug(coordinator), description.key
        )

        env = coordinator.config_entry.data.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE)
        config_url = (
            "https://live.trading212.com/"
            if env == ENVIRONMENT_LIVE
            else "https://demo.trading212.com/"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Trading 212",
            model=f"{env.title()} Trading Account",
            configuration_url=config_url,
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Return suggested object id."""
        return self._attr_suggested_object_id

    @property
    def native_value(self) -> Any:
        """Return sensor native value."""
        if self.coordinator.data is None or self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        if self.entity_description.unit_fn and self.coordinator.data:
            return self.entity_description.unit_fn(self.coordinator.data)
        return self.entity_description.native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attrs_fn and self.coordinator.data:
            return self.entity_description.attrs_fn(self.coordinator.data)
        return None


class Trading212PositionSensor(CoordinatorEntity[Trading212Coordinator], SensorEntity):
    """Sensor for an individual stock/equity position."""

    def __init__(
        self,
        coordinator: Trading212Coordinator,
        slug: str,
        attr_key: str,
        suffix: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        state_class: SensorStateClass | None,
    ) -> None:
        """Initialize position sensor."""
        super().__init__(coordinator)
        self._slug = slug
        self._attr_key = attr_key
        self._unit_override = unit
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{slug}_{attr_key}"

        pos = coordinator.data.positions.get(slug) if coordinator.data else None
        pos_name = pos.instrument_name if pos else slug
        self._attr_name = f"{pos_name} {suffix}"

        entity_slug = _POSITION_ENTITY_SLUG.get(attr_key, attr_key)
        self._attr_suggested_object_id = _entity_id(
            _label_slug(coordinator), slug, entity_slug
        )

        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class

        env = coordinator.config_entry.data.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE)
        config_url = (
            "https://live.trading212.com/"
            if env == ENVIRONMENT_LIVE
            else "https://demo.trading212.com/"
        )

        # Attach position sensors to their dedicated equity sub-device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{slug}")},
            name=f"{pos_name} ({pos.ticker if pos else slug})",
            manufacturer="Trading 212",
            model="Equity Position",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
            configuration_url=config_url,
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Return suggested object id."""
        return self._attr_suggested_object_id

    @property
    def _position(self) -> Position | None:
        """Return position object from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.positions.get(self._slug)

    @property
    def available(self) -> bool:
        """Available only when position exists in active data."""
        return super().available and self._position is not None

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        pos = self._position
        if pos is None:
            return None
        val = getattr(pos, self._attr_key, None)
        if isinstance(val, float):
            return round(val, 4)
        return val

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        if self._unit_override:
            return self._unit_override
        if self.device_class == SensorDeviceClass.MONETARY and self.coordinator.data:
            return self.coordinator.data.currency
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        pos = self._position
        if pos is None:
            return None
        return {
            "ticker": pos.ticker,
            "instrument_name": pos.instrument_name,
            "quantity": pos.quantity,
            "average_price": pos.average_price,
            "current_price": pos.current_price,
        }


class Trading212PieSensor(CoordinatorEntity[Trading212Coordinator], SensorEntity):
    """Sensor for an investment Pie."""

    def __init__(
        self,
        coordinator: Trading212Coordinator,
        slug: str,
        attr_key: str,
        suffix: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        state_class: SensorStateClass | None,
    ) -> None:
        """Initialize pie sensor."""
        super().__init__(coordinator)
        self._slug = slug
        self._attr_key = attr_key
        self._unit_override = unit
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{slug}_{attr_key}"

        pie = coordinator.data.pies.get(slug) if coordinator.data else None
        pie_name = pie.name if pie else slug
        self._attr_name = f"{pie_name} {suffix}"
        self._attr_suggested_object_id = _entity_id(
            _label_slug(coordinator), slug, attr_key
        )

        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class

        env = coordinator.config_entry.data.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE)
        config_url = (
            "https://live.trading212.com/"
            if env == ENVIRONMENT_LIVE
            else "https://demo.trading212.com/"
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{slug}")},
            name=f"Pie: {pie_name}",
            manufacturer="Trading 212",
            model="Investment Pie",
            via_device=(DOMAIN, coordinator.config_entry.entry_id),
            configuration_url=config_url,
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Return suggested object id."""
        return self._attr_suggested_object_id

    @property
    def _pie(self) -> Pie | None:
        """Return pie object from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.pies.get(self._slug)

    @property
    def available(self) -> bool:
        """Available only when pie exists in active data."""
        return super().available and self._pie is not None

    @property
    def native_value(self) -> Any:
        """Return native value."""
        pie = self._pie
        if pie is None:
            return None
        val = getattr(pie, self._attr_key, None)
        if isinstance(val, float):
            return round(val, 2)
        return val

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement."""
        if self._unit_override:
            return self._unit_override
        if self.device_class == SensorDeviceClass.MONETARY and self.coordinator.data:
            return self.coordinator.data.currency
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        pie = self._pie
        if pie is None:
            return None
        return {
            "pie_id": pie.pie_id,
            "name": pie.name,
            "tickers": pie.tickers,
        }
