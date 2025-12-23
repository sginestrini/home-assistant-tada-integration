from __future__ import annotations

from typing import Any, Dict
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= 4:
            return "***"
        return value[:2] + "***" + value[-2:]
    return "***"


def _limited(data: Any) -> Any:
    """Limit size of lists/dicts in diagnostics output."""
    if isinstance(data, list):
        return data[:50]
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            out[k] = _limited(v)
        return out
    return data


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> Dict[str, Any]:
    """Return diagnostics for a config entry, with secrets redacted and payloads trimmed."""
    data = hass.data.get(DOMAIN, {})
    coordinator = data.get("coordinator")
    api = data.get("api")

    entry_info = {
        "title": entry.title,
        "domain": entry.domain,
        "data": {
            "username": _redact(entry.data.get("username")),
            "subscription_id": _redact(entry.data.get("subscription_id")),
            "locale": entry.data.get("locale"),
        },
        "options": entry.options,
    }

    coord_info = {
        "last_update_success": getattr(coordinator, "last_update_success", None) if coordinator else None,
        "data_keys": list((coordinator.data or {}).keys()) if coordinator and coordinator.data else [],
        "data": _limited(coordinator.data) if coordinator and coordinator.data else {},
    }

    api_info = {
        "has_token": bool(getattr(api, "_access_token", None)),
        "has_id_token": bool(getattr(api, "_id_token", None)),
    }

    return {
        "entry": entry_info,
        "coordinator": coord_info,
        "api": api_info,
    }
