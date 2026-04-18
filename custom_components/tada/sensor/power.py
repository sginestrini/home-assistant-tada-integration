from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import DOMAIN, MANUFACTURER, MODEL
from .base import TadaBaseSensor

_LOGGER = logging.getLogger(__name__)


# Re-implement as a standalone SensorEntity (not CoordinatorEntity)
from homeassistant.components.sensor import SensorEntity


class TadaInstantPowerSensor(SensorEntity):
    """Websocket-driven instant power sensor using dispatcher."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, subscription_id: str, device_name: str = "Tada Today", device_id_suffix: str = "today"):
        self.hass = hass
        self._subscription_id = subscription_id
        self._attr_name = "Instant Power"
        self._attr_unique_id = "tada_instant_power"
        # attach to the same device as other sensors
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
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
        self._unsub = async_dispatcher_connect(
            self.hass, "tada_instant_power", self._handle_instant_power
        )

    async def async_will_remove_from_hass(self):
        if self._unsub:
            self._unsub()
            self._unsub = None


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
        # Format names like: Power Events Alarms 30 Days
        period_label = "30 Days" if period_key == "last30Days" else "90 Days"
        name = f"Power Events {event_type.capitalize()} {period_label}"
        unique_id = f"tada_power_events_{event_type}_{period_key}_{subscription_id}"

        device_info = {
            "identifiers": {(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            "name": device_name,
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
