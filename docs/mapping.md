# Mapping: Appliances and Activities

Summary entities use ID→name mappings to label sensors in Italian (unknown IDs are shown as their numeric value).

## Appliances (Elettrodomestici)
- 17 → Stand-by
- 1000 → Altro
- 12 → Macchina del caffè
- 10 → Piano Cottura
- 7 → Condizionatore
- 6 → Frigorifero
- 2 → Lavastoviglie
- 1 → Lavatrice
- 4 → Ferro da stiro

## Activities (Attività)
- 6 → Stand-by
- 1000 → Altro
- 3 → Cucinare
- 2 → Raffrescare
- 1 → Lavare

## Summary entities per item
Each enabled item produces two sensors per selected period when summary is toggled:
- kWh sensor: e.g., "Attività Cucinare kWh" or "Elettrodomestici Frigorifero kWh"
- % sensor: e.g., "Attività Cucinare %" or "Elettrodomestici Frigorifero %"

If `enabled_appliances`/`enabled_activities` are left empty, the integration will include all IDs present in the API response for the selected period. If you specify IDs, only those (intersected with what the API returns) will be created.
