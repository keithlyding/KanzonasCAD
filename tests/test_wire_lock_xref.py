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

    def test_unticked_the_typed_number_still_stays(self):
        # (one wire takes the number of the sheet it starts on: unticked, the number typed
        # would go at once; it is locked instead, the long battery, seed 3152)
        other = self.num(self.s2, self.b)
        self.type_number(other, lock=False, answer="source")
        self.assertEqual(self.num(self.s1, self.a), other)
        self.assertEqual(self.num(self.s2, self.b), other)

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


class ArrowsOnTheLineTest(unittest.TestCase):
    """The owner, 0.17.5: "Destination cross reference arrows need to be connected and pointing
    to the line. Source cross references need to be connected to the line with the arrow
    pointing away from the line." Across and up and down, both ways; the text past the arrow's
    far end, over neither the arrow nor the wire."""

    def test_on_the_line_and_the_text_clear(self):
        win, v = window()
        try:
            p, s = v.project, v.sheet()
            lib = win.library
            ws = []
            with p.edit("w") as ed:
                for a, b in (((1.0, 8.0), (4.0, 8.0)), ((9.0, 8.0), (6.0, 8.0)),
                             ((12.0, 9.0), (12.0, 6.0)), ((15.0, 4.0), (15.0, 7.0))):
                    ws.append(ed.add(s, M.Wire([a, b])))
            from kanzonascad.geometry import dist, segment_hits_rect
            for i, source in ((0, True), (2, False)):
                # (open_end: the end each wire was drawn to, then the other)
                here = wirenums.open_end([(s, ws[i])], first=ws[i])
                there = wirenums.open_end([(s, ws[i + 1])], first=ws[i + 1])
                with p.edit("x") as ed:
                    wirenums.cross_reference(ed, p, here, there,
                                             lib.get("symbol", "Source arrow"),
                                             lib.get("symbol", "Destination arrow"), source)
            texts = xrefs.texts(p, s)
            for e in s.inserts():
                pin = e.pin_points()[0][1]
                w = [x for x in s.wires() if x.touches(pin)][0]
                end = w.points[0] if dist(w.points[0], pin) < 1e-9 else w.points[-1]
                self.assertLess(dist(end, pin), 1e-9)                   # (connected)
                other = w.points[-1] if end is w.points[0] else w.points[0]
                body = [q for x in e.world_entities() if isinstance(x, M.Polyline)
                        for q in x.points]
                tip = max(body, key=lambda q: dist(q, pin))              # (its far point)
                # all of it on the side away from the wire
                self.assertGreater(dist(tip, other), dist(pin, other), e.block)
                # a source's point is its far end; a destination's is on the pin
                ends = sorted(body, key=lambda q: dist(q, pin))
                if e.block == "Destination arrow":
                    self.assertLess(dist(ends[0], pin), 1e-9)               # (tip on the line)
                # the text: past the far end, over neither the arrow nor the wire
                t = min(texts, key=lambda t: dist(t.pos, tip))
                x0, y0, x1, y1 = t.bbox()
                for a, b in zip(w.points, w.points[1:]):
                    self.assertFalse(segment_hits_rect(a, b, (x0, y0, x1, y1)),
                                     (e.block, t.text, (x0, y0, x1, y1)))
                ex = e.bbox()
                self.assertFalse(x0 < ex[2] and x1 > ex[0] and y0 < ex[3] and y1 > ex[1],
                                 (e.block, t.text, (x0, y0, x1, y1), ex))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
