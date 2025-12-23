# Timebands Apex Card (Semi‑Donut)

A Lovelace card that renders Tada timebands as a semi‑donut using ApexCharts. Works with either:
- Individual sensors per timeband (value and optional percentage)
- A single entity exposing a `timebands` attribute (array of `{ label, value, percentage }`)

## Install
1. Copy `cards/apex/timebands-apex-card.js` into your Home Assistant `config/www/` folder (for HACS custom repos this is typically `config/www/community/tada/`).
2. Add a Lovelace resource (Settings → Dashboards → Resources → Add Resource):
   - URL: `/local/community/tada/timebands-apex-card.js?v=0.12`
   - Type: JavaScript Module
3. Reload the dashboard (or hard refresh with Ctrl+F5).

Tip: When you update the file, bump the `?v=` query or hard refresh to avoid cache issues.

## Usage
### A) Individual sensors (recommended)
Computes percentages from `value_entity` if `percentage_entity` is omitted.

```yaml
type: custom:timebands-apex-card
title: Consumo di ieri per fasce
bands:
  - label: mattina
    value_entity: sensor.tada_yesterday_mattina_value
    percentage_entity: sensor.tada_yesterday_mattina_percentage
  - label: pomeriggio
    value_entity: sensor.tada_yesterday_pomeriggio_value
    percentage_entity: sensor.tada_yesterday_pomeriggio_percentage
  - label: sera
    value_entity: sensor.tada_yesterday_sera_value
    percentage_entity: sensor.tada_yesterday_sera_percentage
  - label: notte
    value_entity: sensor.tada_yesterday_notte_value
    percentage_entity: sensor.tada_yesterday_notte_percentage
size: 260
center_label: Totale
colors:
  mattina: '#2e7d32'
  pomeriggio: '#ff8f00'
  sera: '#d84315'
  notte: '#1976d2'
```

### B) Single entity with `timebands` attribute
The card reads an attribute named `timebands` (also supports `timebands_data`, `timebandsJson`, `timebands_json`). Each item is `{ label, value, percentage }`.

```yaml
type: custom:timebands-apex-card
title: Consumo per fasce
entity: sensor.tada_yesterday_overview
```

## Options
- `title`: Text shown at the top of the card.
- `size`: Chart width in pixels (default: `260`).
- `center_label`: Text under the total kWh in the center (default: `Totale`).
- `colors`: Mapping from label (lowercased) to color hex.
- `show_side_legend`: Set to `false` to hide the right-hand legend (default: `true`).
- `bands`: Array of band objects when not using `entity` mode:
  - `label`: e.g., `mattina`, `pomeriggio`, `sera`, `notte`.
  - `value_entity`: sensor with kWh value for the band.
  - `percentage_entity`: optional sensor with percent for the band.
- `entity`: A single entity exposing a `timebands` attribute to drive the card.

## Visual Editor
This card includes a basic Lovelace visual editor:
- Edit title, size, center label
- Switch between “Bands (entities)” and “Single entity (timebands attr)”
- Manage bands (label, `value_entity`, `percentage_entity`)
- Edit default colors for mattina/pomeriggio/sera/notte

If the visual editor is not shown immediately, reload the page after updating the resource.

## Troubleshooting
- Error: “Custom element doesn’t exist: timebands-apex-card”
  - Ensure the resource is added with Type “JavaScript Module”.
  - Confirm the file is accessible: open `https://<ha-host>/local/community/tada/timebands-apex-card.js?v=0.12` in your browser.
  - Bump the `?v=` query or hard refresh (Ctrl+F5).
  - Sometimes a server restart clears stale references.
- Tooltip flicker / white glow
  - Hover glow and expands are disabled by default; if you still notice flicker, try another theme or increase `size` for more room.
- Percent rounding
  - Slice labels are rounded to integer percent in the chart; legend shows integer percent and kWh with two decimals.

## Behavior Notes
- Center label/value: The center shows the hovered band name and its kWh. When not hovering, it shows "Totale" and the total kWh for the period.
- Tooltip: Displays the hovered band’s kWh.

## Notes
- Uses ApexCharts via CDN (`https://cdn.jsdelivr.net/npm/apexcharts`).
- Uses `lit-element` via module import from unpkg.
- The card computes percentages from values if no percent sensors are provided (when total value is > 0).

## Changelog (card)
- 0.12: Disable hover glow/expand, stabilize tooltip; add visual editor.
- 0.11: Initial release.
