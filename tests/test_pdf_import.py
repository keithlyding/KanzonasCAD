"""Import PDF into this sheet... (the owner, Nov 2026: "a feature ... that literally only does
lines and text. That way, I can pull in a picture, PDF, screenshot, whatever of a drawing or
schematic"; this is the PDF part). Pages written byte by byte (tests/pdf_samples.py), so what
each must give is known exactly, and the program's own PDF export read back."""
import os
import sys
import tempfile
import unittest

from tests.util import APP, window

from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import pdf_import as P
from kanzonascad.pdf_samples import Page, write_pdf

IN = 72.0


def sample(**kw):
    p = Page(17 * IN, 11 * IN, **kw)
    p.line((IN, IN), (2 * IN, IN))
    p.rect(2 * IN, 2 * IN, IN, 0.5 * IN)
    p.circle((5 * IN, 5 * IN), 0.25 * IN)
    p.circle((6 * IN, 5 * IN), 0.04 * IN, fill=True)            # (a junction dot)
    p.quarter_arc((8 * IN, 4 * IN), 0.5 * IN)
    p.white_box(0, 0, 17 * IN, 11 * IN)                          # (the page's background)
    p.ops.append("%g %g m %g %g l %g %g l h f" % (10 * IN, IN, 10.1 * IN, IN, 10.05 * IN,
                                                  1.1 * IN))    # (a solid arrowhead)
    p.text((IN, 7 * IN), "CR101 START", 10)
    p.text((4 * IN, 7 * IN), "2004", 8, angle=90)
    p.text((IN, 8 * IN), "LEFT", 10)
    p.text((IN + 300, 8 * IN), "FAR RIGHT", 10)                  # (far along: its own text)
    inner = Page(1, 1)
    inner.line((0, 0), (IN, 0))
    p.form((2, 0, 0, 2, 12 * IN, 9 * IN), inner)                 # (a block drawn twice size)
    return p


def kinds(ents, cls):
    return [e for e in ents if type(e) is cls]


class ReadTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def pdf(self, *pages):
        return write_pdf(os.path.join(self.d, "t.pdf"), list(pages))

    def test_lines_shapes_and_text(self):
        ents, rep = P.read_pdf(self.pdf(sample()))
        lines = kinds(ents, M.Line)
        self.assertIn(((1.0, 1.0), (2.0, 1.0)), [(e.p1, e.p2) for e in lines])
        self.assertIn(((12.0, 9.0), (14.0, 9.0)), [(e.p1, e.p2) for e in lines])   # (form x2)
        box = kinds(ents, M.Polyline)
        self.assertEqual([(b.points, b.closed) for b in box],
                         [([(2.0, 2.0), (3.0, 2.0), (3.0, 2.5), (2.0, 2.5)], True)])
        circles = sorted((e.center, e.radius) for e in kinds(ents, M.Circle))
        self.assertEqual(circles, [((5.0, 5.0), 0.25), ((6.0, 5.0), 0.04)])
        arc = kinds(ents, M.Arc)[0]
        self.assertAlmostEqual(arc.center[0], 8.0, 4)
        self.assertAlmostEqual(arc.center[1], 4.0, 4)
        self.assertAlmostEqual(arc.radius, 0.5, 4)
        self.assertAlmostEqual(arc.start, 0.0, 2)
        self.assertAlmostEqual(arc.end, 90.0, 2)
        self.assertTrue(all(e.layer == P.LAYER_LINES for e in ents if not isinstance(e, M.Text)))
        # the background and the arrowhead aren't lines; the arrowhead is counted
        self.assertEqual(rep["skipped"], {P.FILLED: 1})
        texts = {t.text: t for t in kinds(ents, M.Text)}
        self.assertEqual(sorted(texts), ["2004", "CR101 START", "FAR RIGHT", "LEFT"])
        t = texts["CR101 START"]
        self.assertEqual((t.pos, t.angle, t.layer), ((1.0, 7.0), 0.0, P.LAYER_TEXT))
        self.assertAlmostEqual(t.height, 10 * P.CAP / IN, 6)
        t = texts["2004"]
        self.assertEqual((t.pos, t.angle), ((4.0, 7.0), 90.0))
        self.assertAlmostEqual(t.height, 8 * P.CAP / IN, 6)
        self.assertEqual((rep["texts"], rep["circles"], rep["lines"]), (4, 2, 4))

    def test_filled_shapes_when_asked(self):
        ents, rep = P.read_pdf(self.pdf(sample()), filled=True)
        self.assertEqual(rep["skipped"], {})
        tri = [e for e in kinds(ents, M.Polyline) if e.closed and len(e.points) == 3]
        self.assertEqual(len(tri), 1)

    def test_scale_and_turned_page(self):
        ents, _rep = P.read_pdf(self.pdf(sample()), scale=4.0)
        self.assertIn(((4.0, 4.0), (8.0, 4.0)), [(e.p1, e.p2) for e in kinds(ents, M.Line)])
        t = [e for e in kinds(ents, M.Text) if e.text == "LEFT"][0]
        self.assertAlmostEqual(t.height, 4 * 10 * P.CAP / IN, 6)
        # a portrait page turned to landscape by /Rotate comes in as shown
        q = Page(11 * IN, 17 * IN, rotate=90)
        q.line((IN, IN), (2 * IN, IN))
        q.text((IN, 3 * IN), "ROT", 10)
        ents, _rep = P.read_pdf(self.pdf(q))
        (ln,) = kinds(ents, M.Line)
        self.assertEqual(sorted([ln.p1, ln.p2]), [(1.0, 9.0), (1.0, 10.0)])
        (t,) = kinds(ents, M.Text)
        self.assertEqual((t.text, t.angle), ("ROT", 270.0))

    def test_text_runs(self):
        p = Page(8.5 * IN, 11 * IN)
        p.text((IN, IN), "AB", 10)
        p.text((IN + 18, IN), "CD", 10)          # (a small gap: one text with a space)
        p.text((IN, 2 * IN), "BOLD", 10)
        p.text((IN + 0.2, 2 * IN), "BOLD", 10)   # (drawn twice over itself)
        p.text((IN, 3 * IN), "SMALL", 6)          # (another size: its own text)
        p.text((IN + 32, 3 * IN), "BIG", 12)
        got = sorted(t.text for t in kinds(P.read_pdf(self.pdf(p))[0], M.Text))
        self.assertEqual(got, ["AB CD", "BIG", "BOLD", "SMALL"])

    def test_pages_and_bad_files(self):
        a, b = Page(612, 792), Page(612, 792)
        a.line((0, 0), (72, 0))
        b.line((0, 0), (144, 0))
        path = self.pdf(a, b)
        self.assertEqual(P.page_count(path), 2)
        (ln,) = kinds(P.read_pdf(path, 2)[0], M.Line)
        self.assertEqual(ln.p2, (2.0, 0.0))
        with self.assertRaises(P.PdfError):
            P.read_pdf(path, 3)
        bad = os.path.join(self.d, "bad.pdf")
        with open(bad, "w") as f:
            f.write("not a pdf at all")
        with self.assertRaises(P.PdfError):
            P.page_count(bad)

    def test_reading_doesnt_start_with_the_program(self):
        # (start-up never loads pdfminer: only a PDF read does)
        import subprocess
        code = ("import sys; import kanzonascad.main_window, kanzonascad.fileio; "
                "sys.exit(1 if 'pdfminer' in sys.modules else 0)")
        r = subprocess.run([sys.executable, "-c", code],
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        self.assertEqual(r.returncode, 0)


class RoundTripTest(unittest.TestCase):
    def test_the_programs_own_pdf_comes_back(self):
        """A sheet exported to PDF and brought back in: every line where it was. (Its text is
        drawn as letter shapes, so none comes back as text: said, and the shapes counted.)"""
        p = M.Project.new()
        s = p.sheets[0]
        lines = [((2.0, 2.0), (6.0, 2.0)), ((3.0, 3.5), (3.0, 7.25)), ((7.5, 6.0), (9.25, 4.5))]
        with p.edit("x") as ed:
            for a, b in lines:
                ed.add(s, M.Line(a, b))
            ed.add(s, M.Text((3.0, 4.0), "CR101", 0.125))
        path = os.path.join(tempfile.mkdtemp(), "out.pdf")
        fileio.export_pdf(p, path)
        ents, rep = P.read_pdf(path)
        got = [(e.p1, e.p2) for e in kinds(ents, M.Line)]
        for a, b in lines:
            self.assertTrue(any(max(abs(q[0] - r[0]) + abs(q[1] - r[1]) for q, r in
                                    ((g1, a), (g2, b))) < 0.002 or
                                max(abs(q[0] - r[0]) + abs(q[1] - r[1]) for q, r in
                                    ((g2, a), (g1, b))) < 0.002 for g1, g2 in got), (a, b))
        self.assertEqual(rep["texts"], 0)
        self.assertGreater(rep["skipped"].get(P.FILLED, 0), 0)


class WindowTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.path = write_pdf(os.path.join(tempfile.mkdtemp(), "s.pdf"), [sample()])
        self.asked = []

        def ask(path, pages, k):
            self.asked.append((os.path.basename(path), pages, k))
            return {"page": 1, "scale": k, "filled": False}
        self.win.ask_pdf_import = ask

    def tearDown(self):
        self.win.__dict__.pop("ask_pdf_import", None)
        p = self.v.project
        p.saved_at = len(p.undo_stack)
        self.win.close()

    def test_import_is_one_step_and_selected(self):
        p, s = self.v.project, self.v.sheet()
        steps = len(p.undo_stack)
        ids = self.win.import_pdf(self.path)
        self.assertEqual(self.asked, [("s.pdf", 1, s.k())])
        self.assertEqual(len(p.undo_stack), steps + 1)
        self.assertEqual(set(ids), set(self.v.sel))
        self.assertIn(P.LAYER_LINES, p.layers)
        self.assertIn(P.LAYER_TEXT, p.layers)
        self.assertIn("4 text(s)", self.win.cmdline.history.toPlainText())
        p.undo()
        self.assertFalse(any(i in s.entities for i in ids))
        # cancelled: nothing
        self.win.ask_pdf_import = lambda *a: None
        self.assertEqual(self.win.import_pdf(self.path), [])
        self.assertEqual(len(p.undo_stack), steps)

    def test_the_menu_command_asks_for_a_file(self):
        # (found by the battery: the menu's triggered(False) came in as the path, and the
        # file read was descriptor 0, not the file dialog)
        from PySide6.QtWidgets import QFileDialog
        asked = []
        real = QFileDialog.getOpenFileName
        QFileDialog.getOpenFileName = staticmethod(
            lambda *a, **k: (asked.append(a[1]), (self.path, "PDF (*.pdf)"))[1])
        try:
            self.win.acts["import_pdf"].trigger()
        finally:
            QFileDialog.getOpenFileName = real
        self.assertEqual(asked, ["Import PDF"])
        self.assertEqual(len(self.asked), 1)
        self.assertTrue(self.v.sel)

    def test_dropped_on_the_drawing_lands_there(self):
        ids = self.win.drop_files([self.path], (40.0, 30.0))
        s = self.v.sheet()
        bb = None
        from kanzonascad import geometry as G
        for i in ids:
            bb = G.bbox_union(bb, s.entities[i].bbox())
        self.assertAlmostEqual((bb[0] + bb[2]) / 2, 40.0, 6)
        self.assertAlmostEqual((bb[1] + bb[3]) / 2, 30.0, 6)

    def test_a_file_that_isnt_a_pdf_says_so(self):
        from PySide6.QtWidgets import QMessageBox
        bad = os.path.join(tempfile.mkdtemp(), "bad.pdf")
        with open(bad, "w") as f:
            f.write("nope")
        said = []
        real = QMessageBox.warning
        QMessageBox.warning = staticmethod(lambda *a, **k: said.append(a[2]))
        try:
            self.assertEqual(self.win.import_pdf(bad), [])
        finally:
            QMessageBox.warning = real
        self.assertIn("not a PDF", said[0])


if __name__ == "__main__":
    unittest.main()
