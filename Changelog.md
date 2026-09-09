9/9/26 - v1.5.0 - Stop polling every entity (was ~54 serial round-trips per cycle); all zones are read once at setup, commands update the cached state directly, and a single zone query every 60s only checks the link is alive. Fixes "took longer than the scheduled update interval" warnings and snapshot/restore service timeouts
9/9/26 - v1.5.0 - Automatically reconnect when the serial/socket link drops and resync all zones, instead of failing forever until a manual reload
9/9/26 - v1.5.0 - Catch serialx TimeoutError/EOFError (not subclasses of SerialException) so a dead link marks entities unavailable instead of spamming "Update for ... fails" tracebacks
9/9/26 - v1.5.0 - Source select and media player source/sound mode are populated immediately after a reload/restart
9/9/26 - v1.5.0 - Sound mode is read back from the zone's bass level rather than remembered from the last selection
9/9/26 - v1.5.0 - Service calls raise a visible error when the amplifier is unreachable or an unknown source/sound mode is requested
7/19/26 - v1.4.0 - Bump pymonoprice to 0.6.1 (pyserial replaced by serialx, socket:// addresses still supported)
7/19/26 - v1.4.0 - Migrate custom services to entity services (services.py), requires HA 2025.10+
7/19/26 - v1.4.0 - Fix sound mode selection never showing the selected mode in the UI
7/19/26 - v1.4.0 - Fix set_all_zones_source only affecting targeted entities (now sets zones 11-16 on every configured amp)
7/19/26 - v1.4.0 - Fix select entities doing blocking serial I/O in the event loop (now polled like other platforms)
7/19/26 - v1.4.0 - Fix balance service range (0-21 -> 0-20); bass/treble sliders are now true -7..+7 cut/boost controls (converted to the device's raw 0-14 scale, previously negative values were sent raw and invalid)
7/19/26 - v1.4.0 - Remove dead service handlers in sensor/number, remove unregistered set_volume_level from services.yaml
7/19/26 - v1.4.0 - Add service icons (icons.json), service names/descriptions in the UI, misc style sync with HA core
4/24/22 - Fix balance controls on number entitys and monoprice_custom.set_balance
4/24/22 - Fix balance range monoprice_custom.set_balance from 1-19 to 0-20
4/24/22 - Disable zones 10, 20, 30 by default, there seems to be some issues with these zones. Enable with caution.