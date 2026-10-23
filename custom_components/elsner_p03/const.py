"""Constants for the Elsner P03/3 Modbus integration."""

from __future__ import annotations

DOMAIN = "elsner_p03"

MANUFACTURER = "Elsner Elektronik"
MODEL = "P03/3-Modbus"
MODEL_GPS = "P03/3-Modbus-GPS"
DEFAULT_NAME = "Elsner P03/3 weather station"

# Config entry keys
CONF_CONNECTION_TYPE = "connection_type"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SLAVE = "slave"
CONF_RTU_OVER_TCP = "rtu_over_tcp"
CONF_SERIAL_PORT = "serial_port"
CONF_BAUDRATE = "baudrate"
CONF_PARITY = "parity"
CONF_STOPBITS = "stopbits"
CONF_HAS_GPS = "has_gps"
CONF_NAME = "name"
CONF_AREA = "area_id"

# Option keys
CONF_SCAN_INTERVAL = "scan_interval"

CONNECTION_TCP = "tcp"
CONNECTION_RTU = "rtu"

# Factory defaults of the P03/3-Modbus (all DIP switches OFF): address 1, 19200 baud, 8E1
DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_BAUDRATE = 19200
DEFAULT_PARITY = "E"
DEFAULT_STOPBITS = 1
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

BAUDRATES = ["1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"]
PARITIES = ["E", "O", "N"]
STOPBITS = ["1", "2"]

DEFAULT_TIMEOUT = 3  # seconds per Modbus request
