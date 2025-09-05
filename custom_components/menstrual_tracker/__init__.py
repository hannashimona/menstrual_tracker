"""Setup for menstrual tracker integration."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_loaded_integration

from .const import (
    CONF_CYCLE_LENGTH,
    CONF_LAST_PERIOD,
    CONF_PERIOD_LENGTH,
    DEFAULT_CYCLE_LENGTH,
    DEFAULT_PERIOD_LENGTH,
    DOMAIN,
)
from .coordinator import MenstrualTrackerUpdateCoordinator
from .data import MenstrualTrackerConfigEntry, MenstrualTrackerData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_LAST_PERIOD): cv.date,
                vol.Required(
                    CONF_CYCLE_LENGTH, default=DEFAULT_CYCLE_LENGTH
                ): cv.positive_int,
                vol.Required(
                    CONF_PERIOD_LENGTH, default=DEFAULT_PERIOD_LENGTH
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up integration from YAML configuration."""
    if DOMAIN not in config:
        return True
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_LAST_PERIOD: config[DOMAIN][CONF_LAST_PERIOD].isoformat(),
                CONF_CYCLE_LENGTH: config[DOMAIN][CONF_CYCLE_LENGTH],
                CONF_PERIOD_LENGTH: config[DOMAIN][CONF_PERIOD_LENGTH],
            },
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MenstrualTrackerConfigEntry
) -> bool:
    """Set up menstrual tracker from a config entry."""
    coordinator = MenstrualTrackerUpdateCoordinator(
        hass,
        config_entry=entry,
        last_period=date.fromisoformat(entry.data[CONF_LAST_PERIOD]),
        cycle_length=entry.data[CONF_CYCLE_LENGTH],
        period_length=entry.data[CONF_PERIOD_LENGTH],
    )
    entry.runtime_data = MenstrualTrackerData(
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MenstrualTrackerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: MenstrualTrackerConfigEntry
) -> None:
    """Reload when config entry options change."""
    await hass.config_entries.async_reload(entry.entry_id)
