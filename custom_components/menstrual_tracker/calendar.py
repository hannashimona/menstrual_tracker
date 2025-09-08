"""Calendar platform for menstrual tracker."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.util import dt as dt_util

from .entity import MenstrualTrackerEntity
from .const import CONF_SHOW_FERTILITY_ON_CAL

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


def _as_date(value: date) -> date:
    return value


class MenstrualTrackerCalendar(MenstrualTrackerEntity, CalendarEntity):
    """Calendar representing menstrual cycle events."""

    def __init__(self, coordinator: MenstrualTrackerUpdateCoordinator) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_name = "Menstrual Cycle"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_calendar"
        self._attr_supported_features = CalendarEntityFeature.CREATE_EVENT

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        data = self.coordinator.data
        show_fertility = bool(self.coordinator.config_entry.options.get(CONF_SHOW_FERTILITY_ON_CAL, False))
        today = dt_util.now().date()
        events: list[CalendarEvent] = []

        # Recorded menstruation periods (from storage)
        storage = self.coordinator._storage  # type: ignore[attr-defined]
        for p in storage.periods:
            # p.end is inclusive; convert to exclusive boundary by adding 1 day
            end_date = (
                (p.end + timedelta(days=1)) if p.end else (p.start + timedelta(days=data["period_length"]))
            )
            events.append(
                CalendarEvent(
                    summary="Menstruation",
                    start=_as_date(p.start),
                    end=_as_date(end_date),  # exclusive end -> all-day block
                )
            )

        # Explicit daily logs recorded via the service
        for e in storage.events:
            # Build a concise annotation for the day
            if e.menstruating:
                summary = f"Period: {e.flow}"
            else:
                summary = f"Daily Log: Not menstruating (flow: {e.flow})"
            if e.symptoms:
                summary += f", symptoms: {', '.join(e.symptoms)}"
            events.append(
                CalendarEvent(
                    summary=summary,
                    start=_as_date(e.day),
                    end=_as_date(e.day + timedelta(days=1)),
                )
            )

        # Detected menstruation periods from events
        menstruating_days = sorted({e.day for e in storage.events if e.menstruating})
        if menstruating_days:
            start = menstruating_days[0]
            prev = start
            for d in menstruating_days[1:]:
                if (d - prev).days == 1:
                    prev = d
                    continue
                events.append(
                    CalendarEvent(
                        summary="Detected Menstruation",
                        start=_as_date(start),
                        end=_as_date(prev + timedelta(days=1)),
                    )
                )
                start = d
                prev = d
            events.append(
                CalendarEvent(
                    summary="Detected Menstruation",
                    start=_as_date(start),
                    end=_as_date(prev + timedelta(days=1)),
                )
            )

        # Predicted next period(s) and fertility window(s) (skip during pregnancy mode)
        if not data.get("pregnancy_mode"):
            centers = data.get("predicted_period_centers") or []
            if centers:
                for c in centers:
                    events.append(
                        CalendarEvent(
                            summary="Predicted Period",
                            start=_as_date(c),
                            end=_as_date(c + timedelta(days=data["period_length"])),
                        )
                    )
            else:
                period_start = data.get("next_period_start")
                if period_start:
                    events.append(
                        CalendarEvent(
                            summary="Predicted Period",
                            start=_as_date(period_start),
                            end=_as_date(period_start + timedelta(days=data["period_length"])),
                        )
                    )

            if show_fertility:
                fert_windows = data.get("predicted_fertility_windows") or []
                if fert_windows:
                    for (fs, fe) in fert_windows:
                        events.append(
                            CalendarEvent(
                                summary="Fertility Window",
                                start=_as_date(fs),
                                end=_as_date(fe + timedelta(days=1)),
                            )
                        )
                else:
                    fert_start = data.get("fertility_window_start")
                    fert_end = data.get("fertility_window_end")
                    if fert_start and fert_end:
                        # Treat fert_end as inclusive day; add 1 day to make exclusive boundary
                        events.append(
                            CalendarEvent(
                                summary="Fertility Window",
                                start=_as_date(fert_start),
                                end=_as_date(fert_end + timedelta(days=1)),
                            )
                        )

        def _end_as_date(ev_end: date | datetime) -> date:
            return ev_end if isinstance(ev_end, date) and not isinstance(ev_end, datetime) else ev_end.date()  # type: ignore[return-value]

        upcoming = [e for e in events if _end_as_date(e.end) >= today]
        return min(upcoming, key=lambda e: e.start) if upcoming else None

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a date range."""
        data = self.coordinator.data
        show_fertility = bool(self.coordinator.config_entry.options.get(CONF_SHOW_FERTILITY_ON_CAL, False))
        events: list[CalendarEvent] = []

        # Recorded menstruation periods
        storage = self.coordinator._storage  # type: ignore[attr-defined]
        for p in storage.periods:
            start = p.start
            # Compute inclusive end date for comparisons and convert to exclusive for event
            end_inclusive = p.end or (start + timedelta(days=data["period_length"] - 1))
            if start <= end_date.date() and end_inclusive >= start_date.date():
                events.append(
                    CalendarEvent(
                        summary="Menstruation",
                        start=_as_date(start),
                        end=_as_date(end_inclusive + timedelta(days=1)),
                    )
                )

        # Explicit daily logs recorded via the service
        for e in storage.events:
            if start_date.date() <= e.day <= end_date.date():
                if e.menstruating:
                    summary = f"Period: {e.flow}"
                else:
                    summary = f"Daily Log: Not menstruating (flow: {e.flow})"
                if e.symptoms:
                    summary += f", symptoms: {', '.join(e.symptoms)}"
                events.append(
                    CalendarEvent(
                        summary=summary,
                        start=_as_date(e.day),
                        end=_as_date(e.day + timedelta(days=1)),
                    )
                )

        if not data.get("pregnancy_mode"):
            # Predicted periods: multiple if available
            centers = data.get("predicted_period_centers") or []
            if centers:
                for c in centers:
                    period_end = c + timedelta(days=data["period_length"])  # exclusive
                    if c <= end_date.date() and (period_end - timedelta(days=1)) >= start_date.date():
                        events.append(
                            CalendarEvent(
                                summary="Predicted Period",
                                start=_as_date(c),
                                end=_as_date(period_end),
                            )
                        )
            else:
                period_start = data.get("next_period_start")
                if period_start:
                    period_end = period_start + timedelta(days=data["period_length"])  # exclusive
                    if period_start <= end_date.date() and (period_end - timedelta(days=1)) >= start_date.date():
                        events.append(
                            CalendarEvent(
                                summary="Predicted Period",
                                start=_as_date(period_start),
                                end=_as_date(period_end),
                            )
                        )

            if show_fertility:
                # Fertility windows: multiple if available
                fert_windows = data.get("predicted_fertility_windows") or []
                if fert_windows:
                    for (fs, fe) in fert_windows:
                        if fs <= end_date.date() and fe >= start_date.date():
                            events.append(
                                CalendarEvent(
                                    summary="Fertility Window",
                                    start=_as_date(fs),
                                    end=_as_date(fe + timedelta(days=1)),
                                )
                            )
                else:
                    fert_start = data.get("fertility_window_start")
                    fert_end = data.get("fertility_window_end")
                    if fert_start and fert_end:
                        # fert_end is inclusive; add 1 day for exclusive event end
                        if fert_start <= end_date.date() and fert_end >= start_date.date():
                            events.append(
                                CalendarEvent(
                                    summary="Fertility Window",
                                    start=_as_date(fert_start),
                                    end=_as_date(fert_end + timedelta(days=1)),
                                )
                            )
        return events

    async def async_create_event(self, event: dict) -> None:
        """Create a new event through the calendar UI/service.

        Accepts events whose summary is "Menstruation" or "Period" and
        stores them as recorded periods in history.
        """
        summary = str(event.get("summary", "")).strip().lower()
        if summary not in {"menstruation", "period"}:
            # Ignore unrelated events to keep calendar focused
            return

        def _to_date(val) -> date:
            if isinstance(val, date):
                return val
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, str):
                return date.fromisoformat(val)
            if isinstance(val, dict):
                if "date" in val:
                    return date.fromisoformat(val["date"])  # all-day
                if "datetime" in val:
                    return dt_util.parse_datetime(val["datetime"]).date()
            raise ValueError("Unsupported date format for calendar event")

        start_raw = event.get("start")
        end_raw = event.get("end")
        if not start_raw:
            raise ValueError("Calendar event requires a start date")
        start_day = _to_date(start_raw)
        end_day = _to_date(end_raw) if end_raw else None
        if end_day is not None and end_day < start_day:
            raise ValueError("Calendar event end must be on/after start")

        # Persist to storage, update config entry anchor, refresh
        storage = self.coordinator._storage  # type: ignore[attr-defined]
        await storage.async_add_or_update(start_day, end=end_day)

        entry = self.coordinator.config_entry
        hass = self.coordinator.hass
        new_data = {**entry.data, "last_period_start": start_day.isoformat()}
        hass.config_entries.async_update_entry(entry, data=new_data)
        self.coordinator._last_period = start_day
        await self.coordinator.async_request_refresh()
