"""Binary sensors for menstrual tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import MenstrualTrackerEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import MenstrualTrackerUpdateCoordinator
    from .data import MenstrualTrackerConfigEntry

ENTITY_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="currently_menstruating",
        name="Currently Menstruating",
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: MenstrualTrackerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    async_add_entities(
        MenstrualTrackerBinarySensor(entry.runtime_data.coordinator, description)
        for description in ENTITY_DESCRIPTIONS
    )


class MenstrualTrackerBinarySensor(MenstrualTrackerEntity, BinarySensorEntity):
    """Representation of a menstrual tracker binary sensor."""

    def __init__(
        self,
        coordinator: MenstrualTrackerUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if currently menstruating."""
        return bool(self.coordinator.data.get("currently_menstruating"))
