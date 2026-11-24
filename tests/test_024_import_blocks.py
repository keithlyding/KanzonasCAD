"""Library > Import blocks from folder... (0.24; the owner: "If someone is an AutoCAD user and
wants to switch over but doesn't want to lose ... any [blocks] they've created, can they copy
their blocks into the KanzonasCAD folder and they'll work?"): the blocks of a folder of DWG and
DXF files listed, then put in the library in one go; AutoCAD Electrical's wire connection
attributes (X?TERMnn) become pins, its TAG1 the tag spot. Every drawing here is made by the
test with ezdxf (or ezdwg)."""
import os
import tempfile
import unittest
import unittest.mock

import ezdxf
from PySide6.QtWidgets import (QDialog, QFileDialog, QMessageBox, QTableWidget, QComboBox,
                               QPushButton, QCheckBox)
from PySide6.QtCore import Qt

from tests.util import APP, window, type_in

from kanzonascad import block_import as BI
from kanzonascad import import_blocks_window as IB
from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import wires
from kanzonascad.library import Library


def coil_dxf(path, base=(0.0, 0.0), desc_hidden=True):
    """A coil kept as AutoCAD Electrical keeps one (WBLOCK): its drawing and attribute
    definitions in model space; wire connections X4TERM01 (left) and X1TERM02 (right) with
    their pin numbers A1 and A2 (TERM01, TERM02), the tag TAG1 above."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1
    doc.header["$INSBASE"] = (base[0], base[1], 0.0)
    m = doc.modelspace()
    m.add_circle((0.0, 0.0), 0.25)
    m.add_line((-0.5, 0.0), (-0.25, 0.0))
    m.add_line((0.25, 0.0), (0.5, 0.0))
    m.add_attdef("TAG1", (0.0, 0.4), dxfattribs={"height": 0.1})
    m.add_attdef("X4TERM01", (-0.5, 0.0), dxfattribs={"height": 0.05, "flags": 1})
    m.add_attdef("X1TERM02", (0.5, 0.0), dxfattribs={"height": 0.05, "flags": 1})
    m.add_attdef("TERM01", (-0.4, 0.05), text="A1", dxfattribs={"height": 0.05})
    m.add_attdef("TERM02", (0.4, 0.05), text="A2", dxfattribs={"height": 0.05})
    m.add_attdef("DESC1", (0.0, -0.4), dxfattribs={"height": 0.08,
                                                    "flags": 1 if desc_hidden else 0})
    doc.saveas(path)
    return path


def library_dxf(path):
    """A drawing of three named blocks placed in model space: two pushbutton/limit-switch
    symbols (wire connections, no pin numbers) and a relay base footprint (none), the base
    using a block of its own inside it (a part of it, not a block to import)."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 1
    dot = doc.blocks.new("BASE SCREW")
    dot.add_circle((0.0, 0.0), 0.05)
    for n, w in (("HPB11", 0.5), ("HLS11", 0.6), ("RELAY BASE", 1.0)):
        b = doc.blocks.new(n)
        b.add_lwpolyline([(0, 0), (w, 0), (w, 0.7), (0, 0.7)], close=True)
        if n == "RELAY BASE":
            b.add_blockref("BASE SCREW", (0.2, 0.2))
            b.add_attdef("P_TAG1", (0.5, 0.35))
        else:
            b.add_attdef("X8TERM01", (0.0, 0.35), dxfattribs={"flags": 1})
            b.add_attdef("X2TERM02", (w, 0.35), dxfattribs={"flags": 1})
            b.add_attdef("TAG1", (w / 2, 0.9))
        doc.modelspace().add_blockref(n, (3.0 * len(doc.blocks), 0.0))
    doc.saveas(path)
    return path


def metric_dxf(path):
    """A footprint drawn in millimeters ($INSUNITS 4), 45 x 90, one wire connection."""
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 4
    m = doc.modelspace()
    m.add_lwpolyline([(0, 0), (45, 0), (45, 90), (0, 90)], close=True)
    m.add_attdef("X4TERM01", (0.0, 45.0), dxfattribs={"flags": 1})
    doc.saveas(path)
    return path


def folder_of_blocks():
    d = tempfile.mkdtemp(prefix="kz-blocks-")
    coil_dxf(os.path.join(d, "HCR1.dxf"))
    library_dxf(os.path.join(d, "my blocks.dxf"))
    metric_dxf(os.path.join(d, "metric coil.DXF"))
    with open(os.path.join(d, "damaged.dxf"), "wb") as f:
        f.write(b"\x00\x01 this is not a drawing \xff\xfe" * 20)
    with open(os.path.join(d, "notes.txt"), "w") as f:
        f.write("not a drawing, not listed")
    os.makedirs(os.path.join(d, "more"))
    coil_dxf(os.path.join(d, "more", "HCR9.dxf"))
    return d


def snapshot(folder):
    out = {}
    for root, _dirs, files in os.walk(folder):
        for f in files:
            with open(os.path.join(root, f), "rb") as fh:
                out[os.path.relpath(os.path.join(root, f), folder)] = fh.read()
    return out


def read_folder(folder, subfolders=False):
    rows = []
    for _p, got in BI.read_all(BI.drawing_files(folder, subfolders)):
        rows += got
    return rows


class ReadingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = folder_of_blocks()
        cls.rows = read_folder(cls.folder)
        cls.by = {r.name: r for r in cls.rows}

    def test_every_block_found(self):
        self.assertEqual(sorted(self.by), ["HCR1", "HLS11", "HPB11", "RELAY BASE", "damaged",
                                           "metric coil"])
        # (a block only used inside another is a part of it; a subfolder only when asked)
        self.assertNotIn("BASE SCREW", self.by)
        self.assertNotIn("HCR9", self.by)
        deep = {r.name for r in read_folder(self.folder, True)}
        self.assertIn("HCR9", deep)
        self.assertEqual(self.by["HPB11"].path, os.path.join(self.folder, "my blocks.dxf"))

    def test_kinds_guessed(self):
        kinds = {n: r.kind for n, r in self.by.items() if r.defn is not None}
        self.assertEqual(kinds, {"HCR1": "symbol", "HPB11": "symbol", "HLS11": "symbol",
                                 "RELAY BASE": "footprint", "metric coil": "symbol"})

    def test_pins_from_wire_connections(self):
        coil = self.by["HCR1"].defn
        self.assertEqual(coil.pins, [{"name": "A1", "pos": (-0.5, 0.0)},
                                     {"name": "A2", "pos": (0.5, 0.0)}])
        self.assertTrue(coil.show_pins)         # (its pin numbers were shown)
        # (no pin numbers: the connection's own, in order)
        self.assertEqual(self.by["HPB11"].defn.pins, [{"name": "1", "pos": (0.0, 0.35)},
                                                      {"name": "2", "pos": (0.5, 0.35)}])
        self.assertEqual(self.by["RELAY BASE"].defn.pins, [])

    def test_tag_spot_and_prefix(self):
        coil = self.by["HCR1"].defn
        self.assertEqual(coil.tag_pos, (0.0, 0.4))
        self.assertAlmostEqual(coil.tag_height, 0.1)
        self.assertEqual(coil.prefix, "CR")
        self.assertEqual(self.by["HLS11"].defn.prefix, "LS")
        self.assertEqual(coil.role, "device")       # (left as it is: see the manual)

    def test_hidden_attributes_stay_hidden(self):
        shown = [a["attr"] for a in self.by["HCR1"].defn.attr_texts]
        # (TAG is the tag spot; TERMnn the pin names; X?TERMnn and the hidden DESC1 not shown)
        self.assertEqual(shown, [])
        d = tempfile.mkdtemp()
        shown = BI.read_blocks(coil_dxf(os.path.join(d, "c.dxf"), desc_hidden=False))
        self.assertEqual([a["attr"] for a in shown[0].defn.attr_texts], ["DESC1"])

    def test_base_point(self):
        d = tempfile.mkdtemp()
        row = BI.read_blocks(coil_dxf(os.path.join(d, "c.dxf"), base=(0.5, 0.0)))[0]
        self.assertEqual([p["pos"] for p in row.defn.pins], [(-1.0, 0.0), (0.0, 0.0)])

    def test_metric_scaled_to_inches(self):
        m = self.by["metric coil"].defn
        bb = m.extents()
        self.assertAlmostEqual(bb[2] - bb[0], 45 / 25.4)
        self.assertAlmostEqual(bb[3] - bb[1], 90 / 25.4)
        self.assertAlmostEqual(m.pins[0]["pos"][1], 45 / 25.4)

    def test_damaged_file_reported_not_fatal(self):
        bad = self.by["damaged"]
        self.assertIsNone(bad.defn)
        self.assertTrue(bad.error)
        self.assertFalse(bad.ticked)
        # (a drawing with nothing in it: listed too, with why)
        empty = os.path.join(tempfile.mkdtemp(), "empty.dxf")
        ezdxf.new().saveas(empty)
        rows = BI.read_blocks(empty)
        self.assertEqual([(r.name, r.defn, r.error) for r in rows],
                         [("empty", None, "no block or drawing in it")])
        sts = BI.statuses(Library(tempfile.mkdtemp()), self.rows)
        self.assertEqual(sts[self.rows.index(bad)], "error")
        self.assertEqual(sts.count("new"), 5)

    def test_dwg(self):
        # (ezdwg writes DWG: a coil kept as one block, read through the DWG reader)
        import ezdwg
        d = ezdwg.new("AC1032")
        d.header["insunits"] = 1
        m = d.modelspace()
        m.add_line((-0.5, 0.0, 0.0), (0.5, 0.0, 0.0))
        m.add_attdef("X4TERM01", "", (-0.5, 0.0, 0.0), 0.05, attribute_flags=1)
        m.add_attdef("X1TERM02", "", (0.5, 0.0, 0.0), 0.05, attribute_flags=1)
        m.add_attdef("TERM01", "13", (-0.4, 0.05, 0.0), 0.05)
        m.add_attdef("TAG1", "", (0.0, 0.3, 0.0), 0.1)
        path = os.path.join(tempfile.mkdtemp(), "HFU1.dwg")
        d.save(path, strict=False)
        rows = BI.read_blocks(path)
        self.assertEqual(len(rows), 1, [r.error for r in rows])
        self.assertIsNone(rows[0].error)
        self.assertEqual(rows[0].name, "HFU1")
        self.assertEqual(rows[0].kind, "symbol")
        self.assertEqual([(p["name"], p["pos"]) for p in rows[0].defn.pins],
                         [("13", (-0.5, 0.0)), ("2", (0.5, 0.0))])
        self.assertEqual(rows[0].defn.tag_pos, (0.0, 0.3))
        bad = os.path.join(os.path.dirname(path), "bad.dwg")
        with open(bad, "wb") as f:
            f.write(b"AC1032 not really")
        rows = BI.read_blocks(bad)
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].error)


class ImportingTest(unittest.TestCase):
    def setUp(self):
        self.folder = folder_of_blocks()
        self.lib = Library(tempfile.mkdtemp())
        # (a block of yours already called HCR1)
        self.mine = M.BlockDef("HCR1", "symbol", [M.Line((0, 0), (2, 0))], category="Mine")
        self.lib.save_block(self.mine)
        self.rows = read_folder(self.folder)
        self.by = {r.name: r for r in self.rows}

    def test_name_clash_shown(self):
        sts = dict(zip([r.name for r in self.rows], BI.statuses(self.lib, self.rows)))
        self.assertEqual(sts["HCR1"], "taken")
        self.assertEqual(sts["HPB11"], "new")
        # (the same name as a footprint: not taken)
        self.by["HCR1"].kind = "footprint"
        sts = dict(zip([r.name for r in self.rows], BI.statuses(self.lib, self.rows)))
        self.assertEqual(sts["HCR1"], "new")

    def test_skip(self):
        imp = BI.Importer(self.lib, self.rows)
        imp.run()
        self.assertEqual(self.lib.get("symbol", "HCR1").category, "Mine")
        self.assertEqual([r.name for r, _w in imp.skipped], ["HCR1"])
        self.assertEqual(sorted(n for _r, n in imp.imported),
                         ["HLS11", "HPB11", "RELAY BASE", "metric coil"])
        got = self.lib.get("symbol", "HPB11")
        self.assertEqual(got.category, "Imported")
        self.assertEqual(len(got.pins), 2)
        self.assertIsNotNone(self.lib.get("footprint", "RELAY BASE"))
        self.assertIsNone(self.lib.get("symbol", "RELAY BASE"))

    def test_replace(self):
        self.by["HCR1"].choice = "replace"
        BI.Importer(self.lib, self.rows, "Coils").run()
        got = self.lib.get("symbol", "HCR1")
        self.assertEqual(got.category, "Coils")
        self.assertEqual([p["name"] for p in got.pins], ["A1", "A2"])
        self.assertFalse(self.lib.has_own("symbol", "HCR1 (2)"))

    def test_keep_both(self):
        self.by["HCR1"].choice = "both"
        imp = BI.Importer(self.lib, self.rows)
        imp.run()
        self.assertEqual(self.lib.get("symbol", "HCR1").category, "Mine")
        self.assertEqual([p["name"] for p in self.lib.get("symbol", "HCR1 (2)").pins],
                         ["A1", "A2"])
        self.assertIn("HCR1 as HCR1 (2)", imp.summary())
        # (again: the next free name)
        BI.Importer(self.lib, [self.by["HCR1"]]).run()
        self.assertTrue(self.lib.has_own("symbol", "HCR1 (3)"))

    def test_kind_changed_and_unticked(self):
        self.by["RELAY BASE"].kind = "symbol"
        self.by["HLS11"].ticked = False
        BI.Importer(self.lib, self.rows).run()
        base = self.lib.get("symbol", "RELAY BASE")
        self.assertIsNotNone(base)
        self.assertIsNotNone(base.tag_pos)          # (a symbol gets a tag spot)
        self.assertIsNone(self.lib.get("symbol", "HLS11"))

    def test_second_library(self):
        second = tempfile.mkdtemp()
        lib = Library(self.lib.folder, second)
        BI.Importer(lib, self.rows, target="second").run()
        self.assertTrue(Library(second).has_own("symbol", "HPB11"))
        self.assertFalse(Library(self.lib.folder).has_own("symbol", "HPB11"))

    def test_rollback_leaves_library_as_it_was(self):
        self.by["HCR1"].choice = "replace"
        before = snapshot(self.lib.folder)
        imp = BI.Importer(self.lib, self.rows)
        for _i in range(3):
            imp.step()
        self.assertNotEqual(snapshot(self.lib.folder), before)
        imp.rollback()
        self.assertEqual(snapshot(self.lib.folder), before)


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.folder = folder_of_blocks()
        self.lib = self.win.library
        self.lib.folder = tempfile.mkdtemp()
        self.lib.set_second(None)
        self.lib.save_block(M.BlockDef("HCR1", "symbol", [M.Line((0, 0), (2, 0))],
                                       category="Mine"))
        self.saved = (QFileDialog.getExistingDirectory, IB.ImportBlocksDialog.exec,
                      QMessageBox.information, IB.Progress.tick)
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: self.folder)
        self.told = []
        QMessageBox.information = staticmethod(lambda *a, **k: self.told.append(a[2]))

    def tearDown(self):
        (QFileDialog.getExistingDirectory, IB.ImportBlocksDialog.exec,
         QMessageBox.information, IB.Progress.tick) = self.saved
        self.win.library_dialog.hide()
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def test_menu_and_manual(self):
        from kanzonascad import manual, selftest
        lib_menu = [a for a in self.win.menuBar().actions() if a.text() == "&Library"][0].menu()
        self.assertIn(self.win.acts["import_blocks"], lib_menu.actions())
        self.assertEqual(self.win.acts["import_blocks"].text(), "&Import blocks from folder...")
        self.assertNotIn("Import blocks from folder", selftest.manual_gaps(self.win))
        text = manual.plain_text()
        self.assertIn("Bringing in your own blocks", text)
        self.assertIn("X1TERM01", text)

    def test_preview_window_driven(self):
        seen = {}

        def answer(dlg):
            t = dlg.findChild(QTableWidget, "blocks")
            names = [t.item(i, 0).text() for i in range(t.rowCount())]
            seen["names"] = names
            seen["status"] = {names[i]: t.item(i, 4).text() for i in range(t.rowCount())}
            seen["pins"] = {names[i]: t.item(i, 2).text() for i in range(t.rowCount())}
            seen["source"] = dlg.findChild(QCheckBox, "subfolders") is not None
            i = names.index("HCR1")
            t.selectRow(i)
            dlg.findChild(QPushButton, "selected_both").click()           # (keep both)
            self.assertEqual(dlg.findChild(QComboBox, "taken_%d" % i).currentData(), "both")
            self.assertTrue(dlg.findChild(QComboBox, "taken_%d" % i).isEnabled())
            self.assertFalse(dlg.findChild(QComboBox, "taken_%d" % names.index(
                "HPB11")).isEnabled())
            # (the limit switch made a footprint by selecting its row)
            t.selectRow(names.index("HLS11"))
            dlg.findChild(QPushButton, "selected_footprint").click()
            t.clearSelection()
            # (the metric coil unticked)
            t.item(names.index("metric coil"), 0).setCheckState(Qt.Unchecked)
            dlg.findChild(QComboBox, "category").setCurrentText("My AutoCAD blocks")
            self.assertEqual(dlg.findChild(QComboBox, "target").currentData(), "first")
            dlg.findChild(QPushButton, "import").click()
            return dlg.result()
        IB.ImportBlocksDialog.exec = answer
        imp = self.win.import_blocks()
        self.assertEqual(sorted(seen["names"]), ["HCR1", "HLS11", "HPB11", "RELAY BASE",
                                                 "damaged", "metric coil"])
        self.assertEqual(seen["status"]["HCR1"], "Name already in the library")
        self.assertEqual(seen["status"]["HPB11"], "New")
        self.assertTrue(seen["status"]["damaged"].startswith("Can't be read"))
        self.assertEqual(seen["pins"]["HCR1"], "2")
        lib = self.lib
        self.assertEqual(lib.get("symbol", "HCR1 (2)").category, "My AutoCAD blocks")
        self.assertEqual(lib.get("symbol", "HCR1").category, "Mine")
        self.assertIsNotNone(lib.get("footprint", "HLS11"))
        self.assertIsNone(lib.get("symbol", "HLS11"))
        self.assertIsNone(lib.get("symbol", "metric coil"))
        self.assertIsNotNone(lib.get("footprint", "RELAY BASE"))
        self.assertEqual(len(imp.imported), 4)
        # (the summary, then the Library popup on what came in)
        self.assertEqual(len(self.told), 1)
        self.assertIn("4 imported, 0 skipped, 1 failed", self.told[0])
        self.assertIn("damaged", self.told[0])
        self.assertTrue(self.win.library_dialog.isVisible())
        self.assertEqual(self.win.library_panel.search.text(), "My AutoCAD blocks")
        tree = self.win.library_panel.trees["symbol"]
        listed = [tree.topLevelItem(0).child(j).data(0, Qt.UserRole)
                  for j in range(tree.topLevelItem(0).childCount())]
        self.assertEqual(sorted(listed), ["HCR1 (2)", "HPB11"])

    def test_cancel_while_reading(self):
        seen = {}

        def answer(dlg):
            seen["rows"] = dlg.findChild(QTableWidget, "blocks").rowCount()
            seen["count"] = dlg.count_label.text()
            return QDialog.Rejected
        IB.ImportBlocksDialog.exec = answer
        IB.Progress.tick = lambda prog, done, text=None: False
        before = snapshot(self.lib.folder)
        self.assertIsNone(self.win.import_blocks())
        self.assertEqual(seen, {"rows": 0, "count": "Reading was cancelled: nothing listed"})
        self.assertEqual(snapshot(self.lib.folder), before)

    def test_cancel_while_importing(self):
        before = snapshot(self.lib.folder)

        def answer(dlg):
            return QDialog.Accepted
        IB.ImportBlocksDialog.exec = answer
        calls = []
        real = self.saved[3]

        def tick(prog, done, text=None):
            calls.append(done)
            real(prog, done, text)
            return len(calls) < 9          # (Cancel pressed while importing)
        IB.Progress.tick = tick
        self.assertIsNone(self.win.import_blocks())
        self.assertGreater(len(calls), 5)       # (it was writing when cancelled)
        self.assertEqual(snapshot(self.lib.folder), before)
        self.assertEqual(self.told, ["Cancelled: the library is as it was."])

    def test_imported_symbol_takes_a_wire(self):
        IB.ImportBlocksDialog.exec = lambda dlg: QDialog.Accepted
        self.win.import_blocks()
        coil = self.lib.get("symbol", "HPB11")
        v = self.win.view()
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        s = v.sheet()
        v.run(C.InsertCmd, coil, {})
        type_in(v, "5,5")
        if v.cmd is not None:
            v.cancel()
        ins = [e for e in s.entities.values() if isinstance(e, M.Insert)]
        self.assertEqual(len(ins), 1)
        pins = dict(ins[0].pin_points())
        self.assertEqual(sorted(pins), ["1", "2"])
        self.assertTrue(ins[0].attrs.get("TAG", "").startswith("PB"))
        far = (pins["2"][0] + 2.0, pins["2"][1])
        v.run(C.WireCmd)
        type_in(v, "%r,%r" % pins["2"], "%r,%r" % far)
        v.cmd.enter()
        if v.cmd is not None:
            v.cancel()
        w = [e for e in s.entities.values() if isinstance(e, M.Wire)]
        self.assertEqual(len(w), 1)
        self.assertEqual([n for _e, n in wires.pins_on(s, w[0].points[0])], ["2"])

    def test_read_only_target_told(self):
        IB.ImportBlocksDialog.exec = lambda dlg: QDialog.Accepted
        warned = []
        with unittest.mock.patch.object(QMessageBox, "warning",
                                        lambda *a, **k: warned.append(a[2])), \
                unittest.mock.patch.object(BI, "_writable",
                                           side_effect=OSError("read-only")):
            self.assertIsNone(self.win.import_blocks())
        self.assertEqual(len(warned), 1)
        self.assertIn("read-only", warned[0])


if __name__ == "__main__":
    unittest.main()
