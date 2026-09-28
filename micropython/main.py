# MicroPython entry point (e.g. Raspberry Pi Pico W / ESP32).

import asyncio
import time

import config
from machine import I2C, Pin

from kvm import ddc, usb
from kvm.core import KVM
from kvm.web import serve


def connect_wifi():
    try:
        import network
    except ImportError:
        return
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
        for _ in range(30):
            if wlan.isconnected():
                break
            time.sleep(1)
    print("WiFi:", wlan.ifconfig())


def build():
    monitors = []
    for i, m in enumerate(config.MONITORS):
        bus = I2C(m["i2c"], sda=Pin(m["sda"]), scl=Pin(m["scl"]), freq=50000)
        monitors.append(ddc.Monitor(ddc.MachineI2C(bus), (m["a"], m["b"]), "monitor%d" % (i + 1)))
    switch = usb.UsbSwitch(usb.MachinePin(config.USB_PIN), config.USB_MODE,
                           config.USB_ACTIVE_LOW, config.PULSE_MS)
    return KVM(monitors, switch, config.NAMES)


connect_wifi()
kvm = build()
kvm.sync()
asyncio.run(serve(kvm, "0.0.0.0", config.PORT))
