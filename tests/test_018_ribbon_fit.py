"""The ribbon fits the window (the owner, 0.18: "0.17.4's schematic ribbon goes off the screen.
Block properties should generally only be visible when editing/creating a block. I think we
can take that whole section and make it its own tab that only shows up when needed (or
manually selected)"): a block's tools on a Block tab of their own, shown in a block's tab or
when View, Block tab is on; a tab too wide for the window shows its groups smaller from the
right, and as built again when there is room."""
import tempfile
import unittest

from PySide6.QtWidgets import QToolButton

from tests.util import APP, window

BLOCK_KEYS = ("save_block", "save_block_as", "block_props", "dup_block", "add_pin", "pins", "add_attr")
# (the owner, 0.25, reversed 0.18's decision for Block properties: it is beside Edit block on the
# Schematic and Panel tabs again, tests/test_025_ribbon.py; the others stay on the Block tab only)
BLOCK_ONLY = tuple(k for k in BLOCK_KEYS if k != "block_props")


def tab_actions(win, title):
    r = win.ribbon
    page = r.widget(r.tab_index(title)).widget()
    return {b.defaultAction() for b in page.findChildren(QToolButton)}


class BlockTabTest(unittest.TestCase):
    def setUp(self):
        from kanzonascad import paths
        self.st = paths.settings()
        self.had = self.st.value("ribbon_block_tab", None)
        self.st.remove("ribbon_block_tab")
        self.win, self.v = window()
        self.win.library.folder = tempfile.mkdtemp()

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        if self.had is None:
            self.st.remove("ribbon_block_tab")
        else:
            self.st.setValue("ribbon_block_tab", self.had)
        self.assertTrue(APP)

    def shown(self):
        r = self.win.ribbon
        return r.isTabVisible(r.tab_index("Block"))

    def test_block_tools_are_on_the_block_tab_only(self):
        a = self.win.acts
        for title in ("Schematic", "Panel"):
            got = tab_actions(self.win, title)
            self.assertIn(a["edit_block"], got)       # (to open a block)
            for k in BLOCK_ONLY:
                self.assertNotIn(a[k], got, "%s still on the %s tab" % (k, title))
        got = tab_actions(self.win, "Block")
        for k in BLOCK_KEYS:
            self.assertIn(a[k], got)

    def test_shown_in_a_block_tab_and_gone_after(self):
        r = self.win.ribbon
        self.assertFalse(self.shown())
        d = self.win.edit_block("symbol", "Contact NO")
        self.assertIsNotNone(d)
        APP.processEvents()
        self.assertTrue(self.shown())
        self.assertEqual(r.tabText(r.currentIndex()), "Block")
        self.win.tabs.setCurrentIndex(0)                # back to the drawing
        APP.processEvents()
        self.assertFalse(self.shown())
        self.assertNotEqual(r.tabText(r.currentIndex()), "Block")
        self.win.tabs.setCurrentWidget(d)
        APP.processEvents()
        self.assertTrue(self.shown())

    def test_view_block_tab_keeps_it_shown(self):
        from kanzonascad import paths
        act = self.win.acts["block_tab"]
        self.assertFalse(act.isChecked())
        act.trigger()
        self.assertTrue(self.shown())
        self.assertEqual(str(paths.settings().value("ribbon_block_tab")).lower(), "true")
        self.win.tabs.setCurrentIndex(0)
        APP.processEvents()
        self.assertTrue(self.shown())
        act.trigger()
        self.assertFalse(self.shown())


class RibbonFitsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.show()

    def tearDown(self):
        self.v.project.saved_at = len(self.v.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def fitted(self, width, title):
        r = self.win.ribbon
        self.win.resize(width, 800)
        r.setCurrentIndex(r.tab_index(title))
        APP.processEvents()
        strip = r.currentWidget()
        return strip.widget().minimumWidth(), strip.viewport().width(), r.compacted()

    def test_schematic_tab_fits_a_narrow_window(self):
        full, _room, _small = self.fitted(4000, "Schematic")     # (as built: its whole width)
        for width in (1920, 1536, 1280, 1000):
            need, room, small = self.fitted(width, "Schematic")
            self.assertLessEqual(need, room, "the Schematic tab is %d wide in %d" % (need, room))
            # (made smaller only when it didn't fit as built: fonts differ, Windows' fits 1920)
            self.assertEqual(bool(small), full > room, (width, full, room, small))
            if not small:
                continue
            # smaller from the right: a group shown smaller has every group after it smaller
            order = ("large", "small", "icons")
            groups = self.win.ribbon._groups[self.win.ribbon.currentWidget().widget()]
            first = min(small)
            for g in groups[first:]:
                self.assertGreaterEqual(order.index(g.shown), order.index(g.size)
                                        if g.size == "large" else 1)

    def test_as_built_again_with_room(self):
        self.fitted(1000, "Schematic")
        need, room, small = self.fitted(4000, "Schematic")
        self.assertEqual(small, {})
        self.assertLessEqual(need, room)
        big = [b for b in self.win.ribbon.currentWidget().widget().findChildren(QToolButton)
               if b.defaultAction() is self.win.acts["wire"]]
        self.assertEqual(big[0].iconSize().width(), 20)  # (Wire as built: a big button)

    def test_icons_alone_keep_their_names_as_tooltips(self):
        self.fitted(700, "Schematic")
        groups = self.win.ribbon._groups[self.win.ribbon.currentWidget().widget()]
        icons = [w for g in groups if g.shown == "icons" for w in g.widgets
                 if isinstance(w, QToolButton) and w.defaultAction() is not None]
        self.assertTrue(icons)
        for w in icons:
            self.assertTrue(w.defaultAction().toolTip())


if __name__ == "__main__":
    unittest.main()
