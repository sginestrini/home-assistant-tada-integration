# Configuration & Options

## Add the integration from the UI
1. Open Home Assistant: Settings → Devices & Services → Add Integration.
2. Search for "Tada".
3. Enter the required fields:
   - Username: your Tada web app login.
   - Password: your Tada web app password.
   - Subscription ID: see the guide to retrieve it.
   - Locale: optional (default `it`).
4. Submit and wait for initial setup.

## Options
After the integration is added, you can configure:

### Monitoring ranges
Enable any of: Yesterday, Last week, Last 7/30/365 days, Last month, Last year, or a Custom date range.
- If you enable custom monitoring, set both `custom_from` and `custom_to` in `YYYY-MM-DD` format; otherwise you’ll get an `invalid_date` error.

### Summary (Appliances/Activities)
Toggle per-period creation of summary entities and optionally select which IDs to include.
- Period toggles: Yesterday, Last week, Last 7 days, Last month, Last 30 days, Last year, Last 365 days, and Custom.
- Selection fields: `enabled_appliances` and `enabled_activities` accept a comma-separated list of numeric IDs.
- Leave those fields empty to include ALL items found in the Tada summary payload for that period.
- If you later turn OFF the summary switch for a period, the integration removes ONLY the summary entities for that period (kWh and % for each item) on reload; other period sensors remain.
- If you deselect a monitored period entirely (e.g., uncheck "Last 7 days"), the integration removes ALL entities and the corresponding device for that period during reload.

The options UI is split into two steps: first monitoring/date, then a separate section for summary options (for a clearer visual division).
