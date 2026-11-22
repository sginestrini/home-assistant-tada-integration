"""Tests for TadaAPI REST/auth behaviour.

Uses the phcc-native ``aioclient_mock`` fixture (it patches
homeassistant.helpers.aiohttp_client sessions) instead of aioresponses,
which cannot build aiohttp>=3.11 ClientResponse objects (its last
release predates that change).
"""
import pytest
from homeassistant.helpers import aiohttp_client

from custom_components.tada.api import TadaAPI, AuthError, COGNITO_URL

API = "https://webapp.tada.magie-tada.com/api"


@pytest.fixture
def session(hass, aioclient_mock):
    """ClientSession bound to aioclient_mock (only these sessions are intercepted)."""
    return aiohttp_client.async_get_clientsession(hass)


def _authed_api(session, locale="it"):
    """TadaAPI pre-authenticated with a fixed ID token and far-future expiry."""
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123", locale=locale)
    api._id_token = "valid_token"
    api._token_exp_ts = float("inf")
    return api


async def test_login_success(session, aioclient_mock):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")

    aioclient_mock.post(
        COGNITO_URL,
        json={
            "AuthenticationResult": {
                "IdToken": "id_123",
                "AccessToken": "acc_123",
                "RefreshToken": "ref_123",
                "ExpiresIn": 3600
            }
        }
    )

    result = await api.login()
    assert result is True
    assert api._id_token == "id_123"
    assert api._refresh_token == "ref_123"


async def test_login_failure(session, aioclient_mock):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")

    aioclient_mock.post(COGNITO_URL, status=400, json={"message": "Invalid credentials"})

    with pytest.raises(AuthError):
        await api.login()


async def test_get_power_events(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {
        "last30Days": {
            "period": {"from": "2026-02-22T17:16:25.693Z", "to": "2026-03-24T17:16:25.693Z"},
            "alarms": [], "cutoffs": [],
            "alarmsCount": 5, "cutoffsCount": 1,
            "hasMoreAlarms": False, "hasMoreCutoffs": False
        },
        "last90Days": {
            "period": {"from": "2025-12-24T17:16:25.693Z", "to": "2026-03-24T17:16:25.693Z"},
            "alarms": [], "cutoffs": [],
            "alarmsCount": 10, "cutoffsCount": 0,
            "hasMoreAlarms": False, "hasMoreCutoffs": False
        }
    }

    aioclient_mock.get(
        f"{API}/power/events?subscriptionId=sub_123",
        json=mock_payload,
    )

    data = await api.get_power_events()

    assert data["last30Days"]["alarmsCount"] == 5
    assert data["last30Days"]["cutoffsCount"] == 1
    assert data["last90Days"]["cutoffsCount"] == 0


async def test_get_power_latest(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {"__time":"2026-03-24T18:14:55.000Z","value":0.23,"availablePower":4.5,"powerUsagePercent":5,"maxAvailablePower":5.985}
    aioclient_mock.get(f"{API}/power/latest?subscriptionId=sub_123", json=mock_payload)
    data = await api.get_power_latest()
    assert data["value"] == 0.23
    assert data["powerUsagePercent"] == 5


async def test_get_consumption_today_realtime(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {"data":[{"hour":0,"W":95.07,"kWh":0.08,"label":"0-1 h"}],"lastDetection":{"time":"2026-03-24T18:14:55.000Z"}}
    aioclient_mock.get(f"{API}/energy/home/consumption/today-realtime?subscriptionId=sub_123", json=mock_payload)
    data = await api.get_consumption(period="today-realtime")
    assert len(data["data"]) == 1
    assert data["data"][0]["W"] == 95.07


async def test_get_historical_yesterday(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {"data":{"date":"23 marzo 2026","total":4.47,"topAppliances":[{"applianceId":6,"value":0.67,"percentage":14.99}]}}
    aioclient_mock.get(f"{API}/energy/home/historical-analysis?subscriptionId=sub_123&period=yesterday&locale=it", json=mock_payload)
    data = await api.get_historical_yesterday()
    assert data["data"]["total"] == 4.47


async def test_get_period_check_yesterday(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {"valid":True,"reliable":True,"hasFullCoverage":True,"coverageStartDate":"2025-09-01T00:00:00.000Z"}
    aioclient_mock.get(f"{API}/energy/home/period/check?subscriptionId=sub_123&period=yesterday", json=mock_payload)
    data = await api.get_period_check(period="yesterday")
    assert data["valid"] is True
    assert data["hasFullCoverage"] is True


async def test_get_historical_last_month(session, aioclient_mock):
    api = _authed_api(session)

    mock_payload = {"data":{"date":"01 febbraio 2026 - 28 febbraio 2026","total":132.87,"topAppliances":[{"applianceId":6,"value":17.97,"percentage":13.52}]}}
    aioclient_mock.get(f"{API}/energy/home/historical-analysis?subscriptionId=sub_123&period=last-month&locale=it", json=mock_payload)
    data = await api.get_historical_last_month()
    assert data["data"]["total"] == 132.87


async def test_rest_calls_use_id_token(session, aioclient_mock):
    """Regression for issue #2: TaDa API accepts only the ID token since Oct-2026."""
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    api._id_token = "id_123"
    api._token_exp_ts = float("inf")

    url = f"{API}/power/latest?subscriptionId=sub_123"
    aioclient_mock.get(url, json={"value": 1.0})
    await api.get_power_latest()

    # mock_calls entries: (method, url, request_data, request_headers)
    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer id_123"
