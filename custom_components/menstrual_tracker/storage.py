"""Persistent storage for menstrual_tracker history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, LOGGER


@dataclass
class PeriodEntry:
    """A recorded menstruation period."""

    start: date
    end: date | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
        }

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "PeriodEntry":
        s = date.fromisoformat(obj["start"])  # raises if invalid
        e = date.fromisoformat(obj["end"]) if obj.get("end") else None
        return PeriodEntry(start=s, end=e)


class MenstrualTrackerStorage:
    """Manage persistent history for the integration."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, version=1, key=f"{DOMAIN}.{entry_id}.history")
        self._periods: list[PeriodEntry] = []
        self._events: list[EventEntry] = []

    @property
    def periods(self) -> list[PeriodEntry]:
        return list(self._periods)

    @property
    def events(self) -> list["EventEntry"]:
        return list(self._events)

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if not data:
            self._periods = []
            return
        try:
            raw = data.get("periods", [])
            self._periods = [PeriodEntry.from_dict(p) for p in raw]
            raw_events = data.get("events", [])
            self._events = [EventEntry.from_dict(e) for e in raw_events]
        except Exception:  # pragma: no cover - robustness
            LOGGER.exception("Failed to load stored menstrual history; resetting")
            self._periods = []
            self._events = []

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "periods": [p.to_dict() for p in self._periods],
                "events": [e.to_dict() for e in self._events],
            }
        )

    async def async_import_history(
        self,
        *,
        periods: list[PeriodEntry] | None = None,
        events: list["EventEntry"] | None = None,
        mode: str = "merge",
    ) -> None:
        """Import periods and events in bulk.

        - mode="replace": overwrite existing history with provided data
        - mode="merge" (default): upsert periods by start date and merge events
          avoiding duplicates by (day, menstruating, flow, symptoms)
        """
        periods = periods or []
        events = events or []

        if mode == "replace":
            self._periods = sorted(list(periods), key=lambda p: p.start)
            self._events = sorted(list(events), key=lambda e: (e.day, e.created_at))
            await self._async_save()
            return

        # Merge periods by start date
        by_start: dict[date, PeriodEntry] = {p.start: p for p in self._periods}
        for p in periods:
            if p.start in by_start:
                if p.end is not None:
                    by_start[p.start].end = p.end
            else:
                by_start[p.start] = PeriodEntry(start=p.start, end=p.end)
        self._periods = sorted(by_start.values(), key=lambda p: p.start)

        # Merge events deduping by (day, menstruating, flow, tuple(symptoms))
        def _ekey(e: "EventEntry") -> tuple:
            return (e.day, e.menstruating, e.flow, tuple(e.symptoms))

        existing: dict[tuple, EventEntry] = {_ekey(e): e for e in self._events}
        for e in events:
            key = _ekey(e)
            if key in existing:
                # keep earliest created_at
                if e.created_at < existing[key].created_at:
                    existing[key].created_at = e.created_at
            else:
                existing[key] = e
        self._events = sorted(existing.values(), key=lambda e: (e.day, e.created_at))
        await self._async_save()

    async def async_add_or_update(self, start: date, end: date | None = None) -> None:
        """Add a new period or update an existing start's end date.

        - If a period with the same start exists, update its end (if provided).
        - Otherwise append and keep list sorted by start ascending.
        """
        # Update existing
        for p in self._periods:
            if p.start == start:
                if end is not None:
                    p.end = end
                await self._async_save()
                return

        # Append new
        self._periods.append(PeriodEntry(start=start, end=end))
        self._periods.sort(key=lambda p: p.start)
        await self._async_save()

    async def async_add_event(
        self,
        *,
        day: date,
        menstruating: bool,
        flow: str,
        symptoms: list[str] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Append a structured daily event entry.

        Multiple events per day are allowed and kept in chronological order by created_at.
        """
        event = EventEntry(
            day=day,
            menstruating=menstruating,
            flow=flow,
            symptoms=symptoms or [],
            created_at=created_at or datetime.utcnow(),
        )
        self._events.append(event)
        # Keep stable order by date then created_at
        self._events.sort(key=lambda e: (e.day, e.created_at))
        await self._async_save()

    async def async_delete_events(
        self,
        *,
        day: date,
        menstruating: bool | None = None,
        flow: str | None = None,
        symptoms: list[str] | None = None,
        mode: str = "last",
    ) -> int:
        """Delete stored events for a given day.

        - mode="any": delete all events on that day
        - mode="last": delete the most recent event on that day
        - mode="exact": delete events matching provided menstruating/flow/symptoms
        Returns number of deleted events.
        """
        candidates = [e for e in self._events if e.day == day]
        if not candidates:
            return 0

        to_keep: list[EventEntry]
        deleted = 0

        if mode == "any":
            to_keep = [e for e in self._events if e.day != day]
            deleted = len(candidates)
        elif mode == "last":
            latest = max(candidates, key=lambda e: e.created_at)
            to_keep = [e for e in self._events if e is not latest]
            deleted = 1
        elif mode == "exact":
            sym_set = set((symptoms or []))
            def match(e: EventEntry) -> bool:
                if menstruating is not None and e.menstruating != menstruating:
                    return False
                if flow is not None and e.flow != flow:
                    return False
                if symptoms is not None and set(e.symptoms) != sym_set:
                    return False
                return True
            to_keep = [e for e in self._events if not (e.day == day and match(e))]
            deleted = len(self._events) - len(to_keep)
        else:
            # unknown mode: no changes
            return 0

        if deleted:
            self._events = sorted(to_keep, key=lambda e: (e.day, e.created_at))
            await self._async_save()
        return deleted


@dataclass
class EventEntry:
    """A user-recorded daily event with symptoms and flow."""

    day: date
    menstruating: bool
    flow: str  # enum-like string
    symptoms: list[str]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "menstruating": self.menstruating,
            "flow": self.flow,
            "symptoms": list(self.symptoms),
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def from_dict(obj: dict[str, Any]) -> "EventEntry":
        return EventEntry(
            day=date.fromisoformat(obj["day"]),
            menstruating=bool(obj.get("menstruating", False)),
            flow=str(obj.get("flow", "unknown")),
            symptoms=list(obj.get("symptoms", [])),
            created_at=datetime.fromisoformat(obj.get("created_at")),
        )
