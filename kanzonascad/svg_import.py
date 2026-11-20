"""SVG files brought in as real lines, circles and texts you can snap to and edit (the owner,
Nov 2026: "I want the svg to be editable real lines. But it has to be simple. If the file is too
complex, there's no point in trying to bring it in").

Read: line, polyline, polygon, rect, circle, ellipse, path (M L H V Z, curves C S Q T and arcs A
as short straight pieces) and text, inside groups and with their transforms (matrix,
translate, scale, rotate, skewX, skewY). Lengths in px (96 to the inch, as SVG has them), or
in, cm, mm, pt, pc. Styles, fills, gradients, clipping, masks, filters, pictures and fonts are
left out: only the shapes' outlines and the texts' words come in.

Too complex to be worth editing: more than MAX_PIECES straight pieces, or MAX_ELEMENTS
elements, or a file over MAX_BYTES; then nothing comes in and the reason says so
(TooComplex)."""

import math
import os
import re
import xml.etree.ElementTree as ET

from . import model as M

MAX_BYTES = 5 * 1024 * 1024
MAX_ELEMENTS = 5000
MAX_PIECES = 20000
CURVE_STEPS = 12            # straight pieces per curve or arc

UNITS = {"px": 1.0 / 96.0, "in": 1.0, "cm": 1.0 / 2.54, "mm": 1.0 / 25.4, "pt": 1.0 / 72.0,
         "pc": 1.0 / 6.0, "": 1.0 / 96.0}


class TooComplex(ValueError):
    """The SVG is too big or detailed to bring in as lines (the message says why)."""


def _length(text, default=0.0):
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([a-z%]*)", text or "")
    if not m:
        return default
    v, unit = float(m.group(1)), m.group(2)
    if unit == "%":
        return default
    return v * UNITS.get(unit, UNITS["px"]) * 96.0      # (in SVG user units: px)


def _numbers(text):
    return [float(t) for t in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?",
                                         text or "")]


def _mul(a, b):
    """Two affine transforms (a, b, c, d, e, f) as SVG writes them, a after b."""
    return (a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
            a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
            a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5])


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _transform(text):
    t = IDENTITY
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        n = _numbers(args)
        if name == "matrix" and len(n) == 6:
            m = tuple(n)
        elif name == "translate" and n:
            m = (1.0, 0.0, 0.0, 1.0, n[0], n[1] if len(n) > 1 else 0.0)
        elif name == "scale" and n:
            m = (n[0], 0.0, 0.0, n[1] if len(n) > 1 else n[0], 0.0, 0.0)
        elif name == "rotate" and n:
            a = math.radians(n[0])
            c, s = math.cos(a), math.sin(a)
            m = (c, s, -s, c, 0.0, 0.0)
            if len(n) == 3:
                m = _mul(_mul((1.0, 0.0, 0.0, 1.0, n[1], n[2]), m),
                         (1.0, 0.0, 0.0, 1.0, -n[1], -n[2]))
        elif name == "skewX" and n:
            m = (1.0, 0.0, math.tan(math.radians(n[0])), 1.0, 0.0, 0.0)
        elif name == "skewY" and n:
            m = (1.0, math.tan(math.radians(n[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            continue
        t = _mul(t, m)
    return t


def _apply(t, p):
    return (t[0] * p[0] + t[2] * p[1] + t[4], t[1] * p[0] + t[3] * p[1] + t[5])


def _tag(el):
    return el.tag.rsplit("}", 1)[-1] if isinstance(el.tag, str) else ""


def _arc_points(p0, rx, ry, phi, large, sweep, p1):
    """An SVG elliptical arc from p0 to p1 as points (SVG's endpoint form, its appendix F.6)."""
    if rx == 0 or ry == 0 or p0 == p1:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1, y1 = c * dx + s * dy, -s * dx + c * dy
    lam = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    k = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        k = -k
    cx1, cy1 = k * rx * y1 / ry, -k * ry * x1 / rx
    cx = c * cx1 - s * cy1 + (p0[0] + p1[0]) / 2.0
    cy = s * cx1 + c * cy1 + (p0[1] + p1[1]) / 2.0

    def ang(u, v):
        a = math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])
        return a
    t1 = ang((1, 0), ((x1 - cx1) / rx, (y1 - cy1) / ry))
    dt = ang(((x1 - cx1) / rx, (y1 - cy1) / ry), ((-x1 - cx1) / rx, (-y1 - cy1) / ry))
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, CURVE_STEPS + 1):
        t = t1 + dt * i / CURVE_STEPS
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((c * x - s * y + cx, s * x + c * y + cy))
    return out


def _path(d):
    """An SVG path's outlines: [(points, closed)] in its own units."""
    toks = re.findall(r"[MmLlHhVvZzCcSsQqTtAa]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", d or "")
    out = []
    cur, start = (0.0, 0.0), (0.0, 0.0)
    pts = []
    cmd = None
    last_ctrl = None
    i = 0

    def take(n):
        nonlocal i
        vals = toks[i:i + n]
        if len(vals) < n or any(re.match(r"[A-Za-z]", v) for v in vals):
            raise ValueError("a path's numbers are cut short")
        i += n
        return [float(v) for v in vals]

    def flush(closed=False):
        nonlocal pts
        if len(pts) >= 2:
            out.append((pts, closed))
        pts = []
    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                if pts:
                    flush(True)
                cur = start
                last_ctrl = None
                continue
        if cmd is None:
            raise ValueError("a path doesn't start with a command")
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if c == "M":
            x, y = take(2)
            flush()
            cur = start = (ox + x, oy + y)
            pts = [cur]
            cmd = "l" if rel else "L"          # (more pairs after M: lines)
            last_ctrl = None
            continue
        if not pts:
            pts = [cur]
        if c == "L":
            x, y = take(2)
            cur = (ox + x, oy + y)
            pts.append(cur)
            last_ctrl = None
        elif c == "H":
            (x,) = take(1)
            cur = ((ox if rel else 0.0) + x, cur[1])
            pts.append(cur)
            last_ctrl = None
        elif c == "V":
            (y,) = take(1)
            cur = (cur[0], (oy if rel else 0.0) + y)
            pts.append(cur)
            last_ctrl = None
        elif c in "CS":
            if c == "C":
                x1, y1, x2, y2, x, y = take(6)
                p1 = (ox + x1, oy + y1)
            else:
                x2, y2, x, y = take(4)
                p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) \
                    if last_ctrl else cur
            p2, p3 = (ox + x2, oy + y2), (ox + x, oy + y)
            p0 = cur
            for k in range(1, CURVE_STEPS + 1):
                t = k / CURVE_STEPS
                u = 1 - t
                pts.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] +
                            t ** 3 * p3[0],
                            u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] +
                            t ** 3 * p3[1]))
            cur, last_ctrl = p3, p2
        elif c in "QT":
            if c == "Q":
                x1, y1, x, y = take(4)
                p1 = (ox + x1, oy + y1)
            else:
                x, y = take(2)
                p1 = (2 * cur[0] - last_ctrl[0], 2 * cur[1] - last_ctrl[1]) \
                    if last_ctrl else cur
            p2 = (ox + x, oy + y)
            p0 = cur
            for k in range(1, CURVE_STEPS + 1):
                t = k / CURVE_STEPS
                u = 1 - t
                pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                            u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
            cur, last_ctrl = p2, p1
        elif c == "A":
            rx, ry, phi, large, sweep, x, y = take(7)
            p1 = (ox + x, oy + y)
            pts += _arc_points(cur, rx, ry, phi, bool(large), bool(sweep), p1)
            cur = p1
            last_ctrl = None
        else:
            raise ValueError("unknown path command %s" % cmd)
    flush()
    return out


def read_svg(path, layer="0"):
    """An SVG's shapes and texts in inches, up the page as KanzonasCAD has it (SVG's y runs
    down): (entities, report as read_dxf's). Raises TooComplex, or ValueError for a file that
    isn't an SVG it can read."""
    if os.path.getsize(path) > MAX_BYTES:
        raise TooComplex("the file is over %d MB" % (MAX_BYTES // (1024 * 1024)))
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as ex:
        raise ValueError("not an SVG it can read (%s)" % ex) from ex
    if _tag(root) != "svg":
        raise ValueError("not an SVG file (its first element is <%s>)" % _tag(root))
    elements = sum(1 for _e in root.iter())
    if elements > MAX_ELEMENTS:
        raise TooComplex("%d elements (more than %d)" % (elements, MAX_ELEMENTS))
    # its user units to inches: the viewBox scaled to its width and height
    vb = _numbers(root.get("viewBox"))
    w_in = _length(root.get("width"), 0.0) / 96.0
    h_in = _length(root.get("height"), 0.0) / 96.0
    sx = sy = 1.0 / 96.0
    ox = oy = 0.0
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        ox, oy = vb[0], vb[1]
        if w_in > 0:
            sx = w_in / vb[2]
            sy = h_in / vb[3] if h_in > 0 else sx
        else:
            sy = sx
    top = (oy + (vb[3] if len(vb) == 4 else 0.0))

    def to_sheet(q):
        return ((q[0] - ox) * sx, (top - q[1]) * sy)
    ents = []
    skipped = {}
    pieces = [0]

    def add_poly(pts, closed, t):
        if len(pts) < 2:
            return
        pieces[0] += len(pts)
        if pieces[0] > MAX_PIECES:
            raise TooComplex("more than %d straight pieces" % MAX_PIECES)
        q = [to_sheet(_apply(t, p)) for p in pts]
        if len(q) == 2 and not closed:
            ents.append(M.Line(q[0], q[1], layer=layer))
        else:
            ents.append(M.Polyline(q, closed=closed, layer=layer))

    def walk(el, t):
        tag = _tag(el)
        if tag in ("defs", "clipPath", "mask", "pattern", "marker", "symbol", "style",
                   "metadata", "title", "desc", "linearGradient", "radialGradient", "filter"):
            return
        t = _mul(t, _transform(el.get("transform")))
        g = lambda k: _length(el.get(k), 0.0)      # noqa: E731
        if tag == "line":
            add_poly([(g("x1"), g("y1")), (g("x2"), g("y2"))], False, t)
        elif tag in ("polyline", "polygon"):
            n = _numbers(el.get("points"))
            add_poly(list(zip(n[0::2], n[1::2])), tag == "polygon", t)
        elif tag == "rect":
            x, y, w, h = g("x"), g("y"), g("width"), g("height")
            if w > 0 and h > 0:
                add_poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True, t)
        elif tag in ("circle", "ellipse"):
            cx, cy = g("cx"), g("cy")
            rx = g("r") if tag == "circle" else g("rx")
            ry = g("r") if tag == "circle" else g("ry")
            if rx > 0 and ry > 0:
                plain = abs(t[1]) < 1e-12 and abs(t[2]) < 1e-12 and \
                    abs(abs(t[0] * sx) - abs(t[3] * sy)) < 1e-12
                if tag == "circle" and plain:
                    c = to_sheet(_apply(t, (cx, cy)))
                    ents.append(M.Circle(c, rx * abs(t[0]) * sx, layer=layer))
                    pieces[0] += 1
                else:
                    n = 4 * CURVE_STEPS
                    add_poly([(cx + rx * math.cos(2 * math.pi * i / n),
                               cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)],
                             True, t)
        elif tag == "path":
            try:
                outlines = _path(el.get("d"))
            except ValueError:
                skipped["path (unreadable)"] = skipped.get("path (unreadable)", 0) + 1
                outlines = []
            for pts, closed in outlines:
                add_poly(pts, closed, t)
        elif tag == "text":
            words = " ".join("".join(el.itertext()).split())
            if words:
                size = _length(el.get("font-size") or _style(el, "font-size") or "12", 12.0)
                q = to_sheet(_apply(t, (g("x"), g("y"))))
                h = size * abs(t[3]) * sy * 0.7          # (a font's capitals: 0.7 of its size)
                ents.append(M.Text(q, words, max(h, 1e-3), 0.0, layer=layer))
            return
        elif tag in ("image", "use", "foreignObject"):
            skipped[tag] = skipped.get(tag, 0) + 1
        for ch in el:
            walk(ch, t)
    walk(root, IDENTITY)
    if not ents:
        raise ValueError("nothing in it to bring in as lines")
    return ents, {"layers": {}, "skipped": skipped, "units": "in"}


def _style(el, key):
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            if k.strip() == key:
                return v.strip()
    return None
