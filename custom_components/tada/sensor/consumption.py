from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, MANUFACTURER, MODEL, DEVICE_NAME_BASE, DEVICE_SUFFIX_BASE
from ..utils import parse_hhmm, is_time_in_range, _to_float, _round_safe
from .base import TadaBaseSensor

_LOGGER = logging.getLogger(__name__)


class TadaConsumptionTodayHourlySensor(TadaBaseSensor):
    """Sensor for today's hourly consumption data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        device_name: str = "Tada Today",
        device_id_suffix: str = "today",
        quiet_window_enabled: bool = False,
        quiet_window_from: str | None = None,
        quiet_window_to: str | None = None,
    ):
        name = "Consumption Today"
        unique_id = f"tada_consumption_today_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_translation_key = "tada_consumption_today"
        # Energy Dashboard compatibility
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        # Quiet window configuration
        self._quiet_window_enabled = bool(quiet_window_enabled)
        self._quiet_window_from_t = parse_hhmm(quiet_window_from) if isinstance(quiet_window_from, str) else None
        self._quiet_window_to_t = parse_hhmm(quiet_window_to) if isinstance(quiet_window_to, str) else None
        self._quiet_start_unsub = None
        self._quiet_end_unsub = None

    def _in_quiet_window(self) -> bool:
        if not self._quiet_window_enabled:
            return False
        return is_time_in_range(dt_util.now().time(), self._quiet_window_from_t, self._quiet_window_to_t)

    @property
    def available(self) -> bool:
        base = super().available
        if not base:
            return False
        # Hide during quiet window to avoid ingesting inconsistent backend rollover samples
        return not self._in_quiet_window()

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        consumption = data.get("consumption_today") or {}
        items = consumption.get("data") or []
        if items and isinstance(items, list):
            total = sum(
                _to_float(item.get("kWh"), 0.0)
                for item in items
                if isinstance(item, dict)
            )
            hours = {
                str(item.get("hour")): {"kWh": item.get("kWh"), "W": item.get("W"), "label": item.get("label")}
                for item in items
                if isinstance(item, dict)
            }
            # state: total kWh for today (rounded)
            self._state = _round_safe(total, 3)

            # build extra attributes: raw list, structured hours dict, and flat per-hour keys
            attrs = {"hourly_data": items, "hours": hours, "quiet_window_active": self._in_quiet_window()}
            for h, info in hours.items():
                attrs[f"hour_{h}_kWh"] = info.get("kWh")
                attrs[f"hour_{h}_W"] = info.get("W")

            self._attr_extra_state_attributes = attrs
        else:
            self._state = None
            self._attr_extra_state_attributes = {"hourly_data": [], "hours": {}, "quiet_window_active": self._in_quiet_window()}

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        try:
            await super().async_added_to_hass()
        except Exception:
            pass
        # Schedule precise state flips at quiet window boundaries to ensure clean gaps
        if self._quiet_window_enabled and self._quiet_window_from_t and self._quiet_window_to_t:
            self._schedule_quiet_window_callbacks()

    async def async_will_remove_from_hass(self):
        # Cancel scheduled callbacks
        try:
            if callable(self._quiet_start_unsub):
                self._quiet_start_unsub()
        except Exception:
            _LOGGER.warning("Failed to cancel quiet window start callback", exc_info=True)
        try:
            if callable(self._quiet_end_unsub):
                self._quiet_end_unsub()
        except Exception:
            _LOGGER.warning("Failed to cancel quiet window end callback", exc_info=True)

    def _schedule_quiet_window_callbacks(self):
        # Use local daily time-change triggers to fire exactly at configured clock times
        @callback
        def _on_quiet_start_time(now):
            # Mark unavailable immediately at quiet start
            self._state = None
            self.async_write_ha_state()
            try:
                self.hass.async_create_task(self.coordinator.async_request_refresh())
            except Exception:
                pass

        @callback
        def _on_quiet_end_time(now):
            # Request refresh to restore normal updates after quiet window
            try:
                self.hass.async_create_task(self.coordinator.async_request_refresh())
            except Exception:
                pass
            self.async_write_ha_state()

        try:
            self._quiet_start_unsub = async_track_time_change(
                self.hass,
                _on_quiet_start_time,
                hour=self._quiet_window_from_t.hour,
                minute=self._quiet_window_from_t.minute,
                second=0,
            )
        except Exception:
            self._quiet_start_unsub = None
        try:
            self._quiet_end_unsub = async_track_time_change(
                self.hass,
                _on_quiet_end_time,
                hour=self._quiet_window_to_t.hour,
                minute=self._quiet_window_to_t.minute,
                second=0,
            )
        except Exception:
            self._quiet_end_unsub = None


class TadaLifetimeEnergySensor(TadaBaseSensor):
    """Cumulative lifetime energy sensor built inside the integration.

    It maintains a persisted base (sum of completed days) and adds the current
    day running total from the coordinator to expose a total_increasing energy
    counter suitable for the Energy dashboard.
    """

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        device_name: str = DEVICE_NAME_BASE,
        device_id_suffix: str = DEVICE_SUFFIX_BASE,
    ):
        name = "Total Energy"
        unique_id = f"tada_total_energy_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_translation_key = "tada_total_energy"
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_suggested_object_id = "tada_total_energy"

        # Persisted pieces
        self._store: Store | None = None
        self._base_kwh: float = 0.0
        self._last_rollover_date: str | None = None  # YYYY-MM-DD (day that was added to base)
        self._last_today_seen_kwh: float = 0.0       # last non-decreasing snapshot of today
        self._last_seen_day: str | None = None        # YYYY-MM-DD (current calendar day when last updated)
        self._persisted_today_seen_kwh: float = 0.0

    async def async_added_to_hass(self):
        try:
            await super().async_added_to_hass()
        except Exception:
            pass
        # Initialize storage on first attach
        try:
            self._store = Store(self.hass, 1, f"{DOMAIN}_lifetime_{self._subscription_id}.json")
            data = await self._store.async_load() or {}
            self._base_kwh = float(data.get("base_kwh", 0.0) or 0.0)
            self._last_rollover_date = data.get("last_rollover_date")
            self._last_today_seen_kwh = float(data.get("last_today_seen_kwh", 0.0) or 0.0)
            self._last_seen_day = data.get("last_seen_day")
            self._persisted_today_seen_kwh = self._last_today_seen_kwh
        except Exception:
            # Fallback to defaults if storage not available
            self._store = None
        # Compute an initial state from current coordinator data
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def _persist(self):
        if not self._store:
            return
        try:
            await self._store.async_save(
                {
                    "base_kwh": round(self._base_kwh, 3),
                    "last_rollover_date": self._last_rollover_date,
                    "last_today_seen_kwh": round(self._last_today_seen_kwh, 3),
                    "last_seen_day": self._last_seen_day,
                }
            )
        except Exception:
            pass

    def _calc_today_total(self) -> float:
        data = self.coordinator.data or {}
        consumption = data.get("consumption_today") or {}
        items = consumption.get("data") or []
        if items and isinstance(items, list):
            total = sum(
                _to_float(item.get("kWh"), 0.0)
                for item in items
                if isinstance(item, dict)
            )
            return _round_safe(total, 3)
        return 0.0

    def _maybe_rollover(self, now_day: str):
        """If we crossed to a new day and haven't rolled, add yesterday's total."""
        # If this is the first time we see the day, just set it and return
        if self._last_seen_day is None:
            self._last_seen_day = now_day
            return False

        # No day change
        if now_day == self._last_seen_day:
            return False

        # Day changed: if we haven't already rolled over the previous day, do it now
        prev_day = self._last_seen_day
        if self._last_rollover_date != prev_day:
            self._base_kwh = _round_safe(self._base_kwh + (self._last_today_seen_kwh or 0.0), 3)
            self._last_rollover_date = prev_day
            self._last_today_seen_kwh = 0.0
            self._last_seen_day = now_day
            return True

        # Already rolled for prev_day; just update the marker
        self._last_seen_day = now_day
        return False

    def _update_from_coordinator(self):
        # 1) Check for calendar day transition and perform rollover if needed
        now_day = dt_util.now().date().isoformat()
        rolled = self._maybe_rollover(now_day)

        # 2) Compute today's running total from coordinator
        today_total = self._calc_today_total()
        # Update the last seen snapshot to a non-decreasing value
        if today_total > (self._last_today_seen_kwh or 0.0):
            self._last_today_seen_kwh = today_total
            # Persist occasionally to survive restarts during quiet window
            try:
                if (self._last_today_seen_kwh - (self._persisted_today_seen_kwh or 0.0)) >= 0.01:
                    self._persisted_today_seen_kwh = self._last_today_seen_kwh
                    self.hass.async_create_task(self._persist())
            except Exception:
                pass

        # 3) Expose lifetime total: base + current today
        self._state = _round_safe((self._base_kwh or 0.0) + (today_total or 0.0), 3)
        self._attr_extra_state_attributes = {
            "base_kwh": _round_safe(self._base_kwh, 3),
            "today_total_kwh": today_total,
            "last_rollover_date": self._last_rollover_date,
        }

        # 4) Persist when rollover occurred (to minimize writes)
        if rolled:
            # Schedule persistence asynchronously
            try:
                self.hass.async_create_task(self._persist())
            except Exception:
                pass

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()


class TadaConsumptionPeriodSensor(TadaBaseSensor):
    """Generic consumption sensor for arbitrary period (shows total and raw list)."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,
        label: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        name = f"Consumption {label}"
        unique_id = f"tada_consumption_{period_key}_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._period_key = period_key
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:lightning-bolt"
        # Mark as energy total to enable long-term statistics
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        # Provide translation key for friendly labels
        self._attr_translation_key = f"tada_consumption_{period_key}"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        # Fetch both sources independently
        cons_src = data.get(f"consumption_{self._period_key}") or {}

        flat_items = None
        daily_items = None
        weekly_items = None

        # Responses differ by period:
        # - last-7-days: {"data": [ ... ]}
        # - last-month/last-30-days: {"data": {"daily": [...], "weekly": [...]}}
        cons_data = cons_src.get("data") if isinstance(cons_src, dict) else None
        if isinstance(cons_data, list):
            flat_items = cons_data
        elif isinstance(cons_data, dict):
            daily_items = cons_data.get("daily") if isinstance(cons_data.get("daily"), list) else []
            weekly_items = cons_data.get("weekly") if isinstance(cons_data.get("weekly"), list) else []

        tb_src = data.get(f"timebands_{self._period_key}") or {}
        timebands_items = tb_src.get("data") or []

        # Compute totals from whichever consumption form is available
        total_from_consumption = None
        state_source = None
        if daily_items and isinstance(daily_items, list):
            total = sum(
                _to_float(item.get("kWh"), 0.0)
                for item in daily_items
                if isinstance(item, dict)
            )
            total_from_consumption = _round_safe(total, 3)
            state_source = "consumption_daily"
        elif flat_items and isinstance(flat_items, list):
            total = sum(
                _to_float(item.get("kWh"), 0.0)
                for item in flat_items
                if isinstance(item, dict)
            )
            total_from_consumption = _round_safe(total, 3)
            state_source = "consumption_flat"

        total_from_timebands = None
        if isinstance(timebands_items, list) and timebands_items:
            tb_total = sum(
                _to_float(item.get("value"), 0.0)
                for item in timebands_items
                if isinstance(item, dict)
            )
            total_from_timebands = _round_safe(tb_total, 3)

        # Prefer consumption-derived total, fallback to timebands-derived total
        if total_from_consumption is not None:
            self._state = total_from_consumption
        else:
            self._state = total_from_timebands
            if total_from_timebands is not None:
                state_source = "timebands"

        # Always expose whichever attributes are available
        attrs = {
            "timebands": timebands_items if isinstance(timebands_items, list) else [],
            "state_source": state_source,
        }
        if isinstance(flat_items, list):
            attrs["data"] = flat_items
        if isinstance(daily_items, list):
            attrs["data_daily"] = daily_items
        if isinstance(weekly_items, list):
            attrs["data_weekly"] = weekly_items
        self._attr_extra_state_attributes = attrs

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()
