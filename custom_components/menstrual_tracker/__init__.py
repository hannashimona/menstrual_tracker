"""Setup for menstrual tracker integration."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.loader import async_get_loaded_integration

from .const import (
    CONF_CYCLE_LENGTH,
    CONF_LAST_PERIOD,
    CONF_PERIOD_LENGTH,
)
from .coordinator import MenstrualTrackerUpdateCoordinator
from .data import MenstrualTrackerConfigEntry, MenstrualTrackerData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.CALENDAR]


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
        integration=await async_get_loaded_integration(hass, entry.domain),
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
