import voluptuous as vol
from datetime import datetime
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import (
    DOMAIN,
    DEFAULT_CLIENT_ID,
    DEFAULT_QUIET_WINDOW_ENABLED,
    DEFAULT_QUIET_WINDOW_FROM,
    DEFAULT_QUIET_WINDOW_TO,
    DEFAULT_QUIET_WINDOW_PAUSE_REST,
)
from .api import TadaAPI, AuthError


class TadaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("subscription_id"): str,
                    vol.Optional("locale", default="it"): str,
                }),
                description_placeholders={
                    "help_url": "https://webapp.tada.magie-tada.com"
                }
            )

        data = dict(user_input)
        data.setdefault("client_id", DEFAULT_CLIENT_ID)

        # Validate credentials by attempting a login
        session = async_get_clientsession(self.hass)
        api = TadaAPI(
            session,
            data["username"],
            data["password"],
            data["client_id"],
            data["subscription_id"],
            data.get("locale", "it"),
        )
        try:
            await api.login()
        except AuthError:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                    vol.Required("subscription_id"): str,
                    vol.Optional("locale", default="it"): str,
                }),
                errors={"base": "auth_failed"},
            )

        return self.async_create_entry(title="Tada", data=data)

    @staticmethod
    def async_get_options_flow(config_entry):
        return TadaConfigFlow.TadaOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data):
        """Handle reauthentication when tokens/credentials fail."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context.get("entry_id"))
        # If entry lookup fails, fall back to asking for credentials
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = getattr(self, "_reauth_entry", None)
        defaults = {}
        if entry:
            defaults = {
                "username": entry.data.get("username", ""),
                "password": "",
                "subscription_id": entry.data.get("subscription_id", ""),
                "locale": entry.data.get("locale", "it"),
            }
        schema = vol.Schema({
            vol.Required("username", default=defaults.get("username", "")): str,
            vol.Required("password", default=""): str,
            vol.Required("subscription_id", default=defaults.get("subscription_id", "")): str,
            vol.Optional("locale", default=defaults.get("locale", "it")): str,
        })

        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm", data_schema=schema)

        # Validate credentials by attempting a login
        session = async_get_clientsession(self.hass)
        client_id = DEFAULT_CLIENT_ID
        api = TadaAPI(session, user_input["username"], user_input["password"], client_id, user_input["subscription_id"], user_input.get("locale", "it"))
        try:
            await api.login()
        except AuthError:
            return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors={"base": "auth_failed"})

        # Save updated credentials on the existing entry
        if entry:
            new_data = dict(entry.data)
            new_data.update({
                "username": user_input["username"],
                "password": user_input["password"],
                "subscription_id": user_input["subscription_id"],
                "locale": user_input.get("locale", "it"),
                "client_id": new_data.get("client_id", DEFAULT_CLIENT_ID),
            })
            self.hass.config_entries.async_update_entry(entry, data=new_data)
        return self.async_abort(reason="reauth_successful")

    class TadaOptionsFlowHandler(config_entries.OptionsFlow):
        def __init__(self, config_entry):
            self._entry = config_entry

        async def async_step_init(self, user_input=None):
            current = self._entry.options
            # Period monitoring options + global selections for Appliances/Activities
            defaults = {
                "monitor_last_week": current.get("monitor_last_week", False),
                "monitor_last_7_days": current.get("monitor_last_7_days", False),
                "monitor_last_month": current.get("monitor_last_month", False),
                "monitor_last_30_days": current.get("monitor_last_30_days", False),
                "monitor_last_year": current.get("monitor_last_year", False),
                "monitor_last_365_days": current.get("monitor_last_365_days", False),
                "monitor_custom": current.get("monitor_custom", False),
                "custom_from": current.get("custom_from", ""),
                "custom_to": current.get("custom_to", ""),
                "enabled_appliances": current.get("enabled_appliances", ""),
                "enabled_activities": current.get("enabled_activities", ""),
                # Quiet window defaults
                "quiet_window_enabled": current.get("quiet_window_enabled", DEFAULT_QUIET_WINDOW_ENABLED),
                "quiet_window_from": current.get("quiet_window_from", DEFAULT_QUIET_WINDOW_FROM),
                "quiet_window_to": current.get("quiet_window_to", DEFAULT_QUIET_WINDOW_TO),
                "quiet_window_pause_rest": current.get("quiet_window_pause_rest", DEFAULT_QUIET_WINDOW_PAUSE_REST),
            }

            schema = vol.Schema({
                vol.Optional("monitor_last_week", default=defaults["monitor_last_week"]): bool,
                vol.Optional("monitor_last_7_days", default=defaults["monitor_last_7_days"]): bool,
                vol.Optional("monitor_last_month", default=defaults["monitor_last_month"]): bool,
                vol.Optional("monitor_last_30_days", default=defaults["monitor_last_30_days"]): bool,
                vol.Optional("monitor_last_year", default=defaults["monitor_last_year"]): bool,
                vol.Optional("monitor_last_365_days", default=defaults["monitor_last_365_days"]): bool,
                vol.Optional("monitor_custom", default=defaults["monitor_custom"]): bool,
                vol.Optional("custom_from", default=defaults["custom_from"]): str,
                vol.Optional("custom_to", default=defaults["custom_to"]): str,
                vol.Optional("enabled_appliances", default=defaults["enabled_appliances"]): str,
                vol.Optional("enabled_activities", default=defaults["enabled_activities"]): str,
                # Quiet window controls (simple text HH:MM for broad compatibility)
                vol.Optional("quiet_window_enabled", default=defaults["quiet_window_enabled"]): bool,
                vol.Optional("quiet_window_from", default=defaults["quiet_window_from"]): str,
                vol.Optional("quiet_window_to", default=defaults["quiet_window_to"]): str,
                vol.Optional("quiet_window_pause_rest", default=defaults["quiet_window_pause_rest"]): bool,
            })

            if user_input is None:
                return self.async_show_form(step_id="init", data_schema=schema)

            # Validate enabled IDs format (optional)
            def _validate_ids(s: str) -> str | None:
                if not s:
                    return ""
                try:
                    parts = [p.strip() for p in s.split(",") if p.strip()]
                    for p in parts:
                        int(p)
                    return ",".join(parts)
                except Exception:
                    return None
            ap_ids = _validate_ids(user_input.get("enabled_appliances", ""))
            act_ids = _validate_ids(user_input.get("enabled_activities", ""))
            if ap_ids is None:
                return self.async_show_form(step_id="init", data_schema=schema, errors={"base": "invalid_appliance_ids"})
            if act_ids is None:
                return self.async_show_form(step_id="init", data_schema=schema, errors={"base": "invalid_activity_ids"})

            # Validate custom period dates if monitor_custom is enabled
            monitor_custom = bool(user_input.get("monitor_custom", defaults["monitor_custom"]))
            custom_from = user_input.get("custom_from", defaults["custom_from"]) or ""
            custom_to = user_input.get("custom_to", defaults["custom_to"]) or ""
            if monitor_custom:
                # Both dates required and must be YYYY-MM-DD, from <= to
                try:
                    if not custom_from or not custom_to:
                        raise ValueError("missing")
                    dt_from = datetime.strptime(custom_from, "%Y-%m-%d").date()
                    dt_to = datetime.strptime(custom_to, "%Y-%m-%d").date()
                    if dt_from > dt_to:
                        raise ValueError("order")
                except Exception:
                    return self.async_show_form(step_id="init", data_schema=schema, errors={"base": "invalid_date"})

            # Validate quiet window times if enabled
            quiet_enabled = bool(user_input.get("quiet_window_enabled", defaults["quiet_window_enabled"]))
            quiet_from = user_input.get("quiet_window_from", defaults["quiet_window_from"]) or ""
            quiet_to = user_input.get("quiet_window_to", defaults["quiet_window_to"]) or ""
            if quiet_enabled:
                try:
                    datetime.strptime(quiet_from, "%H:%M")
                    datetime.strptime(quiet_to, "%H:%M")
                except Exception:
                    return self.async_show_form(step_id="init", data_schema=schema, errors={"base": "invalid_quiet_window"})

            # Save monitoring selections and global ID selections
            return self.async_create_entry(title="", data={
                "monitor_last_week": bool(user_input.get("monitor_last_week", defaults["monitor_last_week"])),
                "monitor_last_7_days": bool(user_input.get("monitor_last_7_days", defaults["monitor_last_7_days"])),
                "monitor_last_month": bool(user_input.get("monitor_last_month", defaults["monitor_last_month"])),
                "monitor_last_30_days": bool(user_input.get("monitor_last_30_days", defaults["monitor_last_30_days"])),
                "monitor_last_year": bool(user_input.get("monitor_last_year", defaults["monitor_last_year"])),
                "monitor_last_365_days": bool(user_input.get("monitor_last_365_days", defaults["monitor_last_365_days"])),
                "monitor_custom": monitor_custom,
                "custom_from": custom_from,
                "custom_to": custom_to,
                "enabled_appliances": ap_ids or "",
                "enabled_activities": act_ids or "",
                # Quiet window persistence
                "quiet_window_enabled": quiet_enabled,
                "quiet_window_from": quiet_from,
                "quiet_window_to": quiet_to,
                "quiet_window_pause_rest": bool(user_input.get("quiet_window_pause_rest", defaults["quiet_window_pause_rest"])),
            })
