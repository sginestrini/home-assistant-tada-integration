from __future__ import annotations
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ..const import DOMAIN, MANUFACTURER, MODEL
from ..mapping import APPLIANCES_MAP, ACTIVITIES_MAP, slugify
from ..utils import _to_float
from .base import TadaBaseSensor

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
            "manufacturer": MANUFACTURER,
            "model": MODEL,
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
