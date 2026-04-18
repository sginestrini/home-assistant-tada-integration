from __future__ import annotations
import logging
from datetime import datetime

from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import DOMAIN, MANUFACTURER, MODEL
from ..utils import _parse_iso_to_dt
from .base import TadaBaseSensor

_LOGGER = logging.getLogger(__name__)


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
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,
        label: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        name = "Period Coverage Start"
        unique_id = f"tada_period_coverage_start_{subscription_id}_{period_key}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
