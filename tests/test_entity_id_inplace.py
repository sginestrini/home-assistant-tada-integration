"""Tests for in-place entity_id changes (issue #1).

The sensors that define lifecycle methods (async_added_to_hass /
async_will_remove_from_hass) opt in to HA 2026.11's in-place entity_id
change by defining async_entity_id_changed. On test stacks older than
HA 2026.11 the hook is never called and renames still remove+re-add the
entity, so the behavioural tests are guarded by a capability check; the
opt-in itself (hook present, synchronous, on the owning class) is
asserted on every stack.
"""
import inspect
import logging

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.tada.const import DOMAIN
from custom_components.tada.sensor.consumption import (
    TadaConsumptionTodayHourlySensor,
    TadaLifetimeEnergySensor,
)
from custom_components.tada.sensor.power import TadaInstantPowerSensor
from custom_components.tada.sensor.summary import TadaSummaryItemSensor

# Classes that define lifecycle methods and therefore need the opt-in hook.
OPTED_IN_CLASSES = [
    pytest.param(TadaInstantPowerSensor, id="instant-power"),
    pytest.param(TadaConsumptionTodayHourlySensor, id="hourly"),
    pytest.param(TadaLifetimeEnergySensor, id="lifetime"),
]

# Classes with no lifecycle methods must already be in-place and must NOT
# carry a hook (guards against re-introducing enforcement-era code).
LIFECYCLE_FREE_CLASSES = [
    pytest.param(TadaSummaryItemSensor, id="summary-item"),
]

LIFECYCLE_METHODS = (
    "async_prepare_to_add_to_hass",
    "async_added_to_hass",
    "async_will_remove_from_hass",
)

needs_in_place = pytest.mark.skipif(
    not hasattr(Entity, "async_entity_id_changed"),
    reason="Entity base lacks async_entity_id_changed (HA < 2026.11): "
    "renames still remove and re-add the entity",
)


def _make_coordinator(hass, config_entry, data=None):
    kwargs = {}
    # HA >= 2025.x requires the config entry explicitly (ContextVar fallback
    # is a hard error there); older pinned HA does not know the kwarg.
    if "config_entry" in inspect.signature(DataUpdateCoordinator.__init__).parameters:
        kwargs["config_entry"] = config_entry
    coordinator = DataUpdateCoordinator(
        hass, logging.getLogger(DOMAIN), name="tada", **kwargs
    )
    coordinator.data = data or {}
    coordinator.last_update_success = True
    return coordinator


def _make_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN, title="Tada", data={"subscription_id": "sub_123"},
        entry_id="01TESTTADAENTITYID0000000000",
    )
    entry.add_to_hass(hass)
    return entry


async def _add_entity(hass, entity, suggested_object_id):
    from pytest_homeassistant_custom_component.common import MockEntityPlatform

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    reg = er.async_get(hass)
    reg.async_get_or_create(
        "sensor", DOMAIN, entity._attr_unique_id,
        config_entry=entry, suggested_object_id=suggested_object_id,
    )
    platform = MockEntityPlatform(hass, domain="sensor", platform_name="tada")
    platform.config_entry = entry
    await platform.async_add_entities([entity])
    return entity.entity_id


@pytest.mark.parametrize("cls", OPTED_IN_CLASSES)
def test_classes_define_opt_in_hook(cls):
    """Each lifecycle-defining class opts in on its OWN class (HA checks
    per-class in the MRO, a hook on a base would not cover subclasses)."""
    hook = cls.__dict__.get("async_entity_id_changed")
    assert hook is not None, f"{cls.__name__} must define async_entity_id_changed itself"
    assert not inspect.iscoroutinefunction(hook), "async_entity_id_changed must be a @callback"


@pytest.mark.parametrize("cls", LIFECYCLE_FREE_CLASSES)
def test_lifecycle_free_classes_need_no_hook(cls):
    mro = [c for c in cls.__mro__ if c.__module__.startswith("custom_components.")]
    assert mro, "expected integration-owned classes in the MRO"
    assert not any(
        any(m in c.__dict__ for m in LIFECYCLE_METHODS) for c in mro
    ), f"{cls.__name__} must stay free of add/remove lifecycle overrides"


@needs_in_place
async def test_instant_power_rename_keeps_dispatcher_subscription(hass):
    entry = _make_entry(hass)
    sensor = TadaInstantPowerSensor(hass, "sub_123")
    old_entity_id = await _add_entity(hass, sensor, "tada_instant_power")
    unsub_before = sensor._unsub
    assert callable(unsub_before)

    er.async_get(hass).async_update_entity(old_entity_id, new_entity_id="sensor.potenza_istantanea")
    await hass.async_block_till_done()

    assert sensor.entity_id == "sensor.potenza_istantanea"
    # In place: not removed/re-added, so the dispatcher subscription is the
    # same callable (a re-add would rebuild it in async_added_to_hass).
    assert sensor._unsub is unsub_before

    from homeassistant.helpers.dispatcher import async_dispatcher_send

    async_dispatcher_send(hass, "tada_instant_power", 1234)
    await hass.async_block_till_done()
    assert sensor.native_value == 1234
    assert hass.states.get("sensor.potenza_istantanea").state == "1234"


@needs_in_place
async def test_hourly_rename_keeps_quiet_window_triggers(hass):
    entry = _make_entry(hass)
    coordinator = _make_coordinator(hass, entry)
    sensor = TadaConsumptionTodayHourlySensor(
        coordinator, "sub_123",
        quiet_window_enabled=True, quiet_window_from="01:00", quiet_window_to="05:00",
    )
    old_entity_id = await _add_entity(hass, sensor, "tada_consumption_today")
    assert sensor._quiet_start_unsub is not None
    start_unsub_before = sensor._quiet_start_unsub
    end_unsub_before = sensor._quiet_end_unsub

    er.async_get(hass).async_update_entity(old_entity_id, new_entity_id="sensor.consumi_odierani")
    await hass.async_block_till_done()

    assert sensor.entity_id == "sensor.consumi_odierani"
    # Same unsubscribe handles: triggers were never cancelled and recreated.
    assert sensor._quiet_start_unsub is start_unsub_before
    assert sensor._quiet_end_unsub is end_unsub_before
    assert hass.states.get("sensor.consumi_odierani") is not None


@needs_in_place
async def test_lifetime_rename_keeps_store_and_state(hass):
    entry = _make_entry(hass)
    coordinator = _make_coordinator(hass, entry, {
        "consumption_today": {"data": [{"hour": 10, "kWh": "1.5", "W": 300, "label": "10"}]},
    })
    sensor = TadaLifetimeEnergySensor(coordinator, "sub_123")
    old_entity_id = await _add_entity(hass, sensor, "tada_total_energy")
    assert sensor._store is not None
    store_before = sensor._store

    er.async_get(hass).async_update_entity(old_entity_id, new_entity_id="sensor.totale_vita")
    await hass.async_block_till_done()

    assert sensor.entity_id == "sensor.totale_vita"
    # Store (keyed on subscription_id) survived the rename untouched.
    assert sensor._store is store_before

    # A later coordinator update writes state under the new entity_id.
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get("sensor.totale_vita")
    assert state is not None
    assert state.state != "unavailable"
