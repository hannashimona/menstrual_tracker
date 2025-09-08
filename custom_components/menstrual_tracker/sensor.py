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
    SensorEntityDescription(
        key="cycle_length",
        name="Average Cycle Length",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="period_length",
        name="Average Period Length",
        icon="mdi:calendar-range",
    ),
    SensorEntityDescription(
        key="cycle_length_p25",
        name="Cycle Length 25th Percentile",
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="cycle_length_p50",
        name="Cycle Length Median",
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="cycle_length_p75",
        name="Cycle Length 75th Percentile",
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="period_length_p25",
        name="Period Length 25th Percentile",
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="period_length_p50",
        name="Period Length Median",
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="period_length_p75",
        name="Period Length 75th Percentile",
        icon="mdi:chart-bell-curve",
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
            if not start or not end:
                return None
            return f"{start} - {end}"
        if key == "cycle_length":
            return data.get("cycle_length")
        if key == "period_length":
            return data.get("period_length")
        if key.startswith("cycle_length_p"):
            stats = data.get("cycle_length_stats") or {}
            return stats.get(key.replace("cycle_length_", ""))
        if key.startswith("period_length_p"):
            stats = data.get("period_length_stats") or {}
            return stats.get(key.replace("period_length_", ""))
        return None
