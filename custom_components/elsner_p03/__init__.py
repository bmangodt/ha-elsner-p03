"""The Elsner P03/3 Modbus weather station integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import area_registry as ar, device_registry as dr

from .client import P03Client
from .const import CONF_AREA, DOMAIN
from .coordinator import ElsnerCoordinator
from .entity import build_device_info

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type ElsnerConfigEntry = ConfigEntry[ElsnerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ElsnerConfigEntry) -> bool:
    """Set up the weather station from a config entry."""
    client = P03Client(entry.data)
    coordinator = ElsnerCoordinator(hass, entry, client)

    try:
        # Raises ConfigEntryNotReady on failure, so Home Assistant keeps
        # retrying with back-off if the station is offline at startup.
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await client.async_close()
        raise

    entry.runtime_data = coordinator

    _async_register_device(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _async_register_device(hass: HomeAssistant, entry: ElsnerConfigEntry) -> None:
    """Create the single device and apply the room chosen during setup."""
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id, **build_device_info(entry)
    )

    # The area picked in the setup dialog is applied once. Afterwards the user
    # manages it on the device page, so it must not be re-applied on restart.
    if area_id := entry.data.get(CONF_AREA):
        if device.area_id is None and ar.async_get(hass).async_get_area(area_id):
            registry.async_update_device(device.id, area_id=area_id)
        data = {k: v for k, v in entry.data.items() if k != CONF_AREA}
        hass.config_entries.async_update_entry(entry, data=data)


async def _async_update_listener(hass: HomeAssistant, entry: ElsnerConfigEntry) -> None:
    """Reload when options or connection settings change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ElsnerConfigEntry) -> bool:
    """Unload the config entry and close the Modbus connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.async_close()
    return unloaded
