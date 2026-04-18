"""Tada sensor platform — package entry point."""
from __future__ import annotations
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import (
    DOMAIN,
    DEVICE_NAME_BASE,
    DEVICE_NAME_TODAY,
    DEVICE_NAME_YESTERDAY,
    DEVICE_SUFFIX_BASE,
    DEVICE_SUFFIX_TODAY,
    DEVICE_SUFFIX_YESTERDAY,
    DEFAULT_QUIET_WINDOW_ENABLED,
    DEFAULT_QUIET_WINDOW_FROM,
    DEFAULT_QUIET_WINDOW_TO,
)
from ..api import TadaAPI
from ..utils import _parse_ids, _present_ids_from_summary

from .base import TadaValueSensor
from .consumption import (
    TadaConsumptionTodayHourlySensor,
    TadaConsumptionPeriodSensor,
    TadaLifetimeEnergySensor,
)
from .power import TadaInstantPowerSensor, TadaPowerEventSensor
from .timebands import TadaTimebandsSensor, TadaTimebandSplitSensor
from .comparison import (
    TadaComparisonValueSensor,
    TadaAnnualReferenceSensor,
    PeriodCoverageTimestampSensor,
)
from .summary import TadaSummaryItemSensor, _add_summary_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tada sensors from a config entry."""
    runtime_data = entry.runtime_data
    if not runtime_data:
        _LOGGER.error("Tada integration data missing in entry.runtime_data")
        return False

    coordinator = runtime_data.coordinator
    api: TadaAPI = runtime_data.api
    subscription_id = entry.data.get("subscription_id")

    if coordinator is None or api is None or subscription_id is None:
        _LOGGER.error("Missing coordinator/api/subscription_id for Tada sensors")
        return False

    entities: list[SensorEntity] = []
    opts = entry.options or {}

    # Today device: TODAY group sensors
    # Pass quiet window options to the today sensor
    q_enabled = opts.get("quiet_window_enabled", DEFAULT_QUIET_WINDOW_ENABLED)
    q_from = opts.get("quiet_window_from", DEFAULT_QUIET_WINDOW_FROM)
    q_to = opts.get("quiet_window_to", DEFAULT_QUIET_WINDOW_TO)
    entities.append(TadaConsumptionTodayHourlySensor(
        coordinator,
        subscription_id,
        device_name=DEVICE_NAME_TODAY,
        device_id_suffix=DEVICE_SUFFIX_TODAY,
        quiet_window_enabled=q_enabled,
        quiet_window_from=q_from,
        quiet_window_to=q_to,
    ))
    entities.append(TadaInstantPowerSensor(hass, subscription_id, device_name=DEVICE_NAME_TODAY, device_id_suffix=DEVICE_SUFFIX_TODAY))
    # Base Tada device: GENERAL sensors
    entities.append(TadaValueSensor(coordinator, "Available Power", "power_latest", "availablePower", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Current Power", "power_latest", "value", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Power Usage %", "power_latest", "powerUsagePercent", "%", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaValueSensor(coordinator, "Max Available Power", "power_latest", "maxAvailablePower", "kW", subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    # Lifetime total energy (total_increasing) for Energy dashboard
    entities.append(TadaLifetimeEnergySensor(coordinator, subscription_id, device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))

    # Power Events sensors
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last30Days", "alarms", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last30Days", "cutoffs", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last90Days", "alarms", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    entities.append(TadaPowerEventSensor(coordinator, subscription_id, "last90Days", "cutoffs", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))

    # Add dynamic coverage-start sensors based on options
    monitor_custom = opts.get("monitor_custom", False)
    custom_from = opts.get("custom_from")
    custom_to = opts.get("custom_to")

    # Yesterday device
    entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, "yesterday", "yesterday", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
    entities.append(PeriodCoverageTimestampSensor(coordinator, subscription_id, "yesterday", "yesterday", device_name=DEVICE_NAME_BASE, device_id_suffix=DEVICE_SUFFIX_BASE))
    # Yesterday timeband split sensors (value + percentage for 4 bands)
    for band in ("notte", "mattina", "pomeriggio", "sera"):
        entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, "yesterday", band, "value", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
        entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, "yesterday", band, "percentage", device_name=DEVICE_NAME_YESTERDAY, device_id_suffix=DEVICE_SUFFIX_YESTERDAY))
    # Yesterday comparison sensors
    entities.append(TadaComparisonValueSensor(
        coordinator,
        subscription_id,
        source_key="comparisons_average_yesterday",
        value_key="averageEnergyComparison",
        name="Yesterday Average Comparison",
        unit="%",
        scale_percent=True,
        device_name=DEVICE_NAME_YESTERDAY,
        device_id_suffix=DEVICE_SUFFIX_YESTERDAY,
        translation_key="tada_comparison_yesterday_average_percent",
    ))
    entities.append(TadaComparisonValueSensor(
        coordinator,
        subscription_id,
        source_key="comparisons_previous_yesterday",
        value_key="previousEnergyComparison",
        name="Yesterday Previous Comparison",
        unit="kWh",
        scale_percent=False,
        device_name=DEVICE_NAME_YESTERDAY,
        device_id_suffix=DEVICE_SUFFIX_YESTERDAY,
        translation_key="tada_comparison_yesterday_previous_kwh",
    ))

    # Add optional extra last-* period sensors based on options
    extra_periods = [
        ("last-week", "last_week", "monitor_last_week", "Last week"),
        ("last-7-days", "last_7_days", "monitor_last_7_days", "Last 7 days"),
        ("last-month", "last_month", "monitor_last_month", "Last month"),
        ("last-30-days", "last_30_days", "monitor_last_30_days", "Last 30 days"),
        ("last-year", "last_year", "monitor_last_year", "Last year"),
        ("last-365-days", "last_365_days", "monitor_last_365_days", "Last 365 days"),
    ]

    # Add selected period devices/entities
    for period_param, key_suffix, opt_name, label in extra_periods:
        if not opts.get(opt_name):
            continue
        dev_name = f"Tada {label}"
        dev_suffix = key_suffix
        # total sensor
        entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, key_suffix, label, device_name=dev_name, device_id_suffix=dev_suffix))
        # timebands split sensors (4 bands x 2 modes = 8 sensors)
        for band in ("notte", "mattina", "pomeriggio", "sera"):
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key_suffix, band, "value", device_name=dev_name, device_id_suffix=dev_suffix))
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key_suffix, band, "percentage", device_name=dev_name, device_id_suffix=dev_suffix))
        # comparison sensors for periods that expose comparisons
        comparison_periods = {"last_week", "last_7_days"}
        if key_suffix in comparison_periods:
            entities.append(TadaComparisonValueSensor(
                coordinator,
                subscription_id,
                source_key=f"comparisons_average_{key_suffix}",
                value_key="averageEnergyComparison",
                name=f"{label} Average Comparison",
                unit="%",
                scale_percent=True,
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_comparison_{key_suffix}_average_percent",
            ))
            entities.append(TadaComparisonValueSensor(
                coordinator,
                subscription_id,
                source_key=f"comparisons_previous_{key_suffix}",
                value_key="previousEnergyComparison",
                name=f"{label} Previous Comparison",
                unit="%",
                scale_percent=True,
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_comparison_{key_suffix}_previous_percent",
            ))
        # annual-reference sensors for supported periods
        annual_ref_periods = {"last_month", "last_30_days", "last_year", "last_365_days"}
        if key_suffix in annual_ref_periods:
            entities.append(TadaAnnualReferenceSensor(
                coordinator,
                subscription_id,
                source_key=f"annual_reference_{key_suffix}",
                name=f"{label} Annual Reference",
                device_name=dev_name,
                device_id_suffix=dev_suffix,
                translation_key=f"tada_annual_reference_{key_suffix}",
            ))

        # Summary sensors (appliances/activities) if enabled for this period
        if opts.get(f"summary_{key_suffix}"):
            selected_appliances = _parse_ids(opts.get("enabled_appliances"))
            selected_activities = _parse_ids(opts.get("enabled_activities"))
            present_appliances = _present_ids_from_summary(coordinator, key_suffix, "appliance")
            present_activities = _present_ids_from_summary(coordinator, key_suffix, "activity")
            enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
            enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
            _add_summary_entities(entities, coordinator, subscription_id, key_suffix, dev_name, dev_suffix, enabled_appliances, enabled_activities)
    if monitor_custom and custom_from and custom_to:
        key = f"custom_{custom_from}_{custom_to}"
        label = f"{custom_from}..{custom_to}"
        dev_name = f"Tada {label}"
        dev_suffix = key
        # coverage sensor attached to Today device (diagnostic/general)
        entities.append(PeriodCoverageTimestampSensor(coordinator, subscription_id, key, label, device_name=DEVICE_NAME_TODAY, device_id_suffix=DEVICE_SUFFIX_TODAY))
        # custom period sensors: total and timeband splits
        entities.append(TadaConsumptionPeriodSensor(coordinator, subscription_id, key, label, device_name=dev_name, device_id_suffix=dev_suffix))
        for band in ("notte", "mattina", "pomeriggio", "sera"):
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key, band, "value", device_name=dev_name, device_id_suffix=dev_suffix))
            entities.append(TadaTimebandSplitSensor(coordinator, subscription_id, key, band, "percentage", device_name=dev_name, device_id_suffix=dev_suffix))

        # Custom summary sensors if enabled
        if opts.get("summary_custom"):
            selected_appliances = _parse_ids(opts.get("enabled_appliances"))
            selected_activities = _parse_ids(opts.get("enabled_activities"))
            present_appliances = _present_ids_from_summary(coordinator, key, "appliance")
            present_activities = _present_ids_from_summary(coordinator, key, "activity")
            enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
            enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
            _add_summary_entities(entities, coordinator, subscription_id, key, dev_name, dev_suffix, enabled_appliances, enabled_activities)

    # Yesterday summary sensors if enabled
    if opts.get("summary_yesterday"):
        key_suffix = "yesterday"
        selected_appliances = _parse_ids(opts.get("enabled_appliances"))
        selected_activities = _parse_ids(opts.get("enabled_activities"))
        present_appliances = _present_ids_from_summary(coordinator, key_suffix, "appliance")
        present_activities = _present_ids_from_summary(coordinator, key_suffix, "activity")
        enabled_appliances = present_appliances if not selected_appliances else (present_appliances & selected_appliances)
        enabled_activities = present_activities if not selected_activities else (present_activities & selected_activities)
        _add_summary_entities(entities, coordinator, subscription_id, key_suffix, DEVICE_NAME_YESTERDAY, DEVICE_SUFFIX_YESTERDAY, enabled_appliances, enabled_activities)

    async_add_entities(entities, update_before_add=True)
