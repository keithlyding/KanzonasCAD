"""The owner, 0.18: "Cross reference labels need to be a different layer by default. And a
different color. And slightly smaller font" (cyan, layer XREFS, 0.065"); "I would like to be
able to freeze wire numbers and/or component tag numbers as well. Both individually and by
selecting a bunch at a time and by choosing the entire sheet" (lock what's there); "Is there a
way to stretch a bus of wires at the same time" (both: STRETCH, and several grips picked with
Shift)."""
import os
import tempfile
import unittest

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class XrefLayerTest(unittest.TestCase):
    def test_new_and_old_projects(self):
        p = M.Project()
        self.assertEqual(p.layers["XREFS"].color, "#00e5ff")
        self.assertEqual(p.settings["xref_height"], 0.065)
        d = p.to_dict()
        d["layers"] = [x for x in d["layers"] if x["name"] != "XREFS"]
        d["settings"]["xref_height"] = 0.08                     # (as saved before 0.18)
        q = M.Project.from_dict(d)
        self.assertIn("XREFS", q.layers)
        self.assertEqual(q.settings["xref_height"], 0.065)
        d["settings"]["xref_height"] = 0.1                      # (set by hand: kept)
        self.assertEqual(M.Project.from_dict(d).settings["xref_height"], 0.1)

    def test_drawn_and_exported_on_their_layer(self):
        from kanzonascad import fileio
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            lib = win.library
            coil, no = lib.get("symbol", "Relay coil"), lib.get("symbol", "Contact NO")
            with p.edit("x") as ed:
                ed.block(coil)
                ed.block(no)
                ed.add(s, M.Insert(coil.name, (5.0, 5.0), defn=p.blocks[coil.name],
                                       attrs={"TAG": "CR101", "DEV": "d1"}))
                ed.add(s, M.Insert(no.name, (9.0, 5.0), defn=p.blocks[no.name],
                                   attrs={"TAG": "CR101", "PARENT": "d1"}))
            path = os.path.join(tempfile.mkdtemp(), "x.dxf")
            fileio.export_dxf(p, s, path)
            import ezdxf
            doc = ezdxf.readfile(path)
            on = {e.dxf.layer for e in doc.modelspace() if e.dxftype() in ("TEXT", "MTEXT")
                  and e.dxf.layer == "XREFS"}
            self.assertEqual(on, {"XREFS"})
            # the layer off: none
            with p.edit("off") as ed:
                ed.layer("XREFS", p.layers["XREFS"].to_dict(),
                         dict(p.layers["XREFS"].to_dict(), visible=False))
            fileio.export_dxf(p, s, path)
            doc = ezdxf.readfile(path)
            self.assertFalse([e for e in doc.modelspace() if e.dxftype() == "TEXT"
                              and e.dxf.layer == "XREFS"])
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


class LockAndStretchTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p, self.s = v.project, v.sheet()
        with self.p.edit("bus") as ed:
            self.bus = [ed.add(self.s, M.Wire([(1.0, y), (6.0, y)])) for y in (5.0, 5.5, 6.0)]
        v.center, v.scale = (4.0, 5.0), 100.0

    def tearDown(self):
        for k in ("ask_lock_numbers", "ask_update_numbers"):
            self.win.__dict__.pop(k, None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def wire(self, w):
        return self.s.entities[w.id]

    def test_lock_the_selected_then_the_sheet(self):
        self.v.set_selection({self.bus[0].id, self.bus[1].id})
        self.win.ask_lock_numbers = lambda p, s, n: {"lock": True, "wires": True,
                                                     "tags": True, "sheets": None}
        self.win.lock_numbers()
        self.assertEqual([self.wire(w).num_lock for w in self.bus], [True, True, False])
        self.win.ask_lock_numbers = lambda p, s, n: {"lock": True, "wires": True,
                                                     "tags": True, "sheets": [s]}
        self.win.lock_numbers()
        self.assertTrue(all(self.wire(w).num_lock for w in self.bus))
        # locked: Update numbers (renumber) leaves them as they are
        nums = [self.wire(w).num for w in self.bus]
        self.win.ask_update_numbers = lambda p, s: {"tags": True, "wires": True,
                                                    "xrefs": False, "renumber": True,
                                                    "sheets": [s]}
        self.win.update_numbers()
        self.assertEqual([self.wire(w).num for w in self.bus], nums)
        # unlock; one step each
        self.win.ask_lock_numbers = lambda p, s, n: {"lock": False, "wires": True,
                                                     "tags": True, "sheets": [s]}
        self.win.lock_numbers()
        self.assertFalse(any(self.wire(w).num_lock for w in self.bus))
        self.p.undo()
        self.assertTrue(all(self.wire(w).num_lock for w in self.bus))

    def test_stretch_a_bus(self):
        self.v.run(C.StretchCmd)
        type_in(self.v, "5.5,4.5", "6.5,6.5", "6,5", "8,5")
        self.assertIsNone(self.v.cmd)
        self.assertEqual([self.wire(w).points for w in self.bus],
                         [[(1.0, y), (8.0, y)] for y in (5.0, 5.5, 6.0)])
        self.p.undo()                                             # (one step)
        self.assertEqual(self.wire(self.bus[0]).points, [(1.0, 5.0), (6.0, 5.0)])
        # up: each end goes up, the wires stay square (a jog)
        self.v.run(C.StretchCmd)
        type_in(self.v, "5.5,4.5", "6.5,6.5", "6,5", "6,7")
        for w in self.bus:
            pts = self.wire(w).points
            self.assertEqual(pts[-1][1], w.points[-1][1] + 2.0)
            for a, b in zip(pts, pts[1:]):
                self.assertTrue(a[0] == b[0] or a[1] == b[1], pts)

    def test_several_grips_with_shift(self):
        v = self.v
        v.set_selection({w.id for w in self.bus})

        def click(q, shift=False):
            pos = v.to_screen(q)
            mod = Qt.ShiftModifier if shift else Qt.NoModifier
            for t in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease):
                APP.sendEvent(v, QMouseEvent(t, QPointF(pos), v.mapToGlobal(pos),
                                             Qt.LeftButton, Qt.LeftButton, mod))
        for w in self.bus:
            click(w.points[-1], shift=True)
        self.assertEqual(len(v.picked_grips), 3)
        click(self.bus[1].points[-1])                    # (one of them: they all go)
        self.assertIsInstance(v.cmd, C.GripCmd)
        type_in(v, "7.5,5.5")
        self.assertEqual([self.wire(w).points[-1] for w in self.bus],
                         [(7.5, 5.0), (7.5, 5.5), (7.5, 6.0)])


if __name__ == "__main__":
    unittest.main()
