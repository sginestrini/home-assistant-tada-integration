# Tada (Unofficial) – Home Assistant Integration
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://hacs.xyz/)
[![hacs_store_status](https://img.shields.io/badge/HACS-Store%20Pending-FFC107.svg?style=for-the-badge)](https://hacs.xyz/)

Unofficial Home Assistant integration for the Tada service. Not affiliated with tadapower.it. Provides polling-based sensors and optional binary sensors sourced from Tada cloud APIs.

Status: A PR is open to add this integration to the HACS Store. Until approval, please install via the HACS Custom Repository or manual steps.

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
