"""Custom types for menstrual_tracker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from homeassistant.loader import Integration

    from .coordinator import MenstrualTrackerUpdateCoordinator


class MenstrualTrackerConfigEntry(ConfigEntry["MenstrualTrackerData"]):
    """Config entry type for this integration."""


@dataclass
class MenstrualTrackerData:
    """Runtime data for the integration."""

    coordinator: MenstrualTrackerUpdateCoordinator
    integration: Integration
