"""Data coordinator for menstrual tracker."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class MenstrualTrackerUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to compute menstrual cycle data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        last_period: date,
        cycle_length: int,
        period_length: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="menstrual_tracker",
            update_interval=timedelta(days=1),
        )
        self.config_entry = config_entry
        self._last_period = last_period
        self._cycle_length = cycle_length
        self._period_length = period_length

    @property
    def last_period(self) -> date:
        """Return last period start date for current cycle."""
        return self.data["last_period_start"] if self.data else self._last_period

    async def _async_update_data(self) -> dict:
        today = dt_util.now().date()
        # Adjust last period to most recent cycle start
        days_since = (today - self._last_period).days
        cycles_since = days_since // self._cycle_length
        current_period_start = self._last_period + timedelta(
            days=cycles_since * self._cycle_length
        )
        day_of_cycle = (today - current_period_start).days + 1

        ovulation_day = self._cycle_length - 14
        fertility_start = current_period_start + timedelta(days=ovulation_day - 5)
        fertility_end = current_period_start + timedelta(days=ovulation_day + 1)
        next_period_start = current_period_start + timedelta(days=self._cycle_length)

        return {
            "last_period_start": current_period_start,
            "day_of_cycle": day_of_cycle,
            "currently_menstruating": day_of_cycle <= self._period_length,
            "fertility_window_start": fertility_start,
            "fertility_window_end": fertility_end,
            "next_period_start": next_period_start,
            "period_length": self._period_length,
        }
