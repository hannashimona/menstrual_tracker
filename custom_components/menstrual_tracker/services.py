"""Services for menstrual_tracker."""

from __future__ import annotations

from datetime import date as date_cls
from typing import Any
import json
from pathlib import Path

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER


SERVICE_RECORD_MENSTRUAL_EVENT = "record_menstrual_event"
SERVICE_IMPORT_HISTORY = "import_history"
SERVICE_DELETE_MENSTRUAL_EVENT = "delete_menstrual_event"

FLOW_LEVELS: tuple[str, ...] = (
    "none",
    "spotting",
    "light",
    "medium",
    "heavy",
)

_EVENT_SCHEMA = vol.Schema(
    {
        vol.Optional("date"): cv.date,
        vol.Required("menstruating"): cv.boolean,
        vol.Required("flow"): vol.In(FLOW_LEVELS),
        vol.Optional("symptoms", default=[]): [cv.string],
        vol.Optional("entity_id"): cv.entity_ids,
        vol.Optional("entry_id"): cv.string,
    }
)

_PERIOD_ITEM = vol.Schema({vol.Required("start"): cv.date, vol.Optional("end"): cv.date})
_EVENT_ITEM = vol.Schema(
    {
        vol.Required("day"): cv.date,
        vol.Required("menstruating"): cv.boolean,
        vol.Required("flow"): vol.In(FLOW_LEVELS),
        vol.Optional("symptoms", default=[]): [cv.string],
    }
)

_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Optional("json"): cv.string,
        vol.Optional("file"): cv.string,
        vol.Optional("periods", default=[]): [_PERIOD_ITEM],
        vol.Optional("events", default=[]): [_EVENT_ITEM],
        vol.Optional("mode", default="merge"): vol.In(["merge", "replace"]),
        vol.Optional("entity_id"): cv.entity_ids,
        vol.Optional("entry_id"): cv.string,
    }
)

_DELETE_SCHEMA = vol.Schema(
    {
        vol.Required("date"): cv.date,
        vol.Optional("mode", default="last"): vol.In(["last", "any", "exact"]),
        vol.Optional("menstruating"): cv.boolean,
        vol.Optional("flow"): vol.In(FLOW_LEVELS),
        vol.Optional("symptoms", default=[]): [cv.string],
        vol.Optional("entity_id"): cv.entity_ids,
        vol.Optional("entry_id"): cv.string,
    }
)


async def _resolve_entry_id(hass: HomeAssistant, call: ServiceCall) -> str | None:
    """Resolve a config entry_id from a service call.

    Priority:
    1) entity_id provided -> map to config_entry_id via entity registry
    2) entry_id provided
    3) if only one entry for DOMAIN, use that
    """

    # 1) From entity_id
    if entity_ids := call.data.get("entity_id"):
        ent_reg = er.async_get(hass)
        # take the first entity id
        for entity_id in (entity_ids if isinstance(entity_ids, list) else [entity_ids]):
            ent = ent_reg.async_get(entity_id)
            if ent and ent.config_entry_id:
                return ent.config_entry_id

    # 2) From entry_id param
    if entry_id := call.data.get("entry_id"):
        return entry_id

    # 3) Single entry fallback
    entries = hass.config_entries.async_entries(DOMAIN)
    if len(entries) == 1:
        return entries[0].entry_id

    return None


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    key = f"{DOMAIN}_services_registered"
    if hass.data.get(key):
        return

    async def _handle_record_event(call: ServiceCall) -> None:
        # Use closure-scoped hass; service handlers receive only the call
        target_entry_id = await _resolve_entry_id(hass, call)
        if not target_entry_id:
            LOGGER.error(
                "record_menstrual_event: Could not resolve a config entry. Provide entity_id or entry_id"
            )
            return
        entry = hass.config_entries.async_get_entry(target_entry_id)
        if not entry or entry.domain != DOMAIN:
            LOGGER.error(
                "record_menstrual_event: Invalid or unknown entry_id: %s", target_entry_id
            )
            return
        day: date_cls = call.data.get("date") or dt_util.now().date()
        menstruating: bool = call.data["menstruating"]
        flow: str = call.data["flow"]
        symptoms: list[str] = call.data.get("symptoms", [])

        try:
            storage = entry.runtime_data.storage  # type: ignore[attr-defined]
            await storage.async_add_event(
                day=day, menstruating=menstruating, flow=flow, symptoms=symptoms
            )
        except Exception:
            LOGGER.exception("record_menstrual_event: Failed saving event")

        try:
            # Refresh entities so sensors/binary sensors can reflect today's event
            await entry.runtime_data.coordinator.async_request_refresh()  # type: ignore[attr-defined]
        except Exception:
            LOGGER.exception("record_menstrual_event: Failed to refresh after event save")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECORD_MENSTRUAL_EVENT,
        _handle_record_event,
        schema=_EVENT_SCHEMA,
    )

    async def _handle_import_history(call: ServiceCall) -> None:
        # Resolve target entry
        target_entry_id = await _resolve_entry_id(hass, call)
        if not target_entry_id:
            LOGGER.error(
                "import_history: Could not resolve a config entry. Provide entity_id or entry_id"
            )
            return
        entry = hass.config_entries.async_get_entry(target_entry_id)
        if not entry or entry.domain != DOMAIN:
            LOGGER.error("import_history: Invalid or unknown entry_id: %s", target_entry_id)
            return

        periods: list[dict[str, Any]] = list(call.data.get("periods", []))
        events: list[dict[str, Any]] = list(call.data.get("events", []))

        # Load JSON from file if provided, otherwise from inline json
        raw_json: str | None = None
        if file_path := call.data.get("file"):
            try:
                path = Path(hass.config.path(file_path))
                raw_json = path.read_text(encoding="utf-8")
            except Exception:
                LOGGER.exception("import_history: Failed to read file: %s", file_path)
                raise HomeAssistantError(
                    "Import failed: file not found or unreadable. See logs for details."
                )
        if not raw_json and (j := call.data.get("json")):
            raw_json = j

        if raw_json:
            try:
                obj = json.loads(raw_json)
                # Native format: { periods: [...], events: [...] }
                if isinstance(obj, dict) and ("periods" in obj or "events" in obj):
                    periods.extend(obj.get("periods", []))
                    events.extend(obj.get("events", []))
                # Third-party list/dict format with items like {type, date, value: {option}}
                elif isinstance(obj, list) or (isinstance(obj, dict) and "data" in obj):
                    items = obj if isinstance(obj, list) else obj.get("data", [])
                    for item in items:
                        try:
                            itype = str(item.get("type", "")).lower()
                            if itype != "period":
                                continue
                            d = item.get("date")
                            v = item.get("value", {}) or {}
                            option = str(v.get("option", "medium"))
                            events.append(
                                {
                                    "day": d,
                                    "menstruating": True,
                                    "flow": option if option in FLOW_LEVELS else "medium",
                                    "symptoms": [],
                                }
                            )
                        except Exception:
                            LOGGER.exception(
                                "import_history: Skipping invalid third-party item: %s", item
                            )
                else:
                    LOGGER.error("import_history: Unsupported JSON structure")
                    raise HomeAssistantError(
                        "Import failed: unsupported JSON structure. See logs for details."
                    )
            except Exception:
                LOGGER.exception("import_history: Failed to parse json payload")
                raise HomeAssistantError(
                    "Import failed: invalid JSON. See logs for details."
                )

        # Normalize and validate items
        from .storage import PeriodEntry, EventEntry  # local import to avoid cycle
        norm_periods: list[PeriodEntry] = []
        for p in periods:
            try:
                start = p["start"] if isinstance(p["start"], date_cls) else date_cls.fromisoformat(p["start"])  # type: ignore[arg-type]
                end_val = p.get("end")
                end = (
                    end_val
                    if isinstance(end_val, date_cls) or end_val is None
                    else date_cls.fromisoformat(end_val)
                )
                norm_periods.append(PeriodEntry(start=start, end=end))
            except Exception:
                LOGGER.exception("import_history: Skipping invalid period entry: %s", p)

        norm_events: list[EventEntry] = []
        # Space created_at within a day for stable ordering
        from datetime import datetime, time, timedelta
        per_day_index: dict[date_cls, int] = {}
        for e in events:
            try:
                day = e["day"] if isinstance(e["day"], date_cls) else date_cls.fromisoformat(e["day"])  # type: ignore[arg-type]
                menstruating = bool(e["menstruating"])  # type: ignore[truthy-bool]
                flow = str(e.get("flow", "medium"))
                if flow not in FLOW_LEVELS:
                    flow = "medium"
                symptoms = list(e.get("symptoms", []))
                idx = per_day_index.get(day, 0)
                created_at = datetime.combine(day, time(12, 0)) + timedelta(seconds=idx)
                per_day_index[day] = idx + 1
                norm_events.append(
                    EventEntry(
                        day=day,
                        menstruating=menstruating,
                        flow=flow,
                        symptoms=symptoms,
                        created_at=created_at,
                    )
                )
            except Exception:
                LOGGER.exception("import_history: Skipping invalid event entry: %s", e)

        if not norm_periods and not norm_events:
            LOGGER.error("import_history: No valid periods or events found to import")
            raise HomeAssistantError(
                "Import failed: no valid records found. See logs for details."
            )

        try:
            storage = entry.runtime_data.storage  # type: ignore[attr-defined]
            mode = call.data.get("mode", "merge")
            await storage.async_import_history(periods=norm_periods, events=norm_events, mode=mode)
        except Exception:
            LOGGER.exception("import_history: Failed to import history")
            raise HomeAssistantError(
                "Import failed during storage update. See logs for details."
            )

        try:
            await entry.runtime_data.coordinator.async_request_refresh()  # type: ignore[attr-defined]
        except Exception:
            LOGGER.exception("import_history: Failed to refresh after import")

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        _handle_import_history,
        schema=_IMPORT_SCHEMA,
    )

    async def _handle_delete_event(call: ServiceCall) -> None:
        target_entry_id = await _resolve_entry_id(hass, call)
        if not target_entry_id:
            LOGGER.error(
                "delete_menstrual_event: Could not resolve a config entry. Provide entity_id or entry_id"
            )
            return
        entry = hass.config_entries.async_get_entry(target_entry_id)
        if not entry or entry.domain != DOMAIN:
            LOGGER.error("delete_menstrual_event: Invalid or unknown entry_id: %s", target_entry_id)
            return

        day: date_cls = call.data["date"]
        mode: str = call.data.get("mode", "last")
        menstruating = call.data.get("menstruating")
        flow = call.data.get("flow")
        symptoms = call.data.get("symptoms", [])
        try:
            storage = entry.runtime_data.storage  # type: ignore[attr-defined]
            deleted = await storage.async_delete_events(
                day=day,
                menstruating=menstruating,
                flow=flow,
                symptoms=symptoms,
                mode=mode,
            )
            if not deleted:
                LOGGER.debug("delete_menstrual_event: No matching events for %s", day)
        except Exception:
            LOGGER.exception("delete_menstrual_event: Failed deleting events")
            return

        try:
            await entry.runtime_data.coordinator.async_request_refresh()  # type: ignore[attr-defined]
        except Exception:
            LOGGER.exception("delete_menstrual_event: Failed to refresh after delete")

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_MENSTRUAL_EVENT,
        _handle_delete_event,
        schema=_DELETE_SCHEMA,
    )

    hass.data[key] = True
    LOGGER.debug(
        "Registered services: %s.%s, %s.%s, %s.%s",
        DOMAIN,
        SERVICE_RECORD_MENSTRUAL_EVENT,
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        DOMAIN,
        SERVICE_DELETE_MENSTRUAL_EVENT,
    )
