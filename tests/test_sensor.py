import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.tada.const import DOMAIN

# Minimal coordinator data that all sensors expect to find
MOCK_COORDINATOR_DATA = {
    "power_latest": {"__time":"2026-03-24T18:14:55.000Z", "value": 0.23, "availablePower": 4.5, "powerUsagePercent": 5, "maxAvailablePower": 5.985},
    "subscription_status": {"status": "active"},
    "power_meter_status": {"ok": True},
    "consumption_today": {"data": [{"hour":0,"W":95.07,"kWh":0.08,"label":"0-1 h"}], "lastDetection": {"time": "2026-03-24T18:14:55.000Z"}},
    "energy_total": {"total": 14.43},
    "consumption_yesterday": {"data": []},
    "historical_yesterday": {"data": {"date": "23 marzo 2026", "total": 4.47, "topAppliances": [{"applianceId": 6, "value": 0.67, "percentage": 14.99}]}},
    "timebands_yesterday": {"data": []},
    "comparisons_average_yesterday": {"averageEnergyComparison": -0.05},
    "comparisons_previous_yesterday": {"previousEnergyComparison": -4.48},
    "period_checks": {"yesterday": {"valid": True, "reliable": True, "hasFullCoverage": True, "coverageStartDate": "2025-09-01T00:00:00.000Z"}},
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
        coordinator = entry.runtime_data.coordinator
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
    # Verify general power values are populated
    power_value_id = "sensor.tada_current_power"
    power_state = hass.states.get(power_value_id)
    assert power_state is not None
    assert power_state.state == "0.23"
    
    usage_percent_id = "sensor.tada_power_usage"
    usage_state = hass.states.get(usage_percent_id)
    assert usage_state is not None
    assert usage_state.state == "5"

    max_power_id = "sensor.tada_max_available_power"
    max_state = hass.states.get(max_power_id)
    assert max_state is not None
    assert max_state.state == "5.985"
    
    # Verify consumption-today-hourly
    today_cons_id = "sensor.tada_today_consumption_today"
    today_state = hass.states.get(today_cons_id)
    assert today_state is not None
    assert today_state.state == "0.08"
    assert today_state.attributes.get("hour_0_kWh") == 0.08
    
    # Verify comparison average
    cmp_avg_id = "sensor.tada_yesterday_yesterday_average_comparison"
    cmp_avg_state = hass.states.get(cmp_avg_id)
    assert cmp_avg_state is not None
    assert cmp_avg_state.state == "-5.0"
    
    # Verify coverage state
    cov_id = "sensor.tada_period_coverage_start"
    cov_state = hass.states.get(cov_id)
    assert cov_state is not None
    assert cov_state.state == "2025-09-01T00:00:00+00:00"
