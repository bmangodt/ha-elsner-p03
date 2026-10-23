"""Base entity: every entity belongs to the one weather station device."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HAS_GPS, DOMAIN, MANUFACTURER, MODEL, MODEL_GPS
from .coordinator import ElsnerCoordinator


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Device description shared by device registration and all entities."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=MANUFACTURER,
        model=MODEL_GPS if entry.data.get(CONF_HAS_GPS) else MODEL,
        name=entry.title,
    )


class ElsnerEntity(CoordinatorEntity[ElsnerCoordinator]):
    """Common behaviour of all P03/3 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ElsnerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = build_device_info(entry)
