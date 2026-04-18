import sys
import pytest
from unittest.mock import patch

# On Windows, ProactorEventLoop needs socket.socketpair() (AF_INET) for its
# internal wakeup mechanism. pytest-socket blocks ALL socket creation which
# breaks the event loop before any test even runs. Neutralize it on Windows;
# tests still use aioresponses / requests_mock for network mocking.
if sys.platform == "win32":
    import pytest_socket
    pytest_socket.disable_socket = lambda *args, **kwargs: None

    # aiodns (c-ares) requires SelectorEventLoop on Windows.
    # HassEventLoopPolicy inherits DefaultEventLoopPolicy which uses
    # ProactorEventLoop. Override the loop factory to use SelectorEventLoop.
    import asyncio
    from homeassistant.runner import HassEventLoopPolicy
    HassEventLoopPolicy._loop_factory = asyncio.SelectorEventLoop

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
    """Return mock configuration data for the integration (full entry data)."""
    return {
        "username": "test_user",
        "password": "test_password",
        "subscription_id": "sub_12345",
        "client_id": "test_client",
        "locale": "it"
    }

@pytest.fixture
def mock_user_input():
    """Return mock user input for the config flow (no client_id — added by flow)."""
    return {
        "username": "test_user",
        "password": "test_password",
        "subscription_id": "sub_12345",
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
    ) as mock_ensure, patch(
        "custom_components.tada.api.TadaAPI.ensure_authenticated",
        return_value=None,
    ):
        yield mock_login, mock_ensure

@pytest.fixture
def mock_ws_client_start():
    """Mock the websocket client start to avoid connecting to real endpoints."""
    with patch(
        "custom_components.tada.ws.TadaWSClient.start",
        return_value=None,
    ) as mock_start:
        yield mock_start
