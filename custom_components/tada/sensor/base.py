from __future__ import annotations
import logging
from typing import Any, Iterable, Tuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from ..const import DOMAIN, MANUFACTURER, MODEL

_LOGGER = logging.getLogger(__name__)


class TadaBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Tada integration."""

    _attr_has_entity_name = True

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
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
