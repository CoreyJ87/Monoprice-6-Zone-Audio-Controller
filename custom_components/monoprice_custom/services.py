"""Services for the Monoprice 6-Zone Amplifier integration."""

import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .coordinator import MAIN_ZONES
from .const import (
    ATTR_LEVEL,
    ATTR_SOURCE,
    DOMAIN,
    SERVICE_RESTORE,
    SERVICE_SET_ALL_ZONES_SOURCE,
    SERVICE_SET_BALANCE,
    SERVICE_SET_BASS,
    SERVICE_SET_TREBLE,
    SERVICE_SET_ZONE_SOURCE,
    SERVICE_SNAPSHOT,
)

BALANCE_SCHEMA = {
    vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=20))
}
BASS_TREBLE_SCHEMA = {
    vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Range(min=0, max=14))
}
SOURCE_SCHEMA = {
    vol.Required(ATTR_SOURCE): vol.All(vol.Coerce(int), vol.Range(min=1, max=6))
}

SET_ALL_ZONES_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SOURCE): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        # accepted and ignored for backwards compatibility with old service calls
        vol.Optional("entity_id"): cv.entity_ids,
    }
)

def _set_all_zones(client, source: int) -> None:
    # Main amplifier zones only; expansion unit zones (21-36) are not polled by
    # this integration, so they are not addressed here either.
    for zone_id in MAIN_ZONES:
        client.set_source(zone_id, source)


async def _async_set_all_zones_source(call: ServiceCall) -> None:
    """Set the source for every zone on every configured amplifier."""
    source = call.data[ATTR_SOURCE]
    for entry in call.hass.config_entries.async_entries(DOMAIN):
        if entry.state is not ConfigEntryState.LOADED:
            continue
        await entry.runtime_data.async_command(
            lambda client: _set_all_zones(client, source),
            list(MAIN_ZONES),
            source=source,
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SNAPSHOT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="snapshot",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESTORE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="restore",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_BALANCE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=BALANCE_SCHEMA,
        func="set_balance",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_BASS,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=BASS_TREBLE_SCHEMA,
        func="set_bass",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_TREBLE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=BASS_TREBLE_SCHEMA,
        func="set_treble",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_ZONE_SOURCE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=SOURCE_SCHEMA,
        func="set_zone_source",
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ALL_ZONES_SOURCE,
        _async_set_all_zones_source,
        schema=SET_ALL_ZONES_SOURCE_SCHEMA,
    )
