"""Add attribute, in a block's tab (the owner, Nov 2026, of the ratings a VFD carries, RATING,
HP, VOLTS, AMPS: "there is no way to add additional ones when creating or editing a block in
KanzonasCAD"):

- its name typed, then a click: a marker on BLOCK ATTRIBUTES, saved as one of the block's
  attributes, which every copy then has (a value of its own, shown where the block says);
- a name taken, with a space, or TAG: asked again;
- S puts it under the block's ratings, in their stack: it closes up with them on a copy where
  one above it is empty;
- it works only in a block's tab; undone one attribute at a time."""
import os
import tempfile
import unittest

from PySide6.QtWidgets import QMessageBox

from tests.util import APP, window, type_in

from kanzonascad import block_editor as BE
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad.symbols_jic import RATING_STEP


def coil(name="Rated coil", ratings=True):
    attrs = [{"attr": n, "pos": (0.0, -0.3 - RATING_STEP * i), "height": 0.08, "stack": True}
             for i, n in enumerate(("RATING", "HP"))] if ratings else []
    return M.BlockDef(name, "symbol", [M.Circle((0, 0), 0.125), M.Line((-0.25, 0), (-0.125, 0)),
                                       M.Line((0.125, 0), (0.25, 0))],
                      [{"name": "A1", "pos": (-0.25, 0)}, {"name": "A2", "pos": (0.25, 0)}],
                      (0, 0.2), 0.1, "Mine", "A coil", "parent", "", "CR", attr_texts=attrs)


class AddAttributeTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        self.v.polar_on = self.v.ortho_on = False
        self.win.library.folder = tempfile.mkdtemp()
        self.lib = self.win.library
        self.lib.save_block(coil())
        self.lib.save_block(coil("Plain coil", ratings=False))
        self._q = QMessageBox.question
        QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

    def tearDown(self):
        QMessageBox.question = self._q
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.library_dialog.hide()
        self.win.close()
        self.assertTrue(APP)

    def open(self, name="Rated coil"):
        d = self.win.edit_block("symbol", name)
        return d, d.block_session, d.view.sheet(), d.view

    def markers(self, s):
        return {e.text: e for e in s.entities.values()
                if isinstance(e, M.Text) and e.layer == BE.LAYER_ATTRS}

    def test_named_clicked_saved_and_on_every_copy(self):
        d, sess, s, v = self.open()
        ox, oy = sess.offset
        self.assertTrue(self.win.acts["add_attr"].isVisible())
        v.run(C.AddAttrCmd)
        said = []
        v.messaged.connect(said.append)
        self.assertTrue(v._prompt[2])                   # (the name typed as it is)
        for bad in ("HP", "full load", "tag"):           # (taken, a space, the tag's own)
            self.assertTrue(v.input_text(bad))
            self.assertIsNotNone(v.cmd)
            self.assertEqual(v.cmd.step, "name", bad)
        self.assertEqual(len(said), 3, said)
        self.assertTrue(v.input_text("kw"))             # (names are upper case, as AutoCAD's)
        type_in(v, "%r,%r" % (ox + 0.5, oy + 0.25))
        self.assertEqual(v.cmd.step, "name")            # (on to the next)
        v.input_text("")                                # (Enter ends)
        self.assertIsNone(v.cmd)
        m = self.markers(s)
        self.assertEqual(sorted(m), ["HP", "KW", "RATING"])
        self.assertEqual(m["KW"].pos, (ox + 0.5, oy + 0.25))
        self.assertTrue(self.win.save_block())
        got = {a["attr"]: a for a in self.lib.get("symbol", "Rated coil").attr_texts}
        self.assertEqual(got["KW"]["pos"], (0.5, 0.25))
        self.assertFalse(got["KW"].get("stack"))       # (clicked off the stack: its own spot)
        # a copy: a value of its own, shown where the block says; empty, nothing shown
        self.win.tabs.setCurrentIndex(0)
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Rated coil"), {"TAG": "CR1"})
        type_in(self.v, "4,4")
        ins = next(e for e in self.v.sheet().inserts() if e.block == "Rated coil")
        self.assertNotIn("KW", [a[0] for a in ins.attr_spots()])
        with self.v.project.edit("kw") as ed:
            ed.change(self.v.sheet(), ins.copy(attrs=dict(ins.attrs, KW="7.5")))
        ins = next(e for e in self.v.sheet().inserts() if e.block == "Rated coil")
        spots = {a[0]: a[1] for a in ins.attr_spots()}
        self.assertAlmostEqual(spots["KW"][0], ins.to_world((0.5, 0.25))[0])
        self.assertAlmostEqual(spots["KW"][1], ins.to_world((0.5, 0.25))[1])
        # (and out to AutoCAD as an attribute of its own)
        import ezdxf
        from kanzonascad import fileio
        path = os.path.join(tempfile.mkdtemp(), "x.dxf")
        fileio.export_dxf(self.v.project, self.v.sheet(), path, include_frame=False)
        blk = ezdxf.readfile(path).blocks.get("Rated coil")
        self.assertIn("KW", {a.dxf.tag for a in blk.query("ATTDEF")})

    def test_stacked_under_the_ratings(self):
        d, sess, s, v = self.open()
        ox, oy = sess.offset
        v.run(C.AddAttrCmd)
        v.input_text("FLA")
        self.assertIn("Stack", v._prompt[0])
        self.assertTrue(v.input_text("s"))
        v.input_text("")
        m = self.markers(s)
        self.assertAlmostEqual(m["FLA"].pos[0], ox)
        self.assertAlmostEqual(m["FLA"].pos[1], oy - 0.3 - 2 * RATING_STEP)
        self.assertTrue(self.win.save_block())
        defn = self.lib.get("symbol", "Rated coil")
        self.assertEqual([a["attr"] for a in defn.attr_texts if a.get("stack")],
                         ["RATING", "HP", "FLA"])
        # (on a copy with only FLA: it takes the stack's first spot, no gap above it)
        ins = M.Insert(defn.name, (3.0, 3.0), 0.0, 1.0, False, {"TAG": "CR1", "FLA": "4.2"},
                       defn)
        (name, at, _ang, _a), = ins.attr_spots()
        self.assertEqual(name, "FLA")
        self.assertAlmostEqual(at[1], 3.0 - 0.3)

    def test_stack_needs_ratings(self):
        d, sess, s, v = self.open("Plain coil")
        v.run(C.AddAttrCmd)
        v.input_text("KW")
        self.assertNotIn("Stack", v._prompt[0])
        said = []
        v.messaged.connect(said.append)
        self.assertTrue(v.input_text("S"))
        self.assertTrue(any("no ratings" in t for t in said), said)
        self.assertEqual(v.cmd.step, "pos")             # (still asks where)

    def test_undone_one_at_a_time(self):
        d, sess, s, v = self.open("Plain coil")
        ox, oy = sess.offset
        v.run(C.AddAttrCmd)
        for k, n in enumerate(("HP", "VOLTS")):
            v.input_text(n)
            type_in(v, "%r,%r" % (ox, oy - 0.3 - 0.12 * k))
        v.escape()
        self.assertEqual(sorted(self.markers(s)), ["HP", "VOLTS"])
        d.project.undo()
        self.assertEqual(sorted(self.markers(s)), ["HP"])

    def test_only_in_a_block_tab(self):
        said = []
        self.v.messaged.connect(said.append)
        self.v.run(C.AddAttrCmd)
        self.assertIsNone(self.v.cmd)
        self.assertTrue(any("block's tab" in t for t in said), said)
        self.assertFalse(self.win.acts["add_attr"].isVisible())


if __name__ == "__main__":
    unittest.main()
