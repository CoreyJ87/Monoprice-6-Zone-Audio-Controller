"""The Monoprice 6-Zone Amplifier integration."""

import logging

from pymonoprice import get_monoprice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import CONNECTION_ERRORS, MonopriceCoordinator
from .services import async_setup_services

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.NUMBER, Platform.SELECT]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MonopriceConfigEntry = ConfigEntry[MonopriceCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Set up Monoprice 6-Zone Amplifier from a config entry."""
    port = entry.data[CONF_PORT]

    try:
        monoprice = await hass.async_add_executor_job(get_monoprice, port)
    except CONNECTION_ERRORS as err:
        _LOGGER.error("Error connecting to Monoprice controller at %s: %s", port, err)
        raise ConfigEntryNotReady from err

    coordinator = MonopriceCoordinator(hass, entry, port, monoprice)
    # Raises ConfigEntryNotReady (and HA retries setup) if the first poll fails.
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await hass.async_add_executor_job(coordinator.close)
        raise

    entry.async_on_unload(entry.add_update_listener(_update_listener))
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonopriceConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    await hass.async_add_executor_job(entry.runtime_data.close)

    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
