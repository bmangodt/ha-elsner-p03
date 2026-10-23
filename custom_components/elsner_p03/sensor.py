"""Sensors of the Elsner P03/3 Modbus weather station."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    EntityCategory,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ElsnerCoordinator
from .entity import ElsnerEntity


@dataclass(frozen=True, kw_only=True)
class ElsnerSensorDescription(SensorEntityDescription):
    """Sensor description with a flag for GPS-only measurements."""

    gps_only: bool = False


SENSORS: tuple[ElsnerSensorDescription, ...] = (
    ElsnerSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ElsnerSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    ElsnerSensorDescription(
        key="illuminance",
        translation_key="illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ElsnerSensorDescription(
        key="sun_south",
        translation_key="sun_south",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ElsnerSensorDescription(
        key="sun_west",
        translation_key="sun_west",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ElsnerSensorDescription(
        key="sun_east",
        translation_key="sun_east",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ElsnerSensorDescription(
        key="brightness",
        translation_key="brightness",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    ElsnerSensorDescription(
        key="status_raw",
        translation_key="status_raw",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        icon="mdi:numeric",
    ),
    ElsnerSensorDescription(
        key="sun_azimuth",
        translation_key="sun_azimuth",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:compass-outline",
        gps_only=True,
    ),
    ElsnerSensorDescription(
        key="sun_elevation",
        translation_key="sun_elevation",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:angle-acute",
        gps_only=True,
    ),
    ElsnerSensorDescription(
        key="utc_time",
        translation_key="utc_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        gps_only=True,
    ),
    ElsnerSensorDescription(
        key="longitude",
        translation_key="longitude",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        icon="mdi:longitude",
        gps_only=True,
    ),
    ElsnerSensorDescription(
        key="latitude",
        translation_key="latitude",
        native_unit_of_measurement=DEGREE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=2,
        icon="mdi:latitude",
        gps_only=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors for the weather station."""
    coordinator: ElsnerCoordinator = entry.runtime_data
    async_add_entities(
        ElsnerSensor(coordinator, description)
        for description in SENSORS
        if coordinator.has_gps or not description.gps_only
    )


class ElsnerSensor(ElsnerEntity, SensorEntity):
    """A measurement of the weather station."""

    entity_description: ElsnerSensorDescription

    def __init__(
        self, coordinator: ElsnerCoordinator, description: ElsnerSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | datetime | None:
        """Return the latest value."""
        return self.coordinator.data.get(self.entity_description.key)
