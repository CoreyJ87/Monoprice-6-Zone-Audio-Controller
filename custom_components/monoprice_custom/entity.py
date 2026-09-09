"""Base entity for the Monoprice 6-Zone Amplifier."""

from __future__ import annotations

from typing import override

from pymonoprice import ZoneStatus

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MAIN_ZONES, MonopriceCoordinator


class MonopriceEntity(CoordinatorEntity[MonopriceCoordinator]):
    """Common behaviour for every per-zone Monoprice entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MonopriceCoordinator, namespace: str, zone_id: int
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{namespace}_{zone_id}")},
            manufacturer="Monoprice",
            model="6-Zone Amplifier",
            name=f"Zone {zone_id}",
        )

    @property
    def zone_status(self) -> ZoneStatus | None:
        """Return the last polled status of this zone, if any."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._zone_id)

    @property
    @override
    def available(self) -> bool:
        """Unavailable while the amp is unreachable or the zone is not reported."""
        return super().available and self.zone_status is not None

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Only main-unit zones 11-16 are enabled by default."""
        return self._zone_id in MAIN_ZONES
