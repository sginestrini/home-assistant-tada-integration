import pytest
from unittest.mock import patch

# This fixture enables the custom integration to be loaded by the testing framework
@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

# This fixture ensures we don't accidentally make real network calls
@pytest.fixture(autouse=True)
def prevent_real_network(requests_mock):
    """Prevent real network requests during testing."""
    pass

@pytest.fixture
def mock_config_entry_data():
    """Return mock configuration data for the integration."""
    return {
        "username": "test_user",
        "password": "test_password",
        "subscription_id": "sub_12345",
        "client_id": "test_client",
        "locale": "it"
    }

@pytest.fixture
def mock_tada_api_login():
    """Mock the login flow so we don't hit Cognito."""
    with patch(
        "custom_components.tada.api.TadaAPI.login",
        return_value=True,
    ) as mock_login, patch(
        "custom_components.tada.api.TadaAPI._ensure_token",
        return_value=None,
    ) as mock_ensure:
        yield mock_login, mock_ensure

@pytest.fixture
def mock_ws_client_start():
    """Mock the websocket client start to avoid connecting to real endpoints."""
    with patch(
        "custom_components.tada.ws.TadaWSClient.start",
        return_value=None,
    ) as mock_start:
        yield mock_start
