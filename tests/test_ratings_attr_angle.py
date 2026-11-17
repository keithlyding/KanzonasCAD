"""The owner, 0.17.5: "Electrical symbols need to have voltage, amps, hp, etc (as applicable)
for attributes. I'm working on a motor right now and need those three things. Also, I need to
be able to hide/unhide attributes. And I need to be able to rotate attributes" (asked: fields
of their own beside Rating, each on its own line, an angle in the symbol's window).

- A motor has HP, VOLTS and FLA; a plain number shows with its unit (5HP, 460V, 7.6A FLA),
  each on a line of its own under the rating, an empty one leaving no gap.
- Each can be hidden (as any attribute) and turned: the angle on the drawing, turning with the
  symbol afterward; saved; the tag too.
- The bill of materials tells a 5HP motor from a 10HP one."""
import os
import tempfile
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M


class RatingsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.s, self.p = self.v.sheet(), self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def motor(self, name="Motor 3-phase", at=(5.0, 5.0)):
        self.v.run(C.InsertCmd, self.win.library.get("symbol", name), {})
        type_in(self.v, "%r,%r" % at)
        while self.v.cmd is not None:
            self.v.cmd.enter()
        return self.s.inserts()[-1]

    def test_a_motor_has_hp_volts_and_fla(self):
        e = self.motor()
        names = e.shown_names()
        for n in ("HP", "VOLTS", "FLA", "RATING"):
            self.assertIn(n, names)
        e = e.copy(attrs=dict(e.attrs, HP="5", VOLTS="460", FLA="7.6"))
        t = self.texts_of(e)
        self.assertEqual(set(t) & {"5HP", "460V", "7.6A FLA"}, {"5HP", "460V", "7.6A FLA"})
        # one under the other, the first where the rating goes when there is none
        ys = [t["5HP"].pos[1], t["460V"].pos[1], t["7.6A FLA"].pos[1]]
        self.assertTrue(ys[0] > ys[1] > ys[2], ys)
        with_rating = e.copy(attrs=dict(e.attrs, RATING="TEFC"))
        self.assertLess(self.texts_of(with_rating)["5HP"].pos[1], ys[0])
        # typed with letters: as typed
        self.assertIn("1/2 HP", self.texts_of(e.copy(attrs=dict(e.attrs, HP="1/2 HP"))))
        self.assertIn("1/2HP", self.texts_of(e.copy(attrs=dict(e.attrs, HP="1/2"))))

    def texts_of(self, e):
        return {t.text: t for t in e.world_entities() if isinstance(t, M.Text)}

    def test_other_symbols_have_theirs(self):
        lib = self.win.library
        want = {"Circuit breaker 3-pole": ("AMPS", "VOLTS"), "Fuse": ("VOLTS",),
                "Variable frequency drive": ("HP", "VOLTS", "AMPS"),
                "Control transformer": ("VA", "PRI", "SEC"), "Motor": ("HP", "VOLTS", "FLA")}
        for name, fields in want.items():
            got = [a["attr"] for a in lib.get("symbol", name).attr_texts]
            for f in fields:
                self.assertIn(f, got, name)

    def test_hidden_and_turned(self):
        e = self.motor()
        e = e.copy(attrs=dict(e.attrs, HP="5", VOLTS="460", FLA="7.6"), hidden=["VOLTS"])
        t = self.texts_of(e)
        self.assertNotIn("460V", t)
        self.assertAlmostEqual(t["5HP"].pos[1] - t["7.6A FLA"].pos[1], 0.12, 9)   # (no gap)
        turned = e.with_attr_angle("HP", 90.0).with_attr_angle("TAG", 45.0)
        self.assertEqual(self.texts_of(turned)["5HP"].angle, 90.0)
        self.assertEqual(turned.tag_text().angle, 45.0)
        self.assertEqual(turned.attr_angle("HP"), 90.0)
        # the symbol turned afterward: its attribute turns with it
        r = turned.rotated(turned.pos, 90.0)
        self.assertEqual(self.texts_of(r)["5HP"].angle, 180.0)
        self.assertEqual(r.tag_text().angle, 135.0)
        # flipped: still drawn at the angle asked
        f = e.copy(mirror=True).with_attr_angle("HP", 30.0)
        self.assertAlmostEqual(self.texts_of(f)["5HP"].angle, 30.0, 9)
        # back to the block's own angle: nothing kept
        self.assertEqual(turned.with_attr_angle("HP", 0.0).attr_rot, {"TAG": 45.0})
        # saved and opened
        with self.p.edit("x") as ed:
            ed.change(self.s, turned)
        d = tempfile.mkdtemp()
        path = os.path.join(d, "t.kzcad")
        self.p.save(path)
        q = [x for x in M.Project.load(path).sheets[0].inserts() if x.id == e.id][0]
        self.assertEqual(q.attr_rot, turned.attr_rot)

    def test_through_the_attributes_window(self):
        from PySide6.QtWidgets import QDialog, QDoubleSpinBox, QLineEdit
        from kanzonascad import library_panel
        e = self.motor()

        def answer(dlg):
            dlg.findChild(QLineEdit, "attr_HP").setText("5")
            dlg.findChild(QLineEdit, "attr_VOLTS").setText("460")
            dlg.findChild(QDoubleSpinBox, "angle_HP").setValue(90.0)
            return QDialog.Accepted
        real = library_panel.QDialog.exec
        library_panel.QDialog.exec = answer
        try:
            self.win.edit_attributes(self.s.entities[e.id])
        finally:
            library_panel.QDialog.exec = real
        got = self.s.entities[e.id]
        self.assertEqual((got.attrs["HP"], got.attrs["VOLTS"]), ("5", "460"))
        self.assertEqual(self.texts_of(got)["5HP"].angle, 90.0)
        self.p.undo()
        self.assertNotIn("HP", self.s.entities[e.id].attrs)

    def test_bill_of_materials(self):
        from kanzonascad import bom
        a, b = self.motor(), self.motor(at=(9.0, 5.0))
        with self.p.edit("x") as ed:
            ed.change(self.s, a.copy(attrs=dict(a.attrs, HP="5", TAG="MTR1")))
            ed.change(self.s, b.copy(attrs=dict(b.attrs, HP="10", TAG="MTR2")))
        descs = " | ".join(str(r) for r in bom.rows(self.p))
        self.assertIn("5HP", descs)
        self.assertIn("10HP", descs)


if __name__ == "__main__":
    unittest.main()
