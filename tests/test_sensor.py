import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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

    # Patch the coordinator's update method to return our controlled data
    with patch(
        "custom_components.tada.__init__.async_setup_entry",
        wraps=None,
    ):
        pass  # Just checking import works

    # The cleanest approach: mock the entire update_data coroutine passed to the coordinator
    async def mock_async_update_data():
        return MOCK_COORDINATOR_DATA

    with patch(
        "custom_components.tada.TadaAPI.login", new_callable=AsyncMock
    ), patch(
        "custom_components.tada.ws.TadaWSClient.start", new_callable=AsyncMock
    ), patch(
        "custom_components.tada.DataUpdateCoordinator._async_refresh",
        new_callable=AsyncMock,
        return_value=None,
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data=mock_config_entry_data,
            options={},
        )
        entry.add_to_hass(hass)

        # Manually inject coordinator data by patching async_config_entry_first_refresh
        with patch(
            "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_config_entry_first_refresh",
            new_callable=AsyncMock,
        ) as mock_refresh:
            # After integration sets up coordinator, we inject the data
            async def side_effect(coordinator=None):
                from custom_components.tada import DOMAIN as TADA_DOMAIN
                # Walk through hass.data to find coordinator once integration registers it
                pass

            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

            # Manually set coordinator data and trigger update
            coordinator = hass.data[DOMAIN]["coordinator"]
            coordinator.data = MOCK_COORDINATOR_DATA
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
