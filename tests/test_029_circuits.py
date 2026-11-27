"""0.29: saved circuits (Library > Save circuit..., Insert circuit...; circuits.py): kept in the
library, placed whole in one step with new tags of the sheet, contacts relinked to their own
devices' new copies, wires numbered as the sheet's own (locked numbers kept), connectors
renamed in pairs; turned and scaled as placed; renamed and deleted in the browser."""

import json
import os
import tempfile
import unittest

from tests.util import window, type_in

from kanzonascad import circuits as CI
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.library import Library


class CircuitsTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library = Library(tempfile.mkdtemp())

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def rung(self, y=5.0, locked=None):
        """A rung on the sheet: a wire, a contact of a coil, the coil, a wire to the right."""
        v, lib = self.v, self.lib
        v.run(C.WireCmd)
        type_in(v, "1,%g" % y, "10,%g" % y)
        if v.cmd is not None:
            v.cmd.enter()
        v.run(C.InsertCmd, lib.get("symbol", "Relay coil"), {})
        type_in(v, "8,%g" % y)
        v.run(C.InsertCmd, lib.get("symbol", "Contact NO"), {})
        type_in(v, "3,%g" % y)
        coil = [e for e in self.s.inserts() if e.block == "Relay coil"][-1]
        type_in(v, coil.attrs["TAG"])
        if locked:
            w = [w for w in self.s.wires() if w.touches((1.0, y))][0]
            with self.p.edit("lock") as ed:
                ed.change(self.s, w.copy(num=locked, num_lock=True))
        return set(self.s.entities)

    def save(self, ids, name="Rung", base=None):
        self.v.set_selection(ids)
        self.win.ask_circuit_details = lambda name_="": (name, "Control", "a rung")
        try:
            self.v.run(C.SaveCircuitCmd)
            if base is None:
                self.v.cmd.enter()
            else:
                type_in(self.v, "%g,%g" % base)
        finally:
            self.win.__dict__.pop("ask_circuit_details", None)
        self.assertIsNone(self.v.cmd)
        return self.lib.circuits()[0][name]

    def insert(self, c, at, *typed):
        self.win.ask_circuit = lambda: c
        try:
            self.win.insert_circuit()
        finally:
            self.win.__dict__.pop("ask_circuit", None)
        self.assertIsInstance(self.v.cmd, C.InsertCircuitCmd)
        type_in(self.v, *(typed + ("%g,%g" % at,)))
        self.assertIsNone(self.v.cmd)

    def test_saved_with_its_blocks_layers_and_base(self):
        ids = self.rung()
        c = self.save(ids)
        self.assertEqual((c.category, c.description), ("Control", "a rung"))
        self.assertEqual(c.counts(), (1, 3, 1))
        self.assertEqual({b["name"] for b in c.blocks}, {"Relay coil", "Contact NO"})
        self.assertIn("WIRES", {d["name"] for d in c.layers})
        # (Enter: its base point the lower left corner of what was selected)
        x0, y0, _x1, _y1 = c.extents()
        self.assertAlmostEqual(x0, 0.0)
        self.assertAlmostEqual(y0, 0.0)
        path = os.path.join(self.lib.folder, "circuits", "Rung.kzcircuit")
        with open(path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["format"], CI.FORMAT)

    def test_placed_retagged_relinked_renumbered_one_step(self):
        ids = self.rung(locked="L1")
        c = self.save(ids, base=(1.0, 5.0))
        with self.p.edit("page 2") as ed:
            s2 = ed.add_sheet(self.p.make_sheet("Two"))
        self.v.show_sheet(s2.id)
        self.s = self.v.sheet()
        # (a device of the page already taking CR201)
        with self.p.edit("CR201") as ed:
            ed.add(self.s, M.Insert("Relay coil", (15, 1), defn=self.p.blocks["Relay coil"],
                                    attrs={"TAG": "CR201", "DEV": "other"}))
        n_undo = len(self.p.undo_stack)
        before = dict(self.s.entities)
        self.insert(c, (1.0, 6.0))
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)        # (one step)
        self.insert(c, (1.0, 3.0))
        coils = [e for e in self.s.inserts() if e.block == "Relay coil" and e.id not in before]
        contacts = [e for e in self.s.inserts() if e.block == "Contact NO"]
        self.assertEqual(sorted(e.attrs["TAG"] for e in coils), ["CR202", "CR203"])
        old_dev = [e for e in self.p.sheets[0].inserts() if e.block == "Relay coil"][0]
        devs = {e.attrs["DEV"] for e in coils}
        self.assertEqual(len(devs), 2)
        self.assertNotIn(old_dev.attrs["DEV"], devs)
        for k in contacts:
            coil = [e for e in coils if e.attrs["DEV"] == k.attrs["PARENT"]]
            self.assertEqual(len(coil), 1, k.attrs)
            self.assertEqual(k.attrs["TAG"], coil[0].attrs["TAG"])
            # (in its own rung: the coil 5" to its right)
            self.assertAlmostEqual(coil[0].pos[1], k.pos[1])
        # each coil lists its contact, the contact its coil (cross-references work)
        texts = [t[2] for t in xrefs.shown(self.p, self.s)]
        for e in coils + contacts:
            zone = self.p.zone_text(self.s, *e.pos)
            self.assertTrue(any(zone in t for t in texts), (zone, texts))
        nums = {}
        for w in self.s.wires():
            nums.setdefault(w.num, []).append(w)
        self.assertEqual(len(nums["L1"]), 2)                         # (locked: kept)
        self.assertTrue(all(w.num_lock for w in nums["L1"]))
        others = [n for n in nums if n != "L1"]
        self.assertEqual(len(others), 4)                            # (each its own group)
        self.assertTrue(all(n.startswith("2") and len(n) == 4 for n in others), others)
        self.p.undo()
        self.p.undo()
        self.assertEqual(set(self.s.entities), set(before))

    def test_wires_numbered_in_the_sheets_order(self):
        # (its numbers aren't carried along: turned end for end where the rung was, the wire
        # now on the left takes the page's first number, as one drawn there would)
        ids = self.rung()
        c = self.save(ids, base=(1.0, 5.0))
        left = [w for w in c.objects() if isinstance(w, M.Wire)]
        self.assertEqual(sorted(w.num for w in left), ["1001", "1002", "1003"])
        with self.p.edit("Erase") as ed:
            for i in ids:
                ed.remove(self.s, i)
        self.insert(c, (10.0, 5.0), "R", "R")
        got = sorted(self.s.wires(), key=lambda w: min(q[0] for q in w.points))
        self.assertEqual([w.num for w in got], ["1001", "1002", "1003"])

    def test_tags_and_labels_at_the_projects_heights(self):
        # (saved when the project's heights were others: placed at today's, as Insert would;
        # the battery, seed 29: a footprint's label left at the old height)
        fp = self.lib.get("footprint", "Contactor 9-18 A")
        with self.p.edit("fp") as ed:
            d = M.ensure_block(ed, self.p, fp)
            f = ed.add(self.s, M.Insert(d.name, (20, 2), defn=d, attrs={"TAG": "X1"},
                                        tag_h=0.08, label="tag", label_k=1.0))
        ids = self.rung() | {f.id}
        c = self.save(ids)
        with self.p.edit("heights") as ed:
            ed.project_settings({"fp_label_height": 0.06, "tag_height": 0.14})
        before = set(self.s.entities)
        self.insert(c, (2.0, 1.0))
        new = [self.s.entities[i] for i in set(self.s.entities) - before]
        got = [e for e in new if isinstance(e, M.Insert) and e.defn.kind == "footprint"]
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0].tag_h, 0.06)
        coil = [e for e in new if getattr(e, "block", "") == "Relay coil"][0]
        self.assertAlmostEqual(coil.tag_h, 0.14)

    def test_contact_without_its_device_placed_unlinked(self):
        self.rung()
        k = [e for e in self.s.inserts() if e.block == "Contact NO"][0]
        c = self.save({k.id}, "Contact")
        self.insert(c, (4.0, 2.0))
        new = [e for e in self.s.inserts() if e.block == "Contact NO" and e.id != k.id]
        self.assertEqual(len(new), 1)
        self.assertNotIn("PARENT", new[0].attrs)
        self.assertFalse(new[0].attrs.get("TAG"))
        self.assertEqual(s_parent(self.s, k), k.attrs["PARENT"])

    def test_turned_and_scaled(self):
        ids = self.rung()
        c = self.save(ids, base=(1.0, 5.0))
        self.insert(c, (20.0, 2.0), "R", "S", "2")
        made = set(self.s.entities) - ids
        coil = [self.s.entities[i] for i in made if getattr(self.s.entities[i], "block", "") ==
                "Relay coil"][0]
        self.assertEqual((coil.angle, coil.scale), (90.0, 2.0))
        # the coil was 7" right of the base point (8 - 1): turned and doubled, 14" up
        self.assertAlmostEqual(coil.pos[0], 20.0)
        self.assertAlmostEqual(coil.pos[1] - 2.0, 2 * 7.25)

    def test_connectors_renamed_in_pairs(self):
        lib = self.lib
        with self.p.edit("arrows") as ed:
            a = M.ensure_block(ed, self.p, lib.get("symbol", "Source arrow"))
            b = M.ensure_block(ed, self.p, lib.get("symbol", "Destination arrow"))
            ed.add(self.s, M.Insert(a.name, (2, 2), defn=a, attrs={"TAG": "A"}))
            ed.add(self.s, M.Insert(b.name, (6, 2), defn=b, attrs={"TAG": "A"}))
        ids = set(self.s.entities)
        c = self.save(ids, "Pair")
        self.insert(c, (2.0, 6.0))
        new = [e for e in self.s.inserts() if e.id not in ids]
        names = {e.attrs["TAG"] for e in new}
        self.assertEqual(len(new), 2)
        self.assertEqual(len(names), 1)
        self.assertNotIn("A", names)

    def test_two_libraries_rename_delete(self):
        second = tempfile.mkdtemp()
        self.lib.set_second(second)
        self.lib.save_second = True
        ids = self.rung()
        self.save(ids, "Rung")
        self.assertEqual(self.lib.circuit_where("Rung"), "second")
        self.assertTrue(os.path.exists(os.path.join(second, "circuits", "Rung.kzcircuit")))
        c = self.lib.circuits()[0]["Rung"]
        self.lib.rename_circuit("Rung", c.renamed("Start-stop", "Motor control"))
        got = self.lib.circuits()[0]
        self.assertEqual(sorted(got), ["Start-stop"])
        self.assertEqual(got["Start-stop"].category, "Motor control")
        self.assertEqual(self.lib.circuit_where("Start-stop"), "second")
        with open(os.path.join(second, "circuits", "broken.kzcircuit"), "w") as f:
            f.write("{not json")
        self.assertEqual(len(self.lib.circuits()[1]), 1)
        self.assertTrue(self.lib.delete_circuit("Start-stop"))
        self.assertEqual(self.lib.circuits()[0], {})
        self.assertFalse(self.lib.delete_circuit("Start-stop"))

    def test_newer_or_other_files_refused(self):
        with self.assertRaises(ValueError):
            CI.Circuit.from_dict({"format": "something else", "name": "x"})
        with self.assertRaises(ValueError):
            CI.Circuit.from_dict({"format": CI.FORMAT, "version": CI.VERSION + 1, "name": "x"})

    def test_browser_lists_inserts_renames_deletes(self):
        from PySide6.QtWidgets import QMessageBox
        from kanzonascad import circuit_window as CW
        ids = self.rung()
        self.save(ids, "Rung")
        dlg = CW.CircuitBrowser(self.win, self.lib)
        try:
            self.assertEqual(dlg.tree.topLevelItemCount(), 1)
            self.assertEqual(dlg.tree.topLevelItem(0).text(0), "Control")
            self.assertEqual(dlg.current_name(), "Rung")
            self.assertFalse(dlg.picture.pixmap().isNull())
            self.assertIn("1 device(s), 3 wire(s)", dlg.info.text())
            real = CW.circuit_details
            CW.circuit_details = lambda *a, **k: ("Starter", "Motor control", "")
            try:
                dlg.rename()
            finally:
                CW.circuit_details = real
            self.assertEqual(sorted(self.lib.circuits()[0]), ["Starter"])
            self.assertEqual(dlg.current_name(), "Starter")
            dlg.search.setText("nothing like it")
            self.assertIsNone(dlg.current_name())
            dlg.search.setText("")
            dlg.insert()
            self.assertEqual(dlg.chosen.name, "Starter")
            ask = QMessageBox.question
            QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)
            try:
                dlg.delete()
            finally:
                QMessageBox.question = ask
            self.assertEqual(self.lib.circuits()[0], {})
        finally:
            dlg.deleteLater()


def s_parent(sheet, e):
    return sheet.entities[e.id].attrs.get("PARENT")


if __name__ == "__main__":
    unittest.main()
