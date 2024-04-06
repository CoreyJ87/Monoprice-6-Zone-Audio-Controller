import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .utils import _get_sources
from .const import DOMAIN, MONOPRICE_OBJECT

class MonopriceSourceSelect(SelectEntity):
    def __init__(self, monoprice, zone_id, namespace, source_id_name, source_name_id, source_names):
        self._monoprice = monoprice
        self._zone_id = zone_id
        self._namespace = namespace
        self._source_id_name = source_id_name
        self._source_name_id = source_name_id
        self._attr_options = source_names  
        self._attr_unique_id = f"{namespace}_source_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id} Source"

    @property
    def current_option(self):
        """Return the current source as the current option."""
        state = self._monoprice.zone_status(self._zone_id)
        current_source_name = self._source_id_name.get(state.source, "Unknown")
        return current_source_name

    async def async_select_option(self, option: str):
        """Change the source."""
        source_id = self._source_name_id.get(option)
        if source_id is not None:
            self._monoprice.set_source(self._zone_id, source_id)
            self.async_write_ha_state()
        else:
            _LOGGER.error("Invalid source name selected: %s", option)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, f"{self._namespace}_{self._zone_id}")},
            "manufacturer": "Monoprice",
            "model": "6-Zone Amplifier",
            "name": f"Zone {self._zone_id}"
        }

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Monoprice source select entities."""
    monoprice = hass.data[DOMAIN][config_entry.entry_id][MONOPRICE_OBJECT]
    source_id_name, source_name_id, source_names = _get_sources(config_entry)
    entities = []

    for zone_id in range(11, 17):  # Adjust range based on your zones
        entities.append(MonopriceSourceSelect(monoprice, zone_id, config_entry.entry_id, source_id_name, source_name_id, source_names))

    async_add_entities(entities)
