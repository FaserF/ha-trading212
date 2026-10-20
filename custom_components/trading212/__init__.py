"""Trading 212 custom integration."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api.client import Trading212Client
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_ENVIRONMENT,
    CONF_POLL_INTERVAL,
    DATA_CLIENT,
    DATA_COORDINATOR,
    DEFAULT_POLL_INTERVAL,
    DEMO_BASE_URL,
    DOMAIN,
    ENVIRONMENT_LIVE,
    LIVE_BASE_URL,
)
from .coordinator import Trading212Coordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry upon options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trading 212 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data.get(CONF_API_SECRET)
    environment = entry.options.get(
        CONF_ENVIRONMENT, entry.data.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE)
    )
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    base_url = LIVE_BASE_URL if environment == ENVIRONMENT_LIVE else DEMO_BASE_URL

    connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
    session = aiohttp.ClientSession(connector=connector)

    client = Trading212Client(session, api_key, base_url, api_secret=api_secret)

    # Determine or verify permissions
    permissions = entry.data.get("permissions")
    if not permissions:
        try:
            permissions = await client.test_permissions()
        except Exception as err:
            _LOGGER.debug("Could not determine permissions: %s", err)
            permissions = {
                "account": True,
                "portfolio": True,
                "metadata": True,
                "pies": True,
                "orders": True,
                "history": True,
            }

    coordinator = Trading212Coordinator(hass, client, poll_interval, entry, permissions)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await session.close()
        raise

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_CLIENT: client,
        "session": session,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    # Register services on first entry
    if (
        len(
            [
                k
                for k in hass.data[DOMAIN]
                if not k.endswith("_session") and isinstance(hass.data[DOMAIN][k], dict)
            ]
        )
        == 1
    ):
        await async_setup_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        session: aiohttp.ClientSession | None = entry_data.get("session")
        if session:
            await session.close()

        # Unregister services if no entries remain
        valid_entries = [
            k
            for k in hass.data[DOMAIN]
            if isinstance(hass.data[DOMAIN][k], dict)
            and DATA_CLIENT in hass.data[DOMAIN][k]
        ]
        if not valid_entries:
            await async_unload_services(hass)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry versions (e.g. from Smart-Home-Assistant-UK v1 to v2)."""
    _LOGGER.info(
        "Migrating Trading 212 entry %s from version %s to 2",
        config_entry.entry_id,
        config_entry.version,
    )

    if config_entry.version == 1:
        new_data = dict(config_entry.data)
        # In old version, permissions might not be stored
        if "permissions" not in new_data:
            # Grant default permissions that will be tested on setup
            new_data["permissions"] = {
                "account": True,
                "portfolio": True,
                "metadata": True,
                "pies": True,
                "orders": True,
                "history": True,
            }
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.info(
            "Migration of Trading 212 entry %s to version 2 successful",
            config_entry.entry_id,
        )

    return True
