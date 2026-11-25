"""Ribbon buttons (0.25): Explode on the Home tab's Modify group and on the Block tab (a block's
own tab) in a small Modify group, so a block placed in the block being edited can be exploded
there; Block properties... beside Edit block on the Schematic tab's Symbols group and the Panel
tab's Footprints group (the owner reversed 0.18's "Block properties should generally only be
visible when editing/creating a block": a crowded tab now shrinks its groups, Ribbon.fit).
Each button is on its page and works with a block selected."""
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QToolButton

from tests.util import APP, window

from kanzonascad import model as M


def group_actions(win, tab, index):
    """The actions of a tab's group (its buttons, left to right, top to bottom)."""
    r = win.ribbon
    page = r.widget(r.tab_index(tab)).widget()
    g = r._groups[page][index]
    out = []
    for w in g.widgets:
        if isinstance(w, QToolButton) and w.defaultAction() is not None:
            out.append(w.defaultAction())
    return out


def group_named(win, tab, title):
    """The index of a tab's group by its name."""
    r = win.ribbon
    page = r.widget(r.tab_index(tab)).widget()
    names = [lb.text() for lb in page.findChildren(type(r._labels[0]))
             if lb in r._labels]
    return names.index(title)


class RibbonButtonsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.win.library.folder = tempfile.mkdtemp()
        self.p, self.s = self.v.project, self.v.sheet()
        self.a = self.win.acts

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, kind, name, at=(5.0, 5.0), project=None, sheet=None):
        p = project or self.p
        s = sheet or self.s
        defn = self.win.library.get(kind, name)
        with p.edit("place") as ed:
            ed.block(defn)
            e = ed.add(s, M.Insert(defn.name, at, defn=p.blocks[defn.name],
                                   attrs={"TAG": "CR101", "DEV": "d1"}))
        return e

    def test_buttons_are_on_their_pages(self):
        a, w = self.a, self.win
        self.assertIn(a["explode"], group_actions(w, "Home", group_named(w, "Home", "Modify")))
        sym = group_actions(w, "Schematic", group_named(w, "Schematic", "Symbols"))
        self.assertIn(a["block_props"], sym)
        self.assertEqual(sym.index(a["block_props"]), sym.index(a["edit_block"]) + 1,
                         "Block properties beside Edit block")
        fp = group_actions(w, "Panel", group_named(w, "Panel", "Footprints"))
        self.assertIn(a["block_props"], fp)
        self.assertEqual(fp.index(a["block_props"]), fp.index(a["edit_block"]) + 1)
        i = group_named(w, "Block", "Modify")
        self.assertEqual(group_actions(w, "Block", i), [a["explode"], a["object_color"]])

    def test_explode_from_home_with_a_block_selected(self):
        e = self.place("symbol", "Relay coil")
        self.v.set_selection({e.id})
        self.a["explode"].trigger()
        APP.processEvents()
        self.assertNotIn(e.id, self.s.entities)
        self.assertFalse(any(isinstance(x, M.Insert) for x in self.s.entities.values()))
        self.assertTrue(self.v.sel)
        self.assertTrue(all(i in self.s.entities for i in self.v.sel))

    def test_block_properties_with_a_block_selected(self):
        from kanzonascad import library_panel
        e = self.place("footprint", "Breaker 1-pole (DIN)")
        self.v.set_selection({e.id})
        seen = []

        def details(_parent, _lib, defn=None, **_k):
            seen.append(defn.name)
            return None
        with mock.patch.object(library_panel, "block_details_dialog", details):
            self.a["block_props"].trigger()
        self.assertEqual(seen, [e.block])

    def test_explode_in_a_blocks_tab(self):
        d = self.win.edit_block("symbol", "Relay coil")
        self.assertIsNotNone(d)
        APP.processEvents()
        r = self.win.ribbon
        self.assertEqual(r.tabText(r.currentIndex()), "Block")
        bv = d.view
        inner = self.place("symbol", "Contact NO", (3.0, 3.0), bv.project, bv.sheet())
        before = len(bv.sheet().entities)
        bv.set_selection({inner.id})
        self.assertTrue(self.a["explode"].isEnabled())
        self.a["explode"].trigger()
        APP.processEvents()
        ents = bv.sheet().entities
        self.assertNotIn(inner.id, ents)
        self.assertFalse(any(isinstance(x, M.Insert) for x in ents.values()))
        self.assertGreater(len(ents), before - 1)
        # (undone, the contact is back in the block)
        bv.project.undo()
        self.assertIn(inner.id, bv.sheet().entities)


if __name__ == "__main__":
    unittest.main()
