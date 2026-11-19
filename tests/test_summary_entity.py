"""Tests for TadaSummaryItemSensor registration/lifecycle (issue #1).

Covers: suggested object_id naming at registration, coordinator-listener
wiring after add, and that a user rename of the entity is NOT reverted
(the forced rename in async_added_to_hass was removed for the HA
2026.11+ in-place entity_id change).
"""
import logging

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.tada.const import DOMAIN
from custom_components.tada.sensor.summary import TadaSummaryItemSensor


async def _make_sensor(hass):
    coordinator = DataUpdateCoordinator(hass, logging.getLogger(DOMAIN), name="tada")
    coordinator.data = {
        "summary_yesterday": {
            "data": {"appliances": [{"applianceId": 1, "value": 2.5, "percentage": 33.3}]}
        }
    }
    coordinator.last_update_success = True
    sensor = TadaSummaryItemSensor(
        coordinator, "sub_123", "yesterday", "appliance", 1, "value", "Lavatrice",
        device_name="Tada", device_id_suffix="default",
    )
    return sensor


async def _add_entity(hass, entity):
    from pytest_homeassistant_custom_component.common import MockConfigEntry, MockEntityPlatform
    entry = MockConfigEntry(
        domain=DOMAIN, title="Tada", data={"subscription_id": "sub_123"},
        entry_id="01TESTTADASUMMARY000000000",
    )
    entry.add_to_hass(hass)

    platform = MockEntityPlatform(hass, domain="sensor", platform_name="tada")
    platform.config_entry = entry
    await platform.async_add_entities([entity])
    return entry


async def test_summary_sensor_naming_and_rename(hass, entity_registry):
    sensor = await _make_sensor(hass)
    await _add_entity(hass, sensor)

    # 1) registration is stable and uses the label-derived naming
    #    (on HA>=2025 the suggested object_id "tada_yesterday_..." is used;
    #    on the pinned old test stack the name fallback kicks in)
    assert sensor.entity_id.endswith("elettrodomestici_lavatrice_kwh")

    # 2) coordinator listener wiring works: an update reaches entity + state machine
    sensor.coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert sensor.native_value == 2.5
    assert hass.states.get(sensor.entity_id).state == "2.5"

    # 3) a user rename must stick (no enforcement revert)
    er.async_get(hass).async_update_entity(sensor.entity_id, new_entity_id="sensor.lavatriceieri")
    await hass.async_block_till_done()
    assert sensor.entity_id == "sensor.lavatriceieri"

    # 4) a later coordinator update must not bounce the name back
    sensor.coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert sensor.entity_id == "sensor.lavatriceieri"
    assert hass.states.get("sensor.lavatriceieri").state == "2.5"
