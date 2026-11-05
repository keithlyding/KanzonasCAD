"""The battery (tests/battery.py), short, on every build: random editing with the model's
checks after every step and undo / redo all the way, and every menu command in three states
(a sheet, the title block, no project). The long run (thousands of steps, several seeds) stays
a hand run before releases."""
import tempfile
import unittest

from tests.util import APP  # noqa: F401  (the QApplication)
from tests import battery


class QuickBatteryTest(unittest.TestCase):
    def test_random_editing(self):
        for seed in (11, 12):
            stats = battery.random_editing(None, tempfile.mkdtemp(), 120, seed)
            self.assertIn("120 steps", stats)

    def test_every_menu_command(self):
        battery.CLOSER = battery.DialogCloser()
        try:
            note = battery.every_command(None, tempfile.mkdtemp())
        finally:
            battery.CLOSER.stop()
        self.assertIn("menu commands triggered", note)

    def test_files(self):
        note = battery.files(None, tempfile.mkdtemp())
        self.assertIn("save/open", note)


if __name__ == "__main__":
    unittest.main()
