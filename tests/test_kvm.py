import unittest

from kvm import ddc, usb
from kvm.core import KVM
from kvm.web import route


class DdcTest(unittest.TestCase):
    def test_set_packet_matches_spec(self):
        # Known-good frame: set input source (0x60) to 0x0f
        self.assertEqual(ddc.set_vcp_packet(0x60, 0x0F).hex(), "51840360000f" + "%02x" % (
            0x6E ^ 0x51 ^ 0x84 ^ 0x03 ^ 0x60 ^ 0x00 ^ 0x0F))

    def test_get_roundtrip_with_fake_monitor(self):
        m = ddc.Monitor(ddc.FakeI2C(value=0x0F), (0x0F, 0x11))
        m.set_input(0x11)
        self.assertEqual(m.get_input(), 0x11)

    def test_bad_checksum_rejected(self):
        reply = bytearray(ddc.FakeI2C(value=0x0F).transact(ddc.get_vcp_packet(0x60), 11))
        reply[10] ^= 0xFF
        with self.assertRaises(OSError):
            ddc.parse_get_vcp_reply(reply, 0x60)


class KvmTest(unittest.TestCase):
    def make(self, mode="level", start=0x11):
        self.buses = [ddc.FakeI2C(1, start), ddc.FakeI2C(2, start)]
        self.pin = usb.FakePin(17)
        mons = [ddc.Monitor(b, (0x0F, 0x11)) for b in self.buses]
        return KVM(mons, usb.UsbSwitch(self.pin, mode))

    def test_sync_detects_current_input(self):
        kvm = self.make(start=0x11)
        kvm.sync()
        self.assertEqual(kvm.active, 1)
        self.assertEqual(self.pin.state, 1)

    def test_toggle_level(self):
        kvm = self.make(start=0x0F)
        kvm.sync()
        kvm.toggle()
        self.assertEqual([b.value for b in self.buses], [0x11, 0x11])
        self.assertEqual(self.pin.state, 1)
        kvm.toggle()
        self.assertEqual([b.value for b in self.buses], [0x0F, 0x0F])
        self.assertEqual(self.pin.state, 0)

    def test_pulse_mode_only_pulses_on_change(self):
        states = []
        kvm = self.make(mode="pulse", start=0x0F)
        kvm.usb.pulse_ms = 0
        self.pin.value = lambda v: states.append(int(v))
        kvm.select(0)
        self.assertEqual(states, [])
        kvm.select(1)
        self.assertEqual(states, [1, 0])

    def test_routes(self):
        kvm = self.make(start=0x0F)
        kvm.sync()
        self.assertEqual(route(kvm, "GET", "/")[0], "200 OK")
        status, ctype, body, _ = route(kvm, "POST", "/api/toggle")
        self.assertIn('"active": "B"', body)
        self.assertEqual(route(kvm, "POST", "/toggle")[0], "303 See Other")
        self.assertEqual(kvm.active, 0)
        self.assertEqual(route(kvm, "GET", "/nope")[0], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
