import pytest
from unittest.mock import patch, MagicMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.tada.const import DOMAIN

@pytest.fixture
def mock_api_data():
    """Mock the responses from TadaAPI for the coordinator."""
    with patch(
        "custom_components.tada.api.TadaAPI.get_power_latest", return_value={"value": 1.5, "availablePower": 3.0}
    ), patch(
        "custom_components.tada.api.TadaAPI.get_subscription_status", return_value={}
    ), patch(
        "custom_components.tada.api.TadaAPI.get_power_meter_status", return_value={}
    ), patch(
        "custom_components.tada.api.TadaAPI.get_consumption", return_value={"data": []}
    ), patch(
        "custom_components.tada.api.TadaAPI.get_power_events", return_value={
            "last30Days": {
                "alarmsCount": 5, "cutoffsCount": 1,
                "alarms": [{"date": "2026-03-01", "type": "alarm"}],
                "period": {"from": "2026-02-11", "to": "2026-03-13"},
                "hasMoreAlarms": False
            },
            "last90Days": {
                "alarmsCount": 10, "cutoffsCount": 3,
                "alarms": [],
                "period": {"from": "2025-12-13", "to": "2026-03-13"},
                "hasMoreAlarms": False
            }
        }
    ):
        yield

async def test_sensor_creation_and_state(
    hass: HomeAssistant,
    mock_config_entry_data,
    mock_tada_api_login,
    mock_ws_client_start,
    mock_api_data,
):
    """Test that the sensors are created correctly based on mocked API responses."""
    
    # Create the mock entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        options={}
    )
    entry.add_to_hass(hass)
    
    # Set up the integration
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Verify that the new power events sensors exist in the entity registry
    registry = er.async_get(hass)
    
    alarms_30_id = "sensor.tada_power_events_alarms_30_days"
    cutoffs_30_id = "sensor.tada_power_events_cutoffs_30_days"
    alarms_90_id = "sensor.tada_power_events_alarms_90_days"
    cutoffs_90_id = "sensor.tada_power_events_cutoffs_90_days"

    assert registry.async_is_registered(alarms_30_id)
    assert registry.async_is_registered(cutoffs_30_id)
    assert registry.async_is_registered(alarms_90_id)
    assert registry.async_is_registered(cutoffs_90_id)
    
    # Verify the states are pulled from the `mock_api_data` payload
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
