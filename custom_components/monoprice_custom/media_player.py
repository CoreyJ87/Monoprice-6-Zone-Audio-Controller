"""Support for interfacing with Monoprice 6 zone home audio controller."""

import logging
from typing import override

from serialx import SerialException

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .const import DOMAIN
from .utils import _get_sources

_LOGGER = logging.getLogger(__name__)

MAX_VOLUME = 38
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config_entry.data[CONF_PORT]

    monoprice = config_entry.runtime_data.client

    sources = _get_sources(config_entry)

    entities = []
    for i in range(1, 4):
        for j in range(1, 7):
            zone_id = (i * 10) + j
            _LOGGER.debug("Adding zone %d for port %s", zone_id, port)
            entities.append(
                MonopriceZone(monoprice, sources, config_entry.entry_id, zone_id)
            )

    # only call update before add if it's the first run so we can try to detect zones
    async_add_entities(entities, config_entry.runtime_data.first_run)


class MonopriceZone(MediaPlayerEntity):
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
    _attr_has_entity_name = True
    _attr_name = None
    _attr_volume_step = 1 / MAX_VOLUME
    _attr_sound_mode_list = ["Normal", "High Bass", "Medium Bass", "Low Bass"]
    _attr_sound_mode = None

    def __init__(self, monoprice, sources, namespace, zone_id):
        """Initialize new zone."""
        self._monoprice = monoprice
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._attr_source_list = sources[2]

        self._zone_id = zone_id
        self._attr_unique_id = f"{namespace}_{self._zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {self._zone_id}",
        )

        self._snapshot = None
        self._update_success = True

    def update(self) -> None:
        """Retrieve latest state."""
        if self._zone_id > 20:
            self._update_success = False
            return

        try:
            state = self._monoprice.zone_status(self._zone_id)
        except SerialException:
            self._update_success = False
            _LOGGER.warning("Could not update zone %d", self._zone_id)
            return

        if not state:
            self._update_success = False
            return

        self._attr_state = MediaPlayerState.ON if state.power else MediaPlayerState.OFF
        self._attr_volume_level = state.volume / MAX_VOLUME
        self._attr_is_volume_muted = state.mute
        idx = state.source
        self._attr_source = self._source_id_name.get(idx)

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added."""
        if self._zone_id in (10, 20, 30):
            return False
        return self._zone_id < 20 or self._update_success

    @property
    @override
    def media_title(self):
        """Return the current source as medial title."""
        return self.source

    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = self._monoprice.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._monoprice.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    @override
    def select_source(self, source: str) -> None:
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._monoprice.set_source(self._zone_id, idx)

    @override
    def turn_on(self) -> None:
        """Turn the media player on."""
        self._monoprice.set_power(self._zone_id, True)

    @override
    def turn_off(self) -> None:
        """Turn the media player off."""
        self._monoprice.set_power(self._zone_id, False)

    @override
    def mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        self._monoprice.set_mute(self._zone_id, mute)

    @override
    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._monoprice.set_volume(self._zone_id, round(volume * MAX_VOLUME))

    def set_balance(self, level: int) -> None:
        """Set balance level."""
        self._monoprice.set_balance(self._zone_id, level)

    def set_bass(self, level: int) -> None:
        """Set bass level."""
        self._monoprice.set_bass(self._zone_id, level)

    def set_treble(self, level: int) -> None:
        """Set treble level."""
        self._monoprice.set_treble(self._zone_id, level)

    def set_zone_source(self, source: int) -> None:
        """Set input source by its numeric id."""
        self._monoprice.set_source(self._zone_id, source)

    @override
    def select_sound_mode(self, sound_mode: str) -> None:
        """Switch the sound mode of the entity."""
        self._attr_sound_mode = sound_mode
        if sound_mode == "Normal":
            self._monoprice.set_bass(self._zone_id, 7)
        elif sound_mode == "High Bass":
            self._monoprice.set_bass(self._zone_id, 12)
        elif sound_mode == "Medium Bass":
            self._monoprice.set_bass(self._zone_id, 10)
        elif sound_mode == "Low Bass":
            self._monoprice.set_bass(self._zone_id, 3)
