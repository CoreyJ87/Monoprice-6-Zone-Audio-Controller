"""Support for interfacing with Monoprice 6 zone home audio controller."""

import logging
from typing import override

from pymonoprice import ZoneStatus

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .coordinator import CONNECTION_ERRORS, MonopriceCoordinator
from .entity import MonopriceEntity
from .utils import _get_sources

_LOGGER = logging.getLogger(__name__)

MAX_VOLUME = 38
PARALLEL_UPDATES = 1

# Bass level written by each sound mode, and the reverse lookup for display.
SOUND_MODE_BASS = {"Normal": 7, "High Bass": 12, "Medium Bass": 10, "Low Bass": 3}
BASS_SOUND_MODE = {v: k for k, v in SOUND_MODE_BASS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    coordinator = config_entry.runtime_data
    sources = _get_sources(config_entry)

    async_add_entities(
        MonopriceZone(coordinator, sources, config_entry.entry_id, (i * 10) + j)
        for i in range(1, 4)
        for j in range(1, 7)
    )


class MonopriceZone(MonopriceEntity, MediaPlayerEntity):
    """Representation of a Monoprice amplifier zone."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_name = None
    _attr_volume_step = 1 / MAX_VOLUME
    _attr_sound_mode_list = list(SOUND_MODE_BASS)

    def __init__(
        self, coordinator: MonopriceCoordinator, sources, namespace: str, zone_id: int
    ) -> None:
        """Initialize new zone."""
        super().__init__(coordinator, namespace, zone_id)
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._attr_source_list = sources[2]

        self._attr_unique_id = f"{namespace}_{zone_id}"
        self._snapshot: ZoneStatus | None = None

    @property
    @override
    def state(self) -> MediaPlayerState | None:
        """Return the power state of the zone."""
        if (status := self.zone_status) is None:
            return None
        return MediaPlayerState.ON if status.power else MediaPlayerState.OFF

    @property
    @override
    def volume_level(self) -> float | None:
        """Return the volume level, range 0..1."""
        if (status := self.zone_status) is None:
            return None
        return status.volume / MAX_VOLUME

    @property
    @override
    def is_volume_muted(self) -> bool | None:
        """Return True if the zone is muted."""
        if (status := self.zone_status) is None:
            return None
        return status.mute

    @property
    @override
    def source(self) -> str | None:
        """Return the currently selected source name."""
        if (status := self.zone_status) is None:
            return None
        return self._source_id_name.get(status.source)

    @property
    @override
    def sound_mode(self) -> str | None:
        """Return the sound mode matching the zone's current bass level."""
        if (status := self.zone_status) is None:
            return None
        return BASS_SOUND_MODE.get(status.bass)

    @property
    @override
    def media_title(self) -> str | None:
        """Return the current source as media title."""
        return self.source

    async def snapshot(self) -> None:
        """Save zone's current state."""
        zone_id = self._zone_id
        try:
            self._snapshot = await self.coordinator.async_execute(
                lambda client: client.zone_status(zone_id)
            )
        except HomeAssistantError as err:
            # Fall back to the last polled state so a later restore still works.
            if (status := self.zone_status) is None:
                raise
            _LOGGER.warning(
                "Snapshot of zone %d used last polled state (%s)", zone_id, err
            )
            self._snapshot = status
        if self._snapshot is None:
            raise HomeAssistantError(f"Zone {zone_id} returned no status to snapshot")

    async def restore(self) -> None:
        """Restore saved state."""
        if (snapshot := self._snapshot) is None:
            _LOGGER.warning(
                "No snapshot to restore for zone %d; call snapshot first", self._zone_id
            )
            return
        await self.coordinator.async_command(
            lambda client: client.restore_zone(snapshot),
            [self._zone_id],
            power=snapshot.power,
            mute=snapshot.mute,
            volume=snapshot.volume,
            treble=snapshot.treble,
            bass=snapshot.bass,
            balance=snapshot.balance,
            source=snapshot.source,
        )

    @override
    async def async_select_source(self, source: str) -> None:
        """Set input source."""
        if (idx := self._source_name_id.get(source)) is None:
            raise ServiceValidationError(f"Unknown source: {source}")
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_source(zone_id, idx), [zone_id], source=idx
        )

    @override
    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_power(zone_id, True), [zone_id], power=True
        )

    @override
    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_power(zone_id, False), [zone_id], power=False
        )

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_mute(zone_id, mute), [zone_id], mute=mute
        )

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        zone_id = self._zone_id
        level = round(volume * MAX_VOLUME)
        await self.coordinator.async_command(
            lambda client: client.set_volume(zone_id, level), [zone_id], volume=level
        )

    async def set_balance(self, level: int) -> None:
        """Set balance level."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_balance(zone_id, level), [zone_id], balance=level
        )

    async def set_bass(self, level: int) -> None:
        """Set bass level."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_bass(zone_id, level), [zone_id], bass=level
        )

    async def set_treble(self, level: int) -> None:
        """Set treble level."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_treble(zone_id, level), [zone_id], treble=level
        )

    async def set_zone_source(self, source: int) -> None:
        """Set input source by its numeric id."""
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_source(zone_id, source), [zone_id], source=source
        )

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Switch the sound mode of the entity."""
        if (bass := SOUND_MODE_BASS.get(sound_mode)) is None:
            raise ServiceValidationError(f"Unknown sound mode: {sound_mode}")
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_bass(zone_id, bass), [zone_id], bass=bass
        )
