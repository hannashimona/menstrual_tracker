"""Config flow for menstrual tracker."""

from __future__ import annotations

from datetime import date

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_CYCLE_LENGTH,
    CONF_LAST_PERIOD,
    CONF_PERIOD_LENGTH,
    CONF_SHOW_FERTILITY_ON_CAL,
    DEFAULT_CYCLE_LENGTH,
    DEFAULT_PERIOD_LENGTH,
    DOMAIN,
)


class MenstrualTrackerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                date.fromisoformat(user_input[CONF_LAST_PERIOD])
            except ValueError:
                errors[CONF_LAST_PERIOD] = "invalid_date"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Menstrual Tracker", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LAST_PERIOD): selector.DateSelector(),
                    vol.Optional(
                        CONF_CYCLE_LENGTH, default=DEFAULT_CYCLE_LENGTH
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=1)),
                    vol.Required(
                        CONF_PERIOD_LENGTH, default=DEFAULT_PERIOD_LENGTH
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=1)),
                }
            ),
            errors=errors,
        )

    async def async_step_import(
        self, config: dict
    ) -> config_entries.ConfigFlowResult:
        """Handle import from YAML."""
        return await self.async_step_user(config)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)

        current = self.config_entry.options
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SHOW_FERTILITY_ON_CAL,
                        default=bool(current.get(CONF_SHOW_FERTILITY_ON_CAL, False)),
                    ): selector.BooleanSelector(),
                }
            ),
        )


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> config_entries.OptionsFlow:
    return OptionsFlowHandler(config_entry)
