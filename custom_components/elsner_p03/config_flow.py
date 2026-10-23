"""UI configuration for the Elsner P03/3 Modbus weather station.

Flow: menu (Modbus TCP / Modbus RTU) -> connection form. Submitting a form
performs a live read of the station. When that fails, the same form is shown
again with every value the user typed still filled in plus an explanation, so
they can fix one field (or just press Submit again) without starting over.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .client import P03CannotConnect, P03NoResponse, async_test_connection
from .const import (
    BAUDRATES,
    CONF_AREA,
    CONF_BAUDRATE,
    CONF_CONNECTION_TYPE,
    CONF_HAS_GPS,
    CONF_HOST,
    CONF_NAME,
    CONF_PARITY,
    CONF_PORT,
    CONF_RTU_OVER_TCP,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_PORT,
    CONF_SLAVE,
    CONF_STOPBITS,
    CONNECTION_RTU,
    CONNECTION_TCP,
    DEFAULT_BAUDRATE,
    DEFAULT_NAME,
    DEFAULT_PARITY,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DEFAULT_STOPBITS,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PARITIES,
    STOPBITS,
)

_LOGGER = logging.getLogger(__name__)

# Fields that describe the connection (stored in entry.data)
_TCP_KEYS = (CONF_HOST, CONF_PORT, CONF_RTU_OVER_TCP, CONF_SLAVE, CONF_HAS_GPS)
_RTU_KEYS = (
    CONF_SERIAL_PORT,
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_SLAVE,
    CONF_HAS_GPS,
)

_SLAVE_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, max=247, step=1, mode="box")
)
_AREA_SELECTOR = selector.AreaSelector()


def _tcp_schema(include_identity: bool) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_identity:
        fields[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = str
    fields.update(
        {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=65535, step=1, mode="box")
            ),
            vol.Required(CONF_RTU_OVER_TCP, default=False): bool,
            vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): _SLAVE_SELECTOR,
            vol.Required(CONF_HAS_GPS, default=False): bool,
        }
    )
    if include_identity:
        fields[vol.Optional(CONF_AREA)] = _AREA_SELECTOR
    return vol.Schema(fields)


def _rtu_schema(include_identity: bool, ports: list[str]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if include_identity:
        fields[vol.Required(CONF_NAME, default=DEFAULT_NAME)] = str
    fields.update(
        {
            # Detected ports are offered, but any path (e.g. /dev/ttyUSB0) may be typed
            vol.Required(CONF_SERIAL_PORT): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=ports,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_BAUDRATE, default=str(DEFAULT_BAUDRATE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=BAUDRATES, mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
            vol.Required(CONF_PARITY, default=DEFAULT_PARITY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=PARITIES,
                    translation_key="parity",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_STOPBITS, default=str(DEFAULT_STOPBITS)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=STOPBITS, mode=selector.SelectSelectorMode.LIST
                )
            ),
            vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): _SLAVE_SELECTOR,
            vol.Required(CONF_HAS_GPS, default=False): bool,
        }
    )
    if include_identity:
        fields[vol.Optional(CONF_AREA)] = _AREA_SELECTOR
    return vol.Schema(fields)


def _list_serial_ports() -> list[str]:
    """Return serial devices, preferring stable /dev/serial/by-id paths."""
    ports: list[str] = []
    by_id_dir = "/dev/serial/by-id"
    targets: set[str] = set()
    if os.path.isdir(by_id_dir):
        for name in sorted(os.listdir(by_id_dir)):
            path = os.path.join(by_id_dir, name)
            ports.append(path)
            targets.add(os.path.realpath(path))
    try:
        from serial.tools import list_ports  # noqa: PLC0415

        for port in sorted(list_ports.comports(), key=lambda p: p.device):
            if os.path.realpath(port.device) not in targets:
                ports.append(port.device)
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Could not list serial ports", exc_info=True)
    return ports


def _normalize(conn_type: str, user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert form values (floats from number selectors, strings from selects)."""
    keys = _TCP_KEYS if conn_type == CONNECTION_TCP else _RTU_KEYS
    data: dict[str, Any] = {CONF_CONNECTION_TYPE: conn_type}
    for key in keys:
        data[key] = user_input[key]
    data[CONF_SLAVE] = int(data[CONF_SLAVE])
    if conn_type == CONNECTION_TCP:
        data[CONF_HOST] = str(data[CONF_HOST]).strip()
        data[CONF_PORT] = int(data[CONF_PORT])
    else:
        data[CONF_SERIAL_PORT] = str(data[CONF_SERIAL_PORT]).strip()
        data[CONF_BAUDRATE] = int(data[CONF_BAUDRATE])
        data[CONF_STOPBITS] = int(data[CONF_STOPBITS])
    return data


def _unique_id(data: dict[str, Any]) -> str:
    """One config entry per station: link + Modbus address."""
    if data[CONF_CONNECTION_TYPE] == CONNECTION_TCP:
        link = f"tcp:{data[CONF_HOST].lower()}:{data[CONF_PORT]}"
    else:
        link = f"rtu:{data[CONF_SERIAL_PORT]}"
    return f"{link}:{data[CONF_SLAVE]}"


def _form_values(data: dict[str, Any]) -> dict[str, Any]:
    """Stored entry data -> values the form selectors understand."""
    values = dict(data)
    for key in (CONF_BAUDRATE, CONF_STOPBITS):
        if key in values:
            values[key] = str(values[key])
    return values


async def _async_try_connect(
    hass: HomeAssistant, data: dict[str, Any]
) -> tuple[dict[str, str], str]:
    """Test the connection. Returns (errors, technical detail)."""
    try:
        await async_test_connection(hass, data)
    except P03CannotConnect as err:
        _LOGGER.debug("Connection test failed: %s", err)
        return {"base": "cannot_connect"}, str(err)
    except P03NoResponse as err:
        _LOGGER.debug("Connection test got no valid answer: %s", err)
        return {"base": "no_response"}, str(err)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Unexpected error while testing the connection")
        return {"base": "unknown"}, str(err)
    return {}, ""


class ElsnerP03ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup dialog."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow (poll interval)."""
        return ElsnerP03OptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First screen: choose Modbus TCP or Modbus RTU."""
        return self.async_show_menu(
            step_id="user", menu_options=[CONNECTION_TCP, CONNECTION_RTU]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modbus TCP (or RTU over TCP via an Ethernet gateway)."""
        return await self._async_step_connection(CONNECTION_TCP, user_input)

    async def async_step_rtu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Modbus RTU over a local RS-485 adapter."""
        return await self._async_step_connection(CONNECTION_RTU, user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change connection settings of an existing station."""
        entry = self._get_reconfigure_entry()
        return await self._async_step_connection(
            entry.data[CONF_CONNECTION_TYPE], user_input, step_id="reconfigure"
        )

    async def _async_step_connection(
        self,
        conn_type: str,
        user_input: dict[str, Any] | None,
        step_id: str | None = None,
    ) -> ConfigFlowResult:
        reconfigure = self.source == SOURCE_RECONFIGURE
        step_id = step_id or conn_type
        errors: dict[str, str] = {}
        detail = ""

        if user_input is not None:
            data = _normalize(conn_type, user_input)
            unique_id = _unique_id(data)
            if reconfigure:
                # A new IP / port / address is fine, as long as no *other*
                # entry already talks to that station.
                own_id = self._get_reconfigure_entry().entry_id
                for other in self._async_current_entries(include_ignore=False):
                    if other.unique_id == unique_id and other.entry_id != own_id:
                        return self.async_abort(reason="already_configured")
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

            errors, detail = await _async_try_connect(self.hass, data)
            if not errors:
                if reconfigure:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        unique_id=unique_id,
                        data_updates=data,
                    )
                title = str(user_input.get(CONF_NAME) or DEFAULT_NAME).strip()
                if area_id := user_input.get(CONF_AREA):
                    data[CONF_AREA] = area_id
                return self.async_create_entry(title=title, data=data)

        if conn_type == CONNECTION_TCP:
            schema = _tcp_schema(include_identity=not reconfigure)
        else:
            ports = await self.hass.async_add_executor_job(_list_serial_ports)
            current = (user_input or {}).get(CONF_SERIAL_PORT)
            if reconfigure and not current:
                current = self._get_reconfigure_entry().data.get(CONF_SERIAL_PORT)
            if current and current not in ports:
                ports.insert(0, current)
            schema = _rtu_schema(include_identity=not reconfigure, ports=ports)

        # Pre-fill: what the user just typed (after a failed attempt), or the
        # stored settings when reconfiguring.
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        elif reconfigure:
            schema = self.add_suggested_values_to_schema(
                schema, _form_values(dict(self._get_reconfigure_entry().data))
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders={"error_detail": detail or "-"},
            last_step=True,
        )


class ElsnerP03OptionsFlow(OptionsFlow):
    """Options after setup: how often the station is polled."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])}
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        mode="box",
                        unit_of_measurement="s",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
