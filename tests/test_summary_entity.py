"""Tests for TadaSummaryItemSensor registration/lifecycle (issue #1).

Covers: entity-safe suggested object_id naming at registration,
coordinator-listener wiring after add, and that a user rename of the
entity is NOT reverted (the forced rename in async_added_to_hass was
removed ahead of HA's in-place entity_id change).
"""
import inspect
import logging

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.tada.const import DOMAIN
from custom_components.tada.sensor.summary import TadaSummaryItemSensor

# (appliance id, display label, expected object-id slug)
# The hyphen case guards labels like 'Stand-by': entity ids must not contain hyphens.
LABEL_CASES = [
    pytest.param(1, "Lavatrice", "lavatrice", id="lavatrice"),
    pytest.param(17, "Stand-by", "stand_by", id="hyphen-label"),
]


def _make_sensor(hass, config_entry, appliance_id, label):
    kwargs = {}
    # HA >= 2025.x requires the config entry explicitly (ContextVar fallback is
    # a hard error there); the HA pinned for py3.11 does not know the kwarg.
    if "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters:
        kwargs["config_entry"] = config_entry
    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(DOMAIN), name="tada", **kwargs
    )
    coordinator.data = {
        "summary_yesterday": {
            "data": {"appliances": [{"applianceId": appliance_id, "value": 2.5, "percentage": 33.3}]}
        }
    }
    coordinator.last_update_success = True
    return TadaSummaryItemSensor(
        coordinator, "sub_123", "yesterday", "appliance", appliance_id, "value", label,
        device_name="Tada", device_id_suffix="default",
    )


def _make_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    # entry_id must be ULID-shaped to satisfy MockConfigEntry validation
    entry = MockConfigEntry(
        domain=DOMAIN, title="Tada", data={"subscription_id": "sub_123"},
        entry_id="01TESTTADASUMMARY000000000",
    )
    entry.add_to_hass(hass)
    return entry


async def _add_entity(hass, entry, entity):
    from pytest_homeassistant_custom_component.common import MockEntityPlatform
    platform = MockEntityPlatform(hass, domain="sensor", platform_name="tada")
    platform.config_entry = entry
    await platform.async_add_entities([entity])


@pytest.mark.parametrize("appliance_id,label,object_slug", LABEL_CASES)
async def test_summary_sensor_naming_and_rename(hass, entity_registry, appliance_id, label, object_slug):
    entry = _make_entry(hass)
    sensor = _make_sensor(hass, entry, appliance_id, label)

    # naming is derived from the label and entity-safe (no hyphens)
    assert sensor._attr_suggested_object_id == f"tada_yesterday_elettrodomestici_{object_slug}_kwh"

    # simulate first registration: pre-create the registry entry from the
    # suggested object_id, as HA (>=2024.10, honoring the suggestion) does
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "sensor", DOMAIN, sensor._attr_unique_id,
        suggested_object_id=sensor._attr_suggested_object_id,
    )

    await _add_entity(hass, entry, sensor)
    assert sensor.entity_id == f"sensor.tada_yesterday_elettrodomestici_{object_slug}_kwh"
    # coordinator listener wiring works: an update reaches entity + state machine
    sensor.coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert sensor.native_value == 2.5
    assert hass.states.get(sensor.entity_id).state == "2.5"

    # a user rename must stick (no enforcement revert)
    er.async_get(hass).async_update_entity(sensor.entity_id, new_entity_id="sensor.mio_nome")
    await hass.async_block_till_done()
    assert sensor.entity_id == "sensor.mio_nome"

    # a later coordinator update must not bounce the name back
    sensor.coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert sensor.entity_id == "sensor.mio_nome"
    assert hass.states.get("sensor.mio_nome").state == "2.5"
