# MicroPython configuration (argparse isn't available there).
# Copy this file, main.py and the kvm/ package to the board.

WIFI_SSID = "my-wifi"
WIFI_PASSWORD = "secret"

# One entry per monitor (max 2). "a"/"b" are the DDC input values (VCP 0x60)
# for PC A and PC B. DDC lines are 5 V: use a level shifter!
MONITORS = [
    {"i2c": 0, "sda": 0, "scl": 1, "a": 0x0F, "b": 0x11},
    {"i2c": 1, "sda": 2, "scl": 3, "a": 0x0F, "b": 0x11},
]

USB_PIN = 15
USB_MODE = "level"      # "level" or "pulse"
USB_ACTIVE_LOW = False
PULSE_MS = 200

NAMES = ("PC A", "PC B")
PORT = 80
