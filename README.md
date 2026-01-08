
# Tada (Unofficial) – Home Assistant Integration
[![hacs_badge](https://img.shields.io/badge/HACS-Default-blue.svg?style=for-the-badge&logo=home-assistant)](https://hacs.xyz/)
[![Version](https://img.shields.io/github/v/release/sginestrini/home-assistant-tada-integration?style=for-the-badge)](https://github.com/sginestrini/home-assistant-tada-integration/releases)

Unofficial Home Assistant integration for the Tada service. Not affiliated with tadapower.it.
Provides polling-based sensors and optional binary sensors sourced from Tada cloud APIs.

Download and install directly through [HACS (Home Assistant Community Store)](https://hacs.xyz/):

[![Open your Home Assistant instance and open the Tada (Unofficial) – Home Assistant Integration inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=itginestrins&repository=home-assistant-tada-integration&category=integration)

Status: This integration is now approved and available in the HACS Store! You can install it directly using the button above.

## Quick Start
- Install: see [docs/installation.md](docs/installation.md)
- Configure: see [docs/configuration.md](docs/configuration.md)
- Retrieve subscription ID: see [docs/subscription-id.md](docs/subscription-id.md)

## Features
- Fetches account data via Tada cloud APIs
- Sensors and optional binary sensors for monitoring
- Period-based summary entities (appliances/activities)
- Custom date range support

## Documentation
- Installation: [docs/installation.md](docs/installation.md)
- Configuration & Options: [docs/configuration.md](docs/configuration.md)
- Subscription ID guide: [docs/subscription-id.md](docs/subscription-id.md)
- Mapping (Appliances & Activities): [docs/mapping.md](docs/mapping.md)
- Blueprints & Packages: [docs/blueprints.md](docs/blueprints.md)
- Troubleshooting & Entity ID regeneration: [docs/troubleshooting.md](docs/troubleshooting.md)
- Contributing: [docs/contributing.md](docs/contributing.md)

## Lovelace Card (Apex)
- Semi‑donut chart of timebands using ApexCharts.
- See docs and examples in [cards/apex/timebands-apex-card.md](cards/apex/timebands-apex-card.md).

## Notes
- Unofficial, community-maintained project.
- Credentials stay in your Home Assistant instance.
- Requires internet connectivity to reach Tada cloud APIs.

## License
- See [LICENSE](LICENSE).
