# Installation

## HACS Store (coming soon)
Once approved and available in the HACS Store:
1. Open HACS → Integrations.
2. Search for "Tada" and install.
3. Restart Home Assistant.
4. Go to Settings → Devices & Services → Add Integration → "Tada".

## Install via HACS (Custom Repository)
Until store approval, install via Custom Repository:
1. In Home Assistant, open HACS → Integrations → three-dots menu → Custom repositories.
2. Paste this repository URL: https://github.com/sginestrini/home-assistant-tada-integration and choose Category: Integration.
3. Click Add.
4. Back in HACS → Integrations, search for "Tada" and install.
5. Restart Home Assistant.
6. Go to Settings → Devices & Services → Add Integration → "Tada".

## Manual (alternative)
1. In your Home Assistant configuration directory, ensure `custom_components` exists.
2. Copy the folder `custom_components/tada` from this repository into your Home Assistant `custom_components/` directory.
3. Restart Home Assistant.
