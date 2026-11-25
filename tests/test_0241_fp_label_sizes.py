"""A footprint's label lines each at a text size of their own (the owner, 0.24.1: "I need to be
able to edit footprint rating font sizes. Both in the footprint block itself and the ability
to override individually its instances"): a size per line in the block (Block properties,
Label text sizes), one per line on a copy (its attributes window), else the project's
Footprint label height; paper inches, so a 1:4 panel sheet draws them four times larger."""
import json
import math
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QCheckBox, QDialog, QDoubleSpinBox, QMessageBox, QTableWidget

from tests.util import APP, window

from kanzonascad import model as M

NAME = "Battery 0241 starter"


def block(sizes=None):
    return M.BlockDef(NAME, "footprint", [M.Polyline([(0, 0), (3, 0), (3, 4), (0, 4)], True)],
                      tag_pos=(1.5, 2.0), catalog="100-C09", label_sizes=sizes)


def old_texts(ins):
    """label_texts as 0.24 worked them out (every line tag_h tall, stacked LABEL_LINE apart):
    [(key, text, x, y, height)], to compare an old project with."""
    d = ins.defn
    keys = [k for k in M.label_keys(ins.label) if ins.label_value(k) is not None]
    h = ins.tag_h or 0.125
    bx, by = ins.to_world(d.label_point())
    # (read upward: the lines go to the right)
    ang = math.radians(90.0 if 45.0 <= ins.angle % 180.0 < 135.0 else 0.0)
    out = []
    for i, k in enumerate(keys):
        at = ins.attr_at.get("@" + k.upper())
        off = (i - (len(keys) - 1) / 2.0) * M.LABEL_LINE * h
        if at:
            q = ins.to_world(at[:2])
        else:
            q = (bx + math.sin(ang) * off, by - math.cos(ang) * off)
        out.append((k, ins.label_value(k), q[0], q[1], h))
    return out


def texts(ins):
    return [(k, t.text, t.pos[0], t.pos[1], t.height) for k, t in ins.label_texts()]


class Base(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library
        with self.p.edit("block") as ed:
            ed.block(block())
            self.fp = ed.add(self.s, M.Insert(NAME, (10, 10), defn=self.p.blocks[NAME],
                                              attrs={"TAG": "M1", "HP": "5", "VOLTS": "480"},
                                              tag_h=0.08, label="tag,HP,VOLTS"))

    def tearDown(self):
        self.lib.delete_block("footprint", NAME)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def now(self, sheet=None):
        return (sheet or self.s).entities[self.fp.id]

    def heights(self, sheet=None):
        return {k: t.height for k, t in self.now(sheet).label_texts()}

    def set_block_sizes(self, sizes):
        with self.p.edit("sizes") as ed:
            ed.block(M.BlockDef.from_dict(dict(self.p.blocks[NAME].to_dict(),
                                               label_sizes=sizes)))

    def set_copy_sizes(self, sizes, sheet=None):
        with self.p.edit("copy sizes") as ed:
            ed.change(sheet or self.s, self.now(sheet).copy(label_sizes=sizes))


class PrecedenceTest(Base):
    def test_the_copys_then_the_blocks_then_the_projects(self):
        self.assertEqual(self.heights(), {"tag": 0.08, "HP": 0.08, "VOLTS": 0.08})
        self.set_block_sizes({"HP": 0.15, "TAG": 0.12})
        self.assertEqual(self.heights(), {"tag": 0.12, "HP": 0.15, "VOLTS": 0.08})
        self.set_copy_sizes({"HP": 0.2})
        self.assertEqual(self.heights(), {"tag": 0.12, "HP": 0.2, "VOLTS": 0.08})
        self.assertEqual(self.now().label_size("hp"), (0.2, "copy"))
        self.assertEqual(self.now().label_size("tag"), (0.12, "block"))
        self.assertEqual(self.now().label_size("VOLTS"), (None, "project"))

    def test_the_project_setting_changes_only_lines_without_a_size(self):
        self.set_block_sizes({"TAG": 0.12})
        self.set_copy_sizes({"HP": 0.2})
        with self.p.edit("height") as ed:
            ed.project_settings({"fp_label_height": 0.1})
        self.assertEqual(self.heights(), {"tag": 0.12, "HP": 0.2, "VOLTS": 0.1})

    def test_undo_and_redo(self):
        self.set_block_sizes({"TAG": 0.12})
        self.set_copy_sizes({"HP": 0.2})
        after = self.heights()
        self.p.undo()
        self.assertEqual(self.heights(), {"tag": 0.12, "HP": 0.08, "VOLTS": 0.08})
        self.p.undo()
        self.assertEqual(self.heights(), {"tag": 0.08, "HP": 0.08, "VOLTS": 0.08})
        self.p.redo()
        self.p.redo()
        self.assertEqual(self.heights(), after)

    def test_moved_turned_and_copied_keep_their_sizes(self):
        self.set_copy_sizes({"HP": 0.2})
        with self.p.edit("move") as ed:
            ed.change(self.s, self.now().copy(pos=(20, 5), angle=90.0))
        self.assertEqual(self.heights()["HP"], 0.2)
        self.assertEqual(self.now().label_texts()[1][1].angle, 90.0)

    def test_mixed_sizes_stack_without_overlapping(self):
        self.set_copy_sizes({"HP": 0.3})
        got = self.now().label_texts()
        boxes = [t.bbox() for _k, t in got]
        for a, b in zip(boxes, boxes[1:]):
            self.assertGreater(a[1], b[3], "a line overlaps the one under it: %r" % boxes)
        # each two neighbors' middles LABEL_LINE times their mean height apart, the stack
        # centered on the label spot
        hs = [t.height for _k, t in got]
        ys = [t.pos[1] for _k, t in got]
        for i in range(2):
            self.assertAlmostEqual(ys[i] - ys[i + 1], M.LABEL_LINE * (hs[i] + hs[i + 1]) / 2)
        spot = self.now().to_world(self.now().defn.label_point())[1]
        top, bottom = ys[0] + M.LABEL_LINE * hs[0] / 2, ys[-1] - M.LABEL_LINE * hs[-1] / 2
        self.assertAlmostEqual((top + bottom) / 2, spot)

    def test_a_dragged_line_keeps_its_place_and_takes_its_size(self):
        self.set_copy_sizes({"HP": 0.3})
        with self.p.edit("drag") as ed:
            ed.change(self.s, self.now().copy(attr_at={"@HP": (0.5, -1.0)}))
        t = dict(self.now().label_texts())["HP"]
        self.assertEqual((t.pos, t.height), ((10.5, 9.0), 0.3))

    def test_grips_bbox_and_index_follow_the_size(self):
        small = self.now().bbox()
        self.set_copy_sizes({"HP": 3.0})
        e = self.now()
        self.assertGreater(e.bbox()[2] - e.bbox()[0], small[2] - small[0])
        grips = dict(e.text_grips())
        self.assertEqual(grips["@HP"], dict(e.label_texts())["HP"].pos)
        # found by a window around its big text only, through the sheet's index
        t = dict(e.label_texts())["HP"].bbox()
        self.assertIn(e.id, {x.id for x in self.s.query((t[0], t[1], t[0] + 0.05, t[3]))})


class OldProjectTest(Base):
    def test_an_old_project_reads_as_before(self):
        # a project as 0.24 saved it: no label sizes, no label_k
        with self.p.edit("more") as ed:
            ed.change(self.s, self.now().copy(attr_at={"@VOLTS": (0.2, 0.3)}))
            ed.add(self.s, M.Insert(NAME, (20, 10), 90.0, defn=self.p.blocks[NAME],
                                    attrs={"TAG": "M2", "HP": "3"}, tag_h=0.08,
                                    label="HP,tag,cat"))
        d = self.p.to_dict()
        for sd in d["sheets"]:
            for ed_ in sd["entities"]:
                ed_.pop("label_k", None)
                self.assertNotIn("label_sizes", ed_)
        for b in d["blocks"]:
            self.assertNotIn("label_sizes", b)
        q = M.Project.from_dict(json.loads(json.dumps(d)))
        got = [e for e in q.sheets[0].inserts() if e.label]
        self.assertEqual(len(got), 2)
        for e in got:
            self.assertEqual(texts(e), old_texts(e))
            self.assertEqual(e.label_k, 1.0)
        # and as it was in this project
        for e in got:
            self.assertEqual(texts(e), texts(self.s.entities[e.id]))

    def test_an_old_block_reads_as_before(self):
        d = block().to_dict()
        self.assertNotIn("label_sizes", d)
        self.assertEqual(M.BlockDef.from_dict(d).label_sizes, {})


class FilesTest(Base):
    def test_save_and_open(self):
        self.set_block_sizes({"TAG": 0.12})
        self.set_copy_sizes({"HP": 0.2})
        before = texts(self.now())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.kzcad")
            self.p.save(path)
            q = M.Project.load(path)
        self.assertEqual(q.blocks[NAME].label_sizes, {"TAG": 0.12})
        e = q.sheets[0].entities[self.fp.id]
        self.assertEqual(e.label_sizes, {"HP": 0.2})
        self.assertEqual(texts(e), before)

    def test_kzblock(self):
        self.lib.save_block(block({"HP": 0.15, "tag": 0.1}))
        got = self.lib.get("footprint", NAME)
        self.assertEqual(got.label_sizes, {"HP": 0.15, "TAG": 0.1})
        with open(self.lib._path("footprint", NAME), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["label_sizes"], {"HP": 0.15, "TAG": 0.1})

    def test_dxf_text_heights(self):
        import ezdxf
        from kanzonascad import fileio
        self.set_block_sizes({"TAG": 0.12})
        self.set_copy_sizes({"HP": 0.2})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.dxf")
            fileio.export_dxf(self.p, self.s, path)
            doc = ezdxf.readfile(path)
        ref = [i for i in doc.modelspace().query("INSERT") if i.dxf.name.startswith("Battery")]
        self.assertEqual(len(ref), 1)
        got = {a.dxf.tag: round(a.dxf.height, 9) for a in ref[0].attribs if not a.is_invisible}
        self.assertEqual((got["TAG"], got["HP"], got["VOLTS"]), (0.12, 0.2, 0.08))


class ScaledSheetTest(Base):
    def test_a_quarter_scale_panel_sheet(self):
        with self.p.edit("panel") as ed:
            panel = ed.add_sheet(M.Sheet(title="Panel"))
            ed.sheet_meta(panel, scale=0.25, kind="panel")
            # (placed there, as Insert places it: its tag_h the sheet's, its label_k too)
            fp = ed.add(panel, self.now().copy(id=None, tag_h=0.08 * 4, label_k=None))
        self.assertEqual(fp.label_k, 4.0)
        with self.p.edit("sizes") as ed:
            ed.change(panel, fp.copy(label_sizes={"HP": 0.2}))
        self.set_block_sizes({"TAG": 0.12})
        e = panel.entities[fp.id]
        self.assertEqual({k: round(t.height, 9) for k, t in e.label_texts()},
                         {"tag": 0.48, "HP": 0.8, "VOLTS": 0.32})
        # on the 1:1 sheet the same block's size is drawn as it is
        self.assertEqual(self.heights()["tag"], 0.12)
        # the sheet's scale changed: everything paper-sized follows
        with self.p.edit("scale") as ed:
            ed.sheet_scale(panel, 0.5)
        e = panel.entities[fp.id]
        self.assertEqual({k: round(t.height, 9) for k, t in e.label_texts()},
                         {"tag": 0.24, "HP": 0.4, "VOLTS": 0.16})
        # and kept on paper size off, nothing changes (as the other texts)
        with self.p.edit("scale") as ed:
            ed.sheet_scale(panel, 0.25, paper_text=False)
        e = panel.entities[fp.id]
        self.assertEqual({k: round(t.height, 9) for k, t in e.label_texts()},
                         {"tag": 0.24, "HP": 0.4, "VOLTS": 0.16})
        # saved and opened: the same
        q = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(texts(q.sheet_by_id(panel.id).entities[fp.id]), texts(e))
        # the project's height changed: on paper, its sheet's scale times it
        with self.p.edit("height") as ed:
            ed.project_settings({"fp_label_height": 0.1})
        e = panel.entities[fp.id]
        self.assertEqual({k: round(t.height, 9) for k, t in e.label_texts()},
                         {"tag": 0.48, "HP": 0.8, "VOLTS": 0.4})


class DialogTest(Base):
    def test_block_properties_label_text_sizes(self):
        self.lib.save_block(block())
        seen = {}

        def answer(dlg):
            t = dlg.findChild(QTableWidget, "label_sizes")
            seen["enabled"] = t.isEnabled()
            seen["lines"] = [t.item(r, 0).text() for r in range(t.rowCount())]
            dlg.findChild(QDoubleSpinBox, "label_size_HP").setValue(0.15)
            dlg.findChild(QDoubleSpinBox, "label_size_TAG").setValue(0.1)
            return QDialog.Accepted
        steps = len(self.p.undo_stack)
        with mock.patch.object(QDialog, "exec", answer), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            new = self.win.block_properties("footprint", NAME)
        self.assertTrue(seen["enabled"])
        self.assertEqual(seen["lines"][:2], ["Tag", "Part number"])
        self.assertIn("Horsepower", seen["lines"])
        self.assertEqual(new.label_sizes, {"HP": 0.15, "TAG": 0.1})
        self.assertEqual(self.lib.get("footprint", NAME).label_sizes, {"HP": 0.15, "TAG": 0.1})
        # the drawing's copy took it (Update: yes), one step
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.heights(), {"tag": 0.1, "HP": 0.15, "VOLTS": 0.08})
        self.p.undo()
        self.assertEqual(self.heights(), {"tag": 0.08, "HP": 0.08, "VOLTS": 0.08})

    def test_block_properties_blank_means_the_projects(self):
        self.lib.save_block(block({"HP": 0.15}))

        def answer(dlg):
            b = dlg.findChild(QDoubleSpinBox, "label_size_HP")
            self.assertEqual(b.value(), 0.15)
            b.setValue(0.0)
            self.assertEqual(b.text(), "the project's")
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", answer), \
                mock.patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            new = self.win.block_properties("footprint", NAME)
        self.assertEqual(new.label_sizes, {})

    def test_the_copys_attributes_window(self):
        self.set_block_sizes({"TAG": 0.12})
        seen = {}

        def answer(dlg):
            tag = dlg.findChild(QDoubleSpinBox, "label_size_TAG")
            hp = dlg.findChild(QDoubleSpinBox, "label_size_HP")
            seen["blank"] = (tag.text(), hp.text())
            seen["all"] = dlg.findChild(QCheckBox, "label_sizes_all")
            hp.setValue(0.25)
            return QDialog.Accepted
        steps = len(self.p.undo_stack)
        with mock.patch.object(QDialog, "exec", answer):
            self.win.edit_attributes(self.now())
        self.assertEqual(seen["blank"], ('the block\'s (0.120")', 'the project\'s (0.080")'))
        self.assertIsNone(seen["all"])                  # (nothing else selected)
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.now().label_sizes, {"HP": 0.25})
        self.assertEqual(self.heights(), {"tag": 0.12, "HP": 0.25, "VOLTS": 0.08})
        self.p.undo()
        self.assertEqual(self.now().label_sizes, {})

    def test_several_selected_footprints(self):
        with self.p.edit("more") as ed:
            other = ed.add(self.s, self.now().copy(id=None, pos=(20, 10),
                                                   label_sizes={"VOLTS": 0.3, "HP": 0.4}))
            third = ed.add(self.s, self.now().copy(id=None, pos=(30, 10)))
        self.set_copy_sizes({"HP": 0.2})
        self.v.set_selection({self.fp.id, other.id, third.id})

        def answer(dlg):
            dlg.findChild(QDoubleSpinBox, "label_size_TAG").setValue(0.11)
            dlg.findChild(QDoubleSpinBox, "label_size_HP").setValue(0.0)
            self.assertTrue(dlg.findChild(QCheckBox, "label_sizes_all").isChecked())
            return QDialog.Accepted
        steps = len(self.p.undo_stack)
        with mock.patch.object(QDialog, "exec", answer):
            self.win.edit_attributes(self.now())
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.now().label_sizes, {"TAG": 0.11})
        # the changed ones (TAG set, HP cleared) go to the others; their own VOLTS stays
        self.assertEqual(self.s.entities[other.id].label_sizes, {"TAG": 0.11, "VOLTS": 0.3})
        self.assertEqual(self.s.entities[third.id].label_sizes, {"TAG": 0.11})
        self.p.undo()
        self.assertEqual(self.s.entities[other.id].label_sizes, {"VOLTS": 0.3, "HP": 0.4})

    def test_several_selected_left_alone_when_unticked(self):
        with self.p.edit("more") as ed:
            other = ed.add(self.s, self.now().copy(id=None, pos=(20, 10)))
        self.v.set_selection({self.fp.id, other.id})

        def answer(dlg):
            dlg.findChild(QDoubleSpinBox, "label_size_TAG").setValue(0.11)
            dlg.findChild(QCheckBox, "label_sizes_all").setChecked(False)
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", answer):
            self.win.edit_attributes(self.now())
        self.assertEqual(self.now().label_sizes, {"TAG": 0.11})
        self.assertEqual(self.s.entities[other.id].label_sizes, {})


class AngleTest(Base):
    """A label line turned on its own copy (the owner, 0.24.1: "I also reoriented the label 90
    degrees and it reverted back"; then "Option 2, but overridable": kept readable unless Keep
    readable is unticked for it)."""

    def angles(self, sheet=None):
        return {k: t.angle for k, t in self.now(sheet).label_texts()}

    def turn(self, key, angle, as_set=None):
        e = self.now().with_attr_angle("@" + key, angle)
        if as_set is not None:
            e = e.copy(label_as_set=as_set)
        with self.p.edit("turn") as ed:
            ed.change(self.s, e)

    def window(self, fill):
        seen = {}

        def answer(dlg):
            fill(dlg, seen)
            return QDialog.Accepted
        with mock.patch.object(QDialog, "exec", answer):
            self.win.edit_attributes(self.now())
        return seen

    def test_the_windows_angle_is_kept(self):
        steps = len(self.p.undo_stack)
        self.window(lambda dlg, _s: dlg.findChild(QDoubleSpinBox, "label_angle_HP")
                    .setValue(90.0))
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        self.assertEqual(self.angles(), {"tag": 0.0, "HP": 90.0, "VOLTS": 0.0})
        # drawn so (a repaint draws world_entities), and the window shows it again
        hp = dict(self.now().label_texts())["HP"].text
        self.assertEqual([t.angle for t in self.now().world_entities()
                          if isinstance(t, M.Text) and t.text == hp], [90.0])
        seen = self.window(lambda dlg, seen: seen.update(
            angle=dlg.findChild(QDoubleSpinBox, "label_angle_HP").value(),
            tick=dlg.findChild(QCheckBox, "label_readable_HP").isChecked()))
        self.assertEqual(seen, {"angle": 90.0, "tick": True})
        self.p.undo()
        self.assertEqual(self.angles()["HP"], 0.0)
        self.p.redo()
        self.assertEqual(self.angles()["HP"], 90.0)

    def test_the_window_shows_an_unturned_lines_angle(self):
        with self.p.edit("turn") as ed:
            ed.change(self.s, self.now().copy(angle=90.0))
        seen = self.window(lambda dlg, seen: seen.update(
            angle=dlg.findChild(QDoubleSpinBox, "label_angle_HP").value()))
        self.assertEqual(seen["angle"], 90.0)
        self.assertEqual(self.now().attr_rot, {})       # (nothing turned of its own)

    def test_kept_readable_or_as_set(self):
        for ang, readable, as_set in ((0.0, 0.0, 0.0), (90.0, 90.0, 90.0), (180.0, 0.0, 180.0),
                                      (270.0, 90.0, 270.0), (135.0, 315.0, 135.0)):
            self.turn("HP", ang, as_set=[])
            self.assertAlmostEqual(self.angles()["HP"], readable, msg=ang)
            self.turn("HP", ang, as_set=["HP"])
            self.assertAlmostEqual(self.angles()["HP"], as_set, msg=ang)
            self.assertEqual(self.angles()["tag"], 0.0)
        # (flipped about its own middle: the same spot)
        self.turn("HP", 180.0, as_set=[])
        a = dict(self.now().label_texts())["HP"]
        self.turn("HP", 180.0, as_set=["HP"])
        b = dict(self.now().label_texts())["HP"]
        self.assertEqual((a.pos, a.align, a.valign), (b.pos, b.align, b.valign))

    def test_the_keep_readable_tick_box(self):
        def fill(dlg, _seen):
            dlg.findChild(QDoubleSpinBox, "label_angle_HP").setValue(180.0)
            dlg.findChild(QCheckBox, "label_readable_HP").setChecked(False)
        self.window(fill)
        self.assertEqual(self.now().label_as_set, {"HP"})
        self.assertEqual(self.angles()["HP"], 180.0)
        self.window(lambda dlg, _s: dlg.findChild(QCheckBox, "label_readable_HP")
                    .setChecked(True))
        self.assertEqual(self.now().label_as_set, set())
        self.assertEqual(self.angles()["HP"], 0.0)

    def test_a_footprint_turned_over_reads_as_before(self):
        for a, want in ((180.0, 0.0), (270.0, 90.0), (90.0, 90.0)):
            with self.p.edit("turn") as ed:
                ed.change(self.s, self.now().copy(angle=a, label_as_set=["TAG", "HP"]))
            self.assertEqual(set(self.angles().values()), {want}, a)

    def test_it_turns_with_the_footprint(self):
        from kanzonascad import commands as C
        self.turn("HP", 90.0, as_set=["HP"])
        self.v.set_selection({self.fp.id})
        self.v.run(C.RotateCmd)
        self.v.cmd.point((10.0, 10.0))
        self.v.cmd.number(90.0)
        self.assertEqual(self.now().angle, 90.0)
        self.assertEqual(self.angles(), {"tag": 90.0, "HP": 180.0, "VOLTS": 90.0})
        with self.p.edit("readable") as ed:
            ed.change(self.s, self.now().copy(label_as_set=[]))
        self.assertEqual(self.angles()["HP"], 0.0)

    def test_kept_through_moves_grips_files_and_settings(self):
        self.turn("HP", 90.0, as_set=["HP"])
        with self.p.edit("move") as ed:
            ed.change(self.s, self.now().moved(3.0, 1.0))
        grips = self.now().text_grips()
        i = [n for n, _q in grips].index("@HP")
        with self.p.edit("grip") as ed:
            ed.change(self.s, self.now().with_grip(i + 1, (16.0, 8.0)))
        with self.p.edit("settings") as ed:
            ed.project_settings({"fp_label_height": 0.1, "fp_label_color": "#ffff00"})
        self.assertEqual(self.angles()["HP"], 90.0)
        self.assertEqual(dict(self.now().label_texts())["HP"].pos, (16.0, 8.0))
        self.lib.save_block(block({"HP": 0.15}))
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.win.update_blocks_from_library()
        self.assertEqual(self.angles()["HP"], 90.0)
        self.assertEqual(self.now().label_as_set, {"HP"})
        q = M.Project.from_dict(json.loads(json.dumps(self.p.to_dict())))
        self.assertEqual(texts(q.sheets[0].entities[self.fp.id]), texts(self.now()))
        self.assertEqual({k: t.angle for k, t in q.sheets[0].entities[self.fp.id]
                          .label_texts()}, self.angles())
        # its box is the turned text's: tall, not wide
        t = dict(self.now().label_texts())["HP"].bbox()
        self.assertGreater(t[3] - t[1], t[2] - t[0])

    def test_dxf_rotation(self):
        import ezdxf
        from kanzonascad import fileio
        self.turn("HP", 270.0, as_set=[])
        self.turn("VOLTS", 270.0, as_set=["VOLTS"])
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "p.dxf")
            fileio.export_dxf(self.p, self.s, path)
            doc = ezdxf.readfile(path)
        ref = [i for i in doc.modelspace().query("INSERT") if i.dxf.name.startswith("Battery")]
        got = {a.dxf.tag: round(a.dxf.rotation, 6) for a in ref[0].attribs
               if not a.is_invisible}
        self.assertEqual((got["TAG"], got["HP"], got["VOLTS"]), (0.0, 90.0, 270.0))


class UpdateFromLibraryTest(Base):
    def test_update_blocks_from_library_brings_the_sizes(self):
        self.lib.save_block(block({"HP": 0.15}))
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertEqual(self.win.update_blocks_from_library(), 1)
        self.assertEqual(self.p.blocks[NAME].label_sizes, {"HP": 0.15})
        self.assertEqual(self.heights()["HP"], 0.15)
        self.p.undo()
        self.assertEqual(self.heights()["HP"], 0.08)


if __name__ == "__main__":
    unittest.main()
