"""Adding and arranging a block's pins in its tab (the owner, 0.16.8: "When building/editing
schematic blocks, how do I add or delete connection points? What if I put the connection in
the wrong spot during initially placing?", then "Yes please" to an Add pin command and a Pins
list):

- Add pin: click, then the name (Enter takes the next number); a name already there is asked
  again; it works only in a block's tab.
- Pins...: rename, move (x, y from the base point), reorder and delete, one undoable step;
  Save block keeps that order, and the copies' wires follow the renamed pins.
- next_pin_name, and the Pins dialog's own rows (drag order, a place that isn't a number).
- Edit text: "Keep the text where it is" starts unticked."""
import tempfile
import unittest

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QMessageBox

from tests.util import APP, window, type_in, by_base_point

from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import dialogs as D
from kanzonascad import model as M


def coil(name="Pin coil"):
    return M.BlockDef(name, "symbol", [M.Circle((0, 0), 0.125), M.Line((-0.25, 0), (-0.125, 0)),
                                       M.Line((0.125, 0), (0.25, 0))],
                      [{"name": "A1", "pos": (-0.25, 0)}, {"name": "A2", "pos": (0.25, 0)}],
                      (0, 0.2), 0.1, "Mine", "A coil", "parent", "", "CR")


class NextNameTest(unittest.TestCase):
    def test_names_offered(self):
        self.assertEqual(BE.next_pin_name(["13", "14"]), "15")
        self.assertEqual(BE.next_pin_name(["A1", "A2"]), "A3")
        self.assertEqual(BE.next_pin_name(["L1", "T3", "L2"]), "T4")
        self.assertEqual(BE.next_pin_name([]), "1")
        self.assertEqual(BE.next_pin_name(["+", "-"]), "3")


class BlockPinsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.win.library.folder = tempfile.mkdtemp()
        self.lib = self.win.library
        self.lib.save_block(coil())
        self._q = QMessageBox.question
        self._w = QMessageBox.warning
        self.warned = []
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
        QMessageBox.warning = staticmethod(lambda *a, **k: self.warned.append(a[2]))

    def tearDown(self):
        QMessageBox.question = self._q
        QMessageBox.warning = self._w
        self.win.__dict__.pop("ask_pins", None)
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.library_dialog.hide()
        self.win.close()

    def open(self):
        d = self.win.edit_block("symbol", "Pin coil")
        return d, d.block_session, d.view.sheet()

    def markers(self, s):
        return {e.text: e for e in s.entities.values()
                if isinstance(e, M.Text) and e.layer == BE.LAYER_PINS}

    def test_add_pin_clicks_and_names(self):
        d, sess, s = self.open()
        ox, oy = sess.offset
        self.assertTrue(self.win.acts["add_pin"].isVisible())
        v = d.view
        v.run(C.AddPinCmd)
        type_in(v, "%r,%r" % (ox, oy - 0.25))
        self.assertEqual(v._prompt[0], "Pin name <A3>")
        self.assertTrue(v._prompt[2])                   # (typed as it is: spaces and all)
        v.enter()                                       # (the name offered)
        type_in(v, "%r,%r" % (ox, oy + 0.25))
        self.assertTrue(v.input_text("A1"))             # (taken: asked again)
        self.assertIsNotNone(v.cmd)
        self.assertTrue(v.input_text("X9"))
        v.escape()
        m = self.markers(s)
        self.assertEqual(sorted(m), ["A1", "A2", "A3", "X9"])
        self.assertEqual(m["A3"].pos, (ox, oy - 0.25))
        self.assertEqual(m["A3"].height, BE.PIN_HEIGHT * sess.scale)
        self.assertTrue(self.win.save_block())
        got = self.lib.get("symbol", "Pin coil").pins
        self.assertEqual([(q["name"], q["pos"]) for q in got],
                         [("A1", (-0.25, 0.0)), ("A2", (0.25, 0.0)), ("A3", (0.0, -0.25)),
                          ("X9", (0.0, 0.25))])
        # undone one pin at a time
        d.project.undo()
        self.assertNotIn("X9", self.markers(s))
        self.assertIn("A3", self.markers(s))

    def test_add_pin_outside_a_block_says_so(self):
        said = []
        self.v.messaged.connect(said.append)
        self.v.run(C.AddPinCmd)
        self.assertIsNone(self.v.cmd)
        self.assertTrue(any("block's tab" in t for t in said), said)
        self.assertFalse(self.win.acts["add_pin"].isVisible())
        self.assertFalse(self.win.pins_dialog())

    def test_pins_renamed_moved_reordered_deleted(self):
        # a copy in the drawing with a wire on each pin
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Pin coil"), {"TAG": "CR1"})
        by_base_point(self.v)
        type_in(self.v, "5,5")
        ins = max(self.v.sheet().inserts(), key=lambda e: e.id)
        main = self.win.doc()
        d, sess, s = self.open()
        m = self.markers(s)
        rows_seen = []

        def ask(rows):
            rows_seen.append(rows)
            a1, a2 = rows
            self.assertEqual((a1[1], a1[2], a1[3]), ("A1", -0.25, 0.0))
            # A2 first, renamed 14 and moved down; A1 renamed 13
            return [(a2[0], "14", 0.25, -0.125), (a1[0], "13", -0.25, 0.0)]
        self.win.ask_pins = ask
        steps = len(d.project.undo_stack)
        self.assertTrue(self.win.pins_dialog())
        self.assertEqual(len(d.project.undo_stack), steps + 1)
        now = self.markers(s)
        self.assertEqual(sorted(now), ["13", "14"])
        ox, oy = sess.offset
        self.assertEqual(now["14"].pos, (ox + 0.25, oy - 0.125))
        self.assertEqual(now["13"].id, m["A1"].id)
        self.assertEqual(now["13"].align, "right")
        self.assertEqual([e.text for e, _p in BE.pin_markers(d.project, sess)], ["14", "13"])
        # undone as one: names, place and order back
        d.project.undo()
        self.assertEqual(sorted(self.markers(s)), ["A1", "A2"])
        self.assertEqual([e.text for e, _p in BE.pin_markers(d.project, sess)], ["A1", "A2"])
        d.project.redo()
        self.assertTrue(self.win.save_block(close=False))
        got = self.lib.get("symbol", "Pin coil").pins
        self.assertEqual([(q["name"], q["pos"]) for q in got],
                         [("14", (0.25, -0.125)), ("13", (-0.25, 0.0))])
        # the copy in the drawing took the new pins, by their new names
        self.assertEqual(sorted(n for n, _q in main.project.sheets[0].entities[ins.id]
                                .pin_points()), ["13", "14"])
        # deleted: one row left out
        self.win.ask_pins = lambda rows: rows[:1]
        self.assertTrue(self.win.pins_dialog())
        self.assertEqual(sorted(self.markers(s)), ["14"])

    def test_two_pins_with_one_name_are_refused(self):
        d, sess, s = self.open()
        answers = []

        def ask(rows):
            answers.append(1)
            if len(answers) == 1:
                return [(r[0], "A1", r[2], r[3]) for r in rows]
            return None
        self.win.ask_pins = ask
        self.assertFalse(self.win.pins_dialog())
        self.assertIn("same name", self.warned[-1])
        self.assertEqual(len(answers), 2)              # (asked again, then cancelled)
        self.assertEqual(sorted(self.markers(s)), ["A1", "A2"])

    def test_the_dialog_rows(self):
        found = []
        dlg = D.PinsDialog(None, [(7, "A1", -0.25, 0.0), (8, "A2", 0.25, 0.0),
                                  (9, "A3", 0.0, -0.25)], found.append)
        t = dlg.tree
        t.setCurrentItem(t.topLevelItem(2))
        dlg.move(-1)
        self.assertEqual([r[0] for r in dlg.rows()], [7, 9, 8])
        dlg.move(-1)
        dlg.move(-1)                                    # (already first: stays)
        self.assertEqual([r[0] for r in dlg.rows()], [9, 7, 8])
        dlg.find_it()
        self.assertEqual(found, [9])
        t.topLevelItem(1).setText(1, "-0.5")
        t.topLevelItem(1).setText(0, " B1 ")
        self.assertEqual(dlg.rows()[1], (7, "B1", -0.5, 0.0, ""))
        dlg.delete()
        self.assertEqual([r[0] for r in dlg.rows()], [7, 8])
        t.topLevelItem(0).setText(2, "up")
        with self.assertRaises(ValueError):
            dlg.rows()
        # a row can't be dropped under another (no drop flag on rows)
        self.assertFalse(t.topLevelItem(0).flags() & Qt.ItemIsDropEnabled)
        dlg.deleteLater()


class EditTextKeepTest(unittest.TestCase):
    def test_keep_starts_unticked(self):
        seen = []
        real = QDialog.exec

        def look(dlg):
            seen.extend(c.isChecked() for c in dlg.findChildren(QCheckBox))
            return QDialog.Rejected
        QDialog.exec = look
        try:
            self.assertIsNone(D.edit_text_dialog(None, M.Text((0, 0), "X", 0.1)))
        finally:
            QDialog.exec = real
        self.assertEqual(seen, [False])


if __name__ == "__main__":
    unittest.main()
