import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.tada.const import DOMAIN

# Minimal coordinator data that all sensors expect to find
MOCK_COORDINATOR_DATA = {
    "power_latest": {"value": 1.5, "availablePower": 3.0, "powerUsagePercent": 50, "maxAvailablePower": 6.0},
    "subscription_status": {"status": "active"},
    "power_meter_status": {"ok": True},
    "consumption_today": {"data": []},
    "energy_total": None,
    "consumption_yesterday": {"data": []},
    "historical_yesterday": {},
    "timebands_yesterday": {"data": []},
    "comparisons_average_yesterday": {},
    "comparisons_previous_yesterday": {},
    "period_checks": {"yesterday": {}},
    "power_events": {
        "last30Days": {
            "alarmsCount": 5,
            "cutoffsCount": 1,
            "alarms": [{"date": "2026-03-01", "type": "alarm"}],
            "cutoffs": [],
            "period": {"from": "2026-02-11", "to": "2026-03-13"},
            "hasMoreAlarms": False,
            "hasMoreCutoffs": False,
        },
        "last90Days": {
            "alarmsCount": 10,
            "cutoffsCount": 3,
            "alarms": [],
            "cutoffs": [],
            "period": {"from": "2025-12-13", "to": "2026-03-13"},
            "hasMoreAlarms": False,
            "hasMoreCutoffs": False,
        },
    },
}


async def test_sensor_creation_and_state(
    hass: HomeAssistant,
    mock_config_entry_data,
    mock_tada_api_login,
    mock_ws_client_start,
):
    """Test that the power event sensors are created and populated correctly."""

    async def mock_async_update_data():
        return MOCK_COORDINATOR_DATA

    # Patch DataUpdateCoordinator.__init__ to inject our mock update_method.
    # The coordinator is created BEFORE platforms are forwarded in __init__.py,
    # so this ensures async_config_entry_first_refresh populates coordinator.data.
    original_init = DataUpdateCoordinator.__init__

    def patched_duc_init(self, *args, **kwargs):
        kwargs["update_method"] = mock_async_update_data
        original_init(self, *args, **kwargs)

    with patch(
        "custom_components.tada.TadaAPI.login", new_callable=AsyncMock
    ), patch(
        "custom_components.tada.ws.TadaWSClient.start", new_callable=AsyncMock
    ), patch.object(
        DataUpdateCoordinator, "__init__", patched_duc_init
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data,
            options={},
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Entities are registered AFTER async_config_entry_first_refresh, so they
        # miss the first coordinator update signal. Trigger a second refresh now so
        # that _handle_coordinator_update fires on all registered sensor entities,
        # populating self._state from coordinator.data.
        coordinator = hass.data[DOMAIN]["coordinator"]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Verify that power events sensors exist in the entity registry
    registry = er.async_get(hass)

    alarms_30_id = "sensor.tada_power_events_alarms_30_days"
    cutoffs_30_id = "sensor.tada_power_events_cutoffs_30_days"
    alarms_90_id = "sensor.tada_power_events_alarms_90_days"
    cutoffs_90_id = "sensor.tada_power_events_cutoffs_90_days"

    assert registry.async_is_registered(alarms_30_id)
    assert registry.async_is_registered(cutoffs_30_id)
    assert registry.async_is_registered(alarms_90_id)
    assert registry.async_is_registered(cutoffs_90_id)

    # Verify states are populated from the mocked coordinator data
    state_alarms_30 = hass.states.get(alarms_30_id)
    assert state_alarms_30 is not None
    assert state_alarms_30.state == "5"
    assert state_alarms_30.attributes.get("events") == [{"date": "2026-03-01", "type": "alarm"}]

    state_cutoffs_30 = hass.states.get(cutoffs_30_id)
    assert state_cutoffs_30 is not None
    assert state_cutoffs_30.state == "1"

    state_alarms_90 = hass.states.get(alarms_90_id)
    assert state_alarms_90 is not None
    assert state_alarms_90.state == "10"

    state_cutoffs_90 = hass.states.get(cutoffs_90_id)
    assert state_cutoffs_90 is not None
    assert state_cutoffs_90.state == "3"
