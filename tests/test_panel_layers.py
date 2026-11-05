"""The Panel tab has the layers too (the owner: "I'd also like layers to be viewable from panel
tab"): its own current-layer box and layer list, kept the same as the Home tab's."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M


class PanelLayersTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_panel_tab_has_the_layer_box_and_list_in_step(self):
        w = self.win
        page = None
        for i in range(w.ribbon.count()):
            if w.ribbon.tabText(i) == "Panel":
                page = w.ribbon.widget(i).widget()
        self.assertTrue(page.isAncestorOf(w.panel_layer_box))
        self.assertTrue(page.isAncestorOf(w.panel_layer_states))
        with self.p.edit("layer") as ed:
            ed.layer("RAILS", None, M.Layer("RAILS").to_dict())
        w._fill_layers()
        items = [w.panel_layer_box.itemText(i) for i in range(w.panel_layer_box.count())]
        self.assertEqual(items, [w.layer_box.itemText(i) for i in range(w.layer_box.count())])
        self.assertIn("RAILS", items)
        # picked on the Panel tab: the current layer, shown on the Home tab too
        w._layer_picked(items.index("RAILS"), w.panel_layer_box)
        self.assertEqual(self.v.layer(), "RAILS")
        self.assertEqual(w.layer_box.currentText(), "RAILS")
        # with objects selected: they move to it
        with self.p.edit("line") as ed:
            ln = ed.add(self.v.sheet(), M.Line((1, 1), (2, 1)))
        self.v.set_selection({ln.id})
        w._layer_picked(items.index("0"), w.panel_layer_box)
        self.assertEqual(self.v.sheet().entities[ln.id].layer, "0")
        # its layer list: a row per layer
        menu = w.panel_layer_states.menu()
        w._fill_layer_states(menu)
        rows = [a for a in menu.actions() if a.defaultWidget() is not None]
        self.assertEqual(len(rows), len(self.p.layers))
        self.assertTrue(APP)


if __name__ == "__main__":
    unittest.main()
