# Elsner P03/3 Modbus Weather Station for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![GitHub release](https://img.shields.io/github/v/release/bmangodt/ha-elsner-p03)](https://github.com/bmangodt/ha-elsner-p03/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A Home Assistant custom integration for the **Elsner P03/3-Modbus** and **P03/3-Modbus-GPS** weather stations.

- Set up entirely from the UI, with no YAML.
- Connect over **Modbus TCP** (through an Ethernet gateway), **RTU over TCP** (a transparent serial server), or **Modbus RTU** (an RS-485 adapter on the Home Assistant machine).
- Every reading is an entity on **one device**, which you can assign to an **area** (room or zone).
- The connection is **tested during setup**. If the test fails, the form comes back with your values still filled in, so you can fix one field and retry.
- English and Dutch translations.

## Supported hardware

| Model | Elsner item no. | Supported |
|---|---|---|
| P03/3-Modbus | 30146 | ✅ |
| P03/3-Modbus-GPS | 30147 | ✅ (extra sun position, GPS time and coordinate entities) |

The station itself only speaks Modbus RTU over RS-485. For a network connection you need an RS-485 to Ethernet converter. Both of these work:

- a real **Modbus TCP gateway** (protocol conversion), or
- a **transparent serial server** (for example from USR IOT or Waveshare). For these, turn on *RTU over TCP* in the setup form.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=bmangodt&repository=ha-elsner-p03&category=integration)

Or add it manually:

1. In Home Assistant open **HACS**, then **⋮ → Custom repositories**.
2. Add `https://github.com/bmangodt/ha-elsner-p03` with category **Integration**.
3. Search for **Elsner P03/3** in HACS and click **Download**.
4. **Restart** Home Assistant.

### Manual

1. Download the latest release, or this repository as a ZIP.
2. Copy `custom_components/elsner_p03` into your Home Assistant `config/custom_components/` folder (for example with the *Samba share* or *Studio Code Server* add-on).
3. **Restart** Home Assistant.

Requires Home Assistant **2025.1** or newer.

## Configuration

[![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=elsner_p03)

Or go to **Settings → Devices & services → Add integration** and search for **Elsner**.

1. Choose **Modbus TCP** or **Modbus RTU**.
2. Fill in the form. The defaults match the station's factory settings (all DIP switches off):

   | Setting | Default |
   |---|---|
   | Modbus address | 1 |
   | Baud rate | 19200 |
   | Parity | Even |
   | Stop bits | 1 |
   | TCP port | 502 |

   - Tick **GPS model** if you have the P03/3-Modbus-GPS.
   - Optionally pick an **area** for the station.
3. Press **Submit**. The integration reads the station immediately.
   - If it works, the success dialog shows the new device, where you can also set or change its area.
   - If it fails, the form comes back with your values kept and an error explaining what went wrong (see [Troubleshooting](#troubleshooting)).

### After setup

| Action | Where | What it does |
|---|---|---|
| **Reconfigure** | Integration entry → ⋮ → Reconfigure | Change the IP address, port, serial settings or Modbus address. The new settings are tested before they're saved. |
| **Configure** | Integration entry → Configure | Poll interval (default 30 s, range 5 to 3600 s). |
| **Area** | Device page → ✏️ | Move the station to another room or zone. |

If the station is unreachable when Home Assistant starts, the integration keeps retrying in the background. Entities show *unavailable* until it's back.

## Entities

| Entity | Unit | Notes |
|---|---|---|
| Temperature | °C | 0.1 °C resolution |
| Wind speed | m/s | Can be shown in km/h or Beaufort through the entity settings. Valid about 60 s after the station powers up. |
| Illuminance | lx | Combined value: the brightest sun sensor in daylight, the twilight sensor in the dark. Good for automations. |
| Sun south / west / east | lx | The station measures 1 to 99 klx; converted to lux |
| Twilight brightness | lx | 0 to 999 lx |
| Rain | on/off | Binary sensor (moisture) |
| Sun azimuth | ° | GPS model only |
| Sun elevation | ° | GPS model only |
| GPS time sync | on/off | GPS model only, diagnostic |
| GPS time | timestamp | GPS model only, diagnostic, disabled by default |
| Latitude / Longitude | ° | GPS model only, diagnostic, disabled by default |
| Status register | | Raw register 6, diagnostic, disabled by default |

### Example automation: retract the awning on wind or rain

```yaml
automation:
  - alias: "Awning: retract on wind or rain"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.elsner_p03_3_weather_station_wind_speed
        above: 8
      - trigger: state
        entity_id: binary_sensor.elsner_p03_3_weather_station_rain
        to: "on"
    actions:
      - action: cover.close_cover
        target:
          entity_id: cover.awning
```

Check the actual entity IDs on your device page; they depend on the name you chose during setup.

## How it works

- All values come from **one** request: Modbus function 04 (Read Input Registers) from address 0, reading 7 registers for the standard model and 17 for the GPS model. This is the "read all" request from Elsner's manual. Always starting at address 0 avoids a known quirk where the station misreads other start addresses.
- Negative values (temperature, sun elevation, coordinates) are decoded as two's complement.
- **Rain flag:** Elsner's manual puts the rain flag in the low byte of register 6, but there are reports of rain showing up as 256 (the high byte).
  - On the standard model, any non-zero value counts as rain, so both layouts work.
  - On the GPS model, the high byte is the GPS flag, so the manual's layout is used there.

## Troubleshooting

| Error in the setup form | Likely cause |
|---|---|
| **Could not open the connection** | Wrong IP address or port, gateway offline, serial port path wrong, or the serial port is already used by something else (for example Home Assistant's built-in `modbus` integration on the same adapter) |
| **The station did not answer correctly** | Wrong Modbus address (check the DIP switches), wrong baud rate or parity, A/B wires swapped, or *RTU over TCP* set wrong for your gateway type |

**Other issues:**

- **Rain never turns on:** enable the *Status register* entity, wet the rain sensor, and [open an issue](https://github.com/YOUR_GITHUB_USERNAME/ha-elsner-p03/issues) with the value you see.
- **Bus termination:** turn on the termination DIP switch only when the station is at the end of a long RS-485 cable.

### Debug logging

```yaml
logger:
  logs:
    custom_components.elsner_p03: debug
    pymodbus: debug
```

With `pymodbus: debug`, every Modbus frame is logged. Please include that log when you report a bug.

## Contributing

Issues and pull requests are welcome. If you have a P03/3-Modbus-GPS, feedback on the GPS entities and the rain flag is especially useful.

## Disclaimer

This is a community project and is not affiliated with or endorsed by Elsner Elektronik GmbH. "Elsner" and "P03/3" are names of their respective owner and are used here only to identify compatible hardware.

## License

[MIT](LICENSE)
