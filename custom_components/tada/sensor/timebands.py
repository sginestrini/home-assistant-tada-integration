from __future__ import annotations
import logging

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import DOMAIN, MANUFACTURER, MODEL
from ..utils import _to_float, _round_safe
from .base import TadaBaseSensor

_LOGGER = logging.getLogger(__name__)


class TadaTimebandsSensor(TadaBaseSensor):
    """Timebands breakdown sensor for arbitrary period."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        subscription_id: str,
        period_key: str,
        label: str,
        device_name: str = "Tada",
        device_id_suffix: str = "default",
    ):
        name = f"Total {label}"
        unique_id = f"tada_timebands_{period_key}_{subscription_id}"
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
        name = f"{period_key} {band_slug} {mode}"
        unique_id = f"tada_timeband_{period_key}_{band_slug}_{mode}_{subscription_id}"
        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
