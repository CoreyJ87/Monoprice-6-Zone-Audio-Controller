"""Support for interfacing with Monoprice 6 zone home audio controller."""

import logging
from typing import override

from serialx import SerialException

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config_entry.data[CONF_PORT]
    monoprice = config_entry.runtime_data.client

    entities = []
    for i in range(1, 4):
        for j in range(1, 7):
            zone_id = (i * 10) + j
            _LOGGER.debug(
                "Adding sensor entities for zone %d for port %s", zone_id, port
            )
            entities.append(
                MonopriceZone(monoprice, "Keypad", config_entry.entry_id, zone_id)
            )
            entities.append(
                MonopriceZone(
                    monoprice, "Public Anouncement", config_entry.entry_id, zone_id
                )
            )
            entities.append(
                MonopriceZone(
                    monoprice, "Do Not Disturb", config_entry.entry_id, zone_id
                )
            )
            entities.append(
                MonopriceZone(monoprice, "Source", config_entry.entry_id, zone_id)
            )

    # only call update before add if it's the first run so we can try to detect zones
    async_add_entities(entities, config_entry.runtime_data.first_run)


class MonopriceZone(SensorEntity):
    """Representation of a Monoprice amplifier zone."""

    def __init__(self, monoprice, sensor_type, namespace, zone_id):
        """Initialize new zone sensors."""
        self._monoprice = monoprice
        self._sensor_type = sensor_type
        self._zone_id = zone_id
        self._attr_unique_id = f"{namespace}_{self._zone_id}_{self._sensor_type}"
        self._attr_has_entity_name = True
        self._attr_name = f"{sensor_type}"
        self._attr_native_value = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{namespace}_{self._zone_id}")},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {self._zone_id}",
        )

        if sensor_type == "Keypad":
            self._attr_icon = "mdi:dialpad"
        elif sensor_type == "Public Anouncement":
            self._attr_icon = "mdi:bullhorn"
        elif sensor_type == "Do Not Disturb":
            self._attr_icon = "mdi:weather-night"
        elif sensor_type == "Source":
            self._attr_icon = "mdi:source-branch"

        self._update_success = True

    def update(self):
        """Retrieve latest value."""
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

        if self._sensor_type == "Keypad":
            self._attr_native_value = "Connected" if state.keypad else "Disconnected"
        elif self._sensor_type == "Public Anouncement":
            self._attr_native_value = "On" if state.pa else "Off"
        elif self._sensor_type == "Do Not Disturb":
            self._attr_native_value = "On" if state.do_not_disturb else "Off"
        elif self._sensor_type == "Source":
            self._attr_native_value = str(state.source)

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if self._zone_id in (10, 20, 30):
            return False
        return self._zone_id < 20 or self._update_success
