from __future__ import annotations
from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER, MODEL, DEVICE_NAME_YESTERDAY, DEVICE_SUFFIX_YESTERDAY
from .mapping import SUMMARY_PERIODS
from .utils import _monitored_periods, tk_summary_switch

class TadaSummarySwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        subscription_id: str,
        period_key: str,  # yesterday | last_week | last_7_days | last_month | last_30_days | last_year | last_365_days | custom_...
        device_name: str,
        device_id_suffix: str,
    ):
        super().__init__(coordinator)
        self.hass = hass
        self._entry = entry
        self._subscription_id = subscription_id
        self._period_key = period_key
        self._attr_name = f"Enable Summary ({period_key})"
        self._attr_unique_id = f"tada_{subscription_id}_summary_switch_{period_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{subscription_id}:{device_id_suffix}")},
            name=device_name,
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        self._attr_icon = "mdi:toggle-switch"
        self._attr_entity_category = EntityCategory.CONFIG
        # translation key for switch label
        try:
            self._attr_translation_key = tk_summary_switch(period_key)
        except Exception:
            pass

    @property
    def is_on(self) -> bool:
        # Custom summary uses a single flag "summary_custom"
        if str(self._period_key).startswith("custom_"):
            return bool(self._entry.options.get("summary_custom", False))
        return bool(self._entry.options.get(f"summary_{self._period_key}", False))

    async def async_turn_on(self, **kwargs):
        opts = dict(self._entry.options)
        if str(self._period_key).startswith("custom_"):
            opts["summary_custom"] = True
        else:
            opts[f"summary_{self._period_key}"] = True
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        # Options listener will handle reload

    async def async_turn_off(self, **kwargs):
        opts = dict(self._entry.options)
        if str(self._period_key).startswith("custom_"):
            opts["summary_custom"] = False
        else:
            opts[f"summary_{self._period_key}"] = False
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        # Options listener will handle reload

    @property
    def extra_state_attributes(self):
        # Provide a visible warning/estimate in the more-info panel
        desc = (
            "Enabling summary creates many sensors for this period ("
            "two per item in Appliances and Activities)."
        )
        attrs: dict[str, Any] = {
            "warning": desc,
            "period": self._period_key,
        }
        return attrs

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: DataUpdateCoordinator = entry.runtime_data.coordinator
    subscription_id = entry.data.get("subscription_id")
    if not coordinator or not subscription_id:
        return

    entities: list[SwitchEntity] = []

    # Yesterday summary switch
    entities.append(TadaSummarySwitch(hass, coordinator, entry, subscription_id, "yesterday", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))

    # Extra monitored period switches
    opts = entry.options or {}
    for key_suffix, label in _monitored_periods(opts):
        entities.append(TadaSummarySwitch(hass, coordinator, entry, subscription_id, key_suffix, device_name=label, device_id_suffix=key_suffix))

    # Custom period summary switch
    monitor_custom = opts.get("monitor_custom", False)
    custom_from = opts.get("custom_from")
    custom_to = opts.get("custom_to")
    if monitor_custom and custom_from and custom_to:
        custom_key = f"custom_{custom_from}_{custom_to}"
        dev_name = f"Tada {custom_from}..{custom_to}"
        entities.append(TadaSummarySwitch(hass, coordinator, entry, subscription_id, custom_key, device_name=dev_name, device_id_suffix=custom_key))

    async_add_entities(entities, update_before_add=True)
