# USB switch control over a single GPIO pin.
#
# mode "level": pin low = PC A, pin high = PC B (e.g. driving a mux/relay).
# mode "pulse": each switch emits a short pulse, emulating a press of the
#               switch's toggle button (typical cheap USB KVM switches).

from .ddc import sleep_ms


class GpiozeroPin:
    """CPython on Raspberry Pi OS (works on Pi 5 via lgpio backend)."""

    def __init__(self, pin):
        from gpiozero import DigitalOutputDevice

        self._dev = DigitalOutputDevice(pin, initial_value=None)

    def value(self, v):
        self._dev.value = 1 if v else 0


class MachinePin:
    """MicroPython machine.Pin."""

    def __init__(self, pin):
        from machine import Pin

        self._pin = Pin(pin, Pin.OUT)

    def value(self, v):
        self._pin.value(1 if v else 0)


class FakePin:
    def __init__(self, pin):
        self.pin = pin
        self.state = 0

    def value(self, v):
        self.state = 1 if v else 0
        print("[dry-run] gpio %s -> %d" % (self.pin, self.state))


class UsbSwitch:
    def __init__(self, pin, mode="level", active_low=False, pulse_ms=200):
        if mode not in ("level", "pulse"):
            raise ValueError("usb mode must be 'level' or 'pulse'")
        self.pin = pin
        self.mode = mode
        self.active_low = active_low
        self.pulse_ms = pulse_ms
        self._set(False)

    def _set(self, on):
        self.pin.value(bool(on) != self.active_low)

    def select(self, pc, current):
        """Route USB to pc (0 = A, 1 = B). current is the assumed present state."""
        if self.mode == "level":
            self._set(pc == 1)
        elif pc != current:
            self._set(True)
            sleep_ms(self.pulse_ms)
            self._set(False)
