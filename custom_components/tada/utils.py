from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .mapping import SUMMARY_PERIODS

_LOGGER = logging.getLogger(__name__)

def _parse_ids(s: str | None) -> set[int]:
    """Parse comma-separated IDs into a set[int]."""
    if not s:
        return set()
    ids: set[int] = set()
    for part in str(s).split(","):
        p = part.strip()
        if not p:
            continue
        try:
            ids.add(int(p))
        except Exception:
            continue
    return ids

def _present_ids_from_summary(
    coordinator: DataUpdateCoordinator,
    period_key: str,
    category: str,
) -> set[int]:
    """Return IDs present in coordinator summary payload for a category."""
    src = (coordinator.data or {}).get(f"summary_{period_key}") or {}
    payload = src.get("data") or {}
    items = payload.get("appliances" if category == "appliance" else "activities") or []
    out: set[int] = set()
    for it in items if isinstance(items, list) else []:
        try:
            out.add(int(it.get("applianceId" if category == "appliance" else "activityId")))
        except Exception:
            continue
    return out

def _parse_iso_to_dt(value: str) -> datetime | None:
    """Parse ISO 8601 string to timezone-aware datetime (UTC)."""
    if not value:
        return None
    try:
        if value.endswith("Z"):
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
        # fromisoformat supports offsets like +00:00
        return datetime.fromisoformat(value)
    except Exception:
        _LOGGER.debug("Failed to parse datetime string: %s", value, exc_info=True)
        return None

def _monitored_periods(opts: dict) -> list[tuple[str, str]]:
    """Return list of (key_suffix, label) for monitored periods based on options.

    This consolidates logic duplicated in binary_sensor.py and switch.py.
    Excludes 'yesterday' which is handled separately in callers.
    """
    out: list[tuple[str, str]] = []
    for _param, key_suffix, label in SUMMARY_PERIODS:
        if key_suffix == "yesterday":
            continue
        if opts.get(f"monitor_{key_suffix}", False):
            out.append((key_suffix, label))
    return out


def tk_summary_switch(period_key: str) -> str:
    """Return translation key for summary switch given a period key.

    Custom periods use a shared key; other periods are suffixed by the key.
    """
    try:
        if str(period_key).startswith("custom_"):
            return "tada_summary_switch_custom"
        return f"tada_summary_switch_{period_key}"
    except Exception:
        # Fallback to generic custom key
        return "tada_summary_switch_custom"
