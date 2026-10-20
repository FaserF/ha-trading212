"""Config flow for Trading 212."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api.client import Trading212Client
from .api.exceptions import (
    APIConnectionError,
    InvalidAPIKeyError,
    RateLimitExceededError,
)
from .const import (
    ALL_PIE_SENSORS,
    ALL_POSITION_SENSORS,
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_ENVIRONMENT,
    CONF_LABEL,
    CONF_PIE_SENSORS,
    CONF_POLL_INTERVAL,
    CONF_POSITION_SENSORS,
    DEFAULT_PIE_SENSORS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_POSITION_SENSORS,
    DEMO_BASE_URL,
    DOMAIN,
    ENVIRONMENT_DEMO,
    ENVIRONMENT_LIVE,
    LIVE_BASE_URL,
    MIN_POLL_INTERVAL,
    SCOPE_ACCOUNT,
    SCOPE_HISTORY,
    SCOPE_METADATA,
    SCOPE_ORDERS,
    SCOPE_PIES,
    SCOPE_PORTFOLIO,
)
from .util import combined_config, get_enabled_sensor_list

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LABEL, default=""): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_API_SECRET, default=""): str,
        vol.Required(CONF_ENVIRONMENT, default=ENVIRONMENT_LIVE): vol.In(
            [ENVIRONMENT_LIVE, ENVIRONMENT_DEMO]
        ),
        vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
    }
)

_POSITION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=ALL_POSITION_SENSORS,
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="position_sensors",
    )
)

_PIE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=ALL_PIE_SENSORS,
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="pie_sensors",
    )
)

SENSORS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_POSITION_SENSORS, default=DEFAULT_POSITION_SENSORS
        ): _POSITION_SELECTOR,
        vol.Optional(CONF_PIE_SENSORS, default=DEFAULT_PIE_SENSORS): _PIE_SELECTOR,
    }
)


def _generate_permission_table(permissions: dict[str, bool]) -> str:
    """Generate Markdown permission verification overview table."""

    def to_icon(val: bool) -> str:
        return "✅" if val else "❌"

    header = "| Scope | Status | Provided Entities & Features |\n| --- | --- | --- |\n"
    rows: list[str] = [
        f"| Account | {to_icon(permissions.get(SCOPE_ACCOUNT, False))} | Total value, cash, invested, currency, account sensors |",
        f"| Portfolio | {to_icon(permissions.get(SCOPE_PORTFOLIO, False))} | Open positions, quantities, price, P&L sensors |",
        f"| Metadata | {to_icon(permissions.get(SCOPE_METADATA, False))} | Company names, instruments list, exchange schedules |",
        f"| Pies | {to_icon(permissions.get(SCOPE_PIES, False))} | Pie value, progress, pie cash, dividends in pie |",
        f"| Orders | {to_icon(permissions.get(SCOPE_ORDERS, False))} | Active orders sensor, cancel order button |",
        f"| History | {to_icon(permissions.get(SCOPE_HISTORY, False))} | Total dividends, transaction history, order history |",
    ]
    return header + "\n".join(rows)


def _options_schema(
    current_label: str,
    current_env: str,
    current_interval: int,
    current_position_sensors: list[str],
    current_pie_sensors: list[str],
) -> vol.Schema:
    """Create schema for options flow."""
    return vol.Schema(
        {
            vol.Optional(CONF_LABEL, default=current_label): str,
            vol.Required(CONF_ENVIRONMENT, default=current_env): vol.In(
                [ENVIRONMENT_LIVE, ENVIRONMENT_DEMO]
            ),
            vol.Required(CONF_POLL_INTERVAL, default=current_interval): int,
            vol.Optional("sensor_selection"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_POSITION_SENSORS,
                            default=current_position_sensors,
                        ): _POSITION_SELECTOR,
                        vol.Optional(
                            CONF_PIE_SENSORS,
                            default=current_pie_sensors,
                        ): _PIE_SELECTOR,
                    }
                ),
                {"collapsed": True},
            ),
        }
    )


class Trading212ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trading 212."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._user_input: dict[str, Any] = {}
        self._permissions: dict[str, bool] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                < MIN_POLL_INTERVAL
            ):
                errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
                return self.async_show_form(
                    step_id="user", data_schema=USER_SCHEMA, errors=errors
                )

            base_url = (
                LIVE_BASE_URL
                if user_input[CONF_ENVIRONMENT] == ENVIRONMENT_LIVE
                else DEMO_BASE_URL
            )
            session = async_get_clientsession(self.hass)
            client = Trading212Client(
                session,
                user_input[CONF_API_KEY],
                base_url,
                api_secret=user_input.get(CONF_API_SECRET),
            )
            try:
                summary = await client.get_account_summary()
            except InvalidAPIKeyError:
                errors[CONF_API_KEY] = "invalid_auth"
            except APIConnectionError:
                errors["base"] = "cannot_connect"
            except RateLimitExceededError:
                errors["base"] = "rate_limit"
            except Exception:
                errors["base"] = "unknown"
            else:
                account_id = str(summary.get("id", ""))
                unique_id = f"{account_id}_{user_input[CONF_ENVIRONMENT]}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Test permissions
                self._permissions = await client.test_permissions()
                self._user_input = {
                    **user_input,
                    "_account_id": account_id,
                    "permissions": self._permissions,
                }
                return await self.async_step_permissions()

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_permissions(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Present tested permissions overview page."""
        if user_input is not None:
            return await self.async_step_sensors()

        perm_table = _generate_permission_table(self._permissions)
        return self.async_show_form(
            step_id="permissions",
            data_schema=vol.Schema({}),
            description_placeholders={"permission_table": perm_table},
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure enabled sensor types."""
        if user_input is not None:
            data = {**self._user_input}
            data.pop("_account_id", None)
            data[CONF_POSITION_SENSORS] = user_input.get(
                CONF_POSITION_SENSORS, DEFAULT_POSITION_SENSORS
            )
            data[CONF_PIE_SENSORS] = user_input.get(
                CONF_PIE_SENSORS, DEFAULT_PIE_SENSORS
            )
            env = data[CONF_ENVIRONMENT].title()
            label = data.get(CONF_LABEL, "").strip()
            title = (
                f"Trading 212 – {label} ({env})" if label else f"Trading 212 ({env})"
            )
            return self.async_create_entry(title=title, data=data)

        return self.async_show_form(
            step_id="sensors",
            data_schema=SENSORS_SCHEMA,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create options flow."""
        return Trading212OptionsFlow()


class Trading212OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Trading 212."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (
                user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
                < MIN_POLL_INTERVAL
            ):
                errors[CONF_POLL_INTERVAL] = "invalid_poll_interval"
            else:
                sensor_section = user_input.pop("sensor_selection", None) or {}
                user_input[CONF_POSITION_SENSORS] = sensor_section.get(
                    CONF_POSITION_SENSORS,
                    get_enabled_sensor_list(
                        self.config_entry,
                        CONF_POSITION_SENSORS,
                        DEFAULT_POSITION_SENSORS,
                    ),
                )
                user_input[CONF_PIE_SENSORS] = sensor_section.get(
                    CONF_PIE_SENSORS,
                    get_enabled_sensor_list(
                        self.config_entry, CONF_PIE_SENSORS, DEFAULT_PIE_SENSORS
                    ),
                )
                return self.async_create_entry(title="", data=user_input)

        combined = combined_config(self.config_entry)
        current_position_sensors = (
            combined[CONF_POSITION_SENSORS]
            if CONF_POSITION_SENSORS in combined
            else ALL_POSITION_SENSORS
        )
        current_pie_sensors = (
            combined[CONF_PIE_SENSORS]
            if CONF_PIE_SENSORS in combined
            else ALL_PIE_SENSORS
        )
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(
                current_label=combined.get(CONF_LABEL, ""),
                current_env=combined.get(CONF_ENVIRONMENT, ENVIRONMENT_LIVE),
                current_interval=combined.get(
                    CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                ),
                current_position_sensors=current_position_sensors,
                current_pie_sensors=current_pie_sensors,
            ),
            errors=errors,
        )
