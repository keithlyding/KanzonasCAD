"""Small PDFs written byte by byte for the PDF import's self-test (inside the built program
too), its unit tests and the battery: lines, curves,
filled shapes and real text (Helvetica, one of the 14 fonts every PDF reader has, so nothing
is embedded), on pages of any size, turned by /Rotate. What a CAD program's PDF holds, made
here so the tests need no outside files.

    page = Page(17 * 72, 11 * 72)
    page.line((72, 72), (144, 72))
    page.text((100, 200), "CR101", 9, angle=90)
    write_pdf(path, [page])

Coordinates are PDF points (1/72 inch), the page's lower left corner at 0,0."""
import math


class Page:
    def __init__(self, width, height, rotate=0):
        self.width, self.height, self.rotate = width, height, rotate
        self.ops = []

    def line(self, a, b, width=0.5):
        self.ops.append("%g w %g %g m %g %g l S" % (width, a[0], a[1], b[0], b[1]))

    def polyline(self, pts, closed=False):
        s = "%g %g m " % pts[0] + " ".join("%g %g l" % q for q in pts[1:])
        self.ops.append(s + (" h S" if closed else " S"))

    def rect(self, x, y, w, h, fill=False):
        self.ops.append("%g %g %g %g re %s" % (x, y, w, h, "f" if fill else "S"))

    def circle(self, c, r, fill=False):
        """A circle as four Bezier curves, as PDF writers make one."""
        k = 0.5522847498 * r
        x, y = c
        self.ops.append(
            "%g %g m %g %g %g %g %g %g c %g %g %g %g %g %g c %g %g %g %g %g %g c "
            "%g %g %g %g %g %g c h %s" % (
                x + r, y,
                x + r, y + k, x + k, y + r, x, y + r,
                x - k, y + r, x - r, y + k, x - r, y,
                x - r, y - k, x - k, y - r, x, y - r,
                x + k, y - r, x + r, y - k, x + r, y,
                "f" if fill else "S"))

    def quarter_arc(self, c, r):
        """A quarter circle from angle 0 to 90 degrees, one Bezier curve."""
        k = 0.5522847498 * r
        x, y = c
        self.ops.append("%g %g m %g %g %g %g %g %g c S" % (x + r, y, x + r, y + k,
                                                          x + k, y + r, x, y + r))

    def white_box(self, x, y, w, h):
        """A white filled box (a page's background): no line."""
        self.ops.append("q 1 g %g %g %g %g re f Q" % (x, y, w, h))

    def text(self, at, s, size, angle=0.0):
        a = math.radians(angle)
        c, si = math.cos(a), math.sin(a)
        s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        self.ops.append("BT /F1 %g Tf %.6f %.6f %.6f %.6f %g %g Tm (%s) Tj ET"
                        % (size, c, si, -si, c, at[0], at[1], s))

    def form(self, matrix, inner):
        """Ops drawn through a matrix (cm), as a block or a scaled view is."""
        self.ops.append("q %g %g %g %g %g %g cm %s Q" % (tuple(matrix) + (" ".join(inner.ops),)))


def write_pdf(path, pages):
    objs = []

    def add(body):
        objs.append(body)
        return len(objs)
    font = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
               "/Encoding /WinAnsiEncoding >>")
    pages_id = len(objs) + 2 * len(pages) + 1
    kids = []
    for p in pages:
        data = "\n".join(p.ops).encode("latin-1")
        content = add("<< /Length %d >>\nstream\n%s\nendstream" % (len(data),
                                                                    data.decode("latin-1")))
        kids.append(add("<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %g %g] /Rotate %d "
                        "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                        % (pages_id, p.width, p.height, p.rotate, font, content)))
    assert add("<< /Type /Pages /Kids [%s] /Count %d >>"
               % (" ".join("%d 0 R" % k for k in kids), len(kids))) == pages_id
    catalog = add("<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += ("%d 0 obj\n%s\nendobj\n" % (i, body)).encode("latin-1")
    xref = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    for o in offsets:
        out += ("%010d 00000 n \n" % o).encode()
    out += ("trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, catalog, xref)).encode()
    with open(path, "wb") as f:
        f.write(bytes(out))
    return path
