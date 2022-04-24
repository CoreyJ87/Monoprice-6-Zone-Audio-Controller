"""Support for interfacing with Monoprice 6 zone home audio controller."""
"""This Version add support for sound_mode & services: set_bass, set_treble, set_balance"""
from code import interact
import logging

from serial import SerialException

from homeassistant import core
try:
    from homeassistant.components.media_player import (
        MediaPlayerEntity as MediaPlayerDevice,
    )
except ImportError:
    from homeassistant.components.media_player import MediaPlayerDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import voluptuous as vol

from .const import (
    CONF_SOURCES,
    DOMAIN,
    FIRST_RUN,
    MONOPRICE_OBJECT,
    SERVICE_RESTORE,
    SERVICE_SNAPSHOT,
    SERVICE_SET_BALANCE,
    SERVICE_SET_BASS,
    SERVICE_SET_TREBLE,
    ATTR_BALANCE,
    ATTR_BASS,
    ATTR_TREBLE
)

from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
    SUPPORT_SELECT_SOUND_MODE
)

SUPPORT_FEATURES = (
    SUPPORT_VOLUME_SET
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_VOLUME_STEP
    | SUPPORT_SELECT_SOUND_MODE
)

SET_BALANCE_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id", default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_BALANCE, default=0): vol.All(int, vol.Range(min=0, max=21))
    }
)

SET_BASS_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id", default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_BASS, default=5): vol.All(int, vol.Range(min=0, max=15))
    }
)

SET_TREBLE_SCHEMA = vol.Schema(
    {
        vol.Optional("entity_id", default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_TREBLE, default=5): vol.All(int, vol.Range(min=0, max=15))
    }
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@core.callback
def _get_sources_from_dict(data):
    sources_config = data[CONF_SOURCES]
    source_id_name = {int(index): name for index, name in sources_config.items()}
    source_name_id = {v: k for k, v in source_id_name.items()}
    source_names = sorted(source_name_id.keys(), key=lambda v: source_name_id[v])
    return [source_id_name, source_name_id, source_names]


@core.callback
def _get_sources(config_entry):
    if CONF_SOURCES in config_entry.options:
        data = config_entry.options
    else:
        data = config_entry.data
    return _get_sources_from_dict(data)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config_entry.data[CONF_PORT]

    monoprice = hass.data[DOMAIN][config_entry.entry_id][MONOPRICE_OBJECT]

    sources = _get_sources(config_entry)

    entities = []
    for i in range(1, 4):
        for j in range(0, 7):
            zone_id = (i * 10) + j
            _LOGGER.info("Adding media player entity for zone %d for port %s", zone_id, port)
            entities.append(MonopriceZone(monoprice, sources, config_entry.entry_id, zone_id))

    # only call update before add if it's the first run so we can try to detect zones
    first_run = hass.data[DOMAIN][config_entry.entry_id][FIRST_RUN]
    async_add_entities(entities, first_run)

    platform = entity_platform.async_get_current_platform()

    def _call_service(entities, service_call):
        for entity in entities:
            if service_call.service == SERVICE_SNAPSHOT:
                entity.snapshot()
            elif service_call.service == SERVICE_RESTORE:
                entity.restore()
            elif service_call.service == SERVICE_SET_BALANCE:
                entity.set_balance(service_call)
            elif service_call.service == SERVICE_SET_BASS:
                entity.set_bass(service_call)
            elif service_call.service == SERVICE_SET_TREBLE:
                entity.set_treble(service_call)

    @service.verify_domain_control(hass, DOMAIN)
    async def async_service_handle(service_call: core.ServiceCall) -> None:
        """Handle for services."""
        entities = await platform.async_extract_from_service(service_call)

        if not entities:
            return

        hass.async_add_executor_job(_call_service, entities, service_call)


    hass.services.async_register(
        DOMAIN,
        SERVICE_SNAPSHOT,
        async_service_handle,
        schema=cv.make_entity_service_schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTORE,
        async_service_handle,
        schema=cv.make_entity_service_schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BALANCE,
        async_service_handle,
        schema=SET_BALANCE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BASS,
        async_service_handle,
        schema=SET_BASS_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TREBLE,
        async_service_handle,
        schema=SET_TREBLE_SCHEMA,
    )


class MonopriceZone(MediaPlayerDevice):
    """Representation of a Monoprice amplifier zone."""


    def __init__(self, monoprice, sources, namespace, zone_id):
        """Initialize new zone."""
        self._monoprice = monoprice
        # dict source_id -> source name
        self._source_id_name = sources[0]
        # dict source name -> source_id
        self._source_name_id = sources[1]
        # ordered list of all source names
        self._source_names = sources[2]
        self._zone_id = zone_id
        self._unique_id = f"{namespace}_{self._zone_id}"
        self._name = f"Zone {self._zone_id}"
        self._sound_mode_names = ["Normal", "High Bass", "Medium Bass", "Low Bass"]

        self._snapshot = None
        self._state = None
        self._volume = None
        self._source = None
        self._mute = None
        self._sound_mode = None
        self._update_success = True

    def update(self):
        """Retrieve latest state."""
        try:
            state = self._monoprice.zone_status(self._zone_id)
        except SerialException:
            self._update_success = False
            _LOGGER.warning("Could not update zone %d", self._zone_id)
            return

        if not state:
            self._update_success = False
            return

        self._state = STATE_ON if state.power else STATE_OFF
        self._volume = state.volume
        self._mute = state.mute
        idx = state.source
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        if(self._zone_id == 10 or self._zone_id == 20 or self._zone_id == 30):
            return False
        return self._zone_id < 20 or self._update_success

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name="Zone " + str(self._zone_id)
        )

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_FEATURES

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / 38.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def media_title(self):
        """Return the current source as medial title."""
        return self._source

    @property
    def source(self):
        """Return the current input source of the device."""
        return self._source

    @property
    def sound_mode(self):
        """Return the current sound mode of the device."""
        return self._sound_mode

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def sound_mode_list(self):
        """List of available sound modes."""
        return self._sound_mode_names

    def snapshot(self):
        """Save zone's current state."""
        self._snapshot = self._monoprice.zone_status(self._zone_id)

    def restore(self):
        """Restore saved state."""
        if self._snapshot:
            self._monoprice.restore_zone(self._snapshot)
            self.schedule_update_ha_state(True)

    def set_balance(self, call):
        """Set balance level."""
        level = int(call.data.get(ATTR_BALANCE))
        self._monoprice.set_balance(self._zone_id, level)
 
    def set_bass(self, call):
        """Set bass level."""
        level = int(call.data.get(ATTR_BASS))
        self._monoprice.set_bass(self._zone_id, level)

    def set_treble(self, call):
        """Set treble level."""
        level = int(call.data.get(ATTR_TREBLE))
        self._monoprice.set_treble(self._zone_id, level)

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._monoprice.set_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        self._monoprice.set_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        self._monoprice.set_power(self._zone_id, False)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._monoprice.set_mute(self._zone_id, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._monoprice.set_volume(self._zone_id, int(volume * 38))

    def volume_up(self):
        """Volume up the media player."""
        if self._volume is None:
            return
        self._monoprice.set_volume(self._zone_id, min(self._volume + 1, 38))

    def volume_down(self):
        """Volume down media player."""
        if self._volume is None:
            return
        self._monoprice.set_volume(self._zone_id, max(self._volume - 1, 0))

    def select_sound_mode(self, sound_mode):
        """Switch the sound mode of the entity."""
        self._sound_mode = sound_mode
        if(sound_mode == "Normal"):
            self._monoprice.set_bass(self._zone_id, 7)
        elif(sound_mode == "High Bass"):
            self._monoprice.set_bass(self._zone_id, 12)
        elif(sound_mode == "Medium Bass"):
            self._monoprice.set_bass(self._zone_id, 10)
        elif(sound_mode == "Low Bass"):
            self._monoprice.set_bass(self._zone_id, 3)