"""Support for interfacing with Monoprice 6 zone home audio controller."""

import logging
from typing import override

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MonopriceConfigEntry
from .coordinator import MonopriceCoordinator
from .entity import MonopriceEntity

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1

CONTROL_TYPES = ("Balance", "Bass", "Treble")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MonopriceConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Monoprice 6-zone amplifier platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        MonopriceZone(coordinator, control_type, config_entry.entry_id, (i * 10) + j)
        for i in range(1, 4)
        for j in range(1, 7)
        for control_type in CONTROL_TYPES
    )


class MonopriceZone(MonopriceEntity, NumberEntity):
    """Representation of a Monoprice amplifier zone."""

    _attr_native_step = 1

    def __init__(
        self,
        coordinator: MonopriceCoordinator,
        control_type: str,
        namespace: str,
        zone_id: int,
    ) -> None:
        """Initialize new zone controls."""
        super().__init__(coordinator, namespace, zone_id)
        self._control_type = control_type
        self._attr_unique_id = f"{namespace}_{zone_id}_{control_type}"
        self._attr_name = f"{control_type} level"

        if control_type == "Balance":
            self._attr_native_min_value = 0
            self._attr_native_max_value = 20
            self._attr_icon = "mdi:scale-balance"
        # Bass/treble are 0-14 on the wire with 7 meaning flat; expose them
        # as -7..+7 (cut..boost) and convert when talking to the amp.
        elif control_type == "Bass":
            self._attr_native_min_value = -7
            self._attr_native_max_value = 7
            self._attr_icon = "mdi:speaker"
        elif control_type == "Treble":
            self._attr_native_min_value = -7
            self._attr_native_max_value = 7
            self._attr_icon = "mdi:surround-sound"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current level."""
        if (status := self.zone_status) is None:
            return None
        if self._control_type == "Balance":
            return status.balance
        if self._control_type == "Bass":
            return status.bass - 7
        return status.treble - 7

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        zone_id = self._zone_id
        level = int(value)
        if self._control_type == "Balance":
            await self.coordinator.async_command(
                lambda client: client.set_balance(zone_id, level),
                [zone_id],
                balance=level,
            )
        elif self._control_type == "Bass":
            await self.coordinator.async_command(
                lambda client: client.set_bass(zone_id, level + 7),
                [zone_id],
                bass=level + 7,
            )
        elif self._control_type == "Treble":
            await self.coordinator.async_command(
                lambda client: client.set_treble(zone_id, level + 7),
                [zone_id],
                treble=level + 7,
            )
