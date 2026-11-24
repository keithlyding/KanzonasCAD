"""A symbol held by a pin lands that pin exactly on the point given (0.16): the insertion point
was the point less the pin's offset, and adding the offset back is not always exact in floating
point (the long battery, seed 4773: a 16-point PLC output module's pin 1 at 1.7500000000000002,
not 1.75)."""
import random
import unittest

from tests.util import APP, window

from kanzonascad import commands as C
from kanzonascad import model as M


class PinExactTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.lib = self.win.library

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_the_held_pin_lands_exactly(self):
        rnd = random.Random(4773)
        names = ["PLC digital output module, 16 points", "Relay coil", "Contact NO"]
        missed = []
        for name in names:
            d = self.lib.get("symbol", name)
            cmd = C.InsertCmd(self.v, d, {})
            for angle in (0.0, 90.0, 180.0, 270.0):
                for mirror in (False, True):
                    cmd.angle, cmd.mirror = angle, mirror
                    for hold in range(len(cmd.holds) - 1):
                        cmd.hold = hold
                        pin = cmd.holds[hold][0]
                        for _i in range(40):
                            at = (round(rnd.uniform(0.5, 16.5) * 4) / 4,
                                  round(rnd.uniform(0.5, 10.5) * 4) / 4)
                            ins = M.Insert(d.name, cmd.origin(at), angle, 1.0, mirror, {}, d)
                            got = dict(ins.pin_points())[pin]
                            if got != at:
                                missed.append((name, angle, mirror, pin, at, got))
        self.assertEqual(missed[:3], [], "%d missed" % len(missed))


if __name__ == "__main__":
    unittest.main()
