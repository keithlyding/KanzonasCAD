"""The ribbon's group names show to start (the owner missed DIN rail and Wire duct on the Panel
tab: the groups had no names); PANDUIT starts Wire duct."""
import unittest

from tests.util import APP, window

from kanzonascad import commands as C


class RibbonNamesTest(unittest.TestCase):
    def test_group_names_show_to_start(self):
        from kanzonascad import paths
        st = paths.settings()
        had = st.value("ribbon_group_names", None)
        st.remove("ribbon_group_names")
        try:
            win, v = window()
            try:
                self.assertTrue(win.acts["group_names"].isChecked())
                texts = [lb.text() for lb in win.ribbon._labels if not lb.isHidden()]
                self.assertIn("Rail and duct", texts)
                win.acts["group_names"].trigger()              # turned off, kept off
                self.assertTrue(all(lb.isHidden() for lb in win.ribbon._labels))
                self.assertEqual(str(paths.settings().value("ribbon_group_names")).lower(),
                                 "false")
            finally:
                v.project.saved_at = len(v.project.undo_stack)
                win.close()
        finally:
            if had is None:
                st.remove("ribbon_group_names")
            else:
                st.setValue("ribbon_group_names", had)
        self.assertTrue(APP)

    def test_panduit_starts_wire_duct(self):
        self.assertIn("PANDUIT", C.COMMANDS["DUCT"][1])
        win, v = window()
        try:
            v.run_name("PANDUIT")
            self.assertIsInstance(v.cmd, C.DuctCmd)
            v.cancel()
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
