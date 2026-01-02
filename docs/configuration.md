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

### Midnight quiet window (Today sensor)
Some installations can observe inconsistent or transient backend data shortly after local midnight while the Tada backend rolls over daily totals. To avoid ingesting potentially inaccurate samples during that period, the integration provides a configurable quiet window after midnight:
- The `Today` total sensor becomes unavailable during the window, helping Home Assistant ignore potentially inconsistent samples.
- Optionally, the integration pauses REST calls during the window while keeping the websocket instant power sensor active.

Tip: You can start the quiet window before midnight. Set a wrap-around range like `23:50 → 00:20` to avoid samples right before and after midnight. Wrap-around ranges are supported — when the start time is later than the end time, the window spans midnight.

### Defaults
- Disabled by default.
- Window: 23:59 → 00:20.
- REST pause: on by default.

### Configure
- Home Assistant → Settings → Devices & Services → Tada → Configure
- Fields:
   - Quiet window after midnight (hide 'Today' sensor)
   - Quiet window start (HH:MM)
   - Quiet window end (HH:MM)
   - Pause REST polling during quiet window (keep websocket)

### Recommendations
- Keep “Pause REST polling during quiet window” enabled to avoid backend-derived samples during rollover.

### Why this helps
- Avoids ingesting inconsistent backend rollover samples around midnight.
- Reduces failed REST requests if the backend is busy recalculating daily totals right after midnight.
