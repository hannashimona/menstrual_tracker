"""Sensor platform for menstrual tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)

from .entity import MenstrualTrackerEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MenstrualTrackerUpdateCoordinator
    from .data import MenstrualTrackerConfigEntry

ENTITY_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="day_of_cycle",
        name="Day of Cycle",
        icon="mdi:calendar-today",
    ),
    SensorEntityDescription(
        key="fertility_window",
        name="Predicted Fertility Window",
        icon="mdi:calendar-heart",
    ),
    SensorEntityDescription(
        key="next_period_start",
        name="Next Period Start",
        device_class=SensorDeviceClass.DATE,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MenstrualTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    async_add_entities(
        MenstrualTrackerSensor(entry.runtime_data.coordinator, description)
        for description in ENTITY_DESCRIPTIONS
    )


class MenstrualTrackerSensor(MenstrualTrackerEntity, SensorEntity):
    """Representation of a menstrual tracker sensor."""

    def __init__(
        self,
        coordinator: MenstrualTrackerUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        data = self.coordinator.data
        key = self.entity_description.key
        if key == "day_of_cycle":
            return data.get("day_of_cycle")
        if key == "next_period_start":
            return data.get("next_period_start")
        if key == "fertility_window":
            start = data.get("fertility_window_start")
            end = data.get("fertility_window_end")
            return f"{start} - {end}"
        return None
