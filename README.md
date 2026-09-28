# kvm-poc

A basic KVM for 2 PCs and up to 2 monitors, running on a Raspberry Pi:

- **Video**: each monitor's input is switched over **DDC/CI** (VCP feature `0x60`).
- **USB**: a USB switch is driven by a **GPIO** pin.
- **Web UI**: one big toggle button, plus direct A/B buttons (`http://<pi>/`).

It is pure Python with no pip dependencies. The core (`kvm/ddc.py`, `usb.py`, `core.py`, `web.py`)
also runs on **MicroPython**.

## Install (Raspberry Pi OS Bookworm or newer)

```sh
curl -fsSL https://raw.githubusercontent.com/FuNK3Y/kvm-poc/main/install.sh | sudo bash -s -- \
    --monitor 20:0x0f:0x11 --monitor 21:0x0f:0x11 --usb-pin 17
```

This installs to `/opt/kvm` and creates the `kvm.service` systemd unit. It runs as an unprivileged
`kvm` user in the `i2c` and `gpio` groups. Run the command again with different arguments to reconfigure,
or with no arguments to update and keep the current configuration.

It installs only what's missing: `python3`, `python3-gpiozero`, `python3-lgpio` and `curl`. On Pi OS
these are usually already present. Add `--with-tools` to also install `ddcutil` and `i2c-tools`, which
help you find the values below. `ddcutil` is also installed automatically when you use `--ddc-backend ddcutil`.

To only download and extract, without installing:

```sh
mkdir -p kvm-poc && curl -fsSL https://github.com/FuNK3Y/kvm-poc/releases/latest/download/kvm.tar.gz | tar xz -C kvm-poc
```

### Finding the values

The Pi's HDMI port is wired to a spare input on each monitor, which gives it access to the DDC bus.
You can also tap the DDC lines through a level shifter.

```sh
ddcutil detect                     # lists /dev/i2c-N for each monitor (Pi 4 HDMI: usually 20/21)
ddcutil --bus 20 capabilities      # "Feature: 60 (Input Source)" lists values, e.g. 0x0f=DP1, 0x11=HDMI1
ddcutil --bus 20 setvcp 60 0x11    # try it by hand
```

## Options

| Option | Meaning |
|---|---|
| `--monitor BUS:A:B` | I2C bus, input value for PC A, input value for PC B. Repeat for the 2nd monitor. |
| `--usb-pin N` | BCM GPIO driving the USB switch |
| `--usb-mode level\|pulse` | `level` (default): low = A, high = B. `pulse`: short pulse to toggle a button-driven switch |
| `--usb-active-low` | invert the output |
| `--pulse-ms N` | pulse length (default 200) |
| `--ddc-backend i2c\|ddcutil` | raw I2C (default) or `ddcutil` for picky monitors |
| `--name-a / --name-b` | labels shown in the UI |
| `--port` | HTTP port (default 80) |
| `--dry-run` | simulate the hardware |

HTTP API: `GET /api/status`, `POST /api/toggle`, `POST /api/select/A`, `POST /api/select/B`.

## Develop

```sh
python3 -m kvm --dry-run -m 20:0x0f:0x11 --usb-pin 17 --port 8080
python3 -m unittest discover -s tests -t .
```

## MicroPython (e.g. Pico W)

Copy `kvm/` and the contents of `micropython/` (`main.py`, `config.py`) to the board. Then edit `config.py`.
DDC is 5 V, so use a level shifter on SDA and SCL.
