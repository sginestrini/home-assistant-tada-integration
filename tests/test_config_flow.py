import pytest
from unittest.mock import patch
from homeassistant import data_entry_flow
from homeassistant.config_entries import SOURCE_USER, SOURCE_REAUTH
from custom_components.tada.const import DOMAIN
from custom_components.tada.api import AuthError

@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.tada.async_setup_entry",
        return_value=True,
    ):
        yield

async def test_form_shows(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

async def test_user_authentication_success(hass, mock_tada_api_login, mock_user_input):
    """Test we create an entry on successful login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Submit valid data
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        mock_user_input,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Tada"
    assert result2["data"]["username"] == "test_user"
    assert result2["data"]["password"] == "test_password"
    assert result2["data"]["subscription_id"] == "sub_12345"
    assert result2["data"]["locale"] == "it"
    assert "client_id" in result2["data"]

async def test_user_authentication_failure(hass, mock_user_input):
    """Test we show the form again on AuthError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Force AuthError on login
    with patch(
        "custom_components.tada.api.TadaAPI.login",
        side_effect=AuthError("Invalid credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            mock_user_input,
        )

    # Ensure it returns to form with error
    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "auth_failed"}

async def test_reauth_flow(hass, mock_tada_api_login, mock_config_entry_data):
    """Test reauth flow."""
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        unique_id="test_user"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit valid data back
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test_user",
            "password": "new_password",
            "subscription_id": "sub_12345",
            "locale": "it"
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data["password"] == "new_password"

async def test_options_flow(hass):
    """Test options flow."""
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "password", "subscription_id": "sub"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            "monitor_last_week": True,
            "monitor_custom": False,
            "quiet_window_enabled": True,
            "quiet_window_from": "22:00",
            "quiet_window_to": "06:00"
        },
    )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["data"]["monitor_last_week"] == True
    assert result2["data"]["quiet_window_enabled"] == True
    assert result2["data"]["quiet_window_from"] == "22:00"
