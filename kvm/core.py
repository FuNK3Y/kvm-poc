PCS = ("A", "B")


class KVM:
    def __init__(self, monitors, usb=None, names=("PC A", "PC B")):
        self.monitors = monitors
        self.usb = usb
        self.names = names
        self.active = 0
        self.last_errors = []

    def sync(self):
        """Detect the active PC from the first monitor that answers."""
        for m in self.monitors:
            try:
                value = m.get_input()
            except Exception as e:
                print("KVM: cannot read input of %s: %s" % (m.name, e))
                continue
            if value in m.inputs:
                self.active = m.inputs.index(value)
                break
        # In level mode this aligns the USB pin; in pulse mode it's a no-op.
        if self.usb:
            self.usb.select(self.active, self.active)
        print("KVM: active is %s" % self.names[self.active])

    def select(self, pc):
        errors = []
        for m in self.monitors:
            try:
                m.set_input(m.inputs[pc])
            except Exception as e:
                errors.append("%s: %s" % (m.name, e))
        if self.usb:
            try:
                self.usb.select(pc, self.active)
            except Exception as e:
                errors.append("usb: %s" % e)
        self.active = pc
        self.last_errors = errors
        for e in errors:
            print("KVM error:", e)
        print("KVM: switched to %s" % self.names[pc])
        return errors

    def toggle(self):
        return self.select(1 - self.active)

    def status(self):
        return {
            "active": PCS[self.active],
            "name": self.names[self.active],
            "names": {"A": self.names[0], "B": self.names[1]},
            "errors": self.last_errors,
        }
