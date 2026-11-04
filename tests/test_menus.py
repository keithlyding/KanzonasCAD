import unittest

from tests.util import APP, window


class MenusTest(unittest.TestCase):
    def test_on_off_items_show_a_check_box(self):
        win, v = window()
        try:
            def walk(menu):
                for act in menu.actions():
                    if act.menu() is not None:
                        yield from walk(act.menu())
                    else:
                        yield act
            items = [a for m in win.menuBar().actions() if m.menu() is not None
                     for a in walk(m.menu())]
            on_off = [a for a in items if a.isCheckable()]
            self.assertIn("Check for updates automatically",
                          [a.text().replace("&", "") for a in on_off])
            for a in on_off:
                self.assertFalse(a.isIconVisibleInMenu(), a.text())
            auto = win.acts["auto_updates"]
            was = auto.isChecked()
            auto.trigger()
            self.assertNotEqual(auto.isChecked(), was)
            auto.trigger()
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
