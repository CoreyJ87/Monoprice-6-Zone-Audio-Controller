"""Data update coordinator for the Monoprice 6-Zone Amplifier."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
import logging
import threading
from typing import TypeVar

from pymonoprice import Monoprice, ZoneStatus, get_monoprice
from serialx import SerialException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

# How often the link is probed. A probe is a single cheap zone query; a full
# status read only happens at setup and after a connection failure.
SCAN_INTERVAL = timedelta(seconds=60)

# Only the main unit is polled; expansion units (zones 21-36) are not supported.
MAIN_UNIT = 1
MAIN_ZONES = range(11, 17)

# serialx raises TimeoutError (an OSError) when the amp stops answering and
# EOFError when the socket bridge closes the connection, neither of which is
# a SerialException.
CONNECTION_ERRORS = (SerialException, OSError, EOFError)


class MonopriceCoordinator(DataUpdateCoordinator[dict[int, ZoneStatus]]):
    """Poll the amplifier once per interval and share the result with all entities.

    All serial I/O goes through this class. A single bulk status query is issued
    per poll (instead of one query per entity), and any connection error drops
    the serial port so it is reopened on the next poll or command.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        port: str,
        client: Monoprice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {port}",
            update_interval=SCAN_INTERVAL,
        )
        self._port = port
        self._client: Monoprice | None = client
        # Serializes every serial operation (poll or command) across executor threads.
        self._io_lock = threading.Lock()
        # Set whenever the link drops so the next successful poll resyncs all zones.
        self._need_full_refresh = True

    @property
    def port(self) -> str:
        """Return the serial port / socket URL."""
        return self._port

    @property
    def connected(self) -> bool:
        """Return True if a serial connection is currently open."""
        return self._client is not None

    # ---- executor-side helpers (always called with _io_lock held) ----

    def _close_locked(self) -> None:
        client, self._client = self._client, None
        if client is None:
            return
        try:
            client._port.close()  # noqa: SLF001 - pymonoprice exposes no close()
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error closing Monoprice port %s", self._port, exc_info=True)

    def _drop_connection_locked(self, err: BaseException) -> None:
        if self._client is None:
            return
        _LOGGER.warning(
            "Lost connection to Monoprice amplifier at %s (%s); "
            "will reconnect on the next poll or command",
            self._port,
            err,
        )
        self._need_full_refresh = True
        self._close_locked()

    def _get_client_locked(self) -> Monoprice:
        if self._client is not None:
            return self._client
        _LOGGER.debug("Reconnecting to Monoprice amplifier at %s", self._port)
        self._client = get_monoprice(self._port)
        _LOGGER.info("Reconnected to Monoprice amplifier at %s", self._port)
        return self._client

    def _run(self, func: Callable[[Monoprice], _T]) -> _T:
        """Run ``func(client)`` under the I/O lock, (re)connecting first if needed."""
        with self._io_lock:
            client = self._get_client_locked()
            try:
                return func(client)
            except CONNECTION_ERRORS as err:
                self._drop_connection_locked(err)
                raise

    def close(self) -> None:
        """Close the serial connection (executor)."""
        with self._io_lock:
            self._close_locked()

    # ---- event-loop side ----

    @staticmethod
    def _fetch(client: Monoprice) -> dict[int, ZoneStatus]:
        statuses = client.all_zone_status(MAIN_UNIT)
        if not statuses:
            # Some units do not answer the bulk "?10" query; fall back to per-zone.
            _LOGGER.debug("Bulk zone status returned nothing, querying zones individually")
            statuses = [
                status
                for zone in MAIN_ZONES
                if (status := client.zone_status(zone)) is not None
            ]
        return {status.zone: status for status in statuses}

    @staticmethod
    def _probe(client: Monoprice) -> ZoneStatus | None:
        """Cheapest possible liveness check: one zone status query."""
        return client.zone_status(MAIN_ZONES[0])

    async def _async_update_data(self) -> dict[int, ZoneStatus]:
        """Check the link is alive; resync all zones only after a failure.

        Commands keep the cached state up to date, so the periodic tick just
        sends a single zone query to detect a dead link. A full read of every
        zone happens at setup and once after a reconnect.
        """
        try:
            if self._need_full_refresh or not self.connected or not self.data:
                data = await self.hass.async_add_executor_job(self._run, self._fetch)
                if not data:
                    raise UpdateFailed(
                        f"Monoprice amplifier at {self._port} returned no zone status"
                    )
                self._need_full_refresh = False
                return data

            status = await self.hass.async_add_executor_job(self._run, self._probe)
        except CONNECTION_ERRORS as err:
            raise UpdateFailed(
                f"Monoprice amplifier at {self._port} is not responding: {err}"
            ) from err
        if status is None:
            raise UpdateFailed(
                f"Monoprice amplifier at {self._port} gave an unparseable reply"
            )
        self.data[status.zone] = status
        return self.data

    async def async_execute(self, func: Callable[[Monoprice], _T]) -> _T:
        """Run a command against the amplifier from the event loop.

        Raises HomeAssistantError if the amplifier cannot be reached, so service
        calls fail visibly instead of silently.
        """
        try:
            return await self.hass.async_add_executor_job(self._run, func)
        except CONNECTION_ERRORS as err:
            raise HomeAssistantError(
                f"Monoprice amplifier at {self._port} is not responding: {err}"
            ) from err

    async def async_command(
        self, func: Callable[[Monoprice], object], zone_ids: list[int], **changes
    ) -> None:
        """Run a state-changing command and apply it to the cached zone state.

        No serial read follows the write: the cached ZoneStatus of each zone in
        ``zone_ids`` is patched with ``changes`` and listeners are notified, so
        the UI reacts immediately. The periodic poll reconciles any drift.
        """
        await self.async_execute(func)
        if not self.data or not changes:
            return
        for zone_id in zone_ids:
            if (status := self.data.get(zone_id)) is not None:
                self.data[zone_id] = replace(status, **changes)
        self.async_update_listeners()
