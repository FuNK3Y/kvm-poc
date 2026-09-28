# CPython / Raspberry Pi entry point:  python3 -m kvm --monitor 20:0x0f:0x11 --usb-pin 17

import argparse
import asyncio

from . import ddc, usb
from .core import KVM
from .web import serve


def monitor_spec(text):
    try:
        bus, a, b = text.split(":")
        return int(bus, 0), int(a, 0), int(b, 0)
    except ValueError:
        raise argparse.ArgumentTypeError("expected BUS:INPUT_A:INPUT_B, e.g. 20:0x0f:0x11")


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="kvm", description="DDC/CI + GPIO KVM switch with a web UI")
    p.add_argument("--monitor", "-m", action="append", type=monitor_spec, required=True,
                   metavar="BUS:INPUT_A:INPUT_B",
                   help="I2C bus of the monitor and its DDC input values (VCP 0x60) "
                        "for PC A and PC B. Repeat for the second monitor.")
    p.add_argument("--usb-pin", type=int, required=True, help="BCM GPIO number driving the USB switch")
    p.add_argument("--usb-mode", choices=("level", "pulse"), default="level",
                   help="level: low=A, high=B. pulse: pulse the pin to toggle (default: level)")
    p.add_argument("--usb-active-low", action="store_true", help="invert the GPIO output")
    p.add_argument("--pulse-ms", type=int, default=200, help="pulse length in pulse mode")
    p.add_argument("--ddc-backend", choices=("i2c", "ddcutil"), default="i2c",
                   help="raw /dev/i2c access (default) or shell out to ddcutil")
    p.add_argument("--name-a", default="PC A")
    p.add_argument("--name-b", default="PC B")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--dry-run", action="store_true", help="simulate monitors and GPIO")
    return p.parse_args(argv)


def build(args):
    monitors = []
    for i, (bus, a, b) in enumerate(args.monitor):
        name = "monitor%d(i2c-%d)" % (i + 1, bus)
        if args.dry_run:
            monitors.append(ddc.Monitor(ddc.FakeI2C(bus, a), (a, b), name))
        elif args.ddc_backend == "ddcutil":
            monitors.append(ddc.DdcutilMonitor(bus, (a, b), name))
        else:
            monitors.append(ddc.Monitor(ddc.LinuxI2C(bus), (a, b), name))

    pin_cls = usb.FakePin if args.dry_run else usb.GpiozeroPin
    switch = usb.UsbSwitch(pin_cls(args.usb_pin), args.usb_mode,
                           args.usb_active_low, args.pulse_ms)
    return KVM(monitors, switch, (args.name_a, args.name_b))


def main(argv=None):
    args = parse_args(argv)
    kvm = build(args)
    kvm.sync()
    try:
        asyncio.run(serve(kvm, args.host, args.port))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
