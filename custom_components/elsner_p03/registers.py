"""Register map and decoding for the Elsner P03/3-Modbus(-GPS).

Source: Elsner manual "P03/3-Modbus(-GPS) Weather Stations for Modbus".
All values are read with function 04h (Read Input Registers), starting at
register 0. Each register is 16 bit, high byte first.

This module deliberately has no Home Assistant imports so it can be unit tested
on its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

# Register numbers (0-based)
REG_TEMPERATURE = 0  # int16, value / 10 = degrees C
REG_SUN_SOUTH = 1  # 1...99 kilolux
REG_SUN_WEST = 2  # 1...99 kilolux
REG_SUN_EAST = 3  # 1...99 kilolux
REG_BRIGHTNESS = 4  # 0...999 lux (twilight sensor)
REG_WIND = 5  # value / 10 = m/s
REG_STATUS = 6  # high byte: 1 = GPS, 0 = RTC (GPS model); low byte: 1 = rain
REG_DAY = 7  # GPS model only from here
REG_MONTH = 8
REG_YEAR = 9
REG_HOUR = 10
REG_MINUTE = 11
REG_SECOND = 12
REG_AZIMUTH = 13  # value / 10 = degrees, 0.0 ... 359.9
REG_ELEVATION = 14  # int16, value / 10 = degrees, +/- 90.0
REG_LONGITUDE = 15  # int16, value / 100 = degrees, + east / - west
REG_LATITUDE = 16  # int16, value / 100 = degrees, + north / - south

# Number of registers to read
BASIC_REGISTER_COUNT = 7  # temperature .. status (all models)
GPS_REGISTER_COUNT = 17  # everything (P03/3-Modbus-GPS)

# Byte masks for REG_STATUS. Per the Elsner manual the GPS/RTC flag is the high
# byte and the rain flag the low byte of register 6. Confirmed on a real
# station: it reads 256 (high byte set, low byte 0) while dry, so rain must be
# taken from the low byte only, on every model.
GPS_FLAG_MASK = 0xFF00
RAIN_FLAG_MASK = 0x00FF


def _signed(value: int) -> int:
    """Convert an unsigned 16 bit register to a signed (two's complement) value."""
    return value - 0x10000 if value & 0x8000 else value


def parse_registers(registers: Sequence[int], has_gps: bool) -> dict[str, Any]:
    """Decode raw input registers into a dictionary of measurement values."""
    needed = GPS_REGISTER_COUNT if has_gps else BASIC_REGISTER_COUNT
    if len(registers) < needed:
        raise ValueError(f"Expected {needed} registers, got {len(registers)}")

    status = registers[REG_STATUS]
    sun_lux = [
        registers[REG_SUN_SOUTH] * 1000,
        registers[REG_SUN_WEST] * 1000,
        registers[REG_SUN_EAST] * 1000,
    ]
    data: dict[str, Any] = {
        "temperature": _signed(registers[REG_TEMPERATURE]) / 10,
        # Sun sensors report kilolux; expose lux so HA's illuminance class fits
        "sun_south": sun_lux[0],
        "sun_west": sun_lux[1],
        "sun_east": sun_lux[2],
        "brightness": registers[REG_BRIGHTNESS],
        # One overall value for automations: the brightest sun sensor in
        # daylight, the twilight sensor (0...999 lx) when it is darker. The sun
        # sensors bottom out at 1 klx, so they are only trusted above that.
        "illuminance": (
            max(sun_lux) if max(sun_lux) > 1000 else registers[REG_BRIGHTNESS]
        ),
        "wind_speed": registers[REG_WIND] / 10,
        "rain": bool(status & RAIN_FLAG_MASK),
        "status_raw": status,
    }

    if has_gps:
        gps_fix = bool(status & GPS_FLAG_MASK)
        data["gps_fix"] = gps_fix
        data["sun_azimuth"] = registers[REG_AZIMUTH] / 10
        data["sun_elevation"] = _signed(registers[REG_ELEVATION]) / 10
        data["longitude"] = _signed(registers[REG_LONGITUDE]) / 100
        data["latitude"] = _signed(registers[REG_LATITUDE]) / 100
        data["utc_time"] = _parse_utc(registers) if gps_fix else None

    return data


def _parse_utc(registers: Sequence[int]) -> datetime | None:
    """Build a UTC datetime from the date/time registers (None if invalid)."""
    year = registers[REG_YEAR]
    if year < 100:  # two digit year
        year += 2000
    try:
        return datetime(
            year,
            registers[REG_MONTH],
            registers[REG_DAY],
            registers[REG_HOUR],
            registers[REG_MINUTE],
            registers[REG_SECOND],
            tzinfo=UTC,
        )
    except ValueError:
        return None
