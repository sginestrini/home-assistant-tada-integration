# Tada (Unofficial) – Home Assistant Integration

This is an unofficial Home Assistant integration for the Tada service. I am not associated with www.tadapower.it. This is my first integration, so there may be bugs or limitations.

## Overview
- Fetches account data from Tada’s cloud APIs.
- Provides sensors and (optionally) binary sensors for monitoring.
- Polling-based integration; update interval defaults may apply.

## Installation
### Manual (recommended for now)
1. In your Home Assistant configuration directory, create `custom_components` if it doesn’t exist.
2. Copy the folder `custom_components/tada` from this repository into your Home Assistant `custom_components/` directory (resulting path: `custom_components/tada`).
3. Restart Home Assistant.

### Install via HACS (Custom Repository)
If you use HACS, you can add this repository and install the integration easily:

1. In Home Assistant, open HACS → Integrations → three-dots menu → Custom repositories.
2. Paste this repository URL (https://github.com/sginestrini/home-assistant-tada-integration) and choose Category: `Integration`.
3. Click Add.
4. Back in HACS → Integrations, search for "Tada" and install.
5. Restart Home Assistant.
6. Go to Settings → Devices & Services → Add Integration → "Tada".

## Configuration
Add the integration from the UI:
1. Open Home Assistant: Settings → Devices & Services → "Add Integration".
2. Search for "Tada".
3. Enter the required fields:
   - Username: your Tada web app login.
   - Password: your Tada web app password.
   - Subscription ID: see guide below to retrieve it.
   - Locale: optional (default `it`).
4. Submit and wait for initial setup.

### Options
After the integration is added, you can configure:

- Monitoring ranges: enable any of last week, last 7/30/365 days, last month, last year, or a custom date range.
   - If you enable custom monitoring, set both `custom_from` and `custom_to` in `YYYY-MM-DD` format; otherwise you’ll get an `invalid_date` error.

- Summary (Appliances/Activities): toggle per-period creation of summary entities and optionally select which IDs to include.
   - Period toggles: Yesterday, Last week, Last 7 days, Last month, Last 30 days, Last year, Last 365 days, and Custom.
   - Selection fields: `enabled_appliances` and `enabled_activities` accept a comma-separated list of numeric IDs.
   - Leave those fields empty to include ALL items found in the Tada summary payload for that period.
   - If you later turn OFF the summary switch for a period, the integration removes ONLY the summary entities for that period (kWh and % for each item) on reload; other period sensors remain.
   - If you deselect a monitored period entirely (e.g., uncheck "Last 7 days"), the integration removes ALL entities and the corresponding device for that period during reload.

The options UI is split into two steps: first monitoring/date, then a separate section for summary options (for a clearer visual division).

## Retrieve your Subscription ID
You can obtain `subscription_id` by inspecting network API calls in the Tada web application. It is present in every API call inside the page:

Page: https://webapp.tada.magie-tada.com/it/la-tua-casa

Follow these steps (Chrome/Edge/Firefox):
1. Log in to the Tada web app and navigate to "La tua casa".
2. Open Developer Tools:
   - Chrome/Edge: press `F12` or `Ctrl+Shift+I`.
   - Firefox: press `F12` or `Ctrl+Shift+I`.
3. Go to the "Network" tab.
   - Enable "Preserve log" if available.
   - Filter by "Fetch/XHR" requests to see API calls.
4. Reload the page or interact with the dashboard so calls appear.
5. Click any XHR/API request listed and inspect:
   - Headers → URL/query string: look for `subscription_id`.
   - Payload/Request body (if present): look for `subscription_id`.
   - Response (if easier): some endpoints echo `subscription_id`.
6. Copy the exact `subscription_id` value (it may be numeric or alphanumeric) and paste it into the integration configuration in Home Assistant.

Tips:
- Multiple API calls will contain `subscription_id`; any matching value is fine.
- If you don’t see API calls, ensure you’re on "La tua casa", then reload.

## Mapping: Appliances and Activities

Summary entities use the following ID→name mappings to label sensors in Italian (you can still use any ID—unknown IDs are shown as their numeric value):

- Appliances (Elettrodomestici):
   - 17 → Stand-by
   - 1000 → Altro
   - 6 → Frigorifero
   - 2 → Lavastoviglie
   - 1 → Lavatrice
   - 4 → Ferro da stiro

- Activities (Attività):
   - 6 → Stand-by
   - 1000 → Altro
   - 3 → Cucinare
   - 1 → Lavare

Each enabled item produces two sensors per period when summary is toggled for that period:
- kWh sensor: e.g., "Attività Cucinare kWh" or "Elettrodomestici Frigorifero kWh"
- % sensor: e.g., "Attività Cucinare %" or "Elettrodomestici Frigorifero %"

If `enabled_appliances`/`enabled_activities` are left empty, the integration will automatically include all IDs present in the API response for the selected period. If you specify IDs, only those (intersected with what the API returns) will be created.

## Notes & Disclaimer
- Unofficial: not affiliated with Tada or tadapower.it.
- Credentials: stored in your local Home Assistant instance; handle with care.
- Network: the integration uses cloud APIs; connectivity is required.
- Bugs: as this is an early version, issues may exist.

## Troubleshooting
- Login errors: verify username/password match the Tada web app.
- Subscription issues: re-check the value from Network tab; avoid leading/trailing spaces.
- Custom dates: use `YYYY-MM-DD` format when enabling custom range.
- Logs: check Home Assistant logs for error details (Settings → System → Logs).
 - Reauthentication: if the integration requests reauthentication, re-enter your credentials in the prompted form.

### Entity ID Regeneration Behavior
Home Assistant’s "Regenerate entity ID" uses the current entity name to build the new entity_id. Summary sensors in this integration have human-friendly names like "Attività Cucinare kWh" or "Elettrodomestici Frigorifero %". If you click "Regenerate", Home Assistant will propose IDs like:

- sensor.attivita_cucinare_kwh
- sensor.elettrodomestici_frigorifero

However, the integration enforces a stable ID scheme at creation time (and upon reload) to keep period context in the ID, e.g.:

- sensor.tada_yesterday_attivita_cucinare_kwh
- sensor.tada_yesterday_elettrodomestici_frigorifero_percentuale

If you prefer to keep the original IDs, avoid using "Regenerate entity ID" for these sensors. If you already regenerated, simply reload the integration (or restart Home Assistant) and the integration will restore the original IDs on setup.

Tip: If you want regeneration to produce the same IDs, you can rename the entity to include the period prefix and unit (e.g., "Tada yesterday attività cucinare kWh"). Regeneration would then align with the original scheme.

## Lovelace Card (Apex)
- Semi‑donut chart of timebands using ApexCharts.
- See full docs and examples in [cards/apex/timebands-apex-card.md](cards/apex/timebands-apex-card.md).

## Contributing / Issues
- Feel free to open issues or suggestions in this repository.
- PRs are welcome, especially for bug fixes, improvements, and docs.
