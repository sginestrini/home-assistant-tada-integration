import json
import time
import aiohttp
import async_timeout
from typing import Optional
from datetime import datetime
from .const import COGNITO_URL, TIMEOUT

def _validate_date(d: str):
    """Validate ISO date string YYYY-MM-DD and raise ValueError if invalid."""
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        raise ValueError(f"Invalid date format: {d}. Expected YYYY-MM-DD")

COGNITO_HEADERS = {
    "content-type": "application/x-amz-json-1.1",
    "x-amz-user-agent": "home-assistant-integration/1.0",
}

class AuthError(Exception):
    pass

class TadaAPI:
    def __init__(self, session: aiohttp.ClientSession, username: str, password: str,
                 client_id: str, subscription_id: str, locale: str = "it"):
        self._session = session
        self._username = username
        self._password = password
        self._client_id = client_id
        self._subscription_id = subscription_id
        self._locale = locale

        self._id_token: Optional[str] = None
        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._access_exp_ts: Optional[float] = None

    async def login(self):
        payload = {
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {
                "USERNAME": self._username,
                "PASSWORD": self._password,
            },
            "ClientId": self._client_id,
        }
        headers = {**COGNITO_HEADERS,
                   "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth"}
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.post(COGNITO_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise AuthError(f"InitiateAuth failed: {resp.status}")
                text = await resp.text()
                data = json.loads(text)

        auth = data.get("AuthenticationResult")
        if not auth:
            raise AuthError("AuthenticationResult missing; interactive challenge not supported.")

        self._id_token = auth.get("IdToken")
        self._access_token = auth.get("AccessToken")
        self._refresh_token = auth.get("RefreshToken")
        expires_in = auth.get("ExpiresIn", 3600)
        self._access_exp_ts = time.time() + expires_in - 60
        if not self._access_token or not self._refresh_token:
            raise AuthError("Missing tokens from Cognito response.")
        return True

    async def _refresh_access_token(self):
        if not self._refresh_token:
            raise AuthError("No refresh token available.")
        payload = {
            "AuthFlow": "REFRESH_TOKEN_AUTH",
            "AuthParameters": {"REFRESH_TOKEN": self._refresh_token},
            "ClientId": self._client_id,
        }
        headers = {**COGNITO_HEADERS,
                   "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth"}
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.post(COGNITO_URL, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    raise AuthError(f"Refresh failed: {resp.status}")
                text = await resp.text()
                data = json.loads(text)

        auth = data.get("AuthenticationResult")
        if not auth:
            raise AuthError("Refresh AuthenticationResult missing.")
        self._id_token = auth.get("IdToken")
        self._access_token = auth.get("AccessToken")
        expires_in = auth.get("ExpiresIn", 3600)
        self._access_exp_ts = time.time() + expires_in - 60
        if not self._access_token or not self._id_token:
            raise AuthError("Missing tokens from refresh response.")

    async def _ensure_token(self):
        if not self._access_token:
            await self.login()
            return
        if self._access_exp_ts and time.time() >= self._access_exp_ts:
            try:
                await self._refresh_access_token()
            except AuthError:
                # Refresh failed, try full login
                await self.login()

    def _bearer(self):
        return f"Bearer {self._access_token}"

    async def _get(self, url):
        await self._ensure_token()
        headers = {"Authorization": self._bearer()}
        async with async_timeout.timeout(TIMEOUT):
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    await self._refresh_access_token()
                    async with self._session.get(url, headers={"Authorization": self._bearer()}) as resp2:
                        resp2.raise_for_status()
                        return await resp2.json()
                resp.raise_for_status()
                return await resp.json()

    async def get_subscriptions(self):
        url = "https://webapp.tada.magie-tada.com/api/subscription/list"
        return await self._get(url)

    async def get_power_latest(self):
        url = f"https://webapp.tada.magie-tada.com/api/power/latest?subscriptionId={self._subscription_id}"
        return await self._get(url)

    async def get_subscription_status(self):
        url = f"https://webapp.tada.magie-tada.com/api/subscription/status?subscriptionId={self._subscription_id}"
        return await self._get(url)

    async def get_power_meter_status(self):
        url = f"https://webapp.tada.magie-tada.com/api/power/meter/status?subscriptionId={self._subscription_id}"
        return await self._get(url)

    async def get_consumption(self, period: str = "today-realtime", from_date: Optional[str] = None, to_date: Optional[str] = None):
        """Get consumption data for a given period.

        Returns a dict like {"data": [{"label":..., "date":..., "kWh": ...}, ...]}

        `period` can be standard values or `custom` with `from_date` and `to_date` (YYYY-MM-DD).
        The `locale` parameter is included to control label formatting.
        """
        # Special-case the today-realtime endpoint which is a different path
        if period == "today-realtime":
            url = f"https://webapp.tada.magie-tada.com/api/energy/home/consumption/today-realtime?subscriptionId={self._subscription_id}"
            return await self._get(url)

        # Special-case for yesterday using /consumption/day endpoint
        if period == "yesterday":
            url = f"https://webapp.tada.magie-tada.com/api/energy/home/consumption/day?subscriptionId={self._subscription_id}"
            return await self._get(url)

        params = [f"subscriptionId={self._subscription_id}", f"period={period}", f"locale={self._locale}"]
        if from_date:
            _validate_date(from_date)
            params.append(f"from={from_date}")
        if to_date:
            _validate_date(to_date)
            params.append(f"to={to_date}")

        url = "https://webapp.tada.magie-tada.com/api/energy/home/consumption?" + "&".join(params)
        return await self._get(url)

    async def get_historical_yesterday(self):
        url = (f"https://webapp.tada.magie-tada.com/api/energy/home/historical-analysis"
               f"?subscriptionId={self._subscription_id}&period=yesterday&locale={self._locale}")
        return await self._get(url)

    async def get_historical_last_month(self):
        url = (f"https://webapp.tada.magie-tada.com/api/energy/home/historical-analysis"
               f"?subscriptionId={self._subscription_id}&period=last-month&locale={self._locale}")
        return await self._get(url)

    async def get_timebands(self, period: str = "yesterday", from_date: Optional[str] = None, to_date: Optional[str] = None):
        """Get timeband breakdown for a given period.

        Returns a dict like {"data": [{"label":..., "value":..., "percentage":...}, ...]}

        `period` can be standard values or `custom` with `from_date` and `to_date` (YYYY-MM-DD).
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        if from_date:
            _validate_date(from_date)
            params.append(f"from={from_date}")
        if to_date:
            _validate_date(to_date)
            params.append(f"to={to_date}")

        url = "https://webapp.tada.magie-tada.com/api/energy/home/timebands?" + "&".join(params)
        return await self._get(url)

    async def get_summary(self, period: str = "yesterday", from_date: Optional[str] = None, to_date: Optional[str] = None):
        """Get appliances/activities summary for a given period.

        Returns a dict like {"data": {"appliances": [...], "activities": [...]}}

        `period` can be standard values like `yesterday`, `last-365-days`, etc.,
        or `custom` together with `from_date` and `to_date` (ISO date YYYY-MM-DD).
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        if from_date:
            _validate_date(from_date)
            params.append(f"from={from_date}")
        if to_date:
            _validate_date(to_date)
            params.append(f"to={to_date}")

        url = "https://webapp.tada.magie-tada.com/api/energy/home/summary?" + "&".join(params)
        return await self._get(url)
    
    async def get_comparisons_average(self, period: str = "yesterday"):
        """Get average energy comparison for a given period.

        Example responses: {"averageEnergyComparison": -0.05}
        Note: values are ratios; multiply by 100 for percentage.
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        url = "https://webapp.tada.magie-tada.com/api/energy/home/comparisons/average?" + "&".join(params)
        return await self._get(url)
    
    async def get_comparisons_previous(self, period: str = "yesterday"):
        """Get previous period comparison for a given period.

        Example responses:
        - Yesterday: {"previousEnergyComparison": -4.48} (kWh difference)
        - Last week: {"previousEnergyComparison": 0.15} (ratio vs previous week)
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        url = "https://webapp.tada.magie-tada.com/api/energy/home/comparisons/previous?" + "&".join(params)
        return await self._get(url)
    
    async def get_comparisons_annual_reference(self, period: str = "last-month"):
        """Get annual reference for monthly comparisons.

        Endpoint may return an error payload when data is not available:
        {"error":"No data found for the specified request.","code":"DATA_NOT_FOUND"}
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        url = "https://webapp.tada.magie-tada.com/api/energy/home/comparisons/annual-reference?" + "&".join(params)
        return await self._get(url)
    
    async def get_period_check(self, period: str = "yesterday", from_date: Optional[str] = None, to_date: Optional[str] = None):
        """Check data coverage for a given period.

        Example responses:
        {"valid": true, "reliable": true, "hasFullCoverage": true, "coverageStartDate": "..."}

        The `period` can be standard values like `yesterday` or `last-month`,
        or `custom` together with `from_date` and `to_date` (ISO date YYYY-MM-DD):
        `period=custom&from=2025-12-08&to=2025-12-11`.
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        if from_date:
            _validate_date(from_date)
            params.append(f"from={from_date}")
        if to_date:
            _validate_date(to_date)
            params.append(f"to={to_date}")

        url = "https://webapp.tada.magie-tada.com/api/energy/home/period/check?" + "&".join(params)
        return await self._get(url)
    
    async def get_total(self, period: str = "yesterday", from_date: Optional[str] = None, to_date: Optional[str] = None):
        """Get total energy for a given period.

        Example responses: {"total": 14.43}

        `period` can be standard values like `yesterday` or `last-month`,
        or `custom` together with `from_date` and `to_date` (ISO date YYYY-MM-DD):
        `period=custom&from=2025-12-08&to=2025-12-11`.
        """
        params = [f"subscriptionId={self._subscription_id}", f"period={period}"]
        if from_date:
            _validate_date(from_date)
            params.append(f"from={from_date}")
        if to_date:
            _validate_date(to_date)
            params.append(f"to={to_date}")

        url = "https://webapp.tada.magie-tada.com/api/energy/home/total?" + "&".join(params)
        return await self._get(url)

    @property
    def ws_token(self):
        return self._id_token
