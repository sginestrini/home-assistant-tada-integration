# Troubleshooting

## Common issues
- Login errors: verify username/password match the Tada web app.
- Subscription issues: re-check the value from the Network tab; avoid leading/trailing spaces.
- Custom dates: use `YYYY-MM-DD` format when enabling custom range.
- Logs: check Home Assistant logs for error details (Settings → System → Logs).
- Reauthentication: if the integration requests reauthentication, re-enter your credentials in the prompted form.

## Entity ID Regeneration Behavior
Home Assistant’s "Regenerate entity ID" uses the current entity name to build the new `entity_id`. Summary sensors in this integration have human-friendly names like "Attività Cucinare kWh" or "Elettrodomestici Frigorifero %". If you click "Regenerate", Home Assistant may propose IDs like:

- sensor.attivita_cucinare_kwh
- sensor.elettrodomestici_frigorifero

However, the integration enforces a stable ID scheme at creation time (and upon reload) to keep period context in the ID, for example:

- sensor.tada_yesterday_attivita_cucinare_kwh
- sensor.tada_yesterday_elettrodomestici_frigorifero_percentuale

If you prefer to keep the original IDs, avoid using "Regenerate entity ID" for these sensors. If you already regenerated, simply reload the integration (or restart Home Assistant) and the integration will restore the original IDs on setup.

Tip: If you want regeneration to produce the same IDs, rename the entity to include the period prefix and unit (e.g., "Tada yesterday attività cucinare kWh"). Regeneration would then align with the original scheme.
