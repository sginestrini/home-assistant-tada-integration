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
            "period": {"from": "2026-02-11T18:04:34.125Z", "to": "2026-03-13T18:04:34.125Z"},
            "alarms": [], "cutoffs": [],
            "alarmsCount": 5, "cutoffsCount": 1,
            "hasMoreAlarms": False, "hasMoreCutoffs": False
        },
        "last90Days": {
            "period": {"from": "2025-12-13T18:04:34.125Z", "to": "2026-03-13T18:04:34.125Z"},
            "alarms": [], "cutoffs": [],
            "alarmsCount": 10, "cutoffsCount": 3,
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
        assert data["last90Days"]["alarmsCount"] == 10
        assert data["last90Days"]["cutoffsCount"] == 3
