"""Clickable cross-references in an exported PDF (the owner, 0.23.1: "if I click on a
cross reference, will it navigate me to that location?").

fileio.export_pdf draws the sheets with QPdfWriter, which writes no links; this adds them
afterwards with pypdf (imported here, when a PDF is exported, never at start-up): a Link
annotation over each reference drawn on a sheet (xrefs.link_spans: the line under a coil,
the place under a contact, an off-sheet connector's or arrow's other end, one link per
reference where a text lists several), leading to the page of the sheet it names, zoomed to
the object it names. A reference to a sheet left out of the PDF gets no link.

The destination is /FitR, a box round the object a third of the page across and a third
down: the viewer zooms so the box fills its window, the object in the middle of it with
some of its neighbors round it. (/XYZ puts the point at the window's top left corner, so the
object would sit in a corner at whatever zoom the reader had; /Fit shows the whole page and
the reader still has to look for it.)
"""

import os

from .model import text_width
from . import geometry as G
from . import xrefs

VIEW = 1.0 / 3.0             # the destination box: this share of the page, each way
PAD = 0.15                   # a link's box past its text's, as a share of the text height


def page_point(sheet, top, x, y):
    """A point of the sheet (drawing units) on its PDF page (points from the page's lower
    left corner), as export_pdf lays the page out: the paper's lower left corner at the
    page's, 1/scale drawing units to the paper inch (a scaled panel sheet). top: the page's
    top edge in points; the page is drawn down from it."""
    w, h = sheet.paper_inches()
    return x * sheet.scale * 72.0, top - (h - y * sheet.scale) * 72.0


def span_box(item, first, last):
    """The box, on the sheet, of characters first..last of a reference drawn as item (x, y,
    text, height[, angle]: a centered text, xrefs.text_item), a little past the letters."""
    t = xrefs.text_item(item)
    hh = t.height
    x0 = -t.width() / 2.0 + text_width(t.text[:first], hh)
    x1 = -t.width() / 2.0 + text_width(t.text[:last], hh)
    pad = PAD * hh
    local = [(x0 - pad, -pad), (x1 + pad, -pad), (x1 + pad, hh + pad), (x0 - pad, hh + pad)]
    return G.bbox_of([G.rotate_point((t.pos[0] + a, t.pos[1] + b), t.pos, t.angle)
                      for a, b in local])


def view_box(width, height, x, y):
    """The /FitR box round (x, y) on a page width x height points, kept on the page."""
    bw, bh = width * VIEW, height * VIEW
    left = min(max(x - bw / 2.0, 0.0), width - bw)
    bottom = min(max(y - bh / 2.0, 0.0), height - bh)
    return left, bottom, left + bw, bottom + bh


def links(project, sheets, tops):
    """[(page index, rect, target page index, view box)] of every link of the sheets as
    pages (tops: each page's top edge in points, its width and height: [(top, w, h)])."""
    page_of = {s.id: i for i, s in enumerate(sheets)}
    out = []
    for i, s in enumerate(sheets):
        top = tops[i][0]
        for item, spans in xrefs.link_spans(project, s):
            for first, last, (sid, x, y) in spans:
                j = page_of.get(sid)
                if j is None:
                    continue            # (a sheet not in this PDF)
                bb = span_box(item, first, last)
                a = page_point(s, top, bb[0], bb[1])
                b = page_point(s, top, bb[2], bb[3])
                tx, ty = page_point(sheets[j], tops[j][0], x, y)
                out.append((i, (a[0], a[1], b[0], b[1]), j,
                            view_box(tops[j][1], tops[j][2], tx, ty)))
    return out


def add_links(project, path, sheets):
    """Add the cross-reference links to the PDF export_pdf wrote at path (its pages the
    sheets, in order). Returns how many, or None when pypdf isn't there (the PDF is left as
    it is, without links)."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import (ArrayObject, DictionaryObject, FloatObject, NameObject,
                                   NumberObject)
    except ImportError:
        return None
    reader = PdfReader(path)
    tops = []
    for page in reader.pages:
        mb = page.mediabox
        tops.append((float(mb.top), float(mb.width), float(mb.height)))
    got = links(project, sheets, tops)
    if not got:
        return 0
    writer = PdfWriter(clone_from=reader)
    pages = list(writer.pages)
    for i, rect, j, box in got:
        writer.add_annotation(pages[i], DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Link"),
            NameObject("/Rect"): ArrayObject(FloatObject(round(v, 3)) for v in rect),
            NameObject("/Border"): ArrayObject([NumberObject(0)] * 3),
            NameObject("/Dest"): ArrayObject([pages[j].indirect_reference, NameObject("/FitR")]
                                             + [FloatObject(round(v, 3)) for v in box]),
        }))
    tmp = path + ".links"
    with open(tmp, "wb") as f:
        writer.write(f)
    os.replace(tmp, path)
    return len(got)
