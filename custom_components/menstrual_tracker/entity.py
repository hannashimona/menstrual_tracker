"""Base entity for menstrual tracker."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import MenstrualTrackerUpdateCoordinator


class MenstrualTrackerEntity(CoordinatorEntity[MenstrualTrackerUpdateCoordinator]):
    """Base entity class for this integration."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: MenstrualTrackerUpdateCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,
                    coordinator.config_entry.entry_id,
                )
            }
        )
