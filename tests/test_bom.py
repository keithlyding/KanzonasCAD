"""The bill of materials (the owner, after their panel DWG: "Do all of them"): every part
once, grouped by manufacturer and catalog number; a device and its footprint one part;
contacts their device's; rail and duct as stock lengths; CSV."""
import csv
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog, QTableWidget

from tests.util import APP, window

from kanzonascad import bom
from kanzonascad import model as M


def coil():
    return M.BlockDef("Coil", "symbol", [M.Circle((0, 0), 0.1)],
                      [{"name": "A1", "pos": (-0.1, 0)}], (0, 0.2), 0.1, prefix="CR",
                      role="parent")


def contact():
    return M.BlockDef("NO contact", "symbol", [M.Line((0, 0), (0.2, 0))], prefix="CR",
                      role="child", contact="NO")


def relay_fp():
    return M.BlockDef("Relay base", "footprint", [M.Polyline([(0, 0), (1, 0), (1, 2)], True)],
                      manufacturer="Allen-Bradley", catalog="700-HN100",
                      description="Relay socket")


def terminal():
    return M.BlockDef("TB 2202", "footprint", [M.Polyline([(0, 0), (0.2, 0), (0.2, 1)], True)])


class BomTest(unittest.TestCase):
    def project(self):
        p = M.Project.new()
        with p.edit("sheets") as ed:
            ed.add_sheet(M.Sheet(title="Panel"))
        s1, s2 = p.sheets
        with p.edit("parts") as ed:
            for d in (coil(), contact(), relay_fp(), terminal()):
                ed.block(d)
            B = p.blocks
            for tag in ("CR1", "CR2"):
                ed.add(s1, M.Insert("Coil", (1, 1), attrs={"TAG": tag, "MFR": "Allen-Bradley",
                                                           "CAT": "700-HA32A1"},
                                    defn=B["Coil"]))
                ed.add(s1, M.Insert("NO contact", (2, 1), attrs={"TAG": tag},
                                    defn=B["NO contact"]))
                ed.add(s2, M.Insert("Relay base", (3, 1), attrs={"TAG": tag},
                                    defn=B["Relay base"]))
            for i in range(5):
                ed.add(s2, M.Insert("TB 2202", (5 + i * 0.2, 1), defn=B["TB 2202"]))
            ed.add(s2, M.Rail((0, 5), (20, 5), "TS35x7.5", 35 * M.MM_IN, 7.5 * M.MM_IN,
                              attrs={"MFR": "Phoenix", "CAT": "1208131"}))
        return p

    def test_lines(self):
        p = self.project()
        lines = bom.rows(p)
        by = {(g["mfr"], g["cat"] or g["desc"]): g for g in lines}
        # the coil and its relay base: one part per tag, the coil's catalog number kept
        relay = by[("Allen-Bradley", "700-HA32A1")]
        self.assertEqual((relay["qty"], relay["tags"]), (2, ["CR1", "CR2"]))
        self.assertEqual(relay["sheets"], sorted({p.sheet_number(s) for s in p.sheets},
                                                 key=lambda n: (len(n), n)))
        # contacts are their coil's: no line of their own; untagged terminals by block name
        self.assertNotIn("NO contact", [g["desc"] for g in lines])
        self.assertEqual(by[("", "TB 2202")]["qty"], 5)
        # rail: the stock lengths to buy, last
        self.assertEqual(lines[-1]["kind"], "stock")
        self.assertEqual((lines[-1]["mfr"], lines[-1]["cat"], lines[-1]["qty"]),
                         ("Phoenix", "1208131", 1))
        self.assertEqual([g["item"] for g in lines], list(range(1, len(lines) + 1)))
        # without catalog numbers left out: the terminals go
        self.assertNotIn(("", "TB 2202"), {(g["mfr"], g["cat"] or g["desc"])
                                           for g in bom.rows(p, unnumbered=False)})

    def test_imported_schematic_parts(self):
        """AutoCAD Electrical's schematic components (TAG1) come in as symbols: they are parts;
        an imported symbol without a tag is not."""
        import ezdxf
        from kanzonascad import fileio
        doc = ezdxf.new("R2013")
        doc.header["$INSUNITS"] = 1
        b = doc.blocks.new("HCR1")
        b.add_circle((0, 0), 0.1)
        for k, tag in enumerate(("TAG1", "MFG", "CAT", "DESC1")):
            b.add_attdef(tag, (0, -0.1 * (k + 1)), dxfattribs={"height": 0.05})
        msp = doc.modelspace()
        for i, t in enumerate(("CR1", "CR2", "")):
            r = msp.add_blockref("HCR1", (i, 0))
            r.add_auto_attribs({"TAG1": t, "MFG": "AB", "CAT": "700-HA32Z24", "DESC1": "RELAY"})
        path = os.path.join(tempfile.mkdtemp(), "ace.dxf")
        doc.saveas(path)
        p = M.Project.new()
        fileio.import_dxf(p, p.sheets[0], path)
        got = [r for r in bom.rows(p) if r["cat"] == "700-HA32Z24"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["qty"], 2)
        self.assertEqual(got[0]["mfr"], "AB")

    def test_csv(self):
        path = os.path.join(tempfile.mkdtemp(), "bom.csv")
        n = bom.write_csv(self.project(), path)
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], bom.HEAD)
        self.assertEqual(len(rows) - 1, n)
        self.assertIn("CR1, CR2", [r[5] for r in rows])

    def test_dialog_and_menu(self):
        win, v = window()
        try:
            seen = []

            def run(dlg):
                t = dlg.findChild(QTableWidget, "bom_table")
                seen.append(t.rowCount())
                return QDialog.Rejected
            with mock.patch.object(QDialog, "exec", run):
                win.show_bom()
            self.assertEqual(seen, [0])                     # (an empty project: no lines)
            acts = {b.text().replace("&", "") for a in win.menuBar().actions() if a.menu()
                    for b in a.menu().actions()}
            self.assertIn("Bill of materials...", acts)
        finally:
            win.close()


if __name__ == "__main__":
    unittest.main()
