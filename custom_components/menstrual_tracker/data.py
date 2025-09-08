"""Custom types for menstrual_tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

    from .coordinator import MenstrualTrackerUpdateCoordinator
    from .storage import MenstrualTrackerStorage

    class MenstrualTrackerConfigEntry(ConfigEntry["MenstrualTrackerData"]):
        """Config entry type for this integration."""
else:
    MenstrualTrackerConfigEntry = ConfigEntry


@dataclass
class MenstrualTrackerData:
    """Runtime data for the integration."""

    coordinator: MenstrualTrackerUpdateCoordinator
    integration: Integration
    storage: "MenstrualTrackerStorage"
