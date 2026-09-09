"""Support for Monoprice 6-zone source selection."""

import logging
from typing import override

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .coordinator import MAIN_ZONES, MonopriceCoordinator
from .entity import MonopriceEntity
from .utils import _get_sources

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice source select entities."""
    coordinator = config_entry.runtime_data
    source_id_name, source_name_id, source_names = _get_sources(config_entry)

    async_add_entities(
        MonopriceSourceSelect(
            coordinator,
            zone_id,
            config_entry.entry_id,
            source_id_name,
            source_name_id,
            source_names,
        )
        for zone_id in MAIN_ZONES
    )


class MonopriceSourceSelect(MonopriceEntity, SelectEntity):
    """Representation of a Monoprice source selector."""

    _attr_name = "Source"

    def __init__(
        self,
        coordinator: MonopriceCoordinator,
        zone_id: int,
        namespace: str,
        source_id_name,
        source_name_id,
        source_names,
    ) -> None:
        """Initialize new zone source select."""
        super().__init__(coordinator, namespace, zone_id)
        self._source_id_name = source_id_name
        self._source_name_id = source_name_id
        self._attr_options = source_names
        self._attr_unique_id = f"{namespace}_source_{zone_id}"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the name of the zone's current source."""
        if (status := self.zone_status) is None:
            return None
        return self._source_id_name.get(status.source)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the source."""
        if (source_id := self._source_name_id.get(option)) is None:
            raise ServiceValidationError(f"Invalid source name selected: {option}")
        zone_id = self._zone_id
        await self.coordinator.async_command(
            lambda client: client.set_source(zone_id, source_id),
            [zone_id],
            source=source_id,
        )
