"""Binary sensors of the Elsner P03/3 Modbus weather station."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ElsnerCoordinator
from .entity import ElsnerEntity


@dataclass(frozen=True, kw_only=True)
class ElsnerBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description with a flag for GPS-only measurements."""

    gps_only: bool = False


BINARY_SENSORS: tuple[ElsnerBinarySensorDescription, ...] = (
    ElsnerBinarySensorDescription(
        key="rain",
        translation_key="rain",
        device_class=BinarySensorDeviceClass.MOISTURE,
        icon="mdi:weather-rainy",
    ),
    ElsnerBinarySensorDescription(
        key="gps_fix",
        translation_key="gps_fix",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:satellite-variant",
        gps_only=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors for the weather station."""
    coordinator: ElsnerCoordinator = entry.runtime_data
    async_add_entities(
        ElsnerBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if coordinator.has_gps or not description.gps_only
    )


class ElsnerBinarySensor(ElsnerEntity, BinarySensorEntity):
    """A boolean state of the weather station."""

    entity_description: ElsnerBinarySensorDescription

    def __init__(
        self,
        coordinator: ElsnerCoordinator,
        description: ElsnerBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return True when the condition is active."""
        return self.coordinator.data.get(self.entity_description.key)
