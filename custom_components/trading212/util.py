"""Utility helpers for Trading 212."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


def combined_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return merged options over data dictionary."""
    return {**entry.data, **entry.options}


def get_enabled_sensor_list(
    entry: ConfigEntry, key: str, default: list[str]
) -> list[str]:
    """Return enabled sensor list from options or data."""
    combined = combined_config(entry)
    val = combined.get(key)
    if isinstance(val, list):
        return val
    return default
