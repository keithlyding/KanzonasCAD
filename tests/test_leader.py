"""Leader (the owner: "Should we add leader and multi leader functionality?" ... "Agree with
combining leaders and multileader"): one tool, a note or a balloon with an item number."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M


class LeaderModelTest(unittest.TestCase):
    def test_note_and_balloon_parts(self):
        ld = M.Leader([(0, 0), (1, 1), (2, 1)], "TB1\nSEE NOTE", height=0.1)
        kinds = [e.kind for e in ld.parts()]
        self.assertEqual(kinds, ["polyline", "hatch", "line", "text", "text"])
        arrow = ld.parts()[1]
        self.assertIsInstance(arrow, M.Hatch)                    # (filled, 0.13.3)
        self.assertTrue(arrow.solid())
        self.assertEqual(tuple(arrow.loops[0][0]), (0.0, 0.0))   # (its tip at the first point)
        texts = [e for e in ld.parts() if isinstance(e, M.Text)]
        self.assertEqual([t.text for t in texts], ["TB1", "SEE NOTE"])
        self.assertEqual(texts[0].align, "left")                 # (the line runs right)
        self.assertGreater(texts[0].pos[1], texts[1].pos[1])
        b = M.Leader([(0, 0), (-1, 1)], "12", True, 0.1)
        self.assertEqual(b.side(), -1)
        circle = [e for e in b.parts() if isinstance(e, M.Circle)][0]
        self.assertLess(circle.center[0], -1.0)                  # (to the left of the end)
        num = [e for e in b.parts() if isinstance(e, M.Text)][0]
        self.assertEqual((num.text, tuple(num.pos)), ("12", tuple(circle.center)))

    def test_saved_moved_and_grips(self):
        ld = M.Leader([(0, 0), (1, 1)], "A", True, 0.2, layer="DIMENSIONS")
        again = M.Entity.from_dict(ld.to_dict())
        self.assertEqual(again.to_dict(), ld.to_dict())
        moved = ld.moved(2, 3)
        self.assertEqual([tuple(q) for q in moved.points], [(2.0, 3.0), (3.0, 4.0)])
        self.assertEqual(moved.height, 0.2)
        self.assertEqual(tuple(ld.with_grip(1, (5, 5)).points[1]), (5.0, 5.0))


class LeaderCommandTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.snap_on = self.v.polar_on = self.v.ortho_on = self.v.osnap_on = False
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def newest(self):
        return max(self.s.entities.values(), key=lambda e: e.id)

    def test_note(self):
        self.v.run(C.LeaderCmd)
        type_in(self.v, "1,1", "2,2", "3,2")
        self.v.enter()
        type_in(self.v, "SEE NOTE 3")
        ld = self.newest()
        self.assertIsInstance(ld, M.Leader)
        self.assertEqual(([tuple(q) for q in ld.points], ld.text, ld.balloon),
                         ([(1.0, 1.0), (2.0, 2.0), (3.0, 2.0)], "SEE NOTE 3", False))
        h = self.p.settings.get("dim_height") * self.s.k()
        self.assertAlmostEqual(ld.height, h)
        self.p.undo()
        self.assertNotIn(ld.id, self.s.entities)

    def test_balloons_number_themselves(self):
        for i in range(2):
            self.v.run(C.LeaderCmd)
            type_in(self.v, "%d,1" % (i + 1), "%d,2" % (i + 1))
            self.v.enter()
            type_in(self.v, "B")
            self.v.enter()                                  # (Enter: the next number)
        nums = sorted(e.text for e in self.s.entities.values() if isinstance(e, M.Leader))
        self.assertEqual(nums, ["1", "2"])
        self.v.run(C.LeaderCmd)
        type_in(self.v, "5,1", "5,2")
        self.v.enter()
        type_in(self.v, "B", "17")
        self.assertEqual(self.newest().text, "17")
        self.assertEqual(C.next_balloon(self.p), 18)

    def test_sheet_scale_keeps_it_paper_sized(self):
        with self.p.edit("add") as ed:
            ld = ed.add(self.s, M.Leader([(1, 1), (2, 2)], "A", height=0.1))
        with self.p.edit("scale") as ed:
            ed.sheet_scale(self.s, 0.25, "1:4")
        self.assertAlmostEqual(self.s.entities[ld.id].height, 0.4)

    def test_aliases_and_menu(self):
        for alias in ("LEADER", "LE", "MLEADER", "MLD", "QLEADER"):
            self.assertIn(alias, [C.LeaderCmd.name] + C.COMMANDS["LEADER"][1])
        acts = {b.text().replace("&", "") for a in self.win.menuBar().actions() if a.menu()
                for b in a.menu().actions()}
        self.assertIn("Leader", acts)

    def test_double_click_edits(self):
        with self.p.edit("add") as ed:
            ld = ed.add(self.s, M.Leader([(1, 1), (2, 2)], "OLD", height=0.1))
        from kanzonascad import dialogs

        def run(dlg):
            from PySide6.QtWidgets import QPlainTextEdit, QRadioButton
            dlg.findChild(QPlainTextEdit).setPlainText("7\nignored")
            [r for r in dlg.findChildren(QRadioButton) if r.text().startswith("Balloon")][0] \
                .setChecked(True)
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", run):
            self.win.edit_text(ld)
        got = self.s.entities[ld.id]
        self.assertEqual((got.text, got.balloon), ("7", True))
        del dialogs


class LeaderImportTest(unittest.TestCase):
    def test_leader_and_multileader_from_dxf(self):
        import ezdxf
        from ezdxf.math import Vec2
        from ezdxf.render.mleader import ConnectionSide
        doc = ezdxf.new(setup=True)
        doc.header["$INSUNITS"] = 1
        ms = doc.modelspace()
        ms.add_leader([(10, 0), (11, 1), (12, 1)])
        b = ms.add_multileader_mtext()
        b.set_content("SEE NOTE 3")
        b.add_leader_line(ConnectionSide.left, [Vec2(0, 0), Vec2(2, 1)])
        b.build(Vec2(5, 5))
        path = os.path.join(tempfile.mkdtemp(), "l.dxf")
        doc.saveas(path)
        ents, rep = fileio.read_dxf(path)
        leaders = [e for e in ents if isinstance(e, M.Leader)]
        self.assertEqual(len(leaders), 2)
        plain = [e for e in leaders if not e.text][0]
        self.assertEqual([tuple(q) for q in plain.points], [(10.0, 0.0), (11.0, 1.0),
                                                            (12.0, 1.0)])
        note = [e for e in leaders if e.text][0]
        self.assertEqual(note.text, "SEE NOTE 3")
        self.assertEqual(tuple(note.points[0]), (0.0, 0.0))
        self.assertEqual(rep["skipped"], {})


if __name__ == "__main__":
    unittest.main()
