from typing import Optional
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from .const import DOMAIN, DEVICE_NAME_BASE, DEVICE_NAME_TODAY, DEVICE_NAME_YESTERDAY, DEVICE_SUFFIX_BASE, DEVICE_SUFFIX_TODAY, DEVICE_SUFFIX_YESTERDAY
from .mapping import SUMMARY_PERIODS
from .utils import _monitored_periods

def _period_entities(coordinator, subscription_id: str, key: str, device_name: str, device_id_suffix: str, label: Optional[str] = None) -> list[BinarySensorEntity]:
    """Create the three diagnostics entities for a given period key."""
    return [
        TadaPeriodValidBinary(coordinator, subscription_id, key, label=label, device_name=device_name, device_id_suffix=device_id_suffix),
        TadaPeriodReliableBinary(coordinator, subscription_id, key, label=label, device_name=device_name, device_id_suffix=device_id_suffix),
        TadaPeriodFullCoverageBinary(coordinator, subscription_id, key, label=label, device_name=device_name, device_id_suffix=device_id_suffix),
    ]

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN]
    coordinator = data["coordinator"]
    subscription_id = entry.data["subscription_id"]

    opts = entry.options or {}
    monitor_custom = opts.get("monitor_custom", False)
    custom_from = opts.get("custom_from")
    custom_to = opts.get("custom_to")

    entities: list[BinarySensorEntity] = []

    # Yesterday diagnostics
    entities.extend(_period_entities(coordinator, subscription_id, "yesterday", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY, label="yesterday"))

    # Extra monitored periods
    for key_suffix, label in _monitored_periods(opts):
        entities.extend(_period_entities(coordinator, subscription_id, key_suffix, device_name=label, device_id_suffix=key_suffix, label=key_suffix))

    # Custom period diagnostics if enabled
    if monitor_custom and custom_from and custom_to:
        key = f"custom_{custom_from}_{custom_to}"
        dev_name = f"Tada {custom_from}..{custom_to}"
        entities.extend(_period_entities(coordinator, subscription_id, key, device_name=dev_name, device_id_suffix=key, label=f"{custom_from}..{custom_to}"))

    # Base Tada device diagnostics: subscription status
    entities.append(TadaSubscriptionOnlineBinary(coordinator, subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    # Today device diagnostics: power meter status
    entities.append(TadaPowerMeterStatusBinary(coordinator, subscription_id, device_name=DEVICE_NAME_TODAY, device_id_suffix=DEVICE_SUFFIX_TODAY))

    async_add_entities(entities, update_before_add=True)

class TadaPeriodBinary(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, subscription_id, key, label: Optional[str] = None, device_name: str = "Tada", device_id_suffix: str = "default"):
        super().__init__(coordinator)
        self._subscription_id = subscription_id
        self._key = key
        self._label = label or key
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")}, name=device_name)

class TadaPeriodValidBinary(TadaPeriodBinary):
    def __init__(self, coordinator, subscription_id, key, label: Optional[str] = None, device_name: str = "Tada", device_id_suffix: str = "default"):
        super().__init__(coordinator, subscription_id, key, label, device_name, device_id_suffix)
        self._attr_name = f"Tada Period Valid ({self._label})"
        self._attr_unique_id = f"tada_{subscription_id}_period_valid_{key}"
        self._attr_translation_key = f"tada_period_valid_{key}"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return None
        checks = self.coordinator.data.get("period_checks", {})
        v = checks.get(self._key, {})
        return bool(v.get("valid"))

class TadaPeriodReliableBinary(TadaPeriodBinary):
    def __init__(self, coordinator, subscription_id, key, label: Optional[str] = None, device_name: str = "Tada", device_id_suffix: str = "default"):
        super().__init__(coordinator, subscription_id, key, label, device_name, device_id_suffix)
        self._attr_name = f"Tada Period Reliable ({self._label})"
        self._attr_unique_id = f"tada_{subscription_id}_period_reliable_{key}"
        self._attr_translation_key = f"tada_period_reliable_{key}"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return None
        checks = self.coordinator.data.get("period_checks", {})
        v = checks.get(self._key, {})
        return bool(v.get("reliable"))

class TadaPeriodFullCoverageBinary(TadaPeriodBinary):
    def __init__(self, coordinator, subscription_id, key, label: Optional[str] = None, device_name: str = "Tada", device_id_suffix: str = "default"):
        super().__init__(coordinator, subscription_id, key, label, device_name, device_id_suffix)
        self._attr_name = f"Tada Period Full Coverage ({self._label})"
        self._attr_unique_id = f"tada_{subscription_id}_period_full_coverage_{key}"
        self._attr_translation_key = f"tada_period_full_coverage_{key}"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return None
        checks = self.coordinator.data.get("period_checks", {})
        v = checks.get(self._key, {})
        return bool(v.get("hasFullCoverage"))

class TadaSubscriptionOnlineBinary(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, subscription_id, device_name: str = "Tada", device_id_suffix: str = "base"):
        super().__init__(coordinator)
        self._subscription_id = subscription_id
        self._attr_name = "Tada Subscription Online"
        self._attr_unique_id = f"tada_{subscription_id}_subscription_online"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")}, name=device_name)
        self._attr_translation_key = "tada_subscription_online"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("subscription_status", {})
        return str(status.get("status", "")).upper() == "ONLINE"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {"status": None}
        status = self.coordinator.data.get("subscription_status", {})
        return {"status": status.get("status")}

class TadaPowerMeterStatusBinary(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, subscription_id, device_name: str = "Tada Today", device_id_suffix: str = "today"):
        super().__init__(coordinator)
        self._subscription_id = subscription_id
        self._attr_name = "Tada Power Meter OK"
        self._attr_unique_id = f"tada_{subscription_id}_power_meter_ok"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")}, name=device_name)
        self._attr_translation_key = "tada_power_meter_ok"

    @property
    def is_on(self):
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("power_meter_status", {})
        return str(status.get("status", "")).upper() == "OK"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data:
            return {"status": None}
        status = self.coordinator.data.get("power_meter_status", {})
        return {"status": status.get("status")}
