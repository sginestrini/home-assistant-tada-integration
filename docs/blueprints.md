# Blueprints and Packages

This page documents the ready-to-use YAML provided by the Tada integration to help you set up Italian bioraria energy tariffs and power limit alarms.

- Energy tariffs package (F1/F23) for accurate lifetime energy tracking and tariff switching.
- Power limit alarms automation with multi-level thresholds, reminders, and escalation.

## Energy Tariffs Package (F1/F23)

Location: [blueprints/packages/energy_tariffs_tada.yaml](../blueprints/packages/energy_tariffs_tada.yaml)

### What it does
- Adds an `input_number` (`input_number.tada_base_energy`) used to make the daily "today" energy sensor cumulative across midnights.
- Creates `sensor.tada_total_energy` (total_increasing) that sums `sensor.tada_consumption_today` + base to avoid negative bars at midnight.
- Defines a `utility_meter` named "Home Energy Bioraria" (`home_energy_bioraria`) with tariffs `F1` and `F23` fed by `sensor.tada_total_energy`.
- Includes automations to:
  - Roll the base forward nightly at 23:59:55.
  - Switch tariffs between `F1` and `F23` based on Italian workdays (ARERA/Hera hours).
  - Optionally re-align when the Italian workday calendar events start/end.

### Prerequisites
- Tada integration installed and `sensor.tada_consumption_today` available.
- Optional: `binary_sensor.giorno_lavorativo` and `calendar.giorno_lavorativo_calendar` for workday detection.

### Installation (Home Assistant Packages)
1. Enable packages in your `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Alternatively include the single file:

```yaml
homeassistant:
  packages:
    energy_tariffs_tada: !include packages/energy_tariffs_tada.yaml
```

2. Copy the file content from this repo into your Home Assistant config folder under `packages/energy_tariffs_tada.yaml`.
3. Restart Home Assistant.

### Entities created
- `input_number.tada_base_energy`: Stores the cumulative base in kWh.
- `sensor.tada_total_energy`: Total increasing energy sensor in kWh.
- `select.home_energy_bioraria`: Tariff selector (F1/F23) created by the utility meter.
- Utility meter sensors per tariff (e.g., `sensor.home_energy_bioraria_f1`, `sensor.home_energy_bioraria_f23`).

### Automations explained
- Nightly rollover (23:59:55): Adds the current `sensor.tada_consumption_today` to the base so the next day starts from the cumulative total.
- Tariff switching:
  - F1: Mon–Fri 08:00–19:00 when `binary_sensor.giorno_lavorativo` is `on`.
  - F23: All other times (evenings/nights, Saturday, Sunday, holidays).
- Calendar alignment (optional): Triggers the tariff switch automation when `calendar.giorno_lavorativo_calendar` events begin/end.

You can customize trigger times or remove the calendar alignment if you do not use the workday calendar.

## Power Limit Alarms Automation

Location: [blueprints/automation/tada/alarms.yaml](../blueprints/automation/tada/alarms.yaml)

### What it does
Raises notifications when your instant power exceeds the contracted power (`ap_w`) at three levels:
- 100%: Immediate notification; no reminders.
- 110%: Immediate + reminder every 10 minutes; after 2h45m persistence, sends "Allarme 15'".
- 133%: Immediate + reminder every 30 seconds; after 2 minutes persistence, sends "Allarme 2'".

### Prerequisites
- Tada integration installed and `sensor.tada_instant_power` available.
- Set `ap_w` (in watts) to your contracted power. Default in the file is `4500`.
- Replace the notify service (`notify.mobile_app_iponz_4_simone`) with your device or preferred notification target.

### Importing the automation
You can create an automation in Home Assistant and paste the YAML:
1. Settings → Automations & Scenes → Automations → Add Automation → Start with Empty Automation.
2. Click the three dots → Edit in YAML.
3. Paste the contents of `alarms.yaml` and adjust:
   - `variables.ap_w` and `trigger_variables.ap_w` to your contracted power.
   - All `notify.mobile_app_*` actions to point to your configured notify service(s).
4. Save.

The automation is defined with `mode: parallel` so multiple branches can run concurrently if thresholds change.

## Verification
- Energy tariffs:
  - After restart, confirm `input_number.tada_base_energy`, `sensor.tada_total_energy`, and `select.home_energy_bioraria` exist.
  - At 23:59:55, base should increase by the current `sensor.tada_consumption_today`.
  - Between 08:00–19:00 on workdays, the tariff should switch to `F1`; otherwise `F23`.
- Alarms:
  - Temporarily lower `ap_w` for testing, or simulate high `sensor.tada_instant_power` values, and verify notifications/reminders.

## Troubleshooting
- Unknown/unavailable sensors:
  - Ensure the Tada integration is properly configured and sensors (`sensor.tada_consumption_today`, `sensor.tada_instant_power`) are available.
- No `select.home_energy_bioraria`:
  - Confirm the `utility_meter` is created and the `source` `sensor.tada_total_energy` is available.
- Workday detection:
  - If you do not use `binary_sensor.giorno_lavorativo`, set the tariff manually via the `select.home_energy_bioraria` entity or customize the time conditions.
- Notification service errors:
  - Replace notify targets with your configured service (e.g., `notify.mobile_app_<your_device>` or other notify platforms).

## Related Files
- Energy tariffs package: [blueprints/packages/energy_tariffs_tada.yaml](../blueprints/packages/energy_tariffs_tada.yaml)
- Alarms automation: [blueprints/automation/tada/alarms.yaml](../blueprints/automation/tada/alarms.yaml)
