"""Support for Monoprice 6-zone source selection."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .const import DOMAIN
from .utils import _get_sources

_LOGGER = logging.getLogger(__name__)


class MonopriceSourceSelect(SelectEntity):
    """Representation of a Monoprice source selector."""

    def __init__(
        self, monoprice, zone_id, namespace, source_id_name, source_name_id, source_names
    ):
        """Initialize new zone source select."""
        self._monoprice = monoprice
        self._zone_id = zone_id
        self._namespace = namespace
        self._source_id_name = source_id_name
        self._source_name_id = source_name_id
        self._attr_options = source_names
        self._attr_unique_id = f"{namespace}_source_{self._zone_id}"
        self._attr_name = f"Zone {self._zone_id} Source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{namespace}_{self._zone_id}")},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {self._zone_id}",
        )

    @property
    def current_option(self):
        """Return the current source as the current option."""
        state = self._monoprice.zone_status(self._zone_id)
        return self._source_id_name.get(state.source, "Unknown")

    async def async_select_option(self, option: str):
        """Change the source."""
        source_id = self._source_name_id.get(option)
        if source_id is not None:
            self._monoprice.set_source(self._zone_id, source_id)
            self.async_write_ha_state()
        else:
            _LOGGER.error("Invalid source name selected: %s", option)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice source select entities."""
    monoprice = config_entry.runtime_data.client
    source_id_name, source_name_id, source_names = _get_sources(config_entry)
    entities = []

    for zone_id in range(11, 17):
        entities.append(
            MonopriceSourceSelect(
                monoprice,
                zone_id,
                config_entry.entry_id,
                source_id_name,
                source_name_id,
                source_names,
            )
        )

    async_add_entities(entities)
