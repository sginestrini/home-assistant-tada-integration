import base64
import json
import asyncio
import aiohttp
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
from .const import WS_URL

_LOGGER = logging.getLogger(__name__)

class TadaWSClient:
    def __init__(self, hass, api):
        self._hass = hass
        self._api = api
        self._session = async_get_clientsession(hass)
        self._ws = None
        self._task = None

    async def start(self):
        """Start the websocket listener in background."""
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        reconnect_delay = 5
        max_reconnect_delay = 300  # 5 minutes max
        
        while True:
            try:
                # Refresh token before each connection attempt
                await self._api._ensure_token()
                url = f"{WS_URL}?Authorization={self._api.ws_token}"

                _LOGGER.debug("TadaWSClient connecting to %s", url[:80] + "...")
                self._ws = await self._session.ws_connect(url, heartbeat=30.0)
                _LOGGER.info("TadaWSClient connected")
                # Reset reconnect delay on successful connection
                reconnect_delay = 5

                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        raw = msg.data.strip()
                        if not raw:
                            continue
                        try:
                            _LOGGER.debug("TadaWSClient raw message: %s", raw[:100])
                            decoded = base64.b64decode(raw).decode("utf-8")
                            _LOGGER.debug("TadaWSClient base64 decoded: %s", decoded[:200])
                            data = json.loads(decoded)

                            payload = data.get("Payload", {})
                            if "InstantPower" in payload:
                                value = payload["InstantPower"]
                                _LOGGER.debug("TadaWSClient dispatched instant power: %s", value)
                                async_dispatcher_send(self._hass, "tada_instant_power", value)

                        except Exception as e:
                            _LOGGER.debug("TadaWSClient parse error: %s", e)

                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        exc = self._ws.exception() if self._ws else None
                        _LOGGER.warning("TadaWSClient websocket error: %s", exc)
                        break
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                        code = getattr(self._ws, "close_code", None)
                        _LOGGER.info("TadaWSClient websocket closed (code=%s)", code)
                        break

            except Exception as e:
                _LOGGER.warning("TadaWSClient error: %s, reconnecting in %ds", e, reconnect_delay)
                await asyncio.sleep(reconnect_delay)
                # Exponential backoff for reconnection, capped at max_reconnect_delay
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
