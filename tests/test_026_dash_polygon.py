"""Dashed polygons (the owner, 0.26: "Dashed polygon in addition to the dashed box"): a dashed
outline of any shape, its corners clicked one by one as a polyline's (U takes the last back),
closed with Enter or C; then a dashed box's window (its note, the device it belongs to). Moved,
copied, turned, mirrored, stretched by its corners, erased, undone, saved and opened, written
to DXF and PDF like everything else."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import props_panel as PP
from kanzonascad import xrefs

L_SHAPE = [(1.0, 1.0), (5.0, 1.0), (5.0, 3.0), (3.0, 3.0), (3.0, 6.0), (1.0, 6.0)]


class DashPolygonTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p, self.s = v.project, v.sheet()

    def tearDown(self):
        self.win.__dict__.pop("ask_dash_box", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def poly(self, pts, answer=None, close="C"):
        asked = []

        def ask(box):
            asked.append(box)
            return answer if answer is not None else {"text": "FIELD", "device": None}
        self.win.ask_dash_box = ask
        before = set(self.s.entities)
        self.v.run(C.DashPolygonCmd)
        type_in(self.v, *["#%r,%r" % q for q in pts])
        if close:
            type_in(self.v, close)
        self.asked = asked
        got = [e for i, e in self.s.entities.items() if i not in before]
        return got[0] if got else None

    def test_picked_corner_by_corner_and_closed(self):
        b = self.poly(L_SHAPE)
        self.assertIsInstance(b, M.DashPolygon)
        self.assertIsInstance(b, M.DashBox)         # (everything a dashed box is)
        self.assertEqual(b.points, L_SHAPE)
        self.assertEqual(b.text, "FIELD")
        self.assertEqual(b.layer, "NOTES")
        self.assertEqual(b.kind, "dashpoly")
        self.assertIsNone(self.v.cmd)
        # its dashes all on its six sides, with gaps, the corners drawn
        sides = list(zip(L_SHAPE, L_SHAPE[1:] + L_SHAPE[:1]))
        for a, c in b.dash_pieces():
            self.assertTrue(any(_on(a, s) and _on(c, s) for s in sides), (a, c))
        for q in L_SHAPE:
            self.assertTrue(any(_same(q, a) or _same(q, c) for a, c in b.dash_pieces()), q)
        # the note inside it, by its top left corner
        x, y = b.note_point()
        self.assertTrue(1.0 < x < 1.5 and 5.5 < y < 6.0, (x, y))

    def test_enter_closes_it_too_and_u_takes_a_corner_back(self):
        self.win.ask_dash_box = lambda box: {"text": "", "device": None}
        self.v.run(C.DashPolygonCmd)
        type_in(self.v, "#1,1", "#4,1", "#9,9", "U", "#4,4")
        self.assertIn(("Close", "C"), self.v._prompt[1])
        self.v.enter()
        got = [e for e in self.s.entities.values() if isinstance(e, M.DashPolygon)]
        self.assertEqual([e.points for e in got], [[(1.0, 1.0), (4.0, 1.0), (4.0, 4.0)]])

    def test_too_few_corners_or_in_a_line_is_refused(self):
        msgs = []
        self.v.messaged.connect(msgs.append)
        self.win.ask_dash_box = lambda box: {"text": "", "device": None}
        self.v.run(C.DashPolygonCmd)
        type_in(self.v, "#1,1", "#4,1")
        self.v.enter()
        self.assertIsNotNone(self.v.cmd)            # (still waiting for a corner)
        type_in(self.v, "#7,1")                     # (in a line: no area)
        self.v.enter()
        self.assertIsNotNone(self.v.cmd)
        self.assertIn("three corners", msgs[-1])
        self.v.escape()
        self.assertFalse(self.s.entities)

    def test_cancel_in_its_window_makes_none(self):
        self.win.ask_dash_box = lambda box: None
        self.v.run(C.DashPolygonCmd)
        type_in(self.v, "#1,1", "#4,1", "#4,4", "C")
        self.assertIsNone(self.v.cmd)
        self.assertFalse(self.s.entities)

    def test_the_window_is_a_dashed_box_s_with_its_name(self):
        from kanzonascad import dialogs
        from PySide6.QtWidgets import QDialog
        seen = []
        real = QDialog.exec

        def answer(dlg):
            seen.append(dlg.windowTitle())
            return QDialog.Rejected
        QDialog.exec = answer
        try:
            got = dialogs.dash_box_dialog(self.win, self.p, M.DashPolygon(L_SHAPE))
        finally:
            QDialog.exec = real
        self.assertIsNone(got)
        self.assertEqual(seen, ["Dashed polygon"])

    def test_belongs_to_a_device(self):
        v = self.v
        before = set(self.s.entities)
        v.run(C.InsertCmd, self.win.library.get("symbol", "Contactor coil"), {})
        type_in(v, "8.0,3.0")
        while v.cmd is not None:
            v.cmd.enter()
        coil = [e for i, e in self.s.entities.items() if i not in before][0]
        b = self.poly(L_SHAPE, {"text": "BUCKET 3", "device": coil})
        self.assertEqual(b.attrs["PARENT"], coil.attrs["DEV"])
        self.assertEqual(b.tag(), coil.attrs["TAG"])
        # its tag above its top left corner; the coil lists where it is
        self.assertEqual(b.tag_point(), (1.0, 6.0 + b.height * 0.5))
        self.assertIn(self.p.zone_text(self.s, *L_SHAPE[0]),
                      [t for _x, _y, t, _h in xrefs.live(self.p, self.s)])
        with self.p.edit("retag") as ed:
            ed.change(self.s, coil.copy(attrs=dict(coil.attrs, TAG="M77", TAG_LOCK="1")))
        self.assertEqual(self.s.entities[b.id].tag(), "M77")

    def test_a_corner_dragged_moves_alone(self):
        b = self.poly(L_SHAPE)
        c = b.with_grip(3, (3.5, 2.5))
        self.assertEqual(c.points, L_SHAPE[:3] + [(3.5, 2.5)] + L_SHAPE[4:])
        n = len(b.points)
        self.assertEqual(b.with_grip(n, (2.0, 2.0)).note_point(), (2.0, 2.0))

    def test_moved_turned_mirrored_erased_undone(self):
        b = self.poly(L_SHAPE)
        with self.p.edit("Move") as ed:
            ed.change(self.s, self.s.entities[b.id].moved(2.0, -1.0))
        self.assertEqual(self.s.entities[b.id].points,
                         [(x + 2.0, y - 1.0) for x, y in L_SHAPE])
        r = b.rotated((0.0, 0.0), 90.0)
        self.assertEqual([tuple(round(c, 9) for c in q) for q in r.points],
                         [(-y, x) for x, y in L_SHAPE])
        self.assertIsInstance(r, M.DashPolygon)
        m = b.mirrored((0.0, 0.0), (0.0, 1.0))
        self.assertEqual(m.points, [(-x, y) for x, y in L_SHAPE])
        with self.p.edit("Erase") as ed:
            ed.remove(self.s, b.id)
        self.assertNotIn(b.id, self.s.entities)
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.s.entities[b.id].points, L_SHAPE)
        # found by a window round one of its sides only, through the sheet's index
        self.assertIn(b.id, {e.id for e in self.s.query((2.9, 4.0, 3.1, 4.2))})

    def test_saved_opened_and_written_to_dxf_and_pdf(self):
        b = self.poly(L_SHAPE, {"text": "NOTE", "device": None})
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.kzcad")
        self.p.save(path, backups=0)
        again = M.Project.load(path).sheets[0].entities[b.id]
        self.assertIsInstance(again, M.DashPolygon)
        self.assertEqual(again.to_dict(), b.to_dict())
        dxf = os.path.join(d, "t.dxf")
        fileio.export_dxf(self.p, self.s, dxf)
        import ezdxf
        msp = ezdxf.readfile(dxf).modelspace()
        self.assertIn("NOTE", {e.dxf.text for e in msp.query("TEXT")})
        lines = [(tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]) for e in msp.query("LINE")]
        self.assertEqual(len([1 for a, c in lines if any(_on(a, s) for s in zip(
            L_SHAPE, L_SHAPE[1:] + L_SHAPE[:1]))]), len(b.dash_pieces()))
        pdf = os.path.join(d, "t.pdf")
        fileio.export_pdf(self.p, pdf)
        self.assertGreater(os.path.getsize(pdf), 1000)

    def test_double_click_and_the_properties_panel(self):
        b = self.poly(L_SHAPE, {"text": "OLD", "device": None})
        self.win.ask_dash_box = lambda box: {"text": "NEW", "device": None}
        self.win.edit_text(self.s.entities[b.id])
        self.assertEqual(self.s.entities[b.id].text, "NEW")
        self.assertEqual(self.p.undo_stack[-1].name, "Edit dashed polygon")
        self.assertEqual(PP.kind_name(self.s.entities[b.id]), "Dashed polygon")

    def test_preview_shows_it_closed(self):
        self.v.run(C.DashPolygonCmd)
        type_in(self.v, "#1,1")
        self.assertEqual([type(e) for e in self.v.cmd.preview((4.0, 1.0))], [M.Line])
        type_in(self.v, "#4,1")
        got = self.v.cmd.preview((4.0, 4.0))
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].points, [(1.0, 1.0), (4.0, 1.0), (4.0, 4.0)])
        self.v.escape()

    def test_on_the_menu_and_the_ribbon_next_to_dashed_box(self):
        a = self.win.acts
        draw = [m for m in self.win.menuBar().actions() if m.text() == "&Draw"][0].menu()
        keys = [x.text() for x in draw.actions()]
        i = keys.index(a["dash_box"].text())
        self.assertEqual(keys[i + 1], a["dash_poly"].text())
        self.assertIs(C.lookup("DASHPOLY"), C.DashPolygonCmd)
        self.assertIs(C.lookup("DPOLY"), C.DashPolygonCmd)
        from kanzonascad.ribbon import SplitButton
        held = [b.menu().actions() for b in self.win.ribbon.findChildren(SplitButton)
                if a["dash_box"] in b.menu().actions()]
        held = [acts for acts in held if acts.index(a["dash_poly"]) ==
                acts.index(a["dash_box"]) + 1]
        self.assertTrue(held, "no ribbon button holds Dashed box and Dashed polygon together")


def _same(a, b):
    return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9


def _on(q, side):
    from kanzonascad import geometry as G
    return G.dist_to_segment(q, side[0], side[1]) < 1e-9


if __name__ == "__main__":
    unittest.main()
