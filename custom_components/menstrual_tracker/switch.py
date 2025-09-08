"""Switch platform for menstrual tracker (Pregnancy Mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity

from .entity import MenstrualTrackerEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MenstrualTrackerUpdateCoordinator
    from .data import MenstrualTrackerConfigEntry


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MenstrualTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    async_add_entities([PregnancyModeSwitch(entry.runtime_data.coordinator)])


class PregnancyModeSwitch(MenstrualTrackerEntity, SwitchEntity):
    """A switch to enable/disable pregnancy mode (disables predictions)."""

    _attr_name = "Pregnancy Mode"

    def __init__(self, coordinator: MenstrualTrackerUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_pregnancy_mode"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.config_entry.options.get("pregnancy_mode", False))

    async def async_turn_on(self, **_kwargs) -> None:
        entry = self.coordinator.config_entry
        options = {**entry.options, "pregnancy_mode": True}
        self.hass.config_entries.async_update_entry(entry, options=options)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **_kwargs) -> None:
        entry = self.coordinator.config_entry
        options = {**entry.options, "pregnancy_mode": False}
        self.hass.config_entries.async_update_entry(entry, options=options)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

