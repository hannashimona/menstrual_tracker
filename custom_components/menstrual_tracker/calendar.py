"""Calendar platform for menstrual tracker."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

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
    """Set up calendar entity."""
    async_add_entities([MenstrualTrackerCalendar(entry.runtime_data.coordinator)])


def _as_dt(value: date) -> datetime:
    return dt_util.start_of_local_day(value)


class MenstrualTrackerCalendar(MenstrualTrackerEntity, CalendarEntity):
    """Calendar representing menstrual cycle events."""

    def __init__(self, coordinator: MenstrualTrackerUpdateCoordinator) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_name = "Menstrual Cycle"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        data = self.coordinator.data
        today = dt_util.now().date()
        events: list[CalendarEvent] = []
        period_start: date = data["next_period_start"]
        events.append(
            CalendarEvent(
                summary="Predicted Period",
                start=_as_dt(period_start),
                end=_as_dt(period_start + timedelta(days=data["period_length"])),
            )
        )
        fert_start: date = data["fertility_window_start"]
        events.append(
            CalendarEvent(
                summary="Fertility Window",
                start=_as_dt(fert_start),
                end=_as_dt(data["fertility_window_end"]),
            )
        )
        upcoming = [e for e in events if e.start.date() >= today]
        return min(upcoming, key=lambda e: e.start) if upcoming else None

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a date range."""
        data = self.coordinator.data
        events: list[CalendarEvent] = []
        period_start = data["next_period_start"]
        period_end = period_start + timedelta(days=data["period_length"])
        if period_start <= end_date.date() and period_end >= start_date.date():
            events.append(
                CalendarEvent(
                    summary="Predicted Period",
                    start=_as_dt(period_start),
                    end=_as_dt(period_end),
                )
            )
        fert_start = data["fertility_window_start"]
        fert_end = data["fertility_window_end"]
        if fert_start <= end_date.date() and fert_end >= start_date.date():
            events.append(
                CalendarEvent(
                    summary="Fertility Window",
                    start=_as_dt(fert_start),
                    end=_as_dt(fert_end),
                )
            )
        return events
