"""Setup for menstrual tracker integration."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.loader import async_get_loaded_integration
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CYCLE_LENGTH,
    CONF_LAST_PERIOD,
    CONF_PERIOD_LENGTH,
    CONF_SHOW_FERTILITY_ON_CAL,
    DEFAULT_CYCLE_LENGTH,
    DEFAULT_PERIOD_LENGTH,
    DOMAIN,
    LOGGER,
)
from .coordinator import MenstrualTrackerUpdateCoordinator
from .services import async_register_services
from .data import MenstrualTrackerConfigEntry, MenstrualTrackerData
from .storage import MenstrualTrackerStorage

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.SWITCH,
]


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
                vol.Optional(CONF_SHOW_FERTILITY_ON_CAL, default=False): cv.boolean,
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
                CONF_SHOW_FERTILITY_ON_CAL: config[DOMAIN].get(CONF_SHOW_FERTILITY_ON_CAL, False),
            },
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: MenstrualTrackerConfigEntry
) -> bool:
    """Set up menstrual tracker from a config entry."""
    # Ensure domain services are registered once
    async_register_services(hass)
    last_period_str = entry.data.get(CONF_LAST_PERIOD, entry.data.get("last_period"))
    if not last_period_str:
        # Be resilient: default to today and persist, to avoid setup failure
        today_str = dt_util.now().date().isoformat()
        LOGGER.warning(
            "Missing %s in config entry data; defaulting to today (%s)",
            CONF_LAST_PERIOD,
            today_str,
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_LAST_PERIOD: today_str}
        )
        last_period_str = today_str

    storage = MenstrualTrackerStorage(hass, entry.entry_id)
    await storage.async_load()

    # Seed an initial recorded period based on config values so it appears on the calendar
    try:
        lp = date.fromisoformat(last_period_str)
        period_len = entry.data.get(CONF_PERIOD_LENGTH, DEFAULT_PERIOD_LENGTH)
        # Only add if not already present in history
        if not any(p.start == lp for p in storage.periods):
            end = lp + timedelta(days=max(0, period_len - 1))
            await storage.async_add_or_update(start=lp, end=end)
    except Exception:  # pragma: no cover - be resilient during setup
        LOGGER.debug("Skipping seeding initial period entry due to parsing error", exc_info=True)

    coordinator = MenstrualTrackerUpdateCoordinator(
        hass,
        config_entry=entry,
        last_period=date.fromisoformat(last_period_str),
        cycle_length=entry.data.get(CONF_CYCLE_LENGTH, DEFAULT_CYCLE_LENGTH),
        period_length=entry.data.get(CONF_PERIOD_LENGTH, DEFAULT_PERIOD_LENGTH),
        storage=storage,
    )
    entry.runtime_data = MenstrualTrackerData(
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
        storage=storage,
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # Ensure option for showing fertility on calendar exists; default to YAML value or False
    if CONF_SHOW_FERTILITY_ON_CAL not in entry.options:
        show_flag = bool(entry.data.get(CONF_SHOW_FERTILITY_ON_CAL, False))
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_SHOW_FERTILITY_ON_CAL: show_flag}
        )
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


async def async_migrate_entry(
    hass: HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Migrate old entry data to new format."""
    if entry.version > 1:
        return True

    LOGGER.debug("Migrating config entry from version %s", entry.version)
    data = {**entry.data}
    if "last_period" in data and CONF_LAST_PERIOD not in data:
        data[CONF_LAST_PERIOD] = data.pop("last_period")
    hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True
