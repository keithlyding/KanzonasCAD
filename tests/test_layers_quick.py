import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class LayerQuickTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()
        with self.p.edit("lines") as ed:
            self.a = ed.add(self.s, M.Line((1, 1), (5, 1), layer="NOTES"))
            self.b = ed.add(self.s, M.Line((1, 3), (5, 3), layer="WIRES"))

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def vis(self, name):
        return self.p.layers[name].visible

    def test_hide_isolate_show_all(self):
        self.v.run(C.LayerOffCmd)
        self.v.cmd.pick((3, 1.01))
        self.assertFalse(self.vis("NOTES"))
        self.assertTrue(self.vis("WIRES"))
        self.v.run(C.LayerOnCmd)
        self.assertTrue(self.vis("NOTES"))
        # isolate through the selection
        self.v.set_selection({self.b.id})
        self.v.run(C.LayerIsoCmd)
        self.assertEqual([n for n, l in self.p.layers.items() if l.visible], ["WIRES"])
        # one undo brings them all back
        self.p.undo()
        self.assertTrue(all(l.visible for l in self.p.layers.values()))

    def test_lock_and_unlock_all(self):
        self.v.run(C.LayerLockCmd)
        self.v.cmd.pick((3, 3.01))
        self.assertTrue(self.p.layers["WIRES"].locked)
        self.assertIsNone(self.v.pick_entity((3, 3.01)))        # can't be picked now
        self.v.run(C.LayerUnlockAllCmd)
        self.assertFalse(any(l.locked for l in self.p.layers.values()))

    def test_layer_list_and_quick_undo_redo(self):
        w = self.win
        w._fill_layer_states()
        rows = [a for a in w.layer_states_menu.actions() if a.defaultWidget() is not None]
        self.assertEqual(len(rows), len(self.p.layers))
        w._set_layer_state("NOTES", visible=False)
        self.assertFalse(self.vis("NOTES"))
        APP.processEvents()
        undo = [q for q in w._quick if "Undo" in q.toolTip()][0]
        self.assertTrue(undo.isEnabled())
        undo.trigger()
        self.assertTrue(self.vis("NOTES"))
        self.assertIn(undo, w.menuBar().actions())


if __name__ == "__main__":
    unittest.main()
