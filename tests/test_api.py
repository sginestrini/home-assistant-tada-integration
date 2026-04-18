import pytest
import aiohttp
from aioresponses import aioresponses
from custom_components.tada.api import TadaAPI, AuthError, COGNITO_URL

@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as session:
        yield session

async def test_login_success(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    
    with aioresponses() as m:
        m.post(
            COGNITO_URL,
            payload={
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
        assert api._access_token == "acc_123"

async def test_login_failure(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    
    with aioresponses() as m:
        m.post(COGNITO_URL, status=400, payload={"message": "Invalid credentials"})
        
        with pytest.raises(AuthError):
            await api.login()

async def test_get_power_events(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    # Manually set token to bypass login check for this unit test
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
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
    
    with aioresponses() as m:
        m.get(
            "https://webapp.tada.magie-tada.com/api/power/events?subscriptionId=sub_123",
            payload=mock_payload
        )
        
        data = await api.get_power_events()
        
        assert data["last30Days"]["alarmsCount"] == 5
        assert data["last30Days"]["cutoffsCount"] == 1
        assert data["last90Days"]["cutoffsCount"] == 0

async def test_get_power_latest(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
    mock_payload = {"__time":"2026-03-24T18:14:55.000Z","value":0.23,"availablePower":4.5,"powerUsagePercent":5,"maxAvailablePower":5.985}
    with aioresponses() as m:
        m.get("https://webapp.tada.magie-tada.com/api/power/latest?subscriptionId=sub_123", payload=mock_payload)
        data = await api.get_power_latest()
        assert data["value"] == 0.23
        assert data["powerUsagePercent"] == 5

async def test_get_consumption_today_realtime(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
    # Pruned for brevity
    mock_payload = {"data":[{"hour":0,"W":95.07,"kWh":0.08,"label":"0-1 h"}],"lastDetection":{"time":"2026-03-24T18:14:55.000Z"}}
    with aioresponses() as m:
        m.get("https://webapp.tada.magie-tada.com/api/energy/home/consumption/today-realtime?subscriptionId=sub_123", payload=mock_payload)
        data = await api.get_consumption(period="today-realtime")
        assert len(data["data"]) == 1
        assert data["data"][0]["W"] == 95.07

async def test_get_historical_yesterday(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123", locale="it")
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
    mock_payload = {"data":{"date":"23 marzo 2026","total":4.47,"topAppliances":[{"applianceId":6,"value":0.67,"percentage":14.99}]}}
    with aioresponses() as m:
        m.get("https://webapp.tada.magie-tada.com/api/energy/home/historical-analysis?subscriptionId=sub_123&period=yesterday&locale=it", payload=mock_payload)
        data = await api.get_historical_yesterday()
        assert data["data"]["total"] == 4.47

async def test_get_period_check_yesterday(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123")
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
    mock_payload = {"valid":True,"reliable":True,"hasFullCoverage":True,"coverageStartDate":"2025-09-01T00:00:00.000Z"}
    with aioresponses() as m:
        m.get("https://webapp.tada.magie-tada.com/api/energy/home/period/check?subscriptionId=sub_123&period=yesterday", payload=mock_payload)
        data = await api.get_period_check(period="yesterday")
        assert data["valid"] is True
        assert data["hasFullCoverage"] is True

async def test_get_historical_last_month(session):
    api = TadaAPI(session, "test", "pass", "client_123", "sub_123", locale="it")
    api._access_token = "valid_token"
    api._access_exp_ts = 9999999999.0
    
    mock_payload = {"data":{"date":"01 febbraio 2026 - 28 febbraio 2026","total":132.87,"topAppliances":[{"applianceId":6,"value":17.97,"percentage":13.52}]}}
    with aioresponses() as m:
        m.get("https://webapp.tada.magie-tada.com/api/energy/home/historical-analysis?subscriptionId=sub_123&period=last-month&locale=it", payload=mock_payload)
        data = await api.get_historical_last_month()
        assert data["data"]["total"] == 132.87
