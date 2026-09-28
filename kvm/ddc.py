# DDC/CI monitor input switching.
#
# Implements the DDC/CI "Set VCP Feature" / "Get VCP Feature" messages directly
# on top of a raw I2C bus, so the same code runs on CPython (/dev/i2c-N) and
# MicroPython (machine.I2C). A ddcutil backend is also provided for CPython as
# a fallback for monitors that need ddcutil's retry/timing quirks.

import time

DDC_ADDR = 0x37          # 7-bit I2C address of the monitor's DDC/CI endpoint
HOST_ADDR = 0x51         # source address byte used by the host
VCP_INPUT_SOURCE = 0x60  # MCCS "Input Source" feature code


def sleep_ms(ms):
    if hasattr(time, "sleep_ms"):
        time.sleep_ms(ms)
    else:
        time.sleep(ms / 1000)


def _xor(seed, data):
    for b in data:
        seed ^= b
    return seed


def set_vcp_packet(code, value):
    body = bytes([HOST_ADDR, 0x84, 0x03, code, (value >> 8) & 0xFF, value & 0xFF])
    return body + bytes([_xor(DDC_ADDR << 1, body)])


def get_vcp_packet(code):
    body = bytes([HOST_ADDR, 0x82, 0x01, code])
    return body + bytes([_xor(DDC_ADDR << 1, body)])


def parse_get_vcp_reply(reply, code):
    # Reply: 6E 88 02 rc code type max_hi max_lo cur_hi cur_lo chk
    if len(reply) < 11 or reply[1] != 0x88 or reply[2] != 0x02:
        raise OSError("malformed DDC reply: %r" % (bytes(reply),))
    if reply[3] != 0 or reply[4] != code:
        raise OSError("VCP 0x%02x unsupported by monitor" % code)
    if _xor(0x50, reply[:10]) != reply[10]:
        raise OSError("bad DDC reply checksum")
    return (reply[8] << 8) | reply[9]


class LinuxI2C:
    """Raw /dev/i2c-N access (CPython on Linux / Raspberry Pi)."""

    I2C_SLAVE = 0x0703
    I2C_SLAVE_FORCE = 0x0706

    def __init__(self, bus):
        self.bus = bus
        self.path = "/dev/i2c-%d" % bus

    def _open(self):
        import errno
        import fcntl
        import os

        fd = os.open(self.path, os.O_RDWR)
        try:
            fcntl.ioctl(fd, self.I2C_SLAVE, DDC_ADDR)
        except OSError as e:
            if e.errno != errno.EBUSY:
                os.close(fd)
                raise
            fcntl.ioctl(fd, self.I2C_SLAVE_FORCE, DDC_ADDR)
        return fd

    def write(self, data):
        import os

        fd = self._open()
        try:
            os.write(fd, data)
        finally:
            os.close(fd)

    def transact(self, data, nread, delay_ms=50):
        import os

        fd = self._open()
        try:
            os.write(fd, data)
            sleep_ms(delay_ms)
            return os.read(fd, nread)
        finally:
            os.close(fd)


class MachineI2C:
    """MicroPython machine.I2C / SoftI2C wrapper."""

    def __init__(self, i2c):
        self.i2c = i2c

    def write(self, data):
        self.i2c.writeto(DDC_ADDR, data)

    def transact(self, data, nread, delay_ms=50):
        self.i2c.writeto(DDC_ADDR, data)
        sleep_ms(delay_ms)
        return self.i2c.readfrom(DDC_ADDR, nread)


class FakeI2C:
    """In-memory monitor emulation, for --dry-run and tests."""

    def __init__(self, bus=0, value=0):
        self.bus = bus
        self.value = value

    def write(self, data):
        if data[1] == 0x84 and data[3] == VCP_INPUT_SOURCE:
            self.value = (data[4] << 8) | data[5]
            print("[dry-run] i2c-%s: input -> 0x%02x" % (self.bus, self.value))

    def transact(self, data, nread, delay_ms=0):
        body = bytearray([0x6E, 0x88, 0x02, 0x00, data[3], 0x00, 0x00, 0xFF,
                          (self.value >> 8) & 0xFF, self.value & 0xFF])
        body.append(_xor(0x50, body))
        return bytes(body)


class Monitor:
    """A monitor switched over DDC/CI via a raw I2C bus object."""

    def __init__(self, bus, inputs, name="monitor"):
        self.bus = bus
        self.inputs = inputs  # (value for PC A, value for PC B)
        self.name = name

    def set_input(self, value, retries=3):
        pkt = set_vcp_packet(VCP_INPUT_SOURCE, value)
        err = None
        for _ in range(retries):
            try:
                self.bus.write(pkt)
                sleep_ms(50)  # DDC/CI requires >= 50 ms between messages
                return
            except OSError as e:
                err = e
                sleep_ms(100)
        raise err

    def get_input(self, retries=3):
        pkt = get_vcp_packet(VCP_INPUT_SOURCE)
        err = None
        for _ in range(retries):
            try:
                reply = self.bus.transact(pkt, 11)
                # Many monitors put junk in the high byte of the input source.
                return parse_get_vcp_reply(reply, VCP_INPUT_SOURCE) & 0xFF
            except OSError as e:
                err = e
                sleep_ms(100)
        raise err


class DdcutilMonitor:
    """CPython fallback that shells out to ddcutil."""

    def __init__(self, bus, inputs, name="monitor"):
        self.bus = bus
        self.inputs = inputs
        self.name = name

    def _run(self, *args):
        import subprocess

        return subprocess.run(
            ["ddcutil", "--bus", str(self.bus), "--noverify"] + list(args),
            check=True, capture_output=True, text=True, timeout=10,
        ).stdout

    def set_input(self, value):
        self._run("setvcp", "60", "0x%02x" % value)

    def get_input(self):
        out = self._run("getvcp", "60", "--terse")  # "VCP 60 SNC x0f"
        return int(out.split()[-1].lstrip("x"), 16) & 0xFF
