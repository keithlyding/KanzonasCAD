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
No Qt here except through the view passed in.
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
    assert any(G.dist(gq, c) < 1e-6 for c in cands), \
        "%s snap at %s is no %s point of any object near %s" % (kind, gq, kind, p)
    CHECKED["snap " + kind] += 1
    return kind


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
