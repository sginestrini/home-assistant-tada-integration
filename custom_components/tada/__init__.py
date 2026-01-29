import logging
import time
from datetime import timedelta
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er, device_registry as dr
from homeassistant.util import dt as dt_util
from .const import (
    DOMAIN,
    UPDATE_INTERVAL_MINUTES,
    UPDATE_INTERVAL_TODAY_MINUTES,
    UPDATE_INTERVAL_YESTERDAY_MINUTES,
    UPDATE_INTERVAL_DAILY,
    DEFAULT_QUIET_WINDOW_ENABLED,
    DEFAULT_QUIET_WINDOW_FROM,
    DEFAULT_QUIET_WINDOW_TO,
    DEFAULT_QUIET_WINDOW_PAUSE_REST,
)
from .api import TadaAPI, AuthError
from .ws import TadaWSClient
from .utils import parse_hhmm, is_time_in_range

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    session = async_get_clientsession(hass)
    username = entry.data["username"]
    password = entry.data["password"]
    subscription_id = entry.data["subscription_id"]
    client_id = entry.data["client_id"]
    locale = entry.data.get("locale", "it")


    api = TadaAPI(session, username, password, client_id, subscription_id, locale)
    await api.login()

    # Throttling state shared across updates
    last_fetch_ts = {"today": 0.0, "yesterday": 0.0, "other": 0.0}
    previous_data: dict | None = None
    first_run = True

    async def async_update_data():
        """Fetch data for all required endpoints with concise fallbacks."""
        nonlocal previous_data, first_run

        # Start from previous data so skipped groups keep their values
        data: dict = previous_data.copy() if isinstance(previous_data, dict) else {}

        # Quiet window handling (optional): skip REST polling during specified time range
        opts = entry.options or {}
        q_enabled = opts.get("quiet_window_enabled", DEFAULT_QUIET_WINDOW_ENABLED)
        q_from = opts.get("quiet_window_from", DEFAULT_QUIET_WINDOW_FROM)
        q_to = opts.get("quiet_window_to", DEFAULT_QUIET_WINDOW_TO)
        pause_rest = opts.get("quiet_window_pause_rest", DEFAULT_QUIET_WINDOW_PAUSE_REST)

        def _in_quiet_window() -> bool:
            if not q_enabled:
                return False
            start_s = q_from
            end_s = q_to
            t_now = dt_util.now().time()
            t_start = parse_hhmm(start_s) if isinstance(start_s, str) else None
            t_end = parse_hhmm(end_s) if isinstance(end_s, str) else None
            if not t_start or not t_end:
                return False
            return is_time_in_range(t_now, t_start, t_end)

        def _due(group: str, minutes: int) -> bool:
            """Return True if the group's minimum interval has elapsed or it's first run."""
            now = time.time()
            last = last_fetch_ts.get(group, 0.0)
            if first_run or (now - last) >= (minutes * 60):
                last_fetch_ts[group] = now
                return True
            return False

        async def _fetch(key: str, coro, default):
            try:
                data[key] = await coro
            except AuthError:
                raise
            except Exception as e:
                _LOGGER.debug("Tada fetch '%s' failed: %s", key, e)
                data[key] = default

        try:
            # If configured, pause REST calls during the quiet window
            if pause_rest and _in_quiet_window():
                _LOGGER.debug("Tada: quiet window active, skipping REST polling (websocket remains active)")
                # Neutralize today's consumption to avoid lingering pre-window samples.
                # Keep other previously fetched groups untouched.
                try:
                    data["consumption_today"] = {"data": []}
                except Exception:
                    pass
                # Persist snapshot and exit update without REST polling.
                previous_data = data
                first_run = False
                return data
            # TODAY / GENERAL: update frequently
            if _due("today", UPDATE_INTERVAL_TODAY_MINUTES):
                await _fetch("power_latest", api.get_power_latest(), None)
                await _fetch("subscription_status", api.get_subscription_status(), {})
                await _fetch("power_meter_status", api.get_power_meter_status(), {})
                await _fetch("consumption_today", api.get_consumption("today-realtime"), {"data": []})

            # YESTERDAY: update hourly
            if _due("yesterday", UPDATE_INTERVAL_YESTERDAY_MINUTES):
                await _fetch("energy_total", api.get_total("yesterday"), None)
                await _fetch("consumption_yesterday", api.get_consumption("yesterday"), {"data": []})
                await _fetch("historical_yesterday", api.get_historical_yesterday(), {})
                await _fetch("timebands_yesterday", api.get_timebands("yesterday"), {"data": []})
                await _fetch("comparisons_average_yesterday", api.get_comparisons_average("yesterday"), {})
                await _fetch("comparisons_previous_yesterday", api.get_comparisons_previous("yesterday"), {})
                # Period check for yesterday
                try:
                    data.setdefault("period_checks", {})["yesterday"] = await api.get_period_check("yesterday")
                except Exception:
                    data.setdefault("period_checks", {})["yesterday"] = {}
                # Summary yesterday when enabled
                opts_y = entry.options or {}
                if opts_y.get("summary_yesterday", False):
                    await _fetch("summary_yesterday", api.get_summary("yesterday"), {"data": {"appliances": [], "activities": []}})

            # OTHER PERIODS: update daily
            opts = entry.options or {}
            if _due("other", UPDATE_INTERVAL_DAILY):
                monitor_flags = {
                    "last_week": opts.get("monitor_last_week", False),
                    "last_7_days": opts.get("monitor_last_7_days", False),
                    "last_month": opts.get("monitor_last_month", False),
                    "last_30_days": opts.get("monitor_last_30_days", False),
                    "last_year": opts.get("monitor_last_year", False),
                    "last_365_days": opts.get("monitor_last_365_days", False),
                }
                period_param_map = {
                    "last_week": "last-week",
                    "last_7_days": "last-7-days",
                    "last_month": "last-month",
                    "last_30_days": "last-30-days",
                    "last_year": "last-year",
                    "last_365_days": "last-365-days",
                }

                # Selected extra periods (daily)
                for key_suffix, enabled in monitor_flags.items():
                    if not enabled:
                        continue
                    param = period_param_map[key_suffix]
                    # Period checks
                    try:
                        data.setdefault("period_checks", {})[key_suffix] = await api.get_period_check(param)
                    except Exception:
                        data.setdefault("period_checks", {})[key_suffix] = {}
                    await _fetch(f"consumption_{key_suffix}", api.get_consumption(param), {"data": []})
                    await _fetch(f"timebands_{key_suffix}", api.get_timebands(param), {"data": []})

                    # Comparisons for week periods
                    if key_suffix in ("last_week", "last_7_days"):
                        await _fetch(f"comparisons_average_{key_suffix}", api.get_comparisons_average(param), {})
                        await _fetch(f"comparisons_previous_{key_suffix}", api.get_comparisons_previous(param), {})

                    # Annual reference for month/year periods
                    if key_suffix in ("last_month", "last_30_days", "last_year", "last_365_days"):
                        await _fetch(f"annual_reference_{key_suffix}", api.get_comparisons_annual_reference(param), {})

                    # Summary payloads when enabled
                    if opts.get(f"summary_{key_suffix}", False):
                        await _fetch(f"summary_{key_suffix}", api.get_summary(param), {"data": {"appliances": [], "activities": []}})

                # Custom period (daily)
                monitor_custom = opts.get("monitor_custom", False)
                custom_from = opts.get("custom_from")
                custom_to = opts.get("custom_to")
                if monitor_custom and custom_from and custom_to:
                    custom_key = f"custom_{custom_from}_{custom_to}"
                    await _fetch(
                        f"consumption_{custom_key}",
                        api.get_consumption("custom", from_date=custom_from, to_date=custom_to),
                        {"data": []},
                    )
                    await _fetch(
                        f"timebands_{custom_key}",
                        api.get_timebands("custom", from_date=custom_from, to_date=custom_to),
                        {"data": []},
                    )
                    # Period check and summary for custom if enabled
                    try:
                        data.setdefault("period_checks", {})[custom_key] = await api.get_period_check(
                            "custom", from_date=custom_from, to_date=custom_to
                        )
                    except Exception:
                        data.setdefault("period_checks", {})[custom_key] = {}
                    if opts.get("summary_custom", False):
                        await _fetch(
                            f"summary_{custom_key}",
                            api.get_summary("custom", from_date=custom_from, to_date=custom_to),
                            {"data": {"appliances": [], "activities": []}},
                        )

            # End: persist previous data snapshot and finish
            previous_data = data
            first_run = False
            return data
        except AuthError as e:
            _LOGGER.error("Auth error during update: %s", e)
            raise ConfigEntryAuthFailed from e
        
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Tada energy",
        update_method=async_update_data,
        update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
    )

    await coordinator.async_config_entry_first_refresh()

    # store core objects first so platforms can access them
    hass.data[DOMAIN] = {
        "api": api,
        "coordinator": coordinator,
        "ws_token": api.ws_token,
        "ws_client": None,
    }

    # create and start websocket client now
    try:
        ws_client = TadaWSClient(hass, api)
        await ws_client.start()
        hass.data[DOMAIN]["ws_client"] = ws_client
        _LOGGER.debug("Tada: websocket client started and stored in hass.data")
    except Exception as exc:
        _LOGGER.warning("Tada: failed to start websocket client: %s", exc)
        # keep going so REST sensors still load

    # Reload the entry on options change and proactively clean up deselected periods
    async def async_options_updated(hass, entry):
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)

        subscription_id = entry.data.get("subscription_id")
        opts = entry.options or {}

        # Helper: remove all entities for a given device suffix and then the device if empty
        def _remove_device_and_entities_for_suffix(device_suffix: str):
            try:
                device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{subscription_id}:{device_suffix}")})
                if not device:
                    return
                # Remove all entities tied to this device (including disabled)
                entries = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
                for ent in entries:
                    try:
                        ent_reg.async_remove(ent.entity_id)
                    except Exception:
                        pass
                # If device has no more entities, remove the device
                remaining = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
                if not remaining:
                    try:
                        dev_reg.async_remove_device(device.id)
                    except Exception:
                        pass
            except Exception:
                _LOGGER.debug("Tada cleanup: failed removing device/entities for suffix %s", device_suffix, exc_info=True)

        # Determine which standard periods are currently enabled
        period_flags = {
            "last_week": opts.get("monitor_last_week", False),
            "last_7_days": opts.get("monitor_last_7_days", False),
            "last_month": opts.get("monitor_last_month", False),
            "last_30_days": opts.get("monitor_last_30_days", False),
            "last_year": opts.get("monitor_last_year", False),
            "last_365_days": opts.get("monitor_last_365_days", False),
        }

        # Remove entities/devices for any periods that are now disabled
        for key_suffix, enabled in period_flags.items():
            if not enabled:
                _remove_device_and_entities_for_suffix(key_suffix)

        # Remove summary-only entities when summary switches are turned off
        try:
            summary_flags = {
                "yesterday": opts.get("summary_yesterday", False),
                "last_week": opts.get("summary_last_week", False),
                "last_7_days": opts.get("summary_last_7_days", False),
                "last_month": opts.get("summary_last_month", False),
                "last_30_days": opts.get("summary_last_30_days", False),
                "last_year": opts.get("summary_last_year", False),
                "last_365_days": opts.get("summary_last_365_days", False),
            }

            for period_key, is_on in summary_flags.items():
                if is_on:
                    continue
                try:
                    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{subscription_id}:{period_key}")})
                    if not device:
                        continue
                    entries = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
                    for ent in entries:
                        # Summary sensors unique_id format: "tada_<sub>_summary_<period_key>_<category>_<label_slug>_<mode>"
                        uid = getattr(ent, "unique_id", None)
                        if isinstance(uid, str) and uid.startswith(f"tada_{subscription_id}_summary_{period_key}_"):
                            try:
                                ent_reg.async_remove(ent.entity_id)
                            except Exception:
                                pass
                except Exception:
                    _LOGGER.debug("Tada cleanup: failed removing summary-only entities for %s", period_key, exc_info=True)
        except Exception:
            _LOGGER.debug("Tada cleanup: summary flags processing failed", exc_info=True)

        # Handle custom periods: remove all custom_* devices not matching the currently enabled custom key
        monitor_custom = opts.get("monitor_custom", False)
        custom_from = opts.get("custom_from")
        custom_to = opts.get("custom_to")
        keep_custom_key = None
        if monitor_custom and custom_from and custom_to:
            keep_custom_key = f"custom_{custom_from}_{custom_to}"

            # If custom summary is off, remove only summary sensors for the active custom key
            if not opts.get("summary_custom", False):
                try:
                    device = dev_reg.async_get_device(identifiers={(DOMAIN, f"{subscription_id}:{keep_custom_key}")})
                    if device:
                        entries = er.async_entries_for_device(ent_reg, device.id, include_disabled_entities=True)
                        for ent in entries:
                            uid = getattr(ent, "unique_id", None)
                            if isinstance(uid, str) and uid.startswith(f"tada_{subscription_id}_summary_{keep_custom_key}_"):
                                try:
                                    ent_reg.async_remove(ent.entity_id)
                                except Exception:
                                    pass
                except Exception:
                    _LOGGER.debug("Tada cleanup: failed removing summary-only custom entities for %s", keep_custom_key, exc_info=True)

        try:
            # Iterate all devices and find those belonging to this subscription with custom_* suffix
            for device in list(dev_reg.devices.values()):
                try:
                    # Match any identifier registered by this integration
                    custom_suffix = None
                    for id_domain, ident in device.identifiers:
                        if id_domain != DOMAIN:
                            continue
                        # ident format: f"{subscription_id}:{device_id_suffix}"
                        if isinstance(ident, str) and ident.startswith(f"{subscription_id}:"):
                            suffix = ident.split(":", 1)[1]
                            if suffix.startswith("custom_"):
                                custom_suffix = suffix
                                break
                    if not custom_suffix:
                        continue
                    # If custom period is disabled altogether, remove all custom_* devices
                    # Or if enabled but suffix doesn't match the active key, remove old ones
                    if (keep_custom_key is None) or (custom_suffix != keep_custom_key):
                        _remove_device_and_entities_for_suffix(custom_suffix)
                except Exception:
                    continue
        except Exception:
            _LOGGER.debug("Tada cleanup: scanning custom devices failed", exc_info=True)

        # Finally reload to apply changes
        await hass.config_entries.async_reload(entry.entry_id)

    remove_listener = entry.add_update_listener(async_options_updated)
    # Ensure the listener is removed on unload to prevent accumulation
    entry.async_on_unload(remove_listener)

    # forward platforms (sensors/binary sensors/switches) after WS client is started
    from .const import PLATFORMS
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    from .const import PLATFORMS
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        ws_client = hass.data[DOMAIN].get("ws_client")
        if ws_client:
            await ws_client.close()
        hass.data.pop(DOMAIN, None)
    return unload_ok
