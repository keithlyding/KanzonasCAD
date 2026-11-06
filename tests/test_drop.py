"""DXF and DWG files dragged in from Explorer (the owner: "drag a dxf or even a dwg file from
Explorer into KanzonasCAD and it import in"): dropped on the drawing, imported there and
selected; dropped elsewhere, opened as a project of its own."""
import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtCore import QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent

from tests.util import APP, window

from kanzonascad import model as M


def dxf(name="part.dxf", w=4.0, h=2.0):
    import ezdxf
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 1
    ms = doc.modelspace()
    ms.add_lwpolyline([(100, 100), (100 + w, 100), (100 + w, 100 + h), (100, 100 + h)],
                      close=True)
    ms.add_line((100, 100), (100 + w, 100 + h))
    path = os.path.join(tempfile.mkdtemp(), name)
    doc.saveas(path)
    return path


def mime(*paths):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(p) for p in paths])
    return m


class DropTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            p = self.win.tabs.widget(i).project
            p.saved_at = len(p.undo_stack)
        self.win.close()

    def drop(self, m, widget_pos):
        """A drop at a point of the view (or, with None, on the tab bar)."""
        if widget_pos is None:
            pos = self.win.tabs.tabBar().mapTo(self.win, self.win.tabs.tabBar().rect().center())
        else:
            pos = self.v.mapTo(self.win, widget_pos)
        ev = QDropEvent(QPointF(pos), Qt.CopyAction, m, Qt.LeftButton, Qt.NoModifier)
        self.win.dropEvent(ev)
        return ev

    def test_takes_only_drawings_and_projects(self):
        txt = os.path.join(tempfile.mkdtemp(), "notes.txt")
        open(txt, "w").close()
        self.assertEqual(self.win._dropped_paths(mime(txt)), [])
        path = dxf()
        self.assertEqual(self.win._dropped_paths(mime(path, txt)), [path])
        good, bad = mime(path), mime(txt)        # (kept: the event doesn't own its data)
        ev = QDragEnterEvent(self.win.rect().center(), Qt.CopyAction, good,
                             Qt.LeftButton, Qt.NoModifier)
        self.win.dragEnterEvent(ev)
        self.assertTrue(ev.isAccepted())
        ev = QDragEnterEvent(self.win.rect().center(), Qt.CopyAction, bad,
                             Qt.LeftButton, Qt.NoModifier)
        self.win.dragEnterEvent(ev)
        self.assertFalse(ev.isAccepted())

    def test_dropped_on_the_drawing_lands_where_let_go(self):
        path = dxf()
        tabs = self.win.tabs.count()
        steps = len(self.p.undo_stack)
        pos = self.v.rect().center()
        where = self.v.to_world(pos)
        self.drop(mime(path), pos)
        self.assertEqual(self.win.tabs.count(), tabs)            # (no new project)
        self.assertEqual(len(self.p.undo_stack), steps + 1)      # one step
        sel = [self.s.entities[i] for i in self.v.sel]
        self.assertEqual(len(sel), 2)                            # selected
        bb = None
        from kanzonascad import geometry as G
        for e in sel:
            bb = G.bbox_union(bb, e.bbox())
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, where[0])
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, where[1])
        self.assertAlmostEqual(bb[2] - bb[0], 4.0)               # real size
        self.p.undo()
        self.assertFalse(any(i in self.s.entities for i in (e.id for e in sel)))

    def test_several_go_side_by_side(self):
        a, b = dxf("a.dxf"), dxf("b.dxf", 6.0, 3.0)
        m = mime(a, b)
        self.drop(m, self.v.rect().center())
        from kanzonascad import geometry as G
        ents = sorted((self.s.entities[i] for i in self.v.sel), key=lambda e: e.bbox()[0])
        self.assertEqual(len(ents), 4)
        left = G.bbox_union(ents[0].bbox(), ents[1].bbox())
        right = G.bbox_union(ents[2].bbox(), ents[3].bbox())
        self.assertGreater(right[0], left[2])                    # no overlap

    def test_dropped_elsewhere_opens_its_own_project(self):
        path = dxf()
        tabs = self.win.tabs.count()
        steps = len(self.p.undo_stack)
        m = mime(path)
        self.drop(m, None)
        self.assertEqual(self.win.tabs.count(), tabs + 1)
        self.assertEqual(len(self.p.undo_stack), steps)          # (this project untouched)

    def test_a_project_opens(self):
        path = os.path.join(tempfile.mkdtemp(), "job.kzcad")
        M.Project.new().save(path)
        tabs = self.win.tabs.count()
        m = mime(path)
        self.drop(m, self.v.rect().center())
        self.assertEqual(self.win.tabs.count(), tabs + 1)

    def test_unreadable_file_is_told(self):
        bad = os.path.join(tempfile.mkdtemp(), "bad.dxf")
        with open(bad, "w") as f:
            f.write("not a dxf")
        warned = []
        with mock.patch("kanzonascad.main_window.QMessageBox.warning",
                        lambda *a, **k: warned.append(a[2])):
            self.assertEqual(self.win.drop_files([bad], (1.0, 1.0)), [])
        self.assertIn("Couldn't read", warned[0])


if __name__ == "__main__":
    unittest.main()
