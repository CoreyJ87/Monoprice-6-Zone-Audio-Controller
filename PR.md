# v1.4.0 — Core sync, bug fixes and cleanup

## Summary

Second modernization pass. Syncs the integration with the latest Home Assistant core `monoprice` component (pymonoprice 0.6.1/serialx, entity services), fixes three real bugs found in an audit of the fork, and clears out dead code and metadata drift. All custom features (extra platforms, services, sound modes) are preserved.

**Requires Home Assistant 2025.10.0 or newer** (uses the platform entity service helper introduced there).

## Synced from HA core

- **pymonoprice `0.5` → `0.6.1`** — pymonoprice replaced `pyserial` with `serialx`; all `SerialException` imports updated accordingly. Verified that serialx registers a native `socket://host:port` URL handler, so network-attached amps keep working unchanged.
- **Entity services migration** — snapshot/restore/set_balance/set_bass/set_treble/set_zone_source are now proper entity services registered once in `async_setup` via a new `services.py` (mirroring core), instead of ad-hoc handlers registered in the media_player platform. Schemas are validated by HA, and services now show names, descriptions and icons (`icons.json`) in the UI.
- **Style sync** — removed `from __future__ import annotations`, added `@override` decorators on overridden methods, matching current core conventions.
- **Intentionally skipped**: core's new `SerialPortSelector` config flow field — this fork uses `socket://` addresses, so the free-text "Device address" field stays.

## Bug fixes

- **Sound mode never displayed** — `select_sound_mode` wrote to `self._sound_mode` instead of `self._attr_sound_mode`, so the selected mode was silently dropped from state.
- **`set_all_zones_source` didn't set all zones** — a shadowed loop variable meant it only ever hit the targeted entities (multiple times each). It is now a domain service that sets zones 11–16 on every configured amplifier; a legacy `entity_id` field in old service calls is accepted and ignored.
- **Blocking serial I/O in the event loop (select platform)** — `current_option` was a property doing a live `zone_status()` call on every state write, on the event loop. Select entities are now polled like every other platform (`update()` in the executor, `PARALLEL_UPDATES = 1`) and `select_option` runs in the executor too.
- **Range fixes** — balance service schema allowed 0–21 for a 0–20 device. The bass/treble number sliders previously allowed −7…14 and sent whatever was picked straight to the amp, so negative values were invalid on the wire. They now genuinely work as centered cut/boost controls: the slider shows −7…+7 (0 = flat) and the entity converts to/from the device's raw 0–14 scale in both directions. The `set_bass`/`set_treble` services keep speaking raw 0–14 as always documented.

## Cleanup

- Removed dead, never-registered service handlers (and their unused imports) from `sensor.py` and `number.py`.
- Removed the unregistered `set_volume_level` entry from `services.yaml`; added `name`/`description` to all remaining services and `fields`.
- Collapsed `ATTR_BALANCE`/`ATTR_BASS`/`ATTR_TREBLE` (all `"level"`) into `ATTR_LEVEL`, and the two source attrs into `ATTR_SOURCE`.
- Select entities now use `_attr_has_entity_name` ("Source" under the zone device) — entity IDs and unique IDs are unchanged.
- `hacs.json`: fixed `iot_class` (`local_push` → `local_polling`), added `select` to domains, set minimum HA version to 2025.10.0.
- Added service names/descriptions to `translations/en.json` so they actually render (custom integrations don't resolve `strings.json` key references at runtime).
- Deliberately **not** fixed: the "Public Anouncement" sensor typo — the string is baked into existing unique IDs and renaming would orphan registry entries.

## Breaking changes

- `set_all_zones_source` no longer takes an entity target; it applies to all zones of all configured amps (which is what the name always promised). Existing calls that passed `entity_id` still validate.
- Minimum supported HA version is now 2025.10.0.

## Files changed

| File | Changes |
|------|---------|
| `__init__.py` | serialx import, `async_setup` + `CONFIG_SCHEMA`, service registration hook |
| `services.py` | **New** — entity service + all-zones service registration |
| `media_player.py` | Service plumbing removed, sound mode fix, entity service methods, `@override` |
| `select.py` | Rewritten as a polled platform; blocking-I/O fix, `has_entity_name` |
| `number.py` | Dead code removed, bass/treble range fix, serialx |
| `sensor.py` | Dead code removed, serialx |
| `config_flow.py` | serialx, `@override` (kept free-text device address field) |
| `const.py` | Attr constant consolidation |
| `manifest.json` | pymonoprice 0.6.1, version 1.4.0 |
| `services.yaml` / `strings.json` / `translations/en.json` / `icons.json` | Service metadata, ranges, icons |
| `hacs.json` | iot_class, domains, minimum HA version |

## Testing

- [x] All Python files pass syntax validation
- [x] JSON and YAML files validate
- [x] No stale references to old imports, constants or removed handlers
- [x] serialx `socket://` support verified against the published 1.8.2 wheel
- [ ] Verified on dev HA instance (zones respond, services fire, sound mode shows)
