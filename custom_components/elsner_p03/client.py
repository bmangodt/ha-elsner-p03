"""Thin async Modbus client for the Elsner P03/3 (TCP, RTU-over-TCP or serial RTU)."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType

from .const import (
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_HAS_GPS,
    CONF_HOST,
    CONF_PARITY,
    CONF_PORT,
    CONF_RTU_OVER_TCP,
    CONF_SERIAL_PORT,
    CONF_SLAVE,
    CONF_STOPBITS,
    CONNECTION_TCP,
    DEFAULT_TIMEOUT,
)
from .registers import BASIC_REGISTER_COUNT, GPS_REGISTER_COUNT

_LOGGER = logging.getLogger(__name__)


class P03ConnectionError(Exception):
    """Raised when the weather station cannot be reached or answers badly."""


class P03CannotConnect(P03ConnectionError):
    """The TCP socket or serial port could not be opened."""


class P03NoResponse(P03ConnectionError):
    """The link is open, but the station did not answer (correctly)."""


class P03Client:
    """Manage the Modbus connection and read all registers in one request."""

    def __init__(self, config: Mapping[str, Any], retries: int = 2) -> None:
        self._config = config
        self._retries = retries
        self._lock = asyncio.Lock()
        self._client: AsyncModbusTcpClient | AsyncModbusSerialClient | None = None

    @property
    def _slave(self) -> int:
        return int(self._config[CONF_SLAVE])

    @property
    def _count(self) -> int:
        return (
            GPS_REGISTER_COUNT
            if self._config.get(CONF_HAS_GPS)
            else BASIC_REGISTER_COUNT
        )

    def _build_client(self) -> AsyncModbusTcpClient | AsyncModbusSerialClient:
        cfg = self._config
        if cfg[CONF_CONNECTION_TYPE] == CONNECTION_TCP:
            kwargs: dict[str, Any] = {
                "port": int(cfg[CONF_PORT]),
                "timeout": DEFAULT_TIMEOUT,
                "retries": self._retries,
            }
            if cfg.get(CONF_RTU_OVER_TCP):
                # Transparent RS-485 <-> Ethernet gateways pass raw RTU frames
                kwargs["framer"] = FramerType.RTU
            return AsyncModbusTcpClient(cfg[CONF_HOST], **kwargs)
        return AsyncModbusSerialClient(
            cfg[CONF_SERIAL_PORT],
            baudrate=int(cfg[CONF_BAUDRATE]),
            bytesize=8,
            parity=cfg[CONF_PARITY],
            stopbits=int(cfg[CONF_STOPBITS]),
            timeout=DEFAULT_TIMEOUT,
            retries=self._retries,
        )

    async def _async_connect(self) -> None:
        if self._client is None:
            self._client = self._build_client()
        if self._client.connected:
            return
        try:
            connected = await self._client.connect()
        except (ModbusException, OSError, asyncio.TimeoutError) as err:
            await self._async_reset()
            raise P03CannotConnect(f"Connection failed: {err}") from err
        if not connected:
            await self._async_reset()
            raise P03CannotConnect(
                "Could not open the connection (check host/port or serial device)"
            )

    async def _async_reset(self) -> None:
        """Drop the connection so the next read reconnects from scratch."""
        client, self._client = self._client, None
        if client is None:
            return
        try:
            result = client.close()
            if inspect.isawaitable(result):
                await result
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Error while closing Modbus client", exc_info=True)

    async def _async_read_input_registers(self) -> Any:
        assert self._client is not None
        try:
            # pymodbus >= 3.10
            return await self._client.read_input_registers(
                0, count=self._count, device_id=self._slave
            )
        except TypeError:
            # pymodbus < 3.10
            return await self._client.read_input_registers(
                0, count=self._count, slave=self._slave
            )

    async def async_read(self) -> list[int]:
        """Read all registers; raises P03ConnectionError on any failure."""
        async with self._lock:
            await self._async_connect()
            try:
                response = await self._async_read_input_registers()
            except (ModbusException, OSError, asyncio.TimeoutError) as err:
                await self._async_reset()
                raise P03NoResponse(f"No answer from device: {err}") from err
            if response.isError():
                await self._async_reset()
                raise P03NoResponse(
                    f"Device answered with an error ({response}). "
                    "Check the slave address and serial settings."
                )
            registers = list(response.registers)
            if len(registers) < self._count:
                await self._async_reset()
                raise P03NoResponse(
                    f"Short answer: {len(registers)} of {self._count} registers"
                )
            return registers

    async def async_close(self) -> None:
        """Close the connection (safe to call more than once)."""
        async with self._lock:
            await self._async_reset()


async def async_test_connection(
    hass: HomeAssistant, config: Mapping[str, Any]
) -> None:
    """Connect and read once; raises P03ConnectionError when it fails."""
    client = P03Client(config, retries=1)
    try:
        await client.async_read()
    finally:
        await client.async_close()
