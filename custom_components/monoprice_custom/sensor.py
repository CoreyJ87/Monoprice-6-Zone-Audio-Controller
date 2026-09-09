"""Support for interfacing with Monoprice 6 zone home audio controller."""

import logging
from typing import override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .coordinator import MonopriceCoordinator
from .entity import MonopriceEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

SENSOR_ICONS = {
    "Keypad": "mdi:dialpad",
    # (sic) name kept for backwards compatibility with existing unique_ids
    "Public Anouncement": "mdi:bullhorn",
    "Do Not Disturb": "mdi:weather-night",
    "Source": "mdi:source-branch",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MonopriceZone(coordinator, sensor_type, config_entry.entry_id, (i * 10) + j)
        for i in range(1, 4)
        for j in range(1, 7)
        for sensor_type in SENSOR_ICONS
    )


class MonopriceZone(MonopriceEntity, SensorEntity):
    """Representation of a Monoprice amplifier zone."""

    def __init__(
        self,
        coordinator: MonopriceCoordinator,
        sensor_type: str,
        namespace: str,
        zone_id: int,
    ) -> None:
        """Initialize new zone sensors."""
        super().__init__(coordinator, namespace, zone_id)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{namespace}_{zone_id}_{sensor_type}"
        self._attr_name = sensor_type
        self._attr_icon = SENSOR_ICONS[sensor_type]

    @property
    @override
    def native_value(self) -> str | None:
        """Return the sensor value."""
        if (status := self.zone_status) is None:
            return None
        if self._sensor_type == "Keypad":
            return "Connected" if status.keypad else "Disconnected"
        if self._sensor_type == "Public Anouncement":
            return "On" if status.pa else "Off"
        if self._sensor_type == "Do Not Disturb":
            return "On" if status.do_not_disturb else "Off"
        return str(status.source)
