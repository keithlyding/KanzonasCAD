"""A schematic symbol and a panel footprint with the same name, both placed in one project
(the owner, 0.25: "a footprint and a schematic symbol, both having the same name should be ok.
Right now, one will supersede the other").

The project keeps them apart as since 0.18: the second one placed under "name (footprint)" (or
"name (symbol)"), shown everywhere by its own name (BlockDef.shown_name, Insert.block_name).
0.25 closes the paths that still let one take the other's place: Make block, the I/O list's
modules, Save to library as part, Edit block and Block properties of a copy the library hasn't
got; and it shows the real name in the bill of materials, Trace, the Properties panel, a
footprint's "Block name" label and the lists. A project that already lost one is mended on
open from the library."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QDialog, QMessageBox

from tests.util import APP, window, type_in

from kanzonascad import block_editor as BE
from kanzonascad import bom
from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import where_used


def sym(name="Starter"):
    return M.BlockDef(name, "symbol", [M.Circle((0.25, 0), 0.1), M.Line((0, 0), (0.15, 0)),
                                       M.Line((0.35, 0), (0.5, 0))],
                      pins=[{"name": "A1", "pos": (0, 0)}, {"name": "A2", "pos": (0.5, 0)}],
                      role="device", prefix="M", description="Starter coil")


def fp(name="Starter", w=2.0):
    return M.BlockDef(name, "footprint", [M.Polyline([(0, 0), (w, 0), (w, 3), (0, 3)], True)],
                      description="Starter, 45 mm")


def width(e):
    b = e.bbox()
    return round(b[2] - b[0], 6)


class SameNameBlocksTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        self.lib.save_block(sym())
        self.lib.save_block(fp())
        self.sch = self.v.sheet()
        self.panel = self.p.make_sheet("Panel")
        self.panel.kind = "panel"
        with self.p.edit("panel") as ed:
            ed.add_sheet(self.panel, 1)
        self.said = []
        real = self.win._say
        self.win._say = lambda text, *a: (self.said.append(text), real(text, *a))

    def tearDown(self):
        for kind in ("symbol", "footprint"):
            self.lib.delete_block(kind, "Starter")
            self.lib.delete_block(kind, "1734-IB8 module")
        for _w, d in self.win.documents():
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    # ---- placing them, as a user does ------------------------------------------------------
    def insert(self, kind, at, link=False):
        """Insert from the Library popup (its insert signal), on the sheet of that kind."""
        self.v.show_sheet((self.sch if kind == "symbol" else self.panel).id)
        self.win.library_panel.insertRequested.emit(self.lib.get(kind, "Starter"), {})
        type_in(self.v, at)
        while self.v.cmd is not None:
            if link or not self.v.input_text("N"):
                self.v.cmd.enter()
        sheet = self.v.sheet()
        return max(sheet.inserts(), key=lambda e: e.id)

    def kinds(self):
        return {n: b.kind for n, b in self.p.blocks.items() if n.startswith("Starter")}

    def test_symbol_then_footprint(self):
        s = self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5")
        self.assertEqual(self.kinds(), {"Starter": "symbol", "Starter (footprint)": "footprint"})
        s, f = self.sch.entities[s.id], self.panel.entities[f.id]
        self.assertEqual((s.defn.kind, width(s)), ("symbol", 0.5))
        self.assertEqual((f.defn.kind, width(f)), ("footprint", 2.0))
        self.assertEqual((s.block_name, f.block_name), ("Starter", "Starter"))

    def test_footprint_then_symbol(self):
        f = self.insert("footprint", "5,5")
        s = self.insert("symbol", "3,3")
        self.assertEqual(self.kinds(), {"Starter": "footprint", "Starter (symbol)": "symbol"})
        self.assertEqual(self.sch.entities[s.id].defn.kind, "symbol")
        self.assertEqual(self.panel.entities[f.id].defn.kind, "footprint")
        self.assertEqual(self.sch.entities[s.id].block_name, "Starter")
        # (Devices without a footprint lists it by its own name: "Starter (symbol)" here)
        from kanzonascad import missing_fp
        self.assertEqual([r[2] for r in missing_fp.rows(self.p)], ["Starter"])

    def test_drawn_both(self):
        s = self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5")
        from kanzonascad.render import entities_path
        for sheet, e, w in ((self.sch, s, 0.5), (self.panel, f, 2.0)):
            self.v.show_sheet(sheet.id)
            self.v.repaint()
            APP.processEvents()
            box = entities_path([sheet.entities[e.id]])[0].boundingRect()
            self.assertAlmostEqual(box.width(), w, 3)

    def test_make_footprint_named_as_a_symbol(self):
        s = self.insert("symbol", "3,3")
        self.v.show_sheet(self.panel.id)
        with self.p.edit("draw") as ed:
            r = ed.add(self.panel, M.Polyline([(1, 1), (4, 1), (4, 2), (1, 2)], True))
        self.v.set_selection({r.id})
        self.win.ask_block_details = lambda ents: {
            "kind": "footprint", "name": "Starter", "category": "", "description": "",
            "role": "device", "contact": "", "prefix": "", "pin_names": [], "replace": True}
        self.v.run(C.MakeBlockCmd)
        type_in(self.v, "1,1")
        self.assertEqual(self.sch.entities[s.id].defn.kind, "symbol", "the symbol was replaced")
        self.assertEqual(width(self.sch.entities[s.id]), 0.5)
        made = self.panel.inserts()[0]
        self.assertEqual((made.block, made.defn.kind, width(made)),
                         ("Starter (footprint)", "footprint", 3.0))
        self.assertEqual(self.lib.get("footprint", "Starter").extents()[2], 3.0)
        # made again: the project's footprint replaced, still apart from the symbol
        with self.p.edit("draw") as ed:
            r = ed.add(self.panel, M.Polyline([(6, 1), (7, 1), (7, 2), (6, 2)], True))
        self.v.set_selection({r.id})
        self.v.run(C.MakeBlockCmd)
        type_in(self.v, "6,1")
        self.assertEqual(self.kinds(), {"Starter": "symbol", "Starter (footprint)": "footprint"})
        self.assertEqual({width(e) for e in self.panel.inserts()}, {1.0})

    def test_io_module_beside_a_footprint_of_its_name(self):
        from kanzonascad import io_list
        mod = self.lib.get("symbol", "1734-IB8 module")
        self.lib.save_block(fp("1734-IB8 module", 1.0))
        self.v.show_sheet(self.panel.id)
        self.win.library_panel.insertRequested.emit(self.lib.get("footprint",
                                                                 "1734-IB8 module"), {})
        type_in(self.v, "5,5")
        while self.v.cmd is not None:
            if not self.v.input_text("N"):
                self.v.cmd.enter()
        with self.p.edit("I/O list") as ed:
            made = io_list.place(ed, self.p, [("2", "1734-IB8", mod, [], {})])
        e = made[0].inserts()[0]
        self.assertEqual(e.defn.kind, "symbol")
        self.assertEqual(e.block_name, "1734-IB8 module")
        self.assertTrue(e.pin_points())

    # ---- Edit block, Block properties, Update blocks from library on each kind ------------
    def test_block_properties_and_update_each_kind(self):
        from kanzonascad import library_panel
        s = self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5")
        for kind, sheet, e in (("footprint", self.panel, f), ("symbol", self.sch, s)):
            self.v.show_sheet(sheet.id)
            self.v.set_selection({e.id})
            t = self.win._block_target()
            self.assertEqual((t[0], t[1].kind, t[1].name), (kind, kind, "Starter"))
            real = library_panel.QDialog.exec
            library_panel.QDialog.exec = lambda dlg: QDialog.Accepted
            try:
                with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                    new = self.win.block_properties()
            finally:
                library_panel.QDialog.exec = real
            self.assertEqual((new.name, new.kind), ("Starter", kind))
        self.assertEqual(self.kinds(), {"Starter": "symbol", "Starter (footprint)": "footprint"})
        # the library's footprint changed: Update blocks from library takes it for the
        # footprint only, then the symbol's for the symbol only
        self.lib.save_block(fp(w=4.0))
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(self.win.update_blocks_from_library(), 1)
        self.assertEqual(width(self.panel.entities[f.id]), 4.0)
        self.assertEqual(width(self.sch.entities[s.id]), 0.5)
        wide = sym()
        wide.entities = [M.Line((0, 0), (0.75, 0))]
        self.lib.save_block(wide)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(self.win.update_blocks_from_library(), 1)
        self.assertEqual(width(self.sch.entities[s.id]), 0.75)
        self.assertEqual(width(self.panel.entities[f.id]), 4.0)

    def test_edit_block_of_each_kind(self):
        s = self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5")
        for kind, sheet, e in (("footprint", self.panel, f), ("symbol", self.sch, s)):
            self.v.show_sheet(sheet.id)
            self.v.set_selection({e.id})
            d = self.win.edit_block()
            self.assertEqual((d.block_session.kind, d.block_session.name), (kind, "Starter"))
            self.win.tabs.setCurrentWidget(d)
            self.win.close_tab(self.win.tabs.indexOf(d))
            self.win.tabs.setCurrentIndex(0)

    def test_edit_block_not_in_the_library(self):
        # (a footprint the library hasn't got: its own copy opened under its own name)
        self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5")
        self.lib.delete_block("footprint", "Starter")
        self.v.show_sheet(self.panel.id)
        self.v.set_selection({f.id})
        kind, lib, own = self.win._block_target()
        self.assertEqual((kind, lib, own.name, own.kind), ("footprint", None, "Starter",
                                                           "footprint"))

    # ---- files ----------------------------------------------------------------------------
    def test_save_open_undo_redo(self):
        self.insert("symbol", "3,3")
        before = self.p.to_dict()
        self.insert("footprint", "5,5")
        path = os.path.join(tempfile.mkdtemp(), "same.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual({n: b.kind for n, b in q.blocks.items() if n.startswith("Starter")},
                         {"Starter": "symbol", "Starter (footprint)": "footprint"})
        got = {e.block: e.defn.kind for s in q.sheets for e in s.inserts()}
        self.assertEqual(got, {"Starter": "symbol", "Starter (footprint)": "footprint"})
        after = self.p.to_dict()
        self.p.undo()
        self.assertEqual(self.kinds(), {"Starter": "symbol"})
        self.assertEqual(self.p.to_dict()["blocks"], before["blocks"])
        self.p.redo()
        self.assertEqual(self.p.to_dict(), after)
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.kinds(), {})
        self.p.redo()
        self.p.redo()
        self.assertEqual(self.p.to_dict(), after)

    def test_dxf_export_both(self):
        import ezdxf
        self.insert("symbol", "3,3")
        self.insert("footprint", "5,5")
        out = tempfile.mkdtemp()
        for sheet in (self.sch, self.panel):
            path = os.path.join(out, "%s.dxf" % sheet.kind)
            fileio.export_dxf(self.p, sheet, path)
            doc = ezdxf.readfile(path)
            names = {r.dxf.name for r in doc.modelspace().query("INSERT")}
            want = "Starter" if sheet is self.sch else "Starter (footprint)"
            self.assertIn(want, names)
            self.assertIn("KanzonasCAD %s" % ("symbol" if sheet is self.sch else "footprint"),
                          doc.blocks.get(want).block.dxf.description)

    # ---- what people read -----------------------------------------------------------------
    def test_bom_label_props_trace_and_lists(self):
        s = self.insert("symbol", "3,3")
        f = self.insert("footprint", "5,5", link=True)
        f = self.panel.entities[f.id]
        self.assertEqual(f.attrs.get("PARENT"), self.sch.entities[s.id].attrs.get("DEV"))
        rows = bom.parts(self.p)
        self.assertTrue(rows)
        self.assertEqual({r["block"] for r in rows}, {"Starter"})
        # the footprint's label showing its block's name
        self.assertEqual(f.copy(label="name").label_value(), "Starter")
        # the Properties panel's Block line
        from kanzonascad import props_panel
        field = props_panel.block_fields(self.win, self.p, self.panel, [f])[0]
        self.assertEqual((field.key, field.get(f)), ("block", "Starter"))
        # Trace: the device's rows name it by its own name
        for sheet, e in ((self.panel, f), (self.sch, self.sch.entities[s.id])):
            subj = where_used.subject_of(self.p, sheet, e)
            self.assertIsNotNone(subj)
        self.assertEqual(where_used._desc(f.copy(attrs={})), "Starter")
        # Devices without a footprint: the device has one (same name as its symbol)
        from kanzonascad import missing_fp
        self.assertEqual(missing_fp.find(self.p).missing, [])
        with self.p.edit("unlink") as ed:
            ed.remove(self.panel, f.id)
        self.assertEqual([r[2] for r in missing_fp.rows(self.p)], ["Starter"])

    def test_save_as_part_takes_the_footprints_own_name(self):
        s = self.insert("symbol", "3,3")
        self.insert("footprint", "5,5", link=True)
        self.lib.delete_block("footprint", "Starter")
        with self.p.edit("cat") as ed:
            e = self.sch.entities[s.id]
            ed.change(self.sch, e.copy(attrs=dict(e.attrs, CAT="100-C09")))
        self.v.show_sheet(self.sch.id)
        self.v.set_selection({s.id})
        part = self.win.save_as_part()
        try:
            self.assertEqual((part.symbol, part.footprint), ("Starter", "Starter"))
            got = self.lib.get("footprint", "Starter")
            self.assertEqual((got.name, got.kind, got.extents()[2]), ("Starter", "footprint",
                                                                     2.0))
            self.assertIsNone(self.lib.get("footprint", "Starter (footprint)"))
        finally:
            self.lib.delete_part(part.id)

    # ---- a project that lost one before ---------------------------------------------------
    def lost_project(self):
        """A project as an older version left it: the footprint "Starter" made over the
        symbol "Starter", its symbol copies drawing the footprint."""
        p = M.Project.new()
        panel = p.make_sheet("Panel")
        panel.kind = "panel"
        p.sheets.append(panel)
        d = fp()
        p.blocks["Starter"] = d
        p.sheets[0].entities[1] = M.Insert("Starter", (3, 3), defn=d, attrs={"TAG": "M601"},
                                           id=1)
        panel.entities[1] = M.Insert("Starter", (5, 5), defn=d, id=1)
        path = os.path.join(tempfile.mkdtemp(), "old.kzcad")
        p.save(path, backups=0)
        return path

    def test_lost_one_put_back_on_open(self):
        d = self.win.open_path(self.lost_project())
        q = d.project
        sch, panel = q.sheets[0], q.sheets[1]
        self.assertEqual(sch.entities[1].defn.kind, "symbol")
        self.assertEqual(sch.entities[1].block, "Starter (symbol)")
        self.assertEqual(sch.entities[1].attrs["TAG"], "M601")
        self.assertEqual(width(sch.entities[1]), 0.5)
        self.assertEqual(panel.entities[1].defn.kind, "footprint")
        self.assertTrue(any("put back" in t for t in self.said), self.said)
        self.assertIn("put back", self.win.cmdline.history.toPlainText())
        self.assertTrue(q.is_modified())
        q.undo()                                        # (one step: Undo takes it back)
        self.assertEqual(q.sheets[0].entities[1].defn.kind, "footprint")
        # saved and opened again: nothing more to put back
        q.redo()
        q.save(q.path, backups=0)
        self.assertEqual(BE.lost_kinds(M.Project.load(q.path), self.lib), ([], []))

    def test_lost_one_the_library_has_not(self):
        path = self.lost_project()
        self.lib.delete_block("symbol", "Starter")
        d = self.win.open_path(path)
        self.assertEqual(d.project.sheets[0].entities[1].defn.kind, "footprint")
        self.assertFalse(d.project.is_modified())
        self.assertTrue(any("has no symbol Starter" in t for t in self.said), self.said)

    def test_symbols_on_panel_sheets_alone_left_alone(self):
        # (a symbol placed on a panel sheet only, with a footprint of its name in the
        # library: not a lost one)
        self.v.show_sheet(self.panel.id)
        self.win.library_panel.insertRequested.emit(self.lib.get("symbol", "Starter"), {})
        type_in(self.v, "3,3")
        while self.v.cmd is not None:
            self.v.cmd.enter()
        self.assertEqual(BE.lost_kinds(self.p, self.lib), ([], []))


if __name__ == "__main__":
    unittest.main()
