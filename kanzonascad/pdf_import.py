"""A PDF page's lines and text, as drawing objects (no Qt; the owner, Nov 2026: "a feature ...
that literally only does lines and text. That way, I can pull in a picture, PDF, screenshot,
whatever of a drawing or schematic"). This is the first step: PDFs that hold their drawing as
lines and text (made by a CAD program, or printed to PDF from one); pictures and scans, which
need their lines found and their text read (OCR), come later.

What comes in, read with pdfminer.six (MIT; imported only here, when a PDF is read):
- every stroked path: a straight piece as a Line, more as a Polyline (closed when the path
  is), Bezier curves followed closely (CURVE_STEPS pieces each); a path of curves on one
  circle as a Circle or, open, an Arc;
- filled shapes only when asked (they are mostly text drawn as letter shapes, which can't be
  read back as text, and solid arrowheads), except a filled circle (a junction dot), which
  comes in as a circle; white filled shapes (a page's background) never;
- the text that is real text: characters on one baseline, of one size and turn, close
  together, as one Text (its height the capital letters', CAP of the font size), turned as it
  was; a character the PDF gives no letter for ("(cid:12)") is left out and counted.

Sizes: PDF points (1/72 inch) as inches on paper, times scale (the sheet's drawing units per
paper inch, so the page looks on the sheet as it did printed); the page's lower left corner at
0,0. A page turned by /Rotate comes in as it is shown."""

import math

from . import geometry as G
from . import model as M

LAYER_LINES = "PDF LINES"
LAYER_TEXT = "PDF TEXT"
LAYERS = {LAYER_LINES: "#ffffff", LAYER_TEXT: "#ffffff"}
CURVE_STEPS = 8         # pieces a Bezier curve is followed by, when it isn't part of a circle
CAP = 0.716             # capital letters' height, of the font size (Helvetica and Arial)
ROUND = 6               # decimals points are kept to (no float noise in what comes in)
FILLED = "filled shapes (letters drawn as shapes, solid arrowheads)"
NO_LETTER = "characters the PDF gives no letter for"


class PdfError(Exception):
    """The file can't be read as a PDF, or has no such page."""


def _open(path):
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    f = open(path, "rb")
    try:
        doc = PDFDocument(PDFParser(f))
        pages = list(PDFPage.create_pages(doc))
    except PDFPasswordIncorrect:
        f.close()
        raise PdfError("it asks for a password to open")
    except Exception as ex:             # (pdfminer's errors have no common base: all named)
        f.close()
        raise PdfError("not a PDF that can be read (%s)" % (str(ex) or type(ex).__name__))
    return f, pages


def page_count(path):
    f, pages = _open(path)
    f.close()
    return len(pages)


def _layout(path, page):
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import PDFPageAggregator
    f, pages = _open(path)
    try:
        if not 1 <= page <= len(pages):
            raise PdfError("it has %d page(s), not a page %d" % (len(pages), page))
        rm = PDFResourceManager()
        dev = PDFPageAggregator(rm, laparams=None)     # (raw characters: grouped here)
        PDFPageInterpreter(rm, dev).process_page(pages[page - 1])
        return dev.get_result()
    finally:
        f.close()


def _walk(items):
    """Everything on the page, inside figures (forms) too: their points are the page's."""
    from pdfminer.layout import LTContainer, LTChar, LTCurve
    for o in items:
        if isinstance(o, (LTChar, LTCurve)):
            yield o
        elif isinstance(o, LTContainer):
            yield from _walk(o)


# ---- paths -------------------------------------------------------------------------------------
def _bezier(p0, p1, p2, p3, n=CURVE_STEPS):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] +
                    t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] +
                    t * t * t * p3[1]))
    return out


def _subpaths(path):
    """[(points, closed, all_curves, on)] of a path's pieces (m starts one, h closes it); on:
    the points exactly on the shape (where its segments meet), for fitting a circle without the
    error of the pieces a curve is followed by."""
    out = []
    pts, on, mids, curves, lines = [], [], [], 0, 0

    def done(closed):
        if len(pts) >= 2:
            # (the ends of its segments; with fewer than three apart, a curve's middle too:
            # computed from control points a writer rounded, so only when needed)
            exact = [q for i, q in enumerate(on) if i == 0 or G.dist(q, on[0]) > 1e-9]
            out.append((list(pts), closed, curves > 0 and lines == 0,
                        on if len(exact) >= 3 else on[:1] + mids[:1] + on[1:]))
    for op in path:
        kind = op[0]
        if kind == "m":
            done(False)
            pts, on, mids, curves, lines = [op[1]], [op[1]], [], 0, 0
        elif kind == "l" and pts:
            pts.append(op[1])
            on.append(op[1])
            lines += 1
        elif kind in ("c", "v", "y") and pts:
            q = [tuple(p) for p in op[1:]]
            if kind == "v":                 # (first control point: the current point)
                q = [pts[-1]] + q
            elif kind == "y":               # (second control point: the end point)
                q = q + [q[-1]]
            mids.append(_bezier(pts[-1], q[0], q[1], q[2], 2)[0])
            on.append(q[2])
            pts.extend(_bezier(pts[-1], q[0], q[1], q[2]))
            curves += 1
        elif kind == "h" and pts:
            if G.dist(pts[0], pts[-1]) > 1e-9:
                pts.append(pts[0])
            done(True)
            pts, on, mids, curves, lines = [pts[0]], [pts[0]], [], 0, 0
    done(False)
    return out


def _circle_through(a, b, c):
    """The center and radius of the circle through three points, or None (in a line)."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    return (ux, uy), G.dist((ux, uy), a)


def _on_circle(pts, on=None):
    """(center, radius) when every point is on one circle (within 1% of it), else None; the
    circle through three of on (the points exactly on it) when given."""
    if len(pts) < 4:
        return None
    on = [q for i, q in enumerate(on or pts) if i == 0 or G.dist(q, (on or pts)[0]) > 1e-9]
    if len(on) < 3:
        return None
    got = _circle_through(on[0], on[len(on) // 3], on[(2 * len(on)) // 3])
    if got is None:
        return None
    c, r = got
    if r <= 1e-9 or any(abs(G.dist(c, q) - r) > 0.01 * r for q in pts):
        return None
    return c, r


def _r(v):
    v = round(v, ROUND)
    return 0.0 if v == 0 else v


def _shape(pts, closed, curves, on, to):
    """The drawing object for one piece of a path, or None (no length)."""
    pts = [to(q) for q in pts]
    on = [to(q) for q in on]
    tidy = [pts[0]]
    for q in pts[1:]:
        if G.dist(q, tidy[-1]) > 1e-6:
            tidy.append(q)
    if len(tidy) < 2:
        return None
    if curves:
        round_ = _on_circle(tidy, on)
        if round_ is not None:
            c, r = round_
            c, r = (_r(c[0]), _r(c[1])), _r(r)
            if closed:
                return M.Circle(c, r, layer=LAYER_LINES)
            a0 = math.degrees(math.atan2(on[0][1] - c[1], on[0][0] - c[0]))
            a1 = math.degrees(math.atan2(on[-1][1] - c[1], on[-1][0] - c[0]))
            mid = tidy[len(tidy) // 2]
            am = math.degrees(math.atan2(mid[1] - c[1], mid[0] - c[0]))
            # (counterclockwise from start to end, through the middle: else the other way)
            if (am - a0) % 360.0 > (a1 - a0) % 360.0:
                a0, a1 = a1, a0
            return M.Arc(c, r, _r(a0 % 360.0), _r(a1 % 360.0), layer=LAYER_LINES)
    if len(tidy) == 2:
        return M.Line(tidy[0], tidy[1], layer=LAYER_LINES)
    if closed and G.dist(tidy[0], tidy[-1]) <= 1e-6:
        tidy = tidy[:-1]
    return M.Polyline(tidy, bool(closed) and len(tidy) >= 3, layer=LAYER_LINES)


def _white(color):
    """Is a fill color white (a page's background, a box blanking what's under it)?"""
    if color is None:
        return False
    vals = color if isinstance(color, (tuple, list)) else (color,)
    try:
        vals = [float(v) for v in vals]
    except (TypeError, ValueError):     # (a pattern's name: not white)
        return False
    if len(vals) == 4:                  # (CMYK: no ink)
        return all(v <= 0.02 for v in vals)
    return bool(vals) and all(v >= 0.98 for v in vals)


# ---- text ------------------------------------------------------------------------------------
def _char(o):
    """(text, angle, origin, em, advance) of a character in page points."""
    a, b, c, d, e, f = o.matrix
    sx = math.hypot(a, b) or 1.0
    ux, uy = a / sx, b / sx
    angle = math.degrees(math.atan2(uy, ux))
    w = o.adv * sx
    # the em, from the character's box: across its line, the box is the em high
    W, H = o.x1 - o.x0, o.y1 - o.y0
    ca, sa = abs(ux), abs(uy)
    em = (H - w * sa) / ca if ca >= sa else (W - w * ca) / sa
    return o.get_text(), angle, (e, f), max(em, 1e-6), w


def _texts(chars, to, scale):
    """The characters as Texts: one per run on one baseline, size and turn."""
    lines = {}
    for s, angle, (x, y), em, w in chars:
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)
        t = x * ux + y * uy                     # (along the baseline)
        n = -x * uy + y * ux                    # (across it)
        key = (round(angle * 2) / 2.0 % 360.0, round(em, 1))
        lines.setdefault(key, []).append((n, t, s, w, em, (x, y)))
    out = []
    for (angle, _e), cs in lines.items():
        cs.sort()
        rows, row = [], []
        for c in cs:
            if row and abs(c[0] - row[-1][0]) > 0.15 * c[4]:
                rows.append(row)
                row = []
            row.append(c)
        if row:
            rows.append(row)
        for row in rows:
            row.sort(key=lambda c: c[1])
            run, end = [], None
            for c in row:
                n, t, s, w, em, at = c
                if any(s == r[2] and abs(t - r[1]) < 0.05 * em for r in run[-4:]):
                    continue                    # (drawn twice over itself: bold)
                if run and (t - end > 2.5 * em or t < end - 0.5 * em):
                    out.append(_one_text(run, angle, to, scale))
                    run = []
                if run and t - end > 0.2 * em and not run[-1][2].endswith(" ") and s != " ":
                    run.append((n, end, " ", 0.0, em, at))
                end = t + w if not run else max(end, t + w)
                run.append(c)
            if run:
                out.append(_one_text(run, angle, to, scale))
    return [t for t in out if t is not None]


def _one_text(run, angle, to, scale):
    s = " ".join("".join(c[2] for c in run).split())
    if not s:
        return None
    em = max(c[4] for c in run)
    at = to(run[0][5])
    return M.Text(at, s, _r(em * CAP * scale / 72.0), _r(angle % 360.0), layer=LAYER_TEXT)


# ---- reading ----------------------------------------------------------------------------------
def read_pdf(path, page=1, scale=1.0, filled=False):
    """(entities, report) of one page, as fileio.read_dxf gives them (for add_drawing): the
    report's "layers", "units", "skipped" ({what: count}) and "reader", with "lines",
    "circles" and "texts" counted."""
    from pdfminer.layout import LTChar
    lay = _layout(path, page)
    x0, y0 = lay.bbox[0], lay.bbox[1]
    k = scale / 72.0

    def to(q):
        return (_r((q[0] - x0) * k), _r((q[1] - y0) * k))
    ents, chars = [], []
    skipped = {}

    def skip(what, n=1):
        skipped[what] = skipped.get(what, 0) + n
    for o in _walk(lay):
        if isinstance(o, LTChar):
            s = o.get_text()
            if s.startswith("(cid:"):
                skip(NO_LETTER)
                continue
            chars.append(_char(o))
            continue
        path_ = getattr(o, "original_path", None) or \
            [("m", o.pts[0])] + [("l", q) for q in o.pts[1:]]
        if not o.stroke:
            if not o.fill or _white(getattr(o, "non_stroking_color", None)):
                continue
            pieces = _subpaths(path_)
            # (a filled circle is a junction dot; other filled shapes are letters drawn as
            # shapes or solid arrowheads, brought in only when asked)
            dots = [p for p in pieces if p[2] and p[1] and _on_circle(p[0], p[3])]
            if not filled and len(dots) != len(pieces):
                skip(FILLED)
                continue
        else:
            pieces = _subpaths(path_)
        for pts, closed, curves, on in pieces:
            e = _shape(pts, closed, curves, on, to)
            if e is not None:
                ents.append(e)
    texts = _texts(chars, to, scale)
    ents.extend(texts)
    rep = {"layers": dict(LAYERS), "skipped": skipped, "reader": "pdfminer.six",
           "units": "PDF page %d, as printed%s" % (page, "" if scale == 1 else
                                                    " (x%g)" % scale),
           "texts": len(texts), "circles": sum(1 for e in ents if isinstance(e, M.Circle)),
           "lines": sum(1 for e in ents if isinstance(e, (M.Line, M.Polyline, M.Arc)))}
    return ents, rep
