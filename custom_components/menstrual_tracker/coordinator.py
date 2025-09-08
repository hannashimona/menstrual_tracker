"""Data coordinator for menstrual tracker."""

from __future__ import annotations

from datetime import date, timedelta
import math
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import LOGGER
from .storage import MenstrualTrackerStorage, PeriodEntry

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
        storage: MenstrualTrackerStorage,
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
        self._storage = storage

    @property
    def last_period(self) -> date:
        """Return last period start date for current cycle."""
        return self.data["last_period_start"] if self.data else self._last_period

    async def _async_update_data(self) -> dict:
        today = dt_util.now().date()
        pregnancy_mode = bool(self.config_entry.options.get("pregnancy_mode", False))

        # Use stored history and detected periods to refine predictions
        periods = list(self._storage.periods)

        # Detect periods from sequences of menstruating events
        menstruating_days = sorted({e.day for e in self._storage.events if e.menstruating})
        detected: list[PeriodEntry] = []
        if menstruating_days:
            start = menstruating_days[0]
            prev = start
            for d in menstruating_days[1:]:
                if (d - prev).days == 1:
                    prev = d
                    continue
                detected.append(PeriodEntry(start=start, end=prev))
                start = d
                prev = d
            detected.append(PeriodEntry(start=start, end=prev))

        # Choose base periods: prefer recorded if there are enough; otherwise merge with detected
        if len(periods) >= 3:
            base_periods: list[PeriodEntry] = periods
        elif periods:
            merged: dict[date, PeriodEntry] = {p.start: p for p in periods}
            for p in detected:
                if p.start not in merged:
                    merged[p.start] = p
            base_periods = sorted(merged.values(), key=lambda p: p.start)
        else:
            base_periods = detected

        last_recorded_start: date | None = base_periods[-1].start if base_periods else None

        # Effective cycle length: robust, weighted average between consecutive starts
        effective_cycle = self._cycle_length
        cycle_stats: dict[str, int | float] = {}
        if len(base_periods) >= 2:
            diffs = [
                (base_periods[i + 1].start - base_periods[i].start).days
                for i in range(len(base_periods) - 1)
            ]
            # Robust filtering using IQR to drop outliers
            if diffs:
                sd = sorted(diffs)
                q1 = sd[max(0, (len(sd) - 1) * 25 // 100)]
                q3 = sd[max(0, (len(sd) - 1) * 75 // 100)]
                iqr = max(0, q3 - q1)
                low = q1 - 1.5 * iqr
                high = q3 + 1.5 * iqr
                filtered = [d for d in diffs if low <= d <= high]
                # Weighted average favoring recent cycles
                if filtered:
                    weights = list(range(1, len(filtered) + 1))
                    wsum = sum(w * v for w, v in zip(weights, filtered))
                    wtot = sum(weights)
                    effective_cycle = max(1, int(round(wsum / wtot)))
                    cycle_stats = {
                        "count": len(filtered),
                        "p25": sd[max(0, (len(sd) - 1) * 25 // 100)],
                        "p50": sd[(len(sd) - 1) // 2],
                        "p75": sd[max(0, (len(sd) - 1) * 75 // 100)],
                    }

        # Effective period length: robust, weighted average of recorded durations (inclusive)
        effective_period_len = self._period_length
        durations = [
            (p.end - p.start).days + 1
            for p in base_periods
            if p.end is not None and p.end >= p.start
        ]
        period_stats: dict[str, int | float] = {}
        if durations:
            sd = sorted(durations)
            q1 = sd[max(0, (len(sd) - 1) * 25 // 100)]
            q3 = sd[max(0, (len(sd) - 1) * 75 // 100)]
            iqr = max(0, q3 - q1)
            low = q1 - 1.5 * iqr
            high = q3 + 1.5 * iqr
            filtered = [d for d in durations if low <= d <= high]
            if filtered:
                weights = list(range(1, len(filtered) + 1))
                wsum = sum(w * v for w, v in zip(weights, filtered))
                wtot = sum(weights)
                effective_period_len = max(1, int(round(wsum / wtot)))
                period_stats = {
                    "count": len(filtered),
                    "p25": sd[max(0, (len(sd) - 1) * 25 // 100)],
                    "p50": sd[(len(sd) - 1) // 2],
                    "p75": sd[max(0, (len(sd) - 1) * 75 // 100)],
                }

        base_start = last_recorded_start or self._last_period
        # Adjust base_start to most recent cycle boundary
        days_since = (today - base_start).days
        cycles_since = 0 if days_since < 0 else days_since // effective_cycle
        current_period_start = base_start + timedelta(days=cycles_since * effective_cycle)

        day_of_cycle = (today - current_period_start).days + 1

        # Fallback fertility window using a ~14 day luteal phase
        ovulation_day = max(1, effective_cycle - 14)
        fertility_start = current_period_start + timedelta(days=ovulation_day - 5)
        fertility_end = current_period_start + timedelta(days=ovulation_day + 1)
        # Next period prediction using Drip methodology
        # Build cycle lengths from consecutive starts
        cycle_lengths: list[int] = []
        if len(base_periods) >= 2:
            cycle_lengths = [
                (base_periods[i + 1].start - base_periods[i].start).days
                for i in range(len(base_periods) - 1)
                if (base_periods[i + 1].start - base_periods[i].start).days <= 99
            ]

        next_period_start = None
        next_period_earliest = None
        next_period_latest = None
        predicted_period_centers: list[date] = []
        predicted_fertility_windows: list[tuple[date, date]] = []

        if len(cycle_lengths) >= 3:
            mean = sum(cycle_lengths) / len(cycle_lengths)
            # population std dev like Drip's getCycleLengthStats
            variance = (
                sum((x - mean) ** 2 for x in cycle_lengths) / len(cycle_lengths)
            )
            std_dev = math.sqrt(variance)
            period_distance = int(round(mean))
            # Variation per Drip: std < 1.5 => 1, else 2; if no std then 2
            variation = 1 if std_dev < 1.5 else 2
            # Always generate a rolling two-year horizon once we have ≥3 cycles
            last_start = base_periods[-1].start
            horizon_end = today + timedelta(days=365 * 2)
            center = last_start
            while True:
                center = center + timedelta(days=period_distance)
                if center > horizon_end:
                    break
                predicted_period_centers.append(center)
            # Populate single-value fields for backward compatibility
            if predicted_period_centers:
                next_period_start = predicted_period_centers[0]
                next_period_earliest = next_period_start - timedelta(days=variation)
                next_period_latest = next_period_start + timedelta(days=variation)
                # Also compute first fertility window from earliest/latest
                fert_start = next_period_earliest - timedelta(days=14 + 5)
                fert_end = next_period_latest - timedelta(days=14 - 1)
                fertility_start = fert_start
                fertility_end = fert_end
            # Compute fertility windows for all predicted centers
            for c in predicted_period_centers:
                earliest = c - timedelta(days=variation)
                latest = c + timedelta(days=variation)
                fw_start = earliest - timedelta(days=14 + 5)
                fw_end = latest - timedelta(days=14 - 1)
                predicted_fertility_windows.append((fw_start, fw_end))
        # Fallback to previous single-date estimate if Drip inputs insufficient
        if next_period_start is None:
            next_period_start = current_period_start + timedelta(days=effective_cycle)

        # Determine menstruation status from today's explicit events if present,
        # otherwise based on recorded period window, otherwise heuristic.
        currently_menstruating = False
        todays_events = [e for e in self._storage.events if e.day == today]
        if todays_events:
            currently_menstruating = any(e.menstruating for e in todays_events)
        elif base_periods and base_periods[-1].start <= today:
            rec_start = base_periods[-1].start
            rec_end = base_periods[-1].end or (
                rec_start + timedelta(days=effective_period_len - 1)
            )
            currently_menstruating = rec_start <= today <= rec_end
        else:
            # fallback heuristic
            currently_menstruating = day_of_cycle <= effective_period_len

        return {
            "last_period_start": current_period_start,
            "day_of_cycle": day_of_cycle,
            "currently_menstruating": currently_menstruating,
            "fertility_window_start": None if pregnancy_mode else fertility_start,
            "fertility_window_end": None if pregnancy_mode else fertility_end,
            "next_period_start": None if pregnancy_mode else next_period_start,
            "period_length": effective_period_len,
            "cycle_length": effective_cycle,
            "pregnancy_mode": pregnancy_mode,
            # Extra diagnostics/prediction window
            "next_period_earliest": None if pregnancy_mode else next_period_earliest,
            "next_period_latest": None if pregnancy_mode else next_period_latest,
            "period_length_stats": period_stats,
            "cycle_length_stats": cycle_stats,
            # Multi-cycle predictions
            "predicted_period_centers": [] if pregnancy_mode else predicted_period_centers,
            # Fertility windows as list of (start, end) inclusive dates
            "predicted_fertility_windows": [] if pregnancy_mode else predicted_fertility_windows,
        }
