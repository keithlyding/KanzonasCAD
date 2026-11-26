"""What the battery checks beyond "the model holds together" (the owner, Nov 2026: "I want all of
those added to the battery checks"): each check here would have caught a bug the battery
missed before.

- check_index: the spatial index against every entity, for boxes of any size (a window around
  an imported drawing found nothing past its lower left 32" until 0.15.6).
- expected_window / expected_lasso: what a window, crossing or lasso must select, from every
  entity (not the index).
- snap_oracle: a snap lands on a real point of a real object near the cursor.
- fit_oracle: after Fit the status bar says it fits, and the next bigger scale doesn't (Fit
  picked 1:5 for a drawing that fit at 1:4 until 0.15.7).
- view_shows / zoom checks: Zoom extents shows everything; zooming out shows the whole sheet
  (a sheet at 1:24 couldn't be seen whole until 0.15.7).
- ace_like_dxf: a drawing as AutoCAD Electrical writes it (attributes hidden and moved on a
  copy, description lines, a frame block bigger than the sheet, coordinates far from the
  origin), made by the battery itself: the owner's drawings never go in the repository.
- windows_paths: the recent files list with Windows' path rules (ntpath), on any system.
- printed / print_lands: Print gives one page a sheet chosen and changes nothing; a sheet
  printed lands inside its paper as printed, which fills the page one way (Fit to paper).
- second_window: a sheet in a window of its own edits the same project, and closing that
  window leaves nothing of it behind.
No Qt here except through the view passed in (and pictures painted for print_lands).
"""

import collections
import math
import os
import random

from kanzonascad import model as M
from kanzonascad import geometry as G


# how many times each check ran to the end (reported: a check that always skips proves nothing)
CHECKED = collections.Counter()


def _touch(b, r):
    return b[0] <= r[2] and b[2] >= r[0] and b[1] <= r[3] and b[3] >= r[1]


# ---- the spatial index -------------------------------------------------------------------------
def check_index(sheet, rnd):
    """Sheet.query and query_point find every entity whose box meets a box or point, for a few
    random boxes: small, around an entity, and bigger than everything."""
    ents = list(sheet.entities.values())
    if not ents:
        return
    boxes = [e.bbox() for e in ents]
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[2] for b in boxes)
    y1 = max(b[3] for b in boxes)
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    rects = [(x0 - w, y0 - h, x1 + w, y1 + h)]          # (everything, and far more)
    for _i in range(3):
        cx, cy = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        k = rnd.choice([0.01, 0.5, 5.0, 50.0, max(w, h)])
        rects.append((cx - k, cy - k * rnd.uniform(0.2, 2), cx + k, cy + k))
    for r in rects:
        got = {e.id for e in sheet.query(r)}
        want = {e.id for e in ents if _touch(e.bbox(), r)}
        missing = want - got
        assert not missing, "the index misses %d entities in %s (e.g. %s)" % (
            len(missing), tuple(round(c, 2) for c in r),
            [sheet.entities[i].kind for i in list(missing)[:3]])
    for _i in range(3):
        e = rnd.choice(ents)
        b = e.bbox()
        p = (rnd.uniform(b[0], b[2]), rnd.uniform(b[1], b[3]))
        got = {o.id for o in sheet.query_point(p, 1e-6)}
        assert e.id in got, "query_point misses %s at %s" % (e.kind, p)
    CHECKED['index'] += 1


# ---- selection ---------------------------------------------------------------------------------
def selectable(view, e):
    return view.layer_visible(e.layer) and not view.layer_locked(e.layer)


def expected_window(view, start, end):
    """Ids a window from start to end (world points) must select, from every entity: dragged
    to the right a window (wholly inside), to the left a crossing (touching)."""
    rect = (min(start[0], end[0]), min(start[1], end[1]),
            max(start[0], end[0]), max(start[1], end[1]))
    crossing = end[0] < start[0]
    out = set()
    for e in view.sheet().entities.values():
        if not selectable(view, e):
            continue
        hit = (e.crosses(rect) or e.inside(rect)) if crossing else e.inside(rect)
        if hit:
            out.add(e.id)
    return out


def expected_lasso(view, points, crossing):
    """Ids a lasso through points (world) must select, from every entity."""
    poly = G.PolygonIndex(points)
    out = set()
    for e in view.sheet().entities.values():
        if not selectable(view, e):
            continue
        box = e.bbox()
        if crossing:
            hit = poly.touches(e.outline(), box)
        else:
            hit = G.bbox_inside(box, poly.box) and poly.holds(e.outline(), box)
        if hit:
            out.add(e.id)
    return out


# ---- snaps -------------------------------------------------------------------------------------
def snap_candidates(view, p, r, kind):
    """Every (point) of `kind` within r of p on the sheet and its frame, from every entity and
    block piece (not the index)."""
    out = []
    ents = list(view.sheet().entities.values())
    try:
        frame = list(view._frame_index()[0].values())
    except AttributeError:
        frame = []
    for e in ents + frame:
        if not view.layer_visible(e.layer):
            continue
        parts = [e] + (list(e.world_entities()) if isinstance(e, M.Insert) else [])
        for w in parts:
            for k, q in w.snap_points():
                if k == kind and G.dist(p, q) <= r + 1e-9:
                    out.append(q)
    return out


def snap_oracle(view, rnd):
    """A cursor near a random snap point of a random entity snaps (that kind only) onto a real
    point of that kind within the aperture. Returns a note, or None when nothing to try."""
    from kanzonascad.view import APERTURE
    s = view.sheet()
    ents = [e for e in s.entities.values() if view.layer_visible(e.layer)]
    if not ents:
        return None
    e = rnd.choice(ents)
    pts = list(e.snap_points())
    if isinstance(e, M.Insert):
        for w in e.world_entities():
            pts.extend(w.snap_points())
    if not pts:
        return None
    kind, q = rnd.choice(pts)
    r = APERTURE / view.scale
    a = rnd.uniform(0, 2 * math.pi)
    d = rnd.uniform(0, 0.6) * r
    p = (q[0] + d * math.cos(a), q[1] + d * math.sin(a))
    got = view.object_snap(p, {kind})
    assert got is not None, "no %s snap near %s (one %.4g away)" % (kind, p, d)
    gk, gq = got
    assert gk == kind, (gk, kind)
    assert G.dist(gq, p) <= r + 1e-9, "snapped beyond the aperture: %s" % (gq,)
    cands = snap_candidates(view, p, r, kind)
    # (exactly on it, but for float rounding: a snap a hair off is slop)
    assert any(G.dist(gq, c) <= 1e-9 * max(1.0, abs(c[0]), abs(c[1])) for c in cands), \
        "%s snap at %s is no %s point of any object near %s" % (kind, gq, kind, p)
    CHECKED["snap " + kind] += 1
    return kind


# ---- pressing where nothing is drawn -------------------------------------------------------------
def blank_spot(view, rnd, tries=60):
    """A pixel on the sheet with nothing drawn within the pickbox around it (only the paper's
    color in the picture of the drawing), and no wire crossing's gap there either (the gap is
    painted in the paper's color over the wire: a 1/16" gap on paper is 1.5" at 1:24, all of a
    short wire drawn small), or None."""
    from PySide6.QtCore import QPoint, QPointF
    from kanzonascad import crossings
    from kanzonascad.render import Palette
    from kanzonascad.view import PICKBOX
    sheet = view.sheet()
    jr = crossings.size(sheet)
    gaps = [((p[0] - u[0] * jr, p[1] - u[1] * jr), (p[0] + u[0] * jr, p[1] + u[1] * jr))
            for p, u, _cu, _st in crossings.jumps(view.project, sheet)]
    grid, view.grid_on = view.grid_on, False         # (the grid's dots aren't objects)
    try:
        pm = view._lit_picture(Palette(view.dark))
    finally:
        view.grid_on = grid
    img = pm.toImage()
    dpr = pm.devicePixelRatio()
    back = Palette(view.dark).paper.rgb() & 0xFFFFFF       # (the sheet, where nothing is)
    r = PICKBOX + 1
    for _i in range(tries):
        x, y = rnd.randint(r + 2, view.width() - r - 3), rnd.randint(r + 2, view.height() - r - 3)
        ok = True
        for dx in range(-r, r + 1, 1):
            for dy in range(-r, r + 1, 1):
                if img.pixel(int((x + dx) * dpr), int((y + dy) * dpr)) & 0xFFFFFF != back:
                    ok = False
                    break
            if not ok:
                break
        if ok and gaps:
            w = view.to_world(QPointF(x, y))
            near = (PICKBOX + 2) / view.scale
            ok = all(G.dist_to_segment(w, a, b) > near for a, b in gaps)
        if ok:
            return QPoint(x, y)
    return None


def text_under(view, e, p, r):
    """Is p within r of, or inside the box of, a text of e (a text is picked anywhere in its
    box, as in AutoCAD; the letters leave blank pixels between them)?"""
    parts = [e]
    if isinstance(e, M.Insert):
        parts += list(e.world_entities())
    elif isinstance(e, (M.Composite,)):
        parts += list(e.parts())
    return any(isinstance(w, (M.Text, M.MText)) and w.distance(p) <= r for w in parts)


# ---- drawing slop: almost right, not exactly ----------------------------------------------------
def near_misses(sheet, lo=1e-6, hi=0.01):
    """Wire ends that look joined but aren't: within hi (real inches: the battery draws wires
    a quarter inch apart or more, so anything closer is rounding, not a design) of another
    wire or a symbol's pin, yet farther than the program's own tolerance lo (wires.TOL):
    [(wire id, end, what it nearly meets, distance)]."""
    def slanted(a, b):
        return abs(a[0] - b[0]) >= 1e-9 and abs(a[1] - b[1]) >= 1e-9

    def straight_ends(o):
        # (an end at the end of a slanted run is wherever that run happened to be cut: chance)
        return [q for q, r in ((o.points[0], o.points[1]), (o.points[-1], o.points[-2]))
                if not slanted(q, r)]
    out = []
    for w in sheet.wires():
        for p in straight_ends(w):
            # (what its other end is joined to it is joined to: a sliver of a wire from a pin
            # to where a slanted wire crossed, that wire deleted, ends a sliver's length from
            # its own pin, seed 3152 at 1:9671)
            other = w.points[-1] if p is w.points[0] else w.points[0]
            box = (p[0] - hi, p[1] - hi, p[0] + hi, p[1] + hi)
            near = list(sheet.query(box))
            if any(isinstance(o, M.Wire) and o.id != w.id and any(
                    abs(a[0] - b[0]) >= 1e-9 and abs(a[1] - b[1]) >= 1e-9 and
                    G.dist_to_segment(p, a, b) <= lo for a, b in zip(o.points, o.points[1:]))
                    for o in near):
                # (an end on a slanted run: where it crosses is chance as well, so the end is
                # too; Trim wire cut back to such a crossing 0.0048" from a pin in seed 3152)
                CHECKED["near misses: ends on slanted runs left out"] += 1
                continue
            for o in near:
                if o.id == w.id:
                    continue
                if isinstance(o, M.Wire):
                    # (its ends, and its runs straight across or up and down: a slanted run, a
                    # wire stretched far by a device moved on its pin, passes as near to grid
                    # points as chance has it, 0.0022" in seed 160: not rounding)
                    if o.distance(other) <= lo:
                        continue
                    d = min([G.dist(p, q) for q in straight_ends(o)] or [hi * 2])
                    for a, b in zip(o.points, o.points[1:]):
                        if abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9:
                            d = min(d, G.dist_to_segment(p, a, b))
                        else:
                            CHECKED["near misses: slanted runs left out"] += 1
                elif isinstance(o, M.Insert) and o.defn is not None and o.defn.pins:
                    d = min((G.dist(p, q) for _n, q in o.pin_points()
                             if G.dist(other, q) > lo), default=hi * 2)
                else:
                    continue
                if lo < d < hi:
                    out.append((w.id, p, o.kind, d))
    CHECKED["near misses"] += 1
    return out


def folds(sheet):
    """Wires that double back over themselves (a run going one way, the next straight back
    along it): the owner's bus wires, 0.17.5, ran out past the last drive and back, and the
    corner showed a dot with nothing tapped off. [(wire id, the corner)]."""
    out = []
    for w in sheet.wires():
        pts = w.points
        for a, b, c in zip(pts, pts[1:], pts[2:]):
            u = (b[0] - a[0], b[1] - a[1])
            v = (c[0] - b[0], c[1] - b[1])
            if abs(u[0] * v[1] - u[1] * v[0]) <= 1e-9 * max(1.0, G.dist(a, b) * G.dist(b, c)) \
                    and u[0] * v[0] + u[1] * v[1] < 0:
                out.append((w.id, b))
    CHECKED["wires doubling back"] += 1
    return out


def same_place(a, b, what):
    """a and b (entities) are where each other is, exactly but for float rounding: their
    boxes and snap points."""
    def close(x, y):
        return abs(x - y) <= 1e-9 * max(1.0, abs(x), abs(y))
    ba, bb = a.bbox(), b.bbox()
    assert all(close(x, y) for x, y in zip(ba, bb)), "%s drifted: %s -> %s (%s)" % (
        a.kind, [round(c, 9) for c in ba], [round(c, 9) for c in bb], what)
    sa = sorted((k, q[0], q[1]) for k, q in a.snap_points())
    sb = sorted((k, q[0], q[1]) for k, q in b.snap_points())
    assert len(sa) == len(sb) and all(x[0] == y[0] and close(x[1], y[1]) and close(x[2], y[2])
                                      for x, y in zip(sa, sb)), \
        "%s's points drifted (%s)" % (a.kind, what)


# ---- Fit ---------------------------------------------------------------------------------------
def fit_oracle(project, sheet):
    """After Fit: the status bar says it fits, and the next bigger scale wouldn't (the drawing
    measured as it would be there: text keeps its size on paper)."""
    from kanzonascad import scalefit as F
    box = F.drawing_box(sheet)
    if box is None:
        return
    why = F.outside(project, sheet)
    if why is not None:
        # (only when it fits at no scale: text alone bigger than the room, which on paper never
        # shrinks; then Fit picks the scale the drawing itself fits at)
        most = 1.0 / 100000
        far = box_scaled(sheet, most)
        assert not truly_fits(project, sheet, (far[2] - far[0]) * most,
                              (far[3] - far[1]) * most), \
            "after Fit (%s) the drawing runs %s" % (sheet.scale_text(), why)
        return
    v = sheet.scale
    bigger = [x for _n, x in F.presets_like(sheet.scale_name) if x > v + 1e-12]
    nxt = min(bigger) if bigger else None
    if nxt is None and v < 1.0:
        n = round(1.0 / v)
        nxt = 1.0 / (n - 1) if n > 1 else None
    if nxt is None:
        return
    b = box_scaled(sheet, nxt)
    assert not truly_fits(project, sheet, (b[2] - b[0]) * nxt, (b[3] - b[1]) * nxt), \
        "Fit chose %s but 1:%g fits too" % (sheet.scale_text(), 1 / nxt)
    CHECKED["fit"] += 1


def box_scaled(sheet, scale):
    """The drawing's box at another scale, worked out here (paper-sized pieces as
    Edit.sheet_scale makes them), not by scalefit."""
    f = (1.0 / scale) / sheet.k()
    bb = None
    for e in sheet.entities.values():
        c = M.paper_scaled(e, f) if hasattr(M, "paper_scaled") else None
        bb = G.bbox_union(bb, (c or e).bbox())
    return bb


def truly_fits(project, sheet, w, h, tol=1e-6):
    """Can a drawing w x h (paper inches) sit inside the zone frame and off the title block
    (what the status bar's "doesn't fit" asks), worked out here, not by scalefit: the frame,
    or the parts of it beside, above or below a title block in a corner."""
    from kanzonascad.sheetframe import title_block_rect
    k = sheet.k()
    x0, y0, x1, y1 = (c / k for c in sheet.zone_frame())
    regions = [(x0, y0, x1, y1)]
    if not sheet.reserve and sheet is not project.title_block:
        r = title_block_rect(project, sheet)
        if r is not None:
            t = tuple(c / k for c in r)
            if t[0] < x1 and t[2] > x0 and t[1] < y1 and t[3] > y0:
                regions = [(x0, y0, min(x1, t[0]), y1), (max(x0, t[2]), y0, x1, y1),
                           (x0, y0, x1, min(y1, t[1])), (x0, max(y0, t[3]), x1, y1)]
    return any(w <= rx1 - rx0 + tol and h <= ry1 - ry0 + tol
               for rx0, ry0, rx1, ry1 in regions)


def fit_cases(rnd, n=300):
    """Fit on n random drawings (outlines of any size and place, notes at their edges, some
    drawing-sized, on sheets of every size, turn and scale): each time the status bar says it
    fits and the next bigger scale doesn't."""
    from kanzonascad import scalefit as F
    sizes = sorted(M.SHEET_SIZES)
    done = 0
    for _i in range(n):
        p = M.Project.new()
        s = p.sheets[0]
        with p.edit("sheet") as ed:
            ed.sheet_meta(s, size=rnd.choice(sizes), rotation=rnd.choice([0, 0, 90, 270]),
                          kind=rnd.choice(["schematic", "panel"]))
            ed.sheet_scale(s, rnd.choice([1.0, 0.5, 0.25, 1 / 24]))
        x, y = rnd.uniform(-5000, 5000), rnd.uniform(-5000, 5000)
        w, h = rnd.uniform(0.5, 3000), rnd.uniform(0.5, 3000)
        with p.edit("draw") as ed:
            ed.add(s, M.Polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True))
            for _k in range(rnd.randint(0, 4)):
                t = M.Text((rnd.choice([x - 0.1, x + w + 0.1, x + w / 2]),
                            rnd.uniform(y, y + h)), "NOTE " * rnd.randint(1, 12),
                           rnd.choice([0.08, 0.12, 0.25]) * s.k(),
                           align=rnd.choice(["left", "center", "right"]))
                if rnd.random() < 0.3:
                    t = t.copy(fixed=True)
                ed.add(s, t)
        fit = F.fit_for(p, s)
        if fit is None:
            continue
        name, val = fit
        box = F.box_at(s, val) if hasattr(F, "box_at") else F.drawing_box(s)
        area, tb = F.room(p, s)
        F.apply(p, s, name, val, center=not F.placed_inside(box, val, area, tb))
        fit_oracle(p, s)
        done += 1
    return done


# ---- the view ----------------------------------------------------------------------------------
def view_rect(view):
    a = view.to_world(view.rect().topLeft())
    b = view.to_world(view.rect().bottomRight())
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def view_shows(view, box, tol=1e-6):
    r = view_rect(view)
    return box[0] >= r[0] - tol and box[1] >= r[1] - tol and box[2] <= r[2] + tol and \
        box[3] <= r[3] + tol


def zoom_checks(view, rnd):
    """Zoom extents shows everything drawn; a wheel step keeps the point under the cursor;
    zooming all the way out shows the whole sheet and drawing; a step out never zooms in."""
    from PySide6.QtCore import QPointF
    s = view.sheet()
    view.zoom("extents")
    if s.entities:
        bb = s.extents()
        assert view_shows(view, bb), "Zoom extents doesn't show %s" % (bb,)
    pos = QPointF(rnd.uniform(0, view.width()), rnd.uniform(0, view.height()))
    before = view.to_world(pos)
    lo, hi = view.zoom_limits()
    f = rnd.choice([1.2, 1 / 1.2, 1.5, 1 / 1.5])
    old = view.scale
    view.zoom_at(f, pos)
    if lo < old * f < hi:
        after = view.to_world(pos)
        assert G.dist(before, after) < 1e-6 * max(1.0, abs(before[0]) + abs(before[1])), \
            "the wheel moved the point under the cursor: %s -> %s" % (before, after)
    if f < 1:
        assert view.scale <= old + 1e-12, "a step out zoomed in (%.4g -> %.4g)" % (old,
                                                                                    view.scale)
    for _i in range(120):
        view.zoom_at(1 / 1.2, None)
    w, h = s.paper()
    box = (0.0, 0.0, w, h)
    if s.entities:
        box = G.bbox_union(box, s.extents())
    view.center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
    assert view_shows(view, box), "zoomed all the way out, the sheet and drawing don't show " \
        "(%.4g px/in, sheet %s at %s)" % (view.scale, s.size, s.scale_text())
    view.zoom("extents")
    # (steps show the last picture moved and scaled; once they stop it is drawn sharp, at the
    # view's own zoom and place)
    view.zoom_at(1.2, None)
    view.repaint()
    view._moving_until = 0.0
    view.repaint()
    assert view._shown is not None and view._shown[1] == view.scale and \
        view._shown[2] == view.center, "not drawn sharp at the view's zoom once it stopped"
    # (the wide picture, drawn while still: a step puts each point of it where the drawing's
    # point is now)
    view._make_wide()
    if view._wide is not None:
        _k, _k0, _c0, _pm, mx, my = view._wide
        pts = [view.to_world(QPointF(rnd.uniform(0, view.width()), rnd.uniform(0, view.height())))
               for _i in range(3)]
        before = [view.to_screen(q) for q in pts]
        view.zoom_at(rnd.choice([1.2, 1 / 1.2, 1 / 1.5]), QPointF(view.width() / 3,
                                                                  view.height() / 2))
        got = view._fast_view()
        if got is not None:
            t, _used = got
            off = mx if _used is view._wide[3] else 0
            offy = my if _used is view._wide[3] else 0
            for q, b in zip(pts, before):
                m = t.map(QPointF(b.x() + off, b.y() + offy))
                n = view.to_screen(q)
                assert abs(m.x() - n.x()) < 1e-4 and abs(m.y() - n.y()) < 1e-4, \
                    "the moved picture is off by %.3f px" % max(abs(m.x() - n.x()),
                                                               abs(m.y() - n.y()))
        view._moving_until = 0.0
        view.repaint()
    CHECKED["zoom"] += 1


# ---- an AutoCAD Electrical-style drawing ---------------------------------------------------------
def ace_like_dxf(path, devices=60, far=(12000.0, 8000.0), seed=7):
    """A DXF written as AutoCAD Electrical writes a schematic: a frame block bigger than an
    ANSI sheet with title attributes, device blocks with TAG1, MFG, CAT, DESC1-3, LOC and INST
    attributes (some hidden on the block, some hidden or moved on a copy, some aligned left),
    wires as lines between them and rung numbers as text, all far from the origin; the frame on
    a layer of its own named Border (the export's frame layer is BORDER). Made by the
    battery (no one's real drawing goes in the repository)."""
    import ezdxf
    rnd = random.Random(seed)
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 1
    ox, oy = far
    frame = doc.blocks.new("WD_TB_FRAME")
    frame.add_lwpolyline([(0, 0), (34, 0), (34, 22), (0, 22)], close=True)
    frame.add_lwpolyline([(0.5, 0.5), (33.5, 0.5), (33.5, 21.5), (0.5, 21.5)], close=True)
    frame.add_lwpolyline([(26, 0.5), (33.5, 0.5), (33.5, 3), (26, 3)], close=True)
    for i, tag in enumerate(("DWGNO", "TITLE1", "TITLE2", "DATE")):
        frame.add_attdef(tag, (26.2, 2.6 - 0.5 * i), dxfattribs={"height": 0.18})
    blk = doc.blocks.new("HCR1")
    blk.add_circle((0, 0), 0.25)
    blk.add_line((-0.6, 0), (-0.25, 0))
    blk.add_line((0.25, 0), (0.6, 0))
    tags = ("TAG1", "MFG", "CAT", "DESC1", "DESC2", "DESC3", "LOC", "INST")
    for i, tag in enumerate(tags):
        flags = 1 if tag in ("MFG", "CAT", "INST") else 0          # (hidden on the block)
        blk.add_attdef(tag, (0, 0.35 + 0.15 * i), dxfattribs={"height": 0.1, "flags": flags})
    doc.layers.add("Border", color=7)               # (the export's own frame layer, any case)
    msp = doc.modelspace()
    ref = msp.add_blockref("WD_TB_FRAME", (ox, oy), dxfattribs={"layer": "Border"})
    ref.add_auto_attribs({"DWGNO": "TEST-0001", "TITLE1": "SAMPLE", "TITLE2": "BATTERY",
                          "DATE": "2026-11-11"})
    for k in range(devices):
        x = ox + 2 + (k % 12) * 2.5
        y = oy + 20 - (k // 12) * 1.5
        r = msp.add_blockref("HCR1", (x, y), dxfattribs={"rotation": rnd.choice([0, 0, 90])})
        vals = {"TAG1": "CR%d" % (100 + k), "MFG": "AB", "CAT": "700-HA32A1",
                "DESC1": "CONTROL", "DESC2": "RELAY %d" % k, "DESC3": "", "LOC": "MCP",
                "INST": "PANEL"}
        r.add_auto_attribs(vals)
        for a in r.attribs:
            if rnd.random() < 0.15:
                a.dxf.flags = 1                                     # (hidden on this copy)
            elif rnd.random() < 0.15:
                ins = a.dxf.insert
                a.dxf.insert = (ins[0] + rnd.uniform(-0.5, 0.5), ins[1] + rnd.uniform(0.1, 0.6))
            if rnd.random() < 0.3:
                a.dxf.halign = 0                                    # (left aligned)
        msp.add_line((x - 0.6, y), (x - 1.9, y))                    # (a wire to the next)
        if k % 12 == 0:
            msp.add_text("%04d" % (100 + k // 12), dxfattribs={
                "insert": (ox + 0.8, y), "height": 0.12})
    doc.saveas(path)
    return path


# ---- Windows paths -----------------------------------------------------------------------------
def windows_paths(rnd, rounds=400):
    """The recent files list with Windows' path rules: each file once however its name is
    written (/ or \\, any case), the newest first, never longer than the limit, every entry as
    Windows writes it."""
    import ntpath
    from kanzonascad.paths import path_key, recent_list
    bases = ["C:\\Users\\me\\OneDrive - Co\\AutoCad\\BK010-FPC Test Sheet.kzcad",
             "C:\\Users\\me\\Downloads\\BK010-FPC-100-0002.dwg",
             "D:\\Jobs\\Drum Crusher.dwg", "\\\\server\\share\\panels\\MCP-1.kzcad",
             "C:\\Users\\me\\OneDrive - Co\\Chestnut Hill - General\\RO System\\New.kzcad"]

    def spelled(p):
        q = p
        if rnd.random() < 0.5 and not q.startswith("\\\\"):
            q = q.replace("\\", "/")
        if rnd.random() < 0.3:
            q = q.lower() if rnd.random() < 0.5 else q.upper()
        return q
    recent = []
    for _i in range(rounds):
        new = spelled(rnd.choice(bases))
        recent = recent_list(recent, new, 8, pathmod=ntpath)
        keys = [path_key(p, ntpath) for p in recent]
        assert len(keys) == len(set(keys)), "a file twice: %s" % recent
        assert keys[0] == path_key(new, ntpath), "the newest isn't first"
        assert len(recent) <= 8
        assert all("/" not in p for p in recent), "not written as Windows writes it: %s" % recent
    return "%d files opened and saved under mixed spellings: never listed twice" % rounds


# ---- Print -------------------------------------------------------------------------------------
def printed(path, chosen):
    """The PDF Print wrote has one page a sheet chosen."""
    import re
    with open(path, "rb") as f:
        n = len(re.findall(rb"/Type\s*/Page[^s]", f.read()))
    assert n == len(chosen), "printed %d sheet(s) on %d page(s)" % (len(chosen), n)
    CHECKED["print pages"] += 1


def print_lands(project, sheet, page_w, page_h, fit, dpi=20, box=None, turn_ok=True,
                whole=True):
    """Paint a sheet as Print does on a page_w x page_h page: its ink lies inside the sheet's
    paper as printed (worked out here: the paper turned when that makes it bigger, or for
    Actual size when its long side and the page's differ; as big as the page holds or real
    size; centered), and, fit to paper, that fills the page's width or height. box: the part
    printed (print_out.area_box: paper inches), the whole paper when None (then whole: its
    frame is printed, and fills the page fit to it); turn_ok: Orientation Automatic. Not
    skipped
    for a drawing that runs off its own paper (it prints past it, as on screen): then it is
    checked on a copy of the project with that sheet holding only what lies an inch (on
    paper) inside its edges."""
    import json
    from PySide6.QtGui import QColor, QImage, QPainter
    from kanzonascad import print_out, sheetframe
    # (its frame is printed only where the sheet shows its border: 0.18.4, border and zones
    # off, seed 61; without it the drawing alone needn't fill the page)
    whole = whole and sheetframe.shows(project, sheet, "border")
    w, h = sheet.paper_inches()
    k = sheet.k()

    def on_paper(b, m=k):
        # (an inch, on paper, inside its edges: what is drawn beside an object without being
        # one, a wire's number, can be past its box)
        return b[0] >= m and b[1] >= m and b[2] <= w * k - m and b[3] <= h * k - m
    # (the title block, drawn on every sheet, is in paper inches on the paper as laid out;
    # "Use as title block" can make one of anything, off the paper too)
    lw, lh = M.SHEET_SIZES[sheet.size]

    def tb_on_paper(b):
        return b[0] >= -1e-6 and b[1] >= -1e-6 and b[2] <= lw + 1e-6 and b[3] <= lh + 1e-6
    ext, tb_ext = sheet.extents(), project.title_block.extents()
    if (ext is not None and not on_paper(ext)) or (tb_ext is not None and
                                                   not tb_on_paper(tb_ext)):
        project = M.Project.from_dict(json.loads(json.dumps(project.to_dict())))
        sheet = project.sheet_by_id(sheet.id)
        tb = project.title_block
        with project.edit("only what is on the paper") as ed:
            for e in list(sheet.entities.values()):
                if not on_paper(e.bbox()):
                    ed.remove(sheet, e.id)
            for e in list(tb.entities.values()):
                if not tb_on_paper(e.bbox()):
                    ed.remove(tb, e.id)
        CHECKED["print lands (a copy)"] += 1
    full = box is None
    if full:
        box = (0.0, 0.0, w, h)
    bw, bh = box[2] - box[0], box[3] - box[1]
    if fit:
        flat, turned = min(page_w / bw, page_h / bh), min(page_w / bh, page_h / bw)
        turn = turn_ok and turned > flat + 1e-12
        f = turned if turn else flat
    else:
        turn = turn_ok and (bw > bh) != (page_w > page_h) and abs(bw - bh) > 1e-9 and \
            abs(page_w - page_h) > 1e-9
        f = 1.0
    pw, ph = (bh * f, bw * f) if turn else (bw * f, bh * f)
    x0, y0 = (page_w - pw) / 2, (page_h - ph) / 2
    img = QImage(max(1, round(page_w * dpi)), max(1, round(page_h * dpi)), QImage.Format_RGB32)
    img.fill(QColor("white"))
    pa = QPainter(img)
    print_out.paint_sheet(pa, project, sheet, page_w, page_h, dpi, fit,
                          box=None if full else box, turn_ok=turn_ok)
    pa.end()
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(0, img.width(), 2):
            if img.pixelColor(x, y).lightness() < 250:      # (hairlines: light gray)
                xs.append(x)
                ys.append(y)
    on_page = x0 >= -1e-9 and y0 >= -1e-9       # (the whole paper on the page: its frame shows)
    assert xs or not (whole and on_page), "nothing printed of sheet %s" % sheet.title
    if not xs:
        return None
    slack = 2
    assert min(xs) >= max(0, x0 * dpi) - slack and min(ys) >= max(0, y0 * dpi) - slack and \
        max(xs) <= (x0 + pw) * dpi + slack and max(ys) <= (y0 + ph) * dpi + slack, \
        "printed outside its paper: ink %s, paper %s on a %s page" % (
            (min(xs), min(ys), max(xs), max(ys)),
            tuple(round(c * dpi) for c in (x0, y0, x0 + pw, y0 + ph)), (page_w, page_h))
    if fit and whole:
        span = max((max(xs) - min(xs)) / dpi / page_w, (max(ys) - min(ys)) / dpi / page_h)
        assert span > 0.8, "fit to paper but printed small: %.0f%% of the page" % (span * 100)
    CHECKED["print lands"] += 1
    return True


# ---- a second window ---------------------------------------------------------------------------
def second_window(win, w2, project, listeners_before):
    """After a window opened on a project's sheet was closed: the family is back to the one
    window, and none of the closed window's listeners is left on the project."""
    assert win.family == [win], "%d windows left" % len(win.family)
    assert len(project.listeners) == listeners_before, \
        "listeners left behind: %d -> %d" % (listeners_before, len(project.listeners))
    assert not w2.isVisible(), "the closed window is still shown"
    CHECKED["second window"] += 1


# ---- footprints and their devices --------------------------------------------------------------
def footprints_follow(project):
    """Every footprint linked to a device shows that device's tag as it is now (renumbered,
    its sheet moved, undone...)."""
    from kanzonascad import tags
    index = tags.devices(project)
    for s in project.sheets:
        for e in s.inserts():
            if tags.is_footprint(e) and e.attrs.get("PARENT") in index:
                dev = index[e.attrs["PARENT"]][1]
                assert e.attrs.get("TAG") == dev.attrs.get("TAG"), \
                    "footprint shows %s, its device is %s" % (e.attrs.get("TAG"),
                                                              dev.attrs.get("TAG"))
                CHECKED["footprint follows its device"] += 1


def footprint_label_heights(project):
    """Every footprint's label sizing as the project's: its height for lines without a size of
    their own (tag_h) is Footprint label height times its drawing units per paper inch
    (label_k), whether its lines are shown or all hidden (0.26: hidden, they were left at the
    old height when it changed, and shown again took the sheet's units afresh)."""
    from kanzonascad import tags
    h = float(project.settings.get("fp_label_height", 0.08))
    for s in project.sheets:
        for e in s.inserts():
            if tags.is_footprint(e) and e.tag_h and e.label_k:
                assert abs(e.tag_h - h * e.label_k) <= 1e-9 * max(1.0, e.tag_h), \
                    "footprint %s's label %r tall, not %r x %r" % (
                        e.attrs.get("TAG"), e.tag_h, h, e.label_k)
                CHECKED["footprint label height and units agree"] += 1


def arrows_follow(project):
    """Every source arrow (and its destinations) goes by the number of the wire it sits on
    (0.18.6), worked out from the wires at its pin: unless that number is the name of other
    connectors on another wire already, or two pairs on wires of their own have the same number
    (renaming would join them)."""
    from kanzonascad import wirenums
    if not wirenums.enabled(project):
        return
    # (which wire each wire piece is part of, worked out from scratch)
    gs, _dist = wirenums.groups(project)
    group = {(sh.id, w.id): k for k, members in gs.items() for sh, w in members}
    names = {}
    on = {}
    srcs = []
    for s in project.sheets:
        for e in s.inserts():
            if e.defn is None or e.defn.wiring != "link":
                continue
            name = e.attrs.get("TAG", "").strip().upper()
            ws = [w for _n, q in e.pin_points() for w in s.query_point(q, 1e-6)
                  if getattr(w, "kind", "") == "wire" and w.touches(q, 1e-6)]
            if name:
                names.setdefault(name, []).append(e)
                on.setdefault(name, set()).update(group.get((s.id, w.id)) for w in ws)
            if e.block == wirenums.ARROWS[0]:
                nums = {w.num.upper() for w in ws if w.num}
                if len(nums) == 1 and name:
                    srcs.append((name, nums.pop(), group.get((s.id, ws[0].id))))
    wanted = {}
    for name, num, g in srcs:
        wanted.setdefault(num, set()).add(g)
    for name, num, g in srcs:
        if num == name or len(wanted[num]) > 1 or (num in names and on.get(num) != {g}):
            continue
        raise AssertionError("source arrow %s sits on wire %s" % (name, num))
    CHECKED["source arrows follow their wire's number"] += len(srcs)


def pdf_links_right(project, path, sheets):
    """Every cross-reference in an exported PDF (pages: the sheets, in order) that names a
    place on a sheet in it is a link over that place's text, to that sheet's page, zoomed to
    what it names; one naming a sheet left out (or "?") has none; no other links (0.23.1).
    Worked out from the drawing: the places as written ("2-B3", a rung's number) read against
    every sheet's zones and rungs; the object led to is one whose own place reads the same and
    that belongs with something on the sheet linking to it (a contact and its device, two
    connectors of a name), or, on a frozen sheet out of date, the zone named itself."""
    from pypdf import PdfReader
    from kanzonascad import xrefs
    reader = PdfReader(path)
    assert len(reader.pages) == len(sheets), (len(reader.pages), len(sheets))
    page_of = {pg.indirect_reference.idnum: i for i, pg in enumerate(reader.pages)}
    places = {}                     # place as written -> [sheet index in the PDF]
    for i, s in enumerate(sheets):
        num = project.sheet_number(s)
        for r in s.row_labels():
            for c in s.col_labels():
                places.setdefault(project.zone_format.format(sheet=num, row=r, col=c),
                                  []).append(i)
        places.setdefault("%s-?" % num, []).append(i)       # (outside the zones)
        for lad in s.ladders():
            for n in lad.numbers():
                if n:
                    places.setdefault(str(n), []).append(i)

    def ref_point(e):
        return e.pos if isinstance(e, M.Insert) else e.points[0]

    def to_page(s, x, y):
        return x * s.scale * 72.0, y * s.scale * 72.0

    def belongs(e, devs, parents, names):
        if not isinstance(e, (M.Insert, M.DashBox)):
            return False
        a = e.attrs
        if a.get("DEV") and a["DEV"] in parents or a.get("PARENT") and a["PARENT"] in devs:
            return True
        d = getattr(e, "defn", None)
        return d is not None and d.wiring == "link" and \
            a.get("TAG", "").strip().upper() in names

    def wrong(j, place, where, lo, hi):
        """Why link j isn't right for the place written (over lo..hi on its page), or None."""
        r = rects[j]
        if not (r[0] <= lo[0] + 0.01 and r[1] <= lo[1] + 0.01 and
                r[2] >= hi[0] - 0.01 and r[3] >= hi[1] - 0.01):
            return "the link over %r doesn't cover it: %s, %s" % (place, r, (lo, hi))
        dest = annots[j]["/Dest"]
        to = page_of[dest[0].idnum]
        if to not in where or dest[1] != "/FitR":
            return "%r leads to page %d, not %s" % (place, to + 1, [w + 1 for w in where])
        box = [float(v) for v in dest[2:6]]
        ts = sheets[to]
        W = float(reader.pages[to].mediabox.width)
        H = float(reader.pages[to].mediabox.height)
        if abs(box[2] - box[0] - W / 3.0) > 0.01 or abs(box[3] - box[1] - H / 3.0) > 0.01:
            return "a view of %s, not a third of the page" % box

        def aimed(x, y):
            # (in the box's middle, but for the page's edge it keeps to: then on that side of
            # the middle, in the box or past the page's edge)
            px, py = to_page(ts, x, y)
            for v, a, b, edge in ((px, box[0], box[2], W), (py, box[1], box[3], H)):
                c = (a + b) / 2.0
                if abs(c - v) > 0.01 and not (v < c and abs(a) < 0.01 or
                                              v > c and abs(b - edge) < 0.01):
                    return False
            return True
        unzoned = "%s-?" % project.sheet_number(ts)
        for e in ts.entities.values():
            if not belongs(e, devs, parents, names):
                continue
            q = ref_point(e)
            eb = e.bbox()
            if (project.zone_text(ts, q[0], q[1]) or unzoned) == place and \
                    aimed((eb[0] + eb[2]) / 2.0, (eb[1] + eb[3]) / 2.0):
                return None
        if held:
            x0, y0, x1, y1 = ts.layout_zone_frame()
            # (a place outside the sheet's zones, "2-?": the middle of its frame)
            if place == unzoned and aimed(*ts.turn((x0 + x1) / 2.0, (y0 + y1) / 2.0)):
                return None
            cw, rh = (x1 - x0) / ts.cols, (y1 - y0) / ts.rows
            for ri in range(ts.rows):
                for ci in range(ts.cols):
                    x, y = ts.turn(x0 + (ci + 0.5) * cw, y1 - (ri + 0.5) * rh)
                    if project.zone_text(ts, x, y) == place and aimed(x, y):
                        return None
        return "leads to nothing named %r: %s" % (place, box)

    def named_on(ts, place):
        """Whether a sheet holds something the text names (as wrong() finds it) at place."""
        unzoned = "%s-?" % project.sheet_number(ts)
        for e in ts.entities.values():
            if belongs(e, devs, parents, names):
                q = ref_point(e)
                if (project.zone_text(ts, q[0], q[1]) or unzoned) == place:
                    return True
        return False

    n_links = 0
    for i, s in enumerate(sheets):
        page = reader.pages[i]
        annots = [a.get_object() for a in (page.get("/Annots") or [])]
        rects = [[float(v) for v in a["/Rect"]] for a in annots]
        linked = []                 # (part, text, links over it, those right for it)
        unlinked = []
        devs = {e.attrs["DEV"] for e in s.entities.values()
                if isinstance(e, (M.Insert, M.DashBox)) and e.attrs.get("DEV")}
        parents = {e.attrs["PARENT"] for e in s.entities.values()
                   if isinstance(e, (M.Insert, M.DashBox)) and e.attrs.get("PARENT")}
        names = {e.attrs.get("TAG", "").strip().upper() for e in s.inserts()
                 if e.defn is not None and e.defn.wiring == "link"}
        held = xrefs.held(project, s)
        for item in xrefs.shown(project, s):
            t = xrefs.text_item(item)
            left = -t.width() / 2.0
            k = 0
            for part in item[2].split(", "):
                place = part.rsplit(" ", 1)[-1]
                a0 = left + M.text_width(item[2][:k + len(part) - len(place)], t.height)
                a1 = left + M.text_width(item[2][:k + len(part)], t.height)
                k += len(part) + 2
                corners = [G.rotate_point((t.pos[0] + x, t.pos[1] + y), t.pos, t.angle)
                           for x, y in ((a0, 0.0), (a1, 0.0), (a1, t.height), (a0, t.height))]
                bb = G.bbox_of(corners)
                lo, hi = to_page(s, bb[0], bb[1]), to_page(s, bb[2], bb[3])
                mid = ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0)
                over = [j for j, r in enumerate(rects)
                        if r[0] <= mid[0] <= r[2] and r[1] <= mid[1] <= r[3]]
                where = places.get(place, [])
                if not held:
                    # (only the pages holding what it names: a place as written can be on
                    # more than one sheet (rung 137 on two ladders, one numbered by hand), and
                    # the one it names may be left out of the PDF while another page has a
                    # rung of that number: the long battery, 0.25, seed 4923)
                    where = [w for w in where if named_on(sheets[w], place)]
                if not where:
                    # (no link of its own; one over it must be another text's, drawn over it
                    # or under it: looked at once the page's texts have taken theirs)
                    unlinked.append((part, item[2], over))
                    continue
                # (texts drawn over each other, contacts stacked by the steps: a link each,
                # one of those over it that is right for it, nearest first)
                near = sorted(over, key=lambda j: abs((rects[j][0] + rects[j][2]) / 2.0 -
                                                      mid[0]) +
                              abs((rects[j][1] + rects[j][3]) / 2.0 - mid[1]))
                assert near, "no link over %r of %r on sheet %s" % (
                    part, item[2], project.sheet_number(s))
                why = [wrong(j, place, where, lo, hi) for j in near]
                assert None in why, "%r on sheet %s: %s" % (item[2], project.sheet_number(s),
                                                            why[0])
                linked.append((part, item[2], len(over),
                               [j for j, w in zip(near, why) if w is None]))
        # (each its own: a link for every text that has one, no link for two. Taken one text
        # at a time, a text could take the link of a text drawn over its place and leave that
        # one none: an arrow's whole "6003B / 6-?" is its link, and two arrows a little apart
        # draw the second's text over the first's "6-?"; the short battery, 0.26, seed 5)
        owner = {}                  # link -> the text (index in linked) it is the link of

        def take(r, seen):
            for j in linked[r][3]:
                if j not in seen:
                    seen.add(j)
                    if j not in owner or take(owner[j], seen):
                        owner[j] = r
                        return True
            return False
        for r, (part, text, n_over, _right) in enumerate(linked):
            assert take(r, set()), "%d links over %r of %r on sheet %s, none its own" % (
                n_over, part, text, project.sheet_number(s))
            CHECKED["PDF cross-reference links lead to what they name"] += 1
        used = set(owner)
        for part, text, over in unlinked:
            assert all(j in used for j in over), \
                "a link over %r (%r), a place not in the PDF" % (part, text)
            CHECKED["PDF: no link of its own on a place not in it"] += 1
        extra = [rects[j] for j in range(len(rects)) if j not in used and
                 annots[j].get("/Subtype") == "/Link"]
        assert not extra, "links over no cross-reference on sheet %s: %s" % (
            project.sheet_number(s), extra)
        n_links += len(used)
    return n_links


# ---- a source arrow's wire number (0.19.11) ----------------------------------------------------
def own_wire_number_wrong(project, sheet, wire, split):
    """Why the number of a wire of its own (not a tap) at a source arrow is wrong, or None:
    a number of its page; but a wire on a distribution block outlet's T pin takes its block's
    phase number with the outlet's letter, wherever the block is (the manual: an outlet "on any
    sheet"; outlet 4 of page 25's PDB2501 on page 9 is 25005D: the long battery, 0.27, seed
    5022). Worked out from the drawing: the outlet's OUTLET, the wire on its block's L pin.
    split: wirenums.split."""
    num = wire.num
    for e in sheet.inserts():
        d = e.defn
        if d is None or d.wiring != "pdb" or not e.attrs.get("PARENT"):
            continue
        for n, q in e.pin_points():
            if not (n.startswith("T") and wire.touches(q)):
                continue
            k = (e.attrs.get("OUTLET") or "").strip()
            if not k.isdigit() or int(k) < 1:
                return None             # (an outlet not numbered yet: its wires wait for it)
            i, letter = int(k), ""
            while i:
                i, r = divmod(i - 1, 26)
                letter = chr(65 + r) + letter
            phase = set()
            for bs in project.sheets:
                for b in bs.inserts():
                    if b.defn is not None and b.defn.wiring == "pdb" and \
                            b.attrs.get("DEV") == e.attrs["PARENT"]:
                        q2 = dict(b.pin_points()).get("L" + n[1:])
                        phase |= {w.num for w in bs.wires()
                                  if q2 is not None and w.num and w.touches(q2)}
            if len(phase) != 1:
                return None             # (no block, or its phase not numbered: nothing to say)
            want = phase.pop() + letter
            CHECKED["a source's wire on a distribution outlet takes its phase's number"] += 1
            return None if num == want else "a source arrow's wire on outlet %s's %s took %s, " \
                "not %s" % (k, n, num, want)
    got = split(num)
    if got is None or got[0] != project.sheet_number(sheet):
        return "a source arrow's wire on page %s took %s from a destination's page" % (
            project.sheet_number(sheet), num)
    return None


# ---- devices without a footprint (0.25) --------------------------------------------------------
def missing_footprints(project):
    """{(sheet id, entity id)} of the devices that need a footprint and have none, worked out
    here from every object of every sheet, from the rules (not missing_fp.py's code): a placed
    schematic symbol that is a device or parent with a tag prefix and isn't an off-sheet link;
    not ticked NO_FP; not in the field (its LOC, else its sheet's location: FIELD..., or, when a
    panel sheet names a location, one no panel sheet names); and no footprint on a panel sheet
    linked to it (PARENT its DEV) nor an unlinked one with its tag."""
    panels = [s for s in project.sheets if s.kind == "panel"]
    named = {s.location.strip().upper() for s in panels if s.location.strip()}
    linked, tagged = set(), set()
    for s in panels:
        for e in s.entities.values():
            if isinstance(e, M.Insert) and e.defn is not None and e.defn.kind == "footprint":
                if e.attrs.get("PARENT"):
                    linked.add(e.attrs["PARENT"])
                elif e.attrs.get("TAG", "").strip():
                    tagged.add(e.attrs["TAG"].strip().upper())
    out = set()
    for s in project.sheets:
        for e in s.entities.values():
            d = getattr(e, "defn", None)
            if not isinstance(e, M.Insert) or d is None or d.kind != "symbol":
                continue
            if d.role not in ("device", "parent") or not d.prefix or d.wiring == "link":
                continue
            if e.attrs.get("NO_FP") == "1":
                continue
            loc = ((e.attrs.get("LOC") or "").strip() or s.location or "").strip().upper()
            if loc.startswith("FIELD") or (loc and named and loc not in named):
                continue
            if e.attrs.get("DEV") and e.attrs["DEV"] in linked:
                continue
            if e.attrs.get("TAG", "").strip().upper() in tagged:
                continue
            out.add((s.id, e.id))
    return out


def missing_right(win, project):
    """The check's devices are those worked out here; the status bar counts them; the sheet
    shown marks each of its own (the marks on) or none (off)."""
    from kanzonascad import missing_fp
    want = missing_footprints(project)
    got = {(s.id, e.id) for s, e in missing_fp.find(project).missing}
    assert got == want, "devices without a footprint: %d listed, %d worked out (%s more, %s " \
        "fewer)" % (len(got), len(want), sorted(got - want)[:4], sorted(want - got)[:4])
    b = win.missing_fp_button
    if want:
        assert b.text() == missing_fp.describe(len(want)) and not b.isHidden(), \
            "the status bar says %r for %d" % (b.text(), len(want))
    else:
        assert b.isHidden(), "the status bar shows %r with none" % b.text()
    v = win.view()
    s = v.sheet()
    boxes = missing_fp.marks(project, s)
    mine = sorted(s.entities[i].bbox() for sid, i in want if sid == s.id)
    assert sorted(boxes) == (mine if missing_fp.marks_on(project) else []), \
        "%d orange marks on the sheet, %d devices without a footprint there" % (
            len(boxes), len(mine))
    CHECKED["devices without a footprint"] += 1


TWIN = "Battery twin"           # (a symbol and a footprint of this one name: op_same_name)


def twins_apart(project):
    """(0.25) Every copy placed as the symbol or the footprint named TWIN (its TWIN attribute
    says which, set where it was placed) still draws a block of that kind, the project's
    block of its name that kind, shown by the name both share; and the project has one block
    of each kind for it (never one in the other's place)."""
    seen = set()
    for s in project.sheets:
        for e in s.inserts():
            want = e.attrs.get("TWIN")
            if not want:
                continue
            d = project.blocks.get(e.block)
            assert d is not None and e.defn is not None, "a %s copy of %s without its block" % (
                want, TWIN)
            assert (d.kind, e.defn.kind) == (want, want), \
                "a %s copy of %s draws the %s %s (block %r): one took the other's place" % (
                    want, TWIN, d.kind, d.shown_name, e.block)
            assert e.block_name == TWIN, "%s shown as %r" % (TWIN, e.block_name)
            seen.add(want)
    for kind in seen:
        got = [n for n, b in project.blocks.items() if b.kind == kind and b.shown_name == TWIN]
        assert len(got) == 1, "the project has %d %ss named %s: %r" % (len(got), kind, TWIN,
                                                                       got)
    if len(seen) == 2:
        CHECKED["a symbol and a footprint of one name kept apart"] += 1


TOL = 1e-6


def _has_term(e):
    d = getattr(e, "defn", None)
    return isinstance(e, M.Insert) and d is not None and d.kind == "symbol" and \
        any(a.get("attr") == "TERM" for a in d.attr_texts)


def _wire_group(wires, start):
    """The wires joined to start (one's end on another), worked out wire by wire."""
    out = {w.id for w in start}
    todo = list(start)
    while todo:
        w = todo.pop()
        for o in wires:
            if o.id in out:
                continue
            if any(o.touches(q, TOL) for q in (w.points[0], w.points[-1])) or \
                    any(w.touches(q, TOL) for q in (o.points[0], o.points[-1])):
                out.add(o.id)
                todo.append(o)
    return out


def strips_right(project):
    """(0.27) The terminal strips as the terminals on the drawing say, worked out here from
    every terminal and wire (not strips.py's nets or wirenums' groups): every terminal is in
    exactly one strip, the one of its strip device's tag (else its own); a strip's numbers are
    each on one row; a strip with nothing kept is in number order; each terminal's wire numbers
    (both sides) are those of the wires on its pins, and what its wires land on on its own
    sheet (both sides) the pins of the symbols those wires reach there (off-sheet connectors
    and arrows not landings); its internal and external sides are two of its pins."""
    from kanzonascad import strips, wirenums
    found = strips.find(project)
    seen = collections.Counter()
    by_place = {}
    devs = {}
    for s in project.sheets:
        for e in s.inserts():
            d = e.defn
            if d is not None and d.kind == "symbol" and d.role in ("device", "parent") and \
                    d.prefix and e.attrs.get("DEV"):
                devs[e.attrs["DEV"]] = e
    kept = project.settings.get("strips") or {}
    for st in found:
        nums = [r.num for r in st.rows if r.num]
        assert len(nums) == len(set(nums)), "strip %s has a number twice: %r" % (st.tag, nums)
        if st.key not in kept and "tag:" + st.tag.upper() not in kept:
            assert nums == sorted(nums, key=strips.natural), \
                "strip %s out of number order with nothing kept: %r" % (st.tag, nums)
            CHECKED["terminal strip in number order"] += 1
        for r in st.rows:
            assert r.spare == (not r.places), "terminal %s-%s: spare %r, drawn %d times" % (
                st.tag, r.num, r.spare, len(r.places))
            for s, e in r.places:
                seen[(s.id, e.id)] += 1
                by_place[(s.id, e.id)] = (st, r)
    numbered = wirenums.enabled(project)
    for s in project.sheets:
        terms = [e for e in s.inserts() if _has_term(e)]
        if not terms:
            continue
        wires = list(s.wires())
        many = len(wires) > 1500 or any(w.own_num for w in wires)
        for e in terms:
            assert seen[(s.id, e.id)] == 1, "terminal %s on sheet %s in %d strips' rows" % (
                e.id, s.id, seen[(s.id, e.id)])
            st, r = by_place[(s.id, e.id)]
            par = devs.get(e.attrs.get("PARENT") or "")
            want = ((par if par is not None else e).attrs.get("TAG") or "").strip() or "TB?"
            assert st.tag == want, "terminal %s on strip %s, not %s" % (e.id, st.tag, want)
            assert r.num == (e.attrs.get("TERM") or "").strip(), (r.num, e.attrs.get("TERM"))
            pins = dict(e.pin_points())
            mine = [x for x in (r.inside, r.outside) if x is not None]
            assert all(x.pin in pins for x in mine) and len({x.pin for x in mine}) == len(mine), \
                "terminal %s-%s's sides %r" % (st.tag, r.num, [x.pin for x in mine])
            if many or len(r.places) != 1:
                continue
            on = [w for q in pins.values() for w in wires if w.touches(q, TOL)]
            want_nums = {w.num or "?" for w in on} if numbered else set()
            got_nums = {n for x in mine for n in x.wires}
            assert got_nums == want_nums, "terminal %s-%s: wires %r, on its pins %r" % (
                st.tag, r.num, sorted(got_nums), sorted(want_nums))
            lands, linked = set(), False
            for name, q in pins.items():
                group = _wire_group(wires, [w for w in wires if w.touches(q, TOL)])
                ws = [w for w in wires if w.id in group]
                for x in s.inserts():
                    d = x.defn
                    if d is None or d.kind != "symbol" or not d.pins:
                        continue
                    for pn, xq in x.pin_points():
                        if (x.id, pn) == (e.id, name) or not any(w.touches(xq, TOL)
                                                                 for w in ws):
                            continue
                        if d.wiring == "link":
                            linked = True       # (on through a connector: maybe back here)
                        else:
                            lands.add((x.id, pn))
            if linked:
                continue
            got = {(x.id, pn) for side in mine for sh, x, pn in side.to if sh is s}
            assert got == lands, "terminal %s-%s lands on %s, its wires reach %s" % (
                st.tag, r.num, sorted(got), sorted(lands))
            CHECKED["terminal's wires and landings"] += 1


def _union_groups(wires):
    """{wire id: root} of a sheet's wires joined where one's end lies on another (its end or
    its middle), worked out pair by pair here (not wirenums' groups)."""
    up = {w.id: w.id for w in wires}

    def find(k):
        while up[k] != k:
            up[k] = up[up[k]]
            k = up[k]
        return k
    for i, a in enumerate(wires):
        ea = (a.points[0], a.points[-1])
        for b in wires[i + 1:]:
            if any(b.touches(q, TOL) for q in ea) or \
                    any(a.touches(q, TOL) for q in (b.points[0], b.points[-1])):
                ra, rb = find(a.id), find(b.id)
                if ra != rb:
                    up[rb] = ra
    return {k: find(k) for k in up}


def panel_wiring_right(project):
    """(0.28) The device wiring list and the terminal wire labels as the drawing says, worked
    out here from every wire and pin (not strips.py's nets or wirenums' groups): wires joined
    end to end or end on a middle on a sheet, joined across sheets at off-sheet connectors and
    arrows of one name; each pin of each device (its symbol and those linked to it) and of
    each strip's terminal (every place it is drawn) is a row for each wire group on it, with
    those wires' numbers and the other pins the group lands on (with their location when it
    isn't the device's), and a pin with no wire one empty row; and on a panel sheet showing
    them, each terminal of a device's footprint (its pins, named as the device's) carries a
    label for each of those groups, "number → landings", read across or upward, just off its
    pin. A group with a wire numbered on its own (its taps kept apart) is left out."""
    from kanzonascad import panelwiring, pull, strips, wirenums
    numbered = wirenums.enabled(project)
    sheets = list(project.sheets)
    groups, unsure = {}, set()
    for s in sheets:
        ws = list(s.wires())
        if len(ws) > 600:
            for w in ws:
                groups[(s.id, w.id)] = (s.id, "big")
            unsure.add((s.id, "big"))
            continue
        got = _union_groups(ws)
        for w in ws:
            groups[(s.id, w.id)] = (s.id, got[w.id])
            if w.own_num:
                unsure.add((s.id, got[w.id]))
    # (across sheets: the groups on connectors of one name are one net)
    net = {}

    def find(k):
        while net.get(k, k) != k:
            k = net[k]
        return k

    def on_pin(s, q):
        return [w for w in s.wires() if w.touches(q, TOL)]
    first = {}
    for s in sheets:
        for e in s.inserts():
            d = e.defn
            if d is None or d.wiring != "link":
                continue
            name = (e.attrs.get("TAG") or "").strip().upper()
            if not name:
                continue
            for _n, q in e.pin_points():
                for w in on_pin(s, q):
                    g = groups[(s.id, w.id)]
                    if name not in first:
                        first[name] = g
                    a, b = find(first[name]), find(g)
                    if a != b:
                        net[b] = a
    bad = {find(g) for g in unsure}
    # (every pin wires land on, by net)
    lands = collections.defaultdict(list)
    devs, strip_tags, dev_tags = {}, {}, {}
    for s in sheets:
        for e in s.inserts():
            d = e.defn
            if d is None or d.kind != "symbol":
                continue
            if d.role in ("device", "parent") and d.prefix and e.attrs.get("DEV"):
                devs[e.attrs["DEV"]] = (s, e)
            if not d.pins or d.wiring == "link":
                continue
            for name, q in e.pin_points():
                for g in {find(groups[(s.id, w.id)]) for w in on_pin(s, q)}:
                    lands[g].append((s, e, name))
    for dev, (s, e) in devs.items():
        t = (e.attrs.get("TAG") or "").strip().upper()
        if t:
            (strip_tags if e.defn.prefix == "TB" and e.defn.role == "parent"
             else dev_tags).setdefault(t, dev)
    # (the units: devices with their linked symbols, terminals of strips)
    units = {}
    for i, s in enumerate(sheets):
        for e in s.inserts():
            d = e.defn
            if d is None or d.kind != "symbol" or d.wiring == "link":
                continue
            tag = (e.attrs.get("TAG") or "").strip()
            par = e.attrs.get("PARENT") or ""
            main = False
            if _has_term(e):
                num = (e.attrs.get("TERM") or "").strip()
                strip = par if par in devs else "tag:" + tag.upper()
                if strip.startswith("tag:") and strip[4:] in strip_tags:
                    strip = strip_tags[strip[4:]]
                stag = ((devs[strip][1] if strip in devs else e).attrs.get("TAG") or
                        "").strip() or "TB?"
                key, name = (("term", strip, num), "%s-%s" % (stag, num)) if num else (
                    ("one", s.id, e.id), stag)
                main = True
            elif d.role in ("device", "parent") and d.prefix:
                key, name, main = ("dev", e.attrs.get("DEV")) if e.attrs.get("DEV") else (
                    "one", s.id, e.id), tag or "?", True
            elif d.role == "child":
                if par in devs:
                    key, name = ("dev", par), (devs[par][1].attrs.get("TAG") or "").strip() or "?"
                elif tag:
                    key, name = ("tag", tag.upper()), tag
                else:
                    key, name = ("one", s.id, e.id), e.block_name
            else:
                continue
            u = units.setdefault(key, {"name": name, "syms": []})
            u["syms"].append(((0 if main else 1, i, -e.pos[1], e.pos[0]), s, e))
    for key, u in units.items():
        u["syms"].sort(key=lambda t: t[0])
        u["loc"] = pull.location_of(*devs[key[1]]) if key[0] == "dev" and key[1] in devs \
            else pull.location_of(u["syms"][0][1], u["syms"][0][2])

    def landing_names(g, me, loc):
        out = set()
        for s, x, pin in lands.get(g, ()):
            if s is me[0] and x is me[1] and pin == me[2]:
                continue
            n = pull.landing_name(x, pin)
            there = pull.location_of(s, x)
            out.add(n + (" (%s)" % there if there and there != loc else ""))
        # (as written: a block's name may hold a comma, "PLC ... module, points 8-15")
        return sorted(out, key=strips.natural)

    def pin_ends(s, e, name, q, loc):
        """[(numbers, landings)] of the groups on a pin, or None when one is left out."""
        by = collections.OrderedDict()
        for w in on_pin(s, q):
            by.setdefault(find(groups[(s.id, w.id)]), []).append(w)
        if any(g in bad for g in by):
            return None
        return [(frozenset((w.num or "?") for w in ws) if numbered else frozenset(),
                 tuple(landing_names(g, (s, e, name), loc))) for g, ws in by.items()]
    want, skip = collections.Counter(), set()
    ends_of = {}
    for key, u in units.items():
        for _k, s, e in u["syms"]:
            for name, q in e.pin_points():
                got = pin_ends(s, e, name, q, u["loc"])
                if got is None:
                    skip.add((u["name"], name))
                    continue
                ends_of.setdefault(key, {}).setdefault(name, []).extend(got)
                for nums, to in got or [(None, None)]:
                    want[(u["name"], name, nums, ", ".join(to) if to is not None else None,
                          u["loc"])] += 1

    def split(t):
        return frozenset(x for x in t.split(", ") if x) if t else frozenset()
    have = collections.Counter()
    for r in panelwiring.rows(project):
        if (r[0], r[1]) in skip:
            continue
        nums = split(r[2]) if r[2] or r[6] else None
        to = r[6] if r[2] or r[6] else None
        have[(r[0], r[1], nums, to, r[7])] += 1
    # (a group with no number (numbering off) and landing nowhere: an "empty" row both ways)
    for k in list(want):
        if k[2] == frozenset() and k[3] == "":
            n = want.pop(k)
            want[(k[0], k[1], None, None, k[4])] += n
    assert want == have, "wiring list: missing %s; not on the drawing %s" % (
        sorted(map(str, (want - have).elements()))[:4],
        sorted(map(str, (have - want).elements()))[:4])
    CHECKED["wiring list as the wires and pins say"] += 1
    # ---- the labels on the footprints' terminals
    for s in sheets:
        if s.kind != "panel":
            assert not panelwiring.labels(project, s), "terminal labels on a sheet not a panel"
            continue
        got = panelwiring.labels(project, s)
        if not s.terminal_labels:
            assert not got, "terminal labels on a panel sheet with them off"
            continue
        h = panelwiring.label_height(project) * s.k()
        want_l = collections.Counter()
        spots = []
        unsure_here = False
        for f in s.inserts():
            d = f.defn
            if d is None or d.kind != "footprint" or not d.pins:
                continue
            par = f.attrs.get("PARENT") or ""
            tag = (f.attrs.get("TAG") or "").strip().upper()
            term = (f.attrs.get("TERM") or "").strip()
            if term:
                if par and par in devs and devs[par][1].defn.prefix == "TB" and \
                        devs[par][1].defn.role == "parent":
                    key = ("term", par, term)
                elif not par and tag:
                    key = ("term", strip_tags.get(tag, "tag:" + tag), term)
                else:
                    continue
            elif par:
                key = ("dev", par)
            elif tag:
                key = ("dev", dev_tags[tag]) if tag in dev_tags else ("tag", tag)
            else:
                continue
            if key not in units:
                continue
            u = units[key]
            for name, q in f.pin_points():
                if (u["name"], name) in skip:
                    unsure_here = True
                    continue
                ends = ends_of.get(key, {}).get(name, [])
                n = 0
                for nums, to in ends:
                    if nums or to:
                        # (a label names three pins at most: the first two, then how many more)
                        most = panelwiring.MOST
                        shown = ", ".join(to) if len(to) <= most else "%s +%d" % (
                            ", ".join(to[:most - 1]), len(to) - most + 1)
                        want_l[(nums, shown)] += 1
                        n += 1
                if n:
                    spots.append((q, n))
        if unsure_here:
            continue

        have_l = collections.Counter()
        for t in got:
            assert t.angle in (0.0, 90.0), "a terminal label at %g degrees" % t.angle
            assert abs(t.height - h) < 1e-9, "a terminal label %g tall, not %g" % (t.height, h)
            num, _sep, to = t.text.partition(panelwiring.ARROW)
            if not _sep and t.text.startswith(panelwiring.ARROW.strip() + " "):
                num, to = "", t.text[len(panelwiring.ARROW.strip()) + 1:]
            have_l[(split(num), to)] += 1
            assert any(G.dist(t.pos, q) <= 0.4 * h + (n - 1) / 2.0 * 1.3 * h + 1e-6 * (1 + h)
                       for q, n in spots), "a terminal label %r far from every terminal" % t.text
        assert want_l == have_l, "terminal labels on sheet %s: missing %s; wrong %s" % (
            s.id, sorted(map(str, (want_l - have_l).elements()))[:3],
            sorted(map(str, (have_l - want_l).elements()))[:3])
        if want_l:
            CHECKED["terminal wire labels as the wires and pins say"] += 1
