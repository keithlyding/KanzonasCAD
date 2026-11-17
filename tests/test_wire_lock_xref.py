"""The owner, 0.17.5: "when updating a wire number or tag number, should there be a checkbox to
check locked or unlocked?" (yes, as tags have), and "if I change a wire number to one that's
already used, it should ask me if it's a cross reference and whether it's a source or
destination".

- The Wire number window has "Lock this number", ticked by itself when a number is typed;
  unticked, the number is kept until numbering changes it.
- A number another wire has asks: Source or Destination puts off-sheet connectors of a new name
  on the open ends of both (pointing out where the wire leaves, in where it arrives), so they
  are one wire with that number and each shows the other's place; "just the same number" sets
  it as typed; Cancel changes nothing."""
import unittest

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import wirenums
from kanzonascad import xrefs


class WireLockXrefTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p = v.project
        self.s1 = v.sheet()
        self.win.add_sheet()
        self.s2 = self.p.sheets[1]
        with self.p.edit("wires") as ed:
            self.a = ed.add(self.s1, M.Wire([(1.0, 5.0), (6.0, 5.0)]))
            self.b = ed.add(self.s2, M.Wire([(2.0, 3.0), (8.0, 3.0)]))
        self.v.sheet_id = self.s1.id

    def tearDown(self):
        for k in ("ask_wire_number", "ask_cross_reference"):
            self.win.__dict__.pop(k, None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def num(self, s, w):
        return s.entities[w.id].num

    def type_number(self, num, lock=True, answer=None):
        self.win.ask_wire_number = lambda n, tap_of=None, own=False, locked=False: (num, own,
                                                                                    lock)
        asked = []
        self.win.ask_cross_reference = lambda n, where: asked.append((n, where)) or answer
        self.win.edit_wire_number(self.s1.entities[self.a.id])
        return asked

    def test_lock_box(self):
        self.type_number("1050", lock=False)
        w = self.s1.entities[self.a.id]
        self.assertEqual((w.num, w.num_lock), ("1050", False))
        self.type_number("1050", lock=True)
        self.assertTrue(self.s1.entities[self.a.id].num_lock)

    def test_the_window_ticks_lock_when_typed(self):
        from PySide6.QtWidgets import QDialog, QCheckBox, QLineEdit
        from kanzonascad import dialogs
        got = {}

        def answer(dlg):
            e = dlg.findChild(QLineEdit)
            e.setText("1077")
            e.textEdited.emit("1077")
            got["ticked"] = dlg.findChild(QCheckBox, "num_lock").isChecked()
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            out = dialogs.wire_number_dialog(self.win, "1001")
        finally:
            dialogs.QDialog.exec = real
        self.assertTrue(got["ticked"])
        self.assertEqual(out, ("1077", False, True))

    def test_source_puts_connectors_on_both(self):
        other = self.num(self.s2, self.b)
        asked = self.type_number(other, answer="source")
        self.assertEqual(asked[0][0], other)
        c1 = [e for e in self.s1.inserts() if e.defn.wiring == "link"]
        c2 = [e for e in self.s2.inserts() if e.defn.wiring == "link"]
        self.assertEqual([e.block for e in c1], ["Source arrow"])           # (leaves here)
        self.assertEqual([e.block for e in c2], ["Destination arrow"])      # (arrives there)
        self.assertEqual(c1[0].attrs["TAG"], c2[0].attrs["TAG"])
        # on the open ends, pointing along the wire
        self.assertIn(c1[0].pin_points()[0][1], [(6.0, 5.0), (1.0, 5.0)])
        self.assertIn(c2[0].pin_points()[0][1], [(8.0, 3.0), (2.0, 3.0)])
        # one wire now: the same number both sides, locked
        self.assertEqual(self.num(self.s1, self.a), other)
        self.assertEqual(self.num(self.s2, self.b), other)
        self.assertTrue(self.s1.entities[self.a.id].num_lock)
        # each shows the other's place
        texts = [t.text for t in xrefs.texts(self.p, self.s1)]
        self.assertTrue(any(t.startswith(str(self.p.sheet_number(self.s2))) for t in texts),
                        texts)
        # one step
        self.p.undo()
        self.assertEqual([e for e in self.s1.inserts() if e.defn.wiring == "link"], [])

    def test_destination_points_in_here(self):
        other = self.num(self.s2, self.b)
        self.type_number(other, answer="destination")
        c1 = [e.block for e in self.s1.inserts() if e.defn.wiring == "link"]
        c2 = [e.block for e in self.s2.inserts() if e.defn.wiring == "link"]
        self.assertEqual((c1, c2), (["Destination arrow"], ["Source arrow"]))

    def test_same_number_and_cancel(self):
        other = self.num(self.s2, self.b)
        before = self.num(self.s1, self.a)
        self.type_number(other, answer=None)                    # (cancelled)
        self.assertEqual(self.num(self.s1, self.a), before)
        self.type_number(other, lock=False, answer="same")
        self.assertEqual(self.num(self.s1, self.a), other)
        # (locked though unticked: numbering would give an unlocked duplicate a free number)
        self.assertTrue(self.s1.entities[self.a.id].num_lock)
        self.assertEqual([e for e in self.s1.inserts() if e.defn.wiring == "link"], [])

    def test_no_open_end_says_so(self):
        with self.p.edit("x") as ed:
            # (a loop: every end on another wire)
            ed.add(self.s1, M.Wire([(6.0, 5.0), (6.0, 7.0), (1.0, 7.0), (1.0, 5.0)]))
        from PySide6.QtWidgets import QMessageBox
        said = []
        real = QMessageBox.information
        QMessageBox.information = staticmethod(lambda *a: said.append(a[2]))
        try:
            self.type_number(self.num(self.s2, self.b), answer="source")
        finally:
            QMessageBox.information = real
        self.assertTrue(said and "open end" in said[0], said)
        self.assertEqual([e for e in self.s1.inserts() if e.defn.wiring == "link"], [])


if __name__ == "__main__":
    unittest.main()
