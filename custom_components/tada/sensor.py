from __future__ import annotations
import logging
from datetime import datetime
from typing import Any, Iterable, Tuple

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    DEVICE_NAME_BASE,
    DEVICE_NAME_TODAY,
    DEVICE_NAME_YESTERDAY,
    DEVICE_SUFFIX_BASE,
    DEVICE_SUFFIX_TODAY,
    DEVICE_SUFFIX_YESTERDAY,
    DEFAULT_QUIET_WINDOW_ENABLED,
    DEFAULT_QUIET_WINDOW_FROM,
    DEFAULT_QUIET_WINDOW_TO,
)
from .api import TadaAPI
from .mapping import APPLIANCES_MAP, ACTIVITIES_MAP, slugify
from .utils import _parse_ids, _present_ids_from_summary, _parse_iso_to_dt, parse_hhmm, is_time_in_range, _to_float, _round_safe

_LOGGER = logging.getLogger(__name__)

def _add_summary_entities(
    entities: list[SensorEntity],
    coordinator: DataUpdateCoordinator,
    subscription_id: str,
    period_key: str,
    device_name: str,
    device_id_suffix: str,
    enabled_appliances: set[int],
    enabled_activities: set[int],
) -> None:
    """Append summary item sensors for enabled appliance/activity IDs."""
    for aid in sorted(enabled_appliances):
        label_appl = APPLIANCES_MAP.get(aid, str(aid))
        entities.append(TadaSummaryItemSensor(coordinator, subscription_id, period_key, "appliance", aid, "value", label_appl, device_name=device_name, device_id_suffix=device_id_suffix))
        entities.append(TadaSummaryItemSensor(coordinator, subscription_id, period_key, "appliance", aid, "percentage", label_appl, device_name=device_name, device_id_suffix=device_id_suffix))
    for actid in sorted(enabled_activities):
        label_act = ACTIVITIES_MAP.get(actid, str(actid))
        entities.append(TadaSummaryItemSensor(coordinator, subscription_id, period_key, "activity", actid, "value", label_act, device_name=device_name, device_id_suffix=device_id_suffix))
        entities.append(TadaSummaryItemSensor(coordinator, subscription_id, period_key, "activity", actid, "percentage", label_act, device_name=device_name, device_id_suffix=device_id_suffix))

class TadaBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Tada integration."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        unique_id: str,
        subscription_id: str,
        device_info: dict | None = None,
    ):
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._subscription_id = subscription_id
        if device_info:
            self._attr_device_info = DeviceInfo(**device_info)
        self._state: Any = None

    @property
    def native_value(self):
        return self._state

class TadaValueSensor(TadaBaseSensor):
    """Generic sensor that reads a top-level key from coordinator data."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        source_key: str,
        value_key: str,
        unit: str | None,
        subscription_id: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        unique_id = f"tada_{subscription_id}_{source_key}_{value_key}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._source_key = source_key
        self._value_key = value_key
        self._attr_native_unit_of_measurement = unit
        if unit == "%":
            self._attr_icon = "mdi:percent-outline"
        # Map translation keys for known value sensors
        if source_key == "power_latest":
            if value_key == "value":
                self._attr_translation_key = "tada_current_power"
            elif value_key == "availablePower":
                self._attr_translation_key = "tada_available_power"
            elif value_key == "powerUsagePercent":
                self._attr_translation_key = "tada_power_usage_percent"
            elif value_key == "maxAvailablePower":
                self._attr_translation_key = "tada_max_available_power"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(self._source_key)
        if isinstance(src, dict):
            self._state = src.get(self._value_key)
        else:
            self._state = None

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

class TadaNestedValueSensor(TadaBaseSensor):
    """Sensor that reads a nested value from coordinator data using a path tuple."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        name: str,
        source_key: str,
        path: Tuple[str, ...],
        unit: str | None,
        subscription_id: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        unique_id = f"tada_{subscription_id}_{source_key}_{'_'.join(path)}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._source_key = source_key
        self._path = path
        self._attr_native_unit_of_measurement = unit

    def _get_nested(self, obj: dict, path: Iterable[str]):
        cur = obj
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(self._source_key)
        if isinstance(src, dict):
            self._state = self._get_nested(src, self._path)
        else:
            self._state = None

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()  

class TadaConsumptionTodayHourlySensor(TadaBaseSensor):
    """Sensor for today's hourly consumption data."""

    def __init__(self, coordinator: DataUpdateCoordinator, subscription_id: str, device_name: str = "Tada Today", device_id_suffix: str = "today", quiet_window_enabled: bool = False, quiet_window_from: str | None = None, quiet_window_to: str | None = None):
        name = "Tada consumption today"
        unique_id = f"tada_consumption_today_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
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
            pass
        try:
            if callable(self._quiet_end_unsub):
                self._quiet_end_unsub()
        except Exception:
            pass

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
        name = "Tada total energy"
        unique_id = f"tada_total_energy_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
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
        self._last_seen_day: str | None = None       # YYYY-MM-DD (current calendar day when last updated)
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
        """If we crossed to a new day and haven't rolled, add yesterday's total.

        We rely on the cached last_seen snapshot from the previous day to be robust
        across the quiet window where the coordinator may zero today data.
        """
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

    def __init__(self, coordinator: DataUpdateCoordinator, subscription_id: str, period_key: str, label: str, device_name: str = "Tada", device_id_suffix: str = "default"):
        name = f"Tada consumption {label}"
        unique_id = f"tada_consumption_{period_key}_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
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

class TadaTimebandsSensor(TadaBaseSensor):
    """Timebands breakdown sensor for arbitrary period."""

    def __init__(self, coordinator: DataUpdateCoordinator, subscription_id: str, period_key: str, label: str, device_name: str = "Tada", device_id_suffix: str = "default"):
        name = f"Tada total {label}"
        unique_id = f"tada_timebands_{period_key}_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._period_key = period_key
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_translation_key = f"tada_timebands_total_{period_key}"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(f"timebands_{self._period_key}") or {}
        items = src.get("data") or []
        if items and isinstance(items, list):
            total = sum(
                _to_float(item.get("value"), 0.0)
                for item in items
                if isinstance(item, dict)
            )
            self._state = _round_safe(total, 3)
            self._attr_extra_state_attributes = {"timebands": items}
        else:
            self._state = None
            self._attr_extra_state_attributes = {"timebands": []}

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

class TadaTimebandSplitSensor(TadaBaseSensor):
    """Sensor representing a single timeband (value or percentage) for a period."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,
        band_slug: str,  # notte | mattina | pomeriggio | sera
        mode: str,       # "value" or "percentage"
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        name = f"Tada {period_key} {band_slug} {mode}"
        unique_id = f"tada_timeband_{period_key}_{band_slug}_{mode}_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._period_key = period_key
        self._band_slug = band_slug
        self._mode = mode
        self._attr_native_unit_of_measurement = "kWh" if mode == "value" else "%"
        if mode == "percentage":
            self._attr_icon = "mdi:percent-outline"
        else:
            self._attr_icon = "mdi:lightning-bolt"
        # Provide translation key for friendly labels
        try:
            self._attr_translation_key = f"tada_timeband_{period_key}_{band_slug}_{mode}"
        except Exception:
            pass

    def _normalize_label(self, label: str) -> str:
        s = (label or "").strip().lower()
        # map common Italian/English labels to slugs
        mapping = {
            "notte": "notte",
            "night": "notte",
            "mattina": "mattina",
            "morning": "mattina",
            "pomeriggio": "pomeriggio",
            "afternoon": "pomeriggio",
            "sera": "sera",
            "evening": "sera",
        }
        return mapping.get(s, s)

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        tb_src = data.get(f"timebands_{self._period_key}") or {}
        items = tb_src.get("data") or []
        value = None
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            label = self._normalize_label(str(item.get("label")))
            if label == self._band_slug:
                if self._mode == "value":
                    value = _to_float(item.get("value"), 0.0)
                else:
                    value = _to_float(item.get("percentage"), 0.0)
                break
        self._state = value

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

class TadaSummaryItemSensor(TadaBaseSensor):
    """Sensor for a single summary item (appliance/activity) for a period."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,  # e.g., yesterday | last_365_days | custom_...
        category: str,    # "appliance" or "activity"
        item_id: int,
        mode: str,        # "value" or "percentage"
        display_label: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        # Name in Italian grouping for visual ordering
        if category == "appliance":
            base = "Elettrodomestici"
        else:
            base = "Attività"
        unit_label = "kWh" if mode == "value" else "%"
        name = f"{base} {display_label} {unit_label}"
        # Use label-based unique_id to ensure stable, human-readable IDs
        label_slug = slugify(display_label)
        unique_id = f"tada_{subscription_id}_summary_{period_key}_{category}_{label_slug}_{mode}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._period_key = period_key
        self._category = category
        self._item_id = int(item_id)
        self._mode = mode
        self._attr_native_unit_of_measurement = "kWh" if mode == "value" else "%"
        self._attr_icon = "mdi:lightning-bolt" if mode == "value" else "mdi:percent-outline"
        self._attr_has_entity_name = False
        cat_slug = "attivita" if category == "activity" else "elettrodomestici"
        mode_slug = "kwh" if mode == "value" else "percentuale"
        label_slug = slugify(display_label)
        self._attr_suggested_object_id = f"tada_{period_key}_{cat_slug}_{label_slug}_{mode_slug}"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(f"summary_{self._period_key}") or {}
        payload = src.get("data") or {}
        items = []
        id_key = "applianceId" if self._category == "appliance" else "activityId"
        if self._category == "appliance":
            items = payload.get("appliances") or []
        else:
            items = payload.get("activities") or []
        val = None
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            if int(item.get(id_key, -1)) == self._item_id:
                if self._mode == "value":
                    val = _to_float(item.get("value"), 0.0)
                else:
                    val = _to_float(item.get("percentage"), 0.0)
                break
        self._state = val

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        # Call base to populate initial state immediately
        try:
            await super().async_added_to_hass()
        except Exception:
            pass
        # Ensure desired entity_id naming is applied at creation
        try:
            ent_reg = er.async_get(self.hass)
            cat_slug = "attivita" if self._category == "activity" else "elettrodomestici"
            mode_slug = "kwh" if self._mode == "value" else "percentuale"
            # Use display label from unique_id segment or device maps for robustness
            label_slug = None
            try:
                # unique_id contains label_slug; extract after category
                parts = self._attr_unique_id.split("_")
                # unique_id: tada_<sub>_summary_<period>_<category>_<label_slug>_<mode>
                if len(parts) >= 7:
                    label_slug = parts[-2]
            except Exception:
                label_slug = None
            if not label_slug:
                # fallback to maps
                if self._category == "appliance":
                    label_slug = slugify(APPLIANCES_MAP.get(self._item_id, str(self._item_id)))
                else:
                    label_slug = slugify(ACTIVITIES_MAP.get(self._item_id, str(self._item_id)))
            desired = f"sensor.tada_{self._period_key}_{cat_slug}_{label_slug}_{mode_slug}"
            entry = ent_reg.async_get(self.entity_id)
            if entry and entry.entity_id != desired:
                try:
                    await ent_reg.async_update_entity(entry.entity_id, new_entity_id=desired)
                except Exception:
                    pass
        except Exception:
            pass

class TadaInstantPowerSensor(SensorEntity):
    """Websocket-driven instant power sensor using dispatcher."""

    def __init__(self, hass: HomeAssistant, subscription_id: str, device_name: str = "Tada Today", device_id_suffix: str = "today"):
        self.hass = hass
        self._subscription_id = subscription_id
        self._attr_name = "Tada instant power"
        self._attr_unique_id = "tada_instant_power"
        # attach to the same device as other sensors
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")}, name=device_name)
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:flash"
        self._attr_translation_key = "tada_instant_power"
        self._state: Any = None
        self._unsub = None

    @callback
    def _handle_instant_power(self, value):
        # value expected numeric
        self._state = value
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the current sensor value for HA."""
        return self._state

    async def async_added_to_hass(self):
        # subscribe to dispatcher signal emitted by ws client
        # the ws client should call: async_dispatcher_send(hass, "tada_instant_power", value)
        self._unsub = async_dispatcher_connect(
            self.hass, "tada_instant_power", self._handle_instant_power
        )

    async def async_will_remove_from_hass(self):
        if self._unsub:
            self._unsub()
            self._unsub = None

class TadaComparisonValueSensor(TadaBaseSensor):
    """Generic comparison sensor reading from coordinator comparisons payloads."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        source_key: str,
        value_key: str,
        name: str,
        unit: str | None,
        scale_percent: bool = False,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
        translation_key: str | None = None,
    ):
        unique_id = f"tada_{subscription_id}_{source_key}_{value_key}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._source_key = source_key
        self._value_key = value_key
        self._scale_percent = scale_percent
        self._attr_native_unit_of_measurement = unit
        if unit == "%":
            self._attr_icon = "mdi:percent-outline"
        elif unit == "kWh":
            self._attr_icon = "mdi:lightning-bolt"
        if translation_key:
            self._attr_translation_key = translation_key

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(self._source_key) or {}
        if isinstance(src, dict) and not src.get("error"):
            val = src.get(self._value_key)
            if isinstance(val, (int, float)):
                val = float(val)
                val = round(val * 100.0, 2) if self._scale_percent else round(val, 2)
            self._state = val
            # Keep raw payload for diagnostics
            self._attr_extra_state_attributes = {"payload": src}
        else:
            self._state = None
            self._attr_extra_state_attributes = {"payload": src if isinstance(src, dict) else {}}

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

class TadaAnnualReferenceSensor(TadaBaseSensor):
    """Annual reference sensor for last-month comparisons."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        source_key: str,
        name: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
        translation_key: str | None = None,
    ):
        unique_id = f"tada_{subscription_id}_{source_key}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._source_key = source_key
        # Unit may be kWh depending on API; keep dynamic
        if translation_key:
            self._attr_translation_key = translation_key

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        src = data.get(self._source_key) or {}
        if isinstance(src, dict) and not src.get("error"):
            # Try common numeric keys
            value = None
            value = next(
                (src.get(k) for k in ("annualReference", "value", "total") if isinstance(src.get(k), (int, float))),
                None,
            )
            # Infer unit if present
            if isinstance(value, (int, float)):
                self._state = round(float(value), 2)
            else:
                self._state = None
            self._attr_extra_state_attributes = {"payload": src}
        else:
            self._state = None
            self._attr_extra_state_attributes = {"payload": src if isinstance(src, dict) else {}}

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()

class PeriodCoverageTimestampSensor(TadaBaseSensor):
    """Timestamp sensor for period coverage start date."""

    def __init__(self, coordinator: DataUpdateCoordinator, subscription_id: str, period_key: str, label: str, device_name: str = "Tada", device_id_suffix: str = "default"):
        name = f"Tada period coverage start"
        unique_id = f"tada_period_coverage_start_{subscription_id}_{period_key}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        self._period_key = period_key
        self._attr_device_class = "timestamp"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_translation_key = f"tada_period_coverage_start_{period_key}"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        period_checks = data.get("period_checks") or {}
        entry = period_checks.get(self._period_key) or {}
        raw = entry.get("coverageStartDate")
        dt = None
        if isinstance(raw, str):
            dt = _parse_iso_to_dt(raw)
        elif isinstance(raw, datetime):
            dt = raw
        self._state = dt

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()


class TadaPowerEventSensor(TadaBaseSensor):
    """Sensor tracking power event counts (alarms or cutoffs) for a specific period."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,  # "last30Days" or "last90Days"
        event_type: str,  # "alarms" or "cutoffs"
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        # Format names like: Tada Power Events Alarms 30 Days
        period_label = "30 Days" if period_key == "last30Days" else "90 Days"
        name = f"Tada Power Events {event_type.capitalize()} {period_label}"
        unique_id = f"tada_power_events_{event_type}_{period_key}_{subscription_id}"
        
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
        }
        super().__init__(coordinator, name, unique_id, subscription_id, device_info)
        
        self._period_key = period_key
        self._event_type = event_type
        
        self._attr_icon = "mdi:alert" if event_type == "alarms" else "mdi:power-plug-off"
        # Since these are counts, measurement unit is omitted, and state class can be measurement.
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_translation_key = f"tada_power_events_{event_type}_{period_key.lower()}"

    def _update_from_coordinator(self):
        data = self.coordinator.data or {}
        # We fetch the entire power events payload
        events_data = data.get("power_events") or {}
        
        # Access the specific period (e.g. last30Days)
        period_data = events_data.get(self._period_key) or {}
        
        if period_data and not events_data.get("error"):
            # Depending on event type we fetch 'alarmsCount' or 'cutoffsCount'
            count_key = f"{self._event_type}Count"
            count = period_data.get(count_key)
            self._state = int(count) if count is not None else 0
            
            # Store details in attributes: list of events and period dates
            self._attr_extra_state_attributes = {
                "events": period_data.get(self._event_type, []),
                "period": period_data.get("period", {}),
                "has_more": period_data.get(f"hasMore{self._event_type.capitalize()}", False)
            }
        else:
            self._state = None
            self._attr_extra_state_attributes = {"events": [], "period": {}}

    def _handle_coordinator_update(self) -> None:
        self._update_from_coordinator()
        self.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up Tada sensors from a config entry."""
    data = hass.data.get(DOMAIN)
    if not data:
        _LOGGER.error("Tada integration data missing in hass.data")
        return False

    coordinator: DataUpdateCoordinator = data.get("coordinator")
    api: TadaAPI = data.get("api")
    subscription_id = entry.data.get("subscription_id")

    if coordinator is None or api is None or subscription_id is None:
        _LOGGER.error("Missing coordinator/api/subscription_id for Tada sensors")
        return False

    entities: list[SensorEntity] = []
    opts = entry.options or {}

    # Today device: TODAY group sensors
    # TODAY group
    # Pass quiet window options to the today sensor to avoid ingesting inconsistent backend samples around midnight
    q_enabled = opts.get("quiet_window_enabled", DEFAULT_QUIET_WINDOW_ENABLED)
    q_from = opts.get("quiet_window_from", DEFAULT_QUIET_WINDOW_FROM)
    q_to = opts.get("quiet_window_to", DEFAULT_QUIET_WINDOW_TO)
    entities.append(TadaConsumptionTodayHourlySensor(
        coordinator,
        subscription_id,
        device_name=DEVICE_NAME_TODAY,
        device_id_suffix=DEVICE_SUFFIX_TODAY,
        quiet_window_enabled=q_enabled,
        quiet_window_from=q_from,
        quiet_window_to=q_to,
    ))
    entities.append(TadaInstantPowerSensor(hass, subscription_id, device_name=DEVICE_NAME_TODAY, device_id_suffix=DEVICE_SUFFIX_TODAY))
    # Base Tada device: GENERAL sensors
    entities.append(TadaValueSensor(coordinator, "Available Power", "power_latest", "availablePower", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Current Power", "power_latest", "value", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Power Usage %", "power_latest", "powerUsagePercent", "%", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Max Available Power", "power_latest", "maxAvailablePower", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    # Lifetime total energy (total_increasing) for Energy dashboard
    entities.append(TadaLifetimeEnergySensor(coordinator, subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))

    # Power Events sensors
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last30Days", "alarms", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last30Days", "cutoffs", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last90Days", "alarms", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last90Days", "cutoffs", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))

    # Add dynamic coverage-start sensors based on options
    monitor_custom = opts.get("monitor_custom", False)
    custom_from = opts.get("custom_from")
    custom_to = opts.get("custom_to")

    # Yesterday device
    entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, "yesterday", "yesterday", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
    entities.append(PeriodCoverageTimestampSensor(coordinator, subscription_id, "yesterday", "yesterday", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    # Yesterday timeband split sensors (value + percentage for 4 bands)
    for band in ("notte", "mattina", "pomeriggio", "sera"):
        entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, "yesterday", band, "value", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
        entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, "yesterday", band, "percentage", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
    # Yesterday comparison sensors
    entities.append(TadaComparisonValueSensor(
        coordinator,
        subscription_id,
        source_key="comparisons_average_yesterday",
        value_key="averageEnergyComparison",
        name="Tada yesterday average comparison",
        unit="%",
        scale_percent=True,
        device_name=DEVICE_NAME_YESTERDAY,
        device_id_suffix=DEVICE_SUFFIX_YESTERDAY,
        translation_key="tada_comparison_yesterday_average_percent",
    ))
    entities.append(TadaComparisonValueSensor(
        coordinator,
        subscription_id,
        source_key="comparisons_previous_yesterday",
        value_key="previousEnergyComparison",
        name="Tada yesterday previous comparison",
        unit="kWh",
        scale_percent=False,
        device_name=DEVICE_NAME_YESTERDAY,
        device_id_suffix=DEVICE_SUFFIX_YESTERDAY,
        translation_key="tada_comparison_yesterday_previous_kwh",
    ))

    # Add optional extra last-* period sensors based on options
    extra_periods = [
        ("last-week", "last_week", "monitor_last_week", "Last week"),
        ("last-7-days", "last_7_days", "monitor_last_7_days", "Last 7 days"),
        ("last-month", "last_month", "monitor_last_month", "Last month"),
        ("last-30-days", "last_30_days", "monitor_last_30_days", "Last 30 days"),
        ("last-year", "last_year", "monitor_last_year", "Last year"),
        ("last-365-days", "last_365_days", "monitor_last_365_days", "Last 365 days"),
    ]
    # Cleanup is centralized in __init__.py options listener; avoid duplicate cleanup here.

    # Add selected period devices/entities
    for period_param, key_suffix, opt_name, label in extra_periods:
        if not opts.get(opt_name):
            continue
        dev_name = f"Tada {label}"
        dev_suffix = key_suffix
        # total sensor
        entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, key_suffix, label, device_name=dev_name, device_id_suffix=dev_suffix))
        # timebands split sensors (4 bands x 2 modes = 8 sensors)
        for band in ("notte", "mattina", "pomeriggio", "sera"):
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key_suffix, band, "value", device_name=dev_name, device_id_suffix=dev_suffix))
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key_suffix, band, "percentage", device_name=dev_name, device_id_suffix=dev_suffix))
        # comparison sensors for periods that expose comparisons
        comparison_periods = {"last_week", "last_7_days"}
        if key_suffix in comparison_periods:
            entities.append(TadaComparisonValueSensor(
                coordinator,
                subscription_id,
                source_key=f"comparisons_average_{key_suffix}",
                value_key="averageEnergyComparison",
                name=f"Tada {label} average comparison",
                unit="%",
                scale_percent=True,
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_comparison_{key_suffix}_average_percent",
            ))
            entities.append(TadaComparisonValueSensor(
                coordinator,
                subscription_id,
                source_key=f"comparisons_previous_{key_suffix}",
                value_key="previousEnergyComparison",
                name=f"Tada {label} previous comparison",
                unit="%",
                scale_percent=True,
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_comparison_{key_suffix}_previous_percent",
            ))
        # annual-reference sensors for supported periods
        annual_ref_periods = {"last_month", "last_30_days", "last_year", "last_365_days"}
        if key_suffix in annual_ref_periods:
            entities.append(TadaAnnualReferenceSensor(
                coordinator,
                subscription_id,
                source_key=f"annual_reference_{key_suffix}",
                name=f"Tada {label} annual reference",
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_annual_reference_{key_suffix}",
            ))

        # Summary sensors (appliances/activities) if enabled for this period
        if opts.get(f"summary_{key_suffix}"):
            selected_appliances = _parse_ids(opts.get("enabled_appliances"))
            selected_activities = _parse_ids(opts.get("enabled_activities"))
            present_appliances = _present_ids_from_summary(coordinator, key_suffix, "appliance")
            present_activities = _present_ids_from_summary(coordinator, key_suffix, "activity")
            enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
            enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
            _add_summary_entities(entities, coordinator, subscription_id, key_suffix, dev_name, dev_suffix, enabled_appliances, enabled_activities)
    if monitor_custom and custom_from and custom_to:
        key = f"custom_{custom_from}_{custom_to}"
        label = f"{custom_from}..{custom_to}"
        dev_name = f"Tada {label}"
        dev_suffix = key
        # coverage sensor attached to Today device (diagnostic/general)
        entities.append(PeriodCoverageTimestampSensor(coordinator, subscription_id, key, label, device_name=DEVICE_NAME_TODAY, device_id_suffix=DEVICE_SUFFIX_TODAY))
        # custom period sensors: total and timeband splits
        entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, key, label, device_name=dev_name, device_id_suffix=dev_suffix))
        for band in ("notte", "mattina", "pomeriggio", "sera"):
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key, band, "value", device_name=dev_name, device_id_suffix=dev_suffix))
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key, band, "percentage", device_name=dev_name, device_id_suffix=dev_suffix))

        # Custom summary sensors if enabled
        if opts.get("summary_custom"):
            selected_appliances = _parse_ids(opts.get("enabled_appliances"))
            selected_activities = _parse_ids(opts.get("enabled_activities"))
            present_appliances = _present_ids_from_summary(coordinator, key, "appliance")
            present_activities = _present_ids_from_summary(coordinator, key, "activity")
            enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
            enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
            _add_summary_entities(entities, coordinator, subscription_id, key, dev_name, dev_suffix, enabled_appliances, enabled_activities)

    # Yesterday summary sensors if enabled
    if opts.get("summary_yesterday"):
        key_suffix = "yesterday"
        selected_appliances = _parse_ids(opts.get("enabled_appliances"))
        selected_activities = _parse_ids(opts.get("enabled_activities"))
        present_appliances = _present_ids_from_summary(coordinator, key_suffix, "appliance")
        present_activities = _present_ids_from_summary(coordinator, key_suffix, "activity")
        enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
        enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
        _add_summary_entities(entities, coordinator, subscription_id, key_suffix, DEVICE_NAME_YESTERDAY, DEVICE_SUFFIX_YESTERDAY, enabled_appliances, enabled_activities)

    async_add_entities(entities, update_before_add=True)