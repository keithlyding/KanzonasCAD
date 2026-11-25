"""Export to PDF: every cross-reference is a link to the place it names (the owner, 0.23.1:
"Like for pdf, if I click on a cross reference, will it navigate me to that location?").

What each link must be is worked out here from the drawing (where each text is, where each
object it names is, the page sizes), not from pdf_links: its box over the text as drawn on
the page (checked on the page drawn by Qt's own PDF reader too: ink in the box), its
destination the right page with a /FitR box round the object."""
import builtins
import os
import tempfile
import unittest
from unittest import mock

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import fileio
from kanzonascad import model as M
from kanzonascad import xrefs
from kanzonascad.wirenums import ARROWS

SRC, DST = ARROWS


def page_xy(sheet, x, y):
    """A sheet point in PDF points from the page's lower left corner: the paper's lower left
    corner is the page's, and a drawing unit is `scale` paper inches."""
    return x * sheet.scale * 72.0, y * sheet.scale * 72.0



def draws_text():
    """Whether this Qt draws text at all (Windows' offscreen platform draws none)."""
    from PySide6.QtGui import QColor, QImage, QPainter
    img = QImage(40, 40, QImage.Format_RGB32)
    img.fill(0)
    pt = QPainter(img)
    pt.setPen(QColor("#ffffff"))
    pt.drawText(5, 30, "X")
    pt.end()
    return any(QColor(img.pixel(x, y)).red() for x in range(40) for y in range(40))


class PdfLinksTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.ortho_on = self.v.polar_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
            ed.add_sheet(self.p.make_sheet("Three"))
        self.s1, self.s2, self.s3 = self.p.sheets
        with self.p.edit("turned and scaled") as ed:
            ed.sheet_meta(self.s2, rotation=90)              # (portrait: 11 x 17)
            ed.sheet_scale(self.s3, 0.25)                    # (a panel at 1:4: 68 x 44 units)
        self.coil = self.place(self.s1, "Relay coil", (3, 9))
        tag = self.coil.attrs["TAG"]
        self.no = self.place(self.s2, "Contact NO", (5, 12), tag)
        self.nc = self.place(self.s3, "Contact NC", (30, 18), tag)
        with self.p.edit("wires") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            ed.add(self.s2, M.Wire([(2.0, 3.0), (6.0, 3.0)]))
        self.src = self.place(self.s1, SRC, (6.0, 5.0))
        self.dst = self.place(self.s2, DST, (2.0, 3.0), self.src.attrs["TAG"])
        self.tmp = tempfile.mkdtemp(prefix="kzcad-links")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def place(self, sheet, name, at, *more):
        before = set(sheet.entities)
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at, *more)
        self.assertIsNone(self.v.cmd)
        return [e for i, e in sheet.entities.items() if i not in before and
                isinstance(e, M.Insert)][0]

    def now(self, sheet, e):
        return sheet.entities[e.id]

    def export(self, sheets=None, name="out.pdf"):
        from pypdf import PdfReader
        path = os.path.join(self.tmp, name)
        notes = []
        n = fileio.export_pdf(self.p, path, sheets=sheets, note=notes.append)
        self.assertEqual(notes, [])
        return path, PdfReader(path), n

    def ref(self, sheet, starts):
        got = [t for t in xrefs.shown(self.p, sheet) if t[2].startswith(starts)]
        self.assertEqual(len(got), 1, (starts, xrefs.shown(self.p, sheet)))
        return got[0]

    @staticmethod
    def annots(page):
        return [a.get_object() for a in (page.get("/Annots") or [])]

    def inked(self, path, index, rect):
        """Whether the page as Qt's PDF reader draws it has ink inside rect (PDF points)."""
        from PySide6.QtCore import QSize
        from PySide6.QtPdf import QPdfDocument
        doc = QPdfDocument()
        doc.load(path)
        size = doc.pagePointSize(index)
        f = 4.0                                     # (288 dpi)
        img = doc.render(index, QSize(int(size.width() * f), int(size.height() * f)))
        x0, y0, x1, y1 = rect
        dark = 0
        for px in range(int(x0 * f), int(x1 * f)):
            for py in range(int((size.height() - y1) * f), int((size.height() - y0) * f)):
                c = img.pixelColor(px, py)
                dark += c.red() + c.green() + c.blue() < 300
        doc.close()
        return dark

    def check_link(self, reader, page_i, sheet, item, target_i, target_sheet, target,
                   path=None):
        """The one link over the reference item (or over part of it: item may be a box on
        the sheet) leads to page target_i, its /FitR box round the target's middle."""
        tb = xrefs.text_item(item).bbox() if isinstance(item[2], str) else item
        a, b = page_xy(sheet, tb[0], tb[1]), page_xy(sheet, tb[2], tb[3])
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        hits = [x for x in self.annots(reader.pages[page_i])
                if x["/Subtype"] == "/Link" and
                x["/Rect"][0] <= mid[0] <= x["/Rect"][2] and
                x["/Rect"][1] <= mid[1] <= x["/Rect"][3]]
        self.assertEqual(len(hits), 1, (item, [list(map(float, x["/Rect"]))
                                               for x in self.annots(reader.pages[page_i])]))
        r = [float(v) for v in hits[0]["/Rect"]]
        # (over the whole text, and not much past it: a fifth of its height at most)
        hh = (item[3] if isinstance(item[2], str) else (tb[3] - tb[1])) * sheet.scale * 72
        for got, want, out in ((r[0], a[0], -1), (r[1], a[1], -1), (r[2], b[0], 1),
                               (r[3], b[1], 1)):
            self.assertLessEqual(out * (want - got), 0.01, (r, a, b))
            self.assertLessEqual(out * (got - want), 0.2 * hh + 0.01, (r, a, b))
        dest = hits[0]["/Dest"]
        self.assertEqual(dest[0], reader.pages[target_i].indirect_reference)
        self.assertEqual(dest[1], "/FitR")
        box = [float(v) for v in dest[2:6]]
        bb = target.bbox()
        tx, ty = page_xy(target_sheet, (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0)
        pw = float(reader.pages[target_i].mediabox.width)
        ph = float(reader.pages[target_i].mediabox.height)
        # (the object in the middle of the box, the box a good part of the page: zoomed to it,
        # the things round it in view too)
        self.assertAlmostEqual((box[0] + box[2]) / 2.0, tx, delta=0.5)
        self.assertAlmostEqual((box[1] + box[3]) / 2.0, ty, delta=0.5)
        self.assertTrue(0.15 * pw < box[2] - box[0] < 0.5 * pw, box)
        self.assertTrue(0.15 * ph < box[3] - box[1] < 0.5 * ph, box)
        # (ink under the link where this Qt draws text: Windows' offscreen Qt lists fonts but
        # draws none, so there the link's box, page and destination above are what is checked)
        if path is not None and draws_text():
            self.assertGreater(self.inked(path, page_i, r), 5, (item, r))
        return r

    def test_every_reference_leads_to_what_it_names(self):
        path, reader, n = self.export()
        self.assertEqual(n, 3)
        # (the pages are the sheets' paper: 17 x 11, turned 11 x 17, and 17 x 11 at 1:4)
        for page, s in zip(reader.pages, self.p.sheets):
            w, h = s.paper_inches()
            self.assertEqual((float(page.mediabox.width), float(page.mediabox.height)),
                             (w * 72.0, h * 72.0))
        s1, s2, s3 = self.s1, self.s2, self.s3
        no, nc = self.now(s2, self.no), self.now(s3, self.nc)
        coil, src, dst = self.now(s1, self.coil), self.now(s1, self.src), self.now(s2, self.dst)
        z = self.p.zone_text
        # under the coil: a line for each contact, to the contact
        self.check_link(reader, 0, s1, self.ref(s1, "NO " + z(s2, *no.pos)), 1, s2, no, path)
        self.check_link(reader, 0, s1, self.ref(s1, "NC " + z(s3, *nc.pos)), 2, s3, nc, path)
        # under each contact (on a turned sheet, on a scaled one): to the coil
        self.check_link(reader, 1, s2, self.ref(s2, z(s1, *coil.pos)), 0, s1, coil, path)
        self.check_link(reader, 2, s3, self.ref(s3, z(s1, *coil.pos)), 0, s1, coil, path)
        # the arrows ("1001 / 2-F1"): each to the other
        num = src.attrs["TAG"]
        self.check_link(reader, 0, s1, self.ref(s1, num + " / "), 1, s2, dst, path)
        self.check_link(reader, 1, s2, self.ref(s2, num + " / "), 0, s1, src, path)
        self.assertEqual([len(self.annots(pg)) for pg in reader.pages], [3, 2, 1])

    def test_a_sheet_left_out_gets_no_links(self):
        _path, reader, n = self.export([self.s1, self.s2])
        self.assertEqual(n, 2)
        nc = self.now(self.s3, self.nc)
        item = self.ref(self.s1, "NC " + self.p.zone_text(self.s3, *nc.pos))
        tb = xrefs.text_item(item).bbox()
        mid = page_xy(self.s1, (tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0)
        rects = [[float(v) for v in a["/Rect"]] for a in self.annots(reader.pages[0])]
        self.assertFalse([r for r in rects if r[0] <= mid[0] <= r[2] and r[1] <= mid[1] <= r[3]])
        self.assertEqual(len(rects), 2)                 # (the NO contact's line, the arrow)
        for a in self.annots(reader.pages[0]) + self.annots(reader.pages[1]):
            self.assertIn(a["/Dest"][0], [pg.indirect_reference for pg in reader.pages])
        # (only sheet 3, the coil's: page 2 of 2 is sheet 2, nothing on it leads to sheet 3)
        _path, reader, n = self.export([self.s3], "three.pdf")
        self.assertEqual(n, 1)
        self.assertEqual(self.annots(reader.pages[0]), [])

    def test_several_references_in_one_text_each_their_own_link(self):
        defn = self.lib.get("symbol", "Off-sheet connector")
        ends = []
        with self.p.edit("connectors") as ed:
            for s, at in ((self.s1, (10.0, 6.0)), (self.s2, (6.0, 9.0)), (self.s3, (40.0, 24.0))):
                ends.append(ed.add(s, M.Insert(defn.name, at, defn=defn, attrs={"TAG": "Z"})))
        path, reader, _n = self.export()
        where2 = self.p.zone_text(self.s2, *ends[1].pos)
        where3 = self.p.zone_text(self.s3, *ends[2].pos)
        item = self.ref(self.s1, where2 + ", ")
        self.assertEqual(item[2], where2 + ", " + where3)
        # (each place's part of the text, by the widths the text is drawn with)
        t = xrefs.text_item(item)
        left = t.pos[0] - t.width() / 2.0
        hh = item[3]
        w2, w23 = M.text_width(where2, hh), M.text_width(where2 + ", ", hh)
        part2 = (left, item[1], left + w2, item[1] + hh)
        part3 = (left + w23, item[1], left + t.width(), item[1] + hh)
        r2 = self.check_link(reader, 0, self.s1, part2, 1, self.s2,
                             self.now(self.s2, ends[1]), path)
        r3 = self.check_link(reader, 0, self.s1, part3, 2, self.s3,
                             self.now(self.s3, ends[2]), path)
        self.assertLess(r2[2], r3[0])                    # (side by side, apart)

    def test_a_frozen_sheet_out_of_date_leads_to_the_zone_it_names(self):
        with self.p.edit("freeze") as ed:
            xrefs.freeze(ed, self.p, self.s3, True)
        held = self.ref(self.s3, self.p.zone_text(self.s1, *self.coil.pos))
        with self.p.edit("move the coil") as ed:              # (the sheet still says B2)
            c = self.now(self.s1, self.coil)
            ed.change(self.s1, c.moved(4.0, 0.0))
        self.assertIn(self.s3, xrefs.out_of_date(self.p))
        _path, reader, _n = self.export()
        s1 = self.s1
        x0, y0, x1, y1 = s1.layout_zone_frame()
        cw, rh = (x1 - x0) / s1.cols, (y1 - y0) / s1.rows
        row, col = s1.zone_at(*self.coil.pos)
        i, j = s1.row_labels().index(row), s1.col_labels().index(col)
        mid = (x0 + (j + 0.5) * cw, y1 - (i + 0.5) * rh)
        self.check_link(reader, 2, self.s3, held, 0, s1, M.Line(mid, mid))

    def test_a_frozen_sheet_out_of_date_naming_a_place_outside_the_zones(self):
        # (the long battery, 0.25, seed 4912: a frozen sheet's "2069 / 2-?", the other arrow
        # since moved into a zone, had no link, while "2-?" is a place on page 2: it leads to
        # the middle of that sheet's frame)
        from tests import battery_checks as BC
        with self.p.edit("the destination off the zones") as ed:
            ed.change(self.s2, self.now(self.s2, self.dst).moved(-60.0, 0.0))
        with self.p.edit("freeze") as ed:
            xrefs.freeze(ed, self.p, self.s1, True)
        held = [t for t in xrefs.shown(self.p, self.s1) if t[2].endswith("2-?")]
        self.assertEqual(len(held), 1, xrefs.shown(self.p, self.s1))
        with self.p.edit("back") as ed:
            ed.change(self.s2, self.now(self.s2, self.dst).moved(60.0, 0.0))
        self.assertIn(self.s1, xrefs.out_of_date(self.p))
        path, reader, _n = self.export()
        x0, y0, x1, y1 = self.s2.layout_zone_frame()
        mid = self.s2.turn((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        self.check_link(reader, 0, self.s1, held[0], 1, self.s2, M.Line(mid, mid))
        self.assertGreater(BC.pdf_links_right(self.p, path, self.p.sheets), 0)

    def test_a_rung_number_on_two_sheets_one_left_out(self):
        # (the long battery, 0.25, seed 4923: places by ladder, the coil on rung 137 of sheet
        # 1, and sheet 3 has a rung 137 too (a ladder's first number typed); sheet 1 left out
        # of the PDF, the contact's "137" on sheet 2 rightly has no link, since what it names
        # isn't in the PDF; the check took "137" for a place in the PDF, sheet 3's rung)
        from tests import battery_checks as BC
        self.p.settings["referencing"] = "ladder"
        with self.p.edit("ladders") as ed:
            ed.add(self.s1, M.Ladder((1.0, 9.0), (6.0, 9.0), rungs=1, spacing=0.5, first=137))
            ed.add(self.s3, M.Ladder((10.0, 30.0), (40.0, 30.0), rungs=1, spacing=2.0,
                                     first=137))
        self.assertEqual(self.p.zone_text(self.s1, *self.coil.pos), "137")
        self.ref(self.s2, "137")
        path, reader, _n = self.export([self.s2, self.s3])
        page = reader.pages[0]
        item = self.ref(self.s2, "137")
        tb = xrefs.text_item(item).bbox()
        mid = page_xy(self.s2, (tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0)
        self.assertEqual([a for a in self.annots(page)
                          if a["/Rect"][0] <= mid[0] <= a["/Rect"][2] and
                          a["/Rect"][1] <= mid[1] <= a["/Rect"][3]], [])
        BC.pdf_links_right(self.p, path, [self.s2, self.s3])
        # with sheet 1 in it, the link is there and the check still wants it
        path, reader, _n = self.export([self.s1, self.s2, self.s3], "all.pdf")
        self.assertGreater(BC.pdf_links_right(self.p, path, [self.s1, self.s2, self.s3]), 0)

    def test_the_battery_check_with_texts_drawn_over_each_other(self):
        # (the battery, seeds 41 and 468 after 0.23: a contact's "?", or an arrow's device
        # line, drawn under another reference; that one's link over it is right, not a link
        # of its own)
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import ArrayObject, DictionaryObject, FloatObject, NameObject
        from tests import battery_checks as BC
        defn = self.lib.get("symbol", "Contact NO")
        no = self.now(self.s2, self.no)
        with self.p.edit("a contact on no coil, beside the one on CR") as ed:
            ed.add(self.s2, M.Insert(defn.name, (no.pos[0] + 0.05, no.pos[1]), defn=defn))
        lone = self.ref(self.s2, "?")
        path, reader, _n = self.export()
        tb = xrefs.text_item(lone).bbox()
        mid = page_xy(self.s2, (tb[0] + tb[2]) / 2.0, (tb[1] + tb[3]) / 2.0)
        over = [a for a in self.annots(reader.pages[1])
                if a["/Rect"][0] <= mid[0] <= a["/Rect"][2] and
                a["/Rect"][1] <= mid[1] <= a["/Rect"][3]]
        self.assertEqual(len(over), 1)                  # (the coil's place, beside it)
        self.assertGreater(BC.pdf_links_right(self.p, path, self.p.sheets), 0)
        # (a link of its own over the "?" still fails the check)
        w = PdfWriter(clone_from=reader)
        w.add_annotation(1, DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): ArrayObject(FloatObject(v) for v in (
                mid[0] - 1, mid[1] - 1, mid[0] + 1, mid[1] + 1)),
            NameObject("/Dest"): ArrayObject([w.pages[0].indirect_reference,
                                              NameObject("/Fit")])}))
        bad = os.path.join(self.tmp, "stray.pdf")
        with open(bad, "wb") as f:
            w.write(f)
        with self.assertRaises(AssertionError):
            BC.pdf_links_right(self.p, bad, self.p.sheets)

    def test_without_pypdf_the_pdf_is_written_without_links(self):
        real = builtins.__import__

        def no_pypdf(name, *a, **k):
            if name == "pypdf" or name.startswith("pypdf."):
                raise ImportError("No module named 'pypdf'")
            return real(name, *a, **k)
        path = os.path.join(self.tmp, "plain.pdf")
        notes = []
        with mock.patch("builtins.__import__", no_pypdf):
            n = fileio.export_pdf(self.p, path, note=notes.append)
        self.assertEqual(n, 3)
        self.assertEqual(len(notes), 1)
        self.assertIn("pypdf", notes[0])
        from pypdf import PdfReader
        reader = PdfReader(path)
        self.assertEqual(len(reader.pages), 3)
        self.assertEqual([self.annots(pg) for pg in reader.pages], [[]] * 3)


if __name__ == "__main__":
    unittest.main()
