"""0.29: more symbols and footprints, leaning on Allen-Bradley (allen_bradley.py), and IEC 60617
symbols as a project's symbol standard (symbols_iec.py; Project properties, Symbol standard)."""

import tempfile
import unittest

from PySide6.QtWidgets import QComboBox, QDialog

from tests.util import window, type_in

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import symbols_iec as IEC
from kanzonascad import wirenums
from kanzonascad.library import Library, Part


def on_grid(test, b):
    for p in b.pins:
        for c in p["pos"]:
            test.assertAlmostEqual(round(c / 0.03125) * 0.03125, c, msg="%s pin %s" % (
                b.name, p["name"]))


class IECSetTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(tempfile.mkdtemp())
        self.syms = self.lib.builtins("symbol")

    def test_core_set_stands_for_the_jic_one(self):
        iec = {n: b for n, b in self.syms.items() if b.category.startswith("IEC/")}
        self.assertGreaterEqual(len(iec), 30)
        self.assertEqual(set(iec), set(IEC.IEC_FOR))
        for name, b in iec.items():
            jic = self.syms[IEC.IEC_FOR[name]]
            # the same device to the program: its role, contact kind, prefix and pin names
            self.assertEqual((b.role, b.contact, b.prefix), (jic.role, jic.contact,
                                                             jic.prefix), name)
            self.assertEqual([p["name"] for p in b.pins], [p["name"] for p in jic.pins], name)
            self.assertTrue(name.endswith(" (IEC)"), name)
            self.assertTrue(b.builtin and b.entities, name)
            on_grid(self, b)
        for core in ("Relay coil (IEC)", "Contact NO (IEC)", "Contact NC (IEC)",
                     "Pushbutton NO (IEC)", "Circuit breaker 1-pole (IEC)", "Fuse (IEC)",
                     "Thermal overload (IEC)", "Motor 3-phase (IEC)", "Terminal (IEC)",
                     "Indicator lamp (IEC)", "Control transformer (IEC)",
                     "Protective earth (IEC)"):
            self.assertIn(core, iec)

    def test_drawn_otherwise_than_the_jic_one(self):
        # (an IEC coil is a rectangle, a JIC one a circle; an IEC lamp a circle with an X)
        coil = self.syms["Relay coil (IEC)"]
        self.assertTrue(any(isinstance(e, M.Polyline) and e.closed for e in coil.entities))
        self.assertFalse(any(isinstance(e, M.Circle) for e in coil.entities))
        lamp = self.syms["Indicator lamp (IEC)"]
        self.assertEqual(sum(isinstance(e, M.Circle) for e in lamp.entities), 1)
        for name in IEC.IEC_FOR:
            jic = self.syms[IEC.IEC_FOR[name]]
            self.assertNotEqual([e.to_dict() for e in self.syms[name].entities],
                                [e.to_dict() for e in jic.entities], name)

    def test_hidden_by_standard(self):
        self.assertEqual(IEC.hidden_builtins("jic"), set(IEC.IEC_FOR))
        self.assertEqual(IEC.hidden_builtins("iec"), set(IEC.IEC_FOR.values()))
        self.assertNotIn("1734-IB8 module", IEC.hidden_builtins("iec"))

    def test_old_projects_are_jic(self):
        p = M.Project.new()
        self.assertEqual(IEC.standard_of(p), "jic")
        d = p.to_dict()
        del d["settings"]["symbol_standard"]
        self.assertEqual(IEC.standard_of(M.Project.from_dict(d)), "jic")
        p.settings["symbol_standard"] = "iec"
        self.assertEqual(IEC.standard_of(M.Project.from_dict(p.to_dict())), "iec")


class StandardInWindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def listed(self):
        t = self.win.library_panel.trees["symbol"]
        out = set()
        for i in range(t.topLevelItemCount()):
            cat = t.topLevelItem(i)
            for j in range(cat.childCount()):
                out.add(cat.child(j).data(0, 0x0100))
        return out

    def test_project_properties_sets_it_and_insert_symbol_offers_it(self):
        self.win.show_library(0)
        got = self.listed()
        self.assertIn("Relay coil", got)
        self.assertNotIn("Relay coil (IEC)", got)
        seen = {}

        def answer(dlg):
            box = dlg.findChild(QComboBox, "symbol_standard")
            seen["was"] = box.currentData()
            box.setCurrentIndex(box.findData("iec"))
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            self.win.project_properties(1)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual(seen["was"], "jic")
        self.assertEqual(self.p.settings["symbol_standard"], "iec")
        got = self.listed()
        self.assertIn("Relay coil (IEC)", got)
        self.assertNotIn("Relay coil", got)
        self.assertIn("1734-IB8 module", got)            # (in both)
        self.p.undo()
        self.assertEqual(IEC.standard_of(self.p), "jic")
        self.win.library_dialog.hide()

    def test_iec_rung_tags_links_and_numbers(self):
        lib = self.win.library
        v = self.v
        v.osnap_on = v.snap_on = v.polar_on = v.ortho_on = False
        v.run(C.WireCmd)
        type_in(v, "1,5", "10,5")
        if v.cmd is not None:
            v.cmd.enter()
        v.run(C.InsertCmd, lib.get("symbol", "Relay coil (IEC)"), {})
        type_in(v, "8,5")
        v.run(C.InsertCmd, lib.get("symbol", "Contact NO (IEC)"), {})
        type_in(v, "3,5")
        coil = [e for e in v.sheet().inserts() if e.block == "Relay coil (IEC)"][0]
        type_in(v, coil.attrs["TAG"])
        k = [e for e in v.sheet().inserts() if e.block == "Contact NO (IEC)"][0]
        self.assertEqual(coil.attrs["TAG"], "CR101")
        self.assertEqual(k.attrs["PARENT"], coil.attrs["DEV"])
        nums = {w.num for w in v.sheet().wires()}
        self.assertEqual(len(nums), 3)                  # (cut at both symbols' pins)
        self.assertTrue(all(wirenums.split(n) for n in nums), nums)


class AllenBradleyTest(unittest.TestCase):
    def setUp(self):
        self.lib = Library(tempfile.mkdtemp())

    def test_parts_link_blocks_that_exist(self):
        syms, fps = self.lib.builtins("symbol"), self.lib.builtins("footprint")
        parts = [p for p in self.lib.parts() if p.builtin]
        self.assertGreaterEqual(len(parts), 50)
        cats = {p.catalog for p in parts}
        for c in ("100-C09D10", "140M-C2E-C10", "700-HA32Z24", "800F-X10", "1492-J3",
                  "1606-XLP50E", "25B-D4P0N104", "1756-IB16", "1769-OB16", "5069-IB16",
                  "1756-L83E", "1769-L33ER"):
            self.assertIn(c, cats)
        ids = [p.id for p in parts]
        self.assertEqual(len(ids), len(set(ids)))
        for p in parts:
            self.assertEqual(p.manufacturer, "Allen-Bradley")
            self.assertTrue(p.symbol or p.footprint, p.catalog)
            self.assertTrue(not p.symbol or p.symbol in syms, (p.catalog, p.symbol))
            self.assertTrue(not p.footprint or p.footprint in fps, (p.catalog, p.footprint))
            self.assertIn("selection guide", p.notes)

    def test_footprints_say_how_sure_their_size_is(self):
        fps = [b for b in self.lib.builtins("footprint").values()
               if b.manufacturer == "Allen-Bradley"]
        self.assertGreaterEqual(len(fps), 10)
        for b in fps:
            if "(approximate)" in b.name:
                self.assertIn("about", b.description)
            else:
                self.assertTrue(b.name.startswith("PowerFlex 525 frame"), b.name)
                self.assertIn("nominal", b.description)
        a = self.lib.builtins("footprint")["PowerFlex 525 frame A"]
        x0, y0, x1, y1 = a.extents()
        self.assertAlmostEqual((x1 - x0) * 25.4, 72.0, places=6)
        self.assertAlmostEqual((y1 - y0) * 25.4, 152.0, places=6)

    def test_new_symbols(self):
        syms = self.lib.builtins("symbol")
        for name, prefix, role in (("Motor protection circuit breaker 3-pole", "CB", "parent"),
                                   ("Overload relay, electronic 3-pole", "OL", "parent"),
                                   ("Overload contact NO", "OL", "child"),
                                   ("Selector switch 3-position", "SS", "parent"),
                                   ("Selector switch 3-position contact, closed right", "SS",
                                    "child"),
                                   ("Pilot light with color letter", "LT", "device"),
                                   ("1756-IB16 module", "PLC", "parent"),
                                   ("1769-OF2 module", "PLC", "parent")):
            b = syms[name]
            self.assertEqual((b.prefix, b.role), (prefix, role), name)
            on_grid(self, b)
        mpcb = syms["Motor protection circuit breaker 3-pole"]
        self.assertEqual(M.phases_of(mpcb), "3")
        ib16 = syms["1756-IB16 module"]
        self.assertEqual((ib16.catalog, ib16.manufacturer, ib16.family),
                         ("1756-IB16", "Allen-Bradley", "ControlLogix"))
        self.assertEqual(len(wirenums.io_points(ib16)), 16)
        ob = syms["1769-OB16 module"]
        self.assertEqual({k for k, _n in wirenums.io_points(ob).values()}, {"O"})

    def test_builtin_part_read_only_and_yours_takes_its_place(self):
        p = self.lib.part("ab-100-c09d10")
        self.assertTrue(p.builtin)
        self.lib.delete_part(p.id)              # (nothing to delete: still there)
        self.assertIsNotNone(self.lib.part(p.id))
        mine = Part.from_dict(dict(p.to_dict(), description="my contactor"))
        self.lib.save_part(mine)
        got = self.lib.part(p.id)
        self.assertEqual((got.description, got.builtin), ("my contactor", False))
        self.assertEqual(len([x for x in self.lib.parts() if x.id == p.id]), 1)
        # (saving the library's parts never writes the built-in ones as files)
        self.lib.save_parts(self.lib.parts())
        self.assertEqual([x.id for x in self.lib.parts(builtin=False)], [p.id])
        self.lib.delete_part(p.id)
        self.assertTrue(self.lib.part(p.id).builtin)


if __name__ == "__main__":
    unittest.main()
