"""Data update coordinator for the Elsner P03/3 Modbus weather station."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import P03Client, P03ConnectionError
from .const import CONF_HAS_GPS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .registers import parse_registers

_LOGGER = logging.getLogger(__name__)


class ElsnerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the weather station and share the decoded values with all entities."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: P03Client
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.has_gps: bool = bool(entry.data.get(CONF_HAS_GPS))

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            registers = await self.client.async_read()
            return parse_registers(registers, self.has_gps)
        except P03ConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except ValueError as err:
            raise UpdateFailed(f"Unexpected data from device: {err}") from err
