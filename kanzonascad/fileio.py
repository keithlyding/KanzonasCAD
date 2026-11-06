"""DXF import and export (through ezdxf, imported only when used), DWG import (ezdwg, imported
only when used) and PDF export (Qt's own PDF writer: vector lines and outlined text, one page
per sheet at its real size)."""

import math
import os
import sys

from . import model as M
from . import geometry as G
from .sheetframe import frame_entities, printing, FRAME_LAYER

MM = 1 / 25.4
# $INSUNITS -> inches per drawing unit (0 = unitless: taken as inches)
_UNITS = {0: 1.0, 1: 1.0, 2: 12.0, 4: MM, 5: MM * 10, 6: MM * 1000}


def _true_color(hexcolor):
    h = hexcolor.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ============================================================================================
# DXF export
# ============================================================================================
def export_dxf(project, sheet, path, include_frame=True):
    """Write one sheet as a DXF in inches (AutoCAD 2013 format). The border, zones and title
    block go on layer BORDER."""
    import ezdxf
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 1
    doc.header["$MEASUREMENT"] = 0
    w, h = sheet.paper()
    doc.header["$LIMMIN"] = (0, 0)
    doc.header["$LIMMAX"] = (w, h)
    for name, lay in project.layers.items():
        if name == "0":
            continue
        dl = doc.layers.add(name)
        _layer_color(dl, lay.color)
        if not lay.visible:
            dl.off()
    if include_frame and FRAME_LAYER not in project.layers:
        doc.layers.add(FRAME_LAYER, color=7)
    l0 = doc.layers.get("0")
    _layer_color(l0, project.layer_color("0"))
    msp = doc.modelspace()
    ents = []
    from . import crossings
    jumps = crossings.jumps(project, sheet)
    r = crossings.size(sheet)
    for e in sheet.entities.values():
        if isinstance(e, M.WireCross):
            continue                    # (drawn through the jump it makes, below)
        if isinstance(e, M.Wire) and jumps:
            # wires with gaps or loops: cut where they jump
            for pts in crossings.cut_wire(e, jumps, r):
                ents.append(e.copy(points=[list(q) for q in pts]))
            continue
        # block references go out as their lines and texts, on the reference's layer
        ents.extend(e.exploded() if isinstance(e, (M.Insert, M.Composite)) else [e])
    for p, u, _cu, st in jumps:
        if st == "loop":
            ents.append(M.Polyline(crossings.loop_points(p, u, r), layer="WIRES"
                                   if "WIRES" in project.layers else "0"))
    if include_frame:
        with printing():                # ({Print date}: now)
            ents = frame_entities(project, sheet) + ents
    # the cross-references, as plain texts on layer SYMBOLS
    from .xrefs import texts as xref_texts
    for t in xref_texts(project, sheet):
        t.layer = "SYMBOLS" if "SYMBOLS" in project.layers else "0"
        ents.append(t)
    # the wire numbers, on layer WIRES
    from .wirenums import labels
    for t in labels(project, sheet):
        ents.append(t.copy(layer="WIRES" if "WIRES" in project.layers else "0"))
    for e in ents:
        _write(msp, e)
    doc.saveas(path)


def _layer_color(dl, color):
    if color in (None, M.ADAPTIVE):
        dl.color = 7
    else:
        try:
            dl.rgb = _true_color(color)
        except (ValueError, IndexError):
            dl.color = 7


def _write(msp, e):
    attribs = {"layer": e.layer or "0"}
    ent = None
    if isinstance(e, M.Line):
        ent = msp.add_line(e.p1, e.p2, dxfattribs=attribs)
    elif isinstance(e, M.Polyline):
        ent = msp.add_lwpolyline(e.points, close=e.closed, dxfattribs=attribs)
    elif isinstance(e, M.Circle):
        ent = msp.add_circle(e.center, e.radius, dxfattribs=attribs)
    elif isinstance(e, M.Arc):
        ent = msp.add_arc(e.center, e.radius, e.start, e.end, dxfattribs=attribs)
    elif isinstance(e, M.Text):
        from ezdxf.enums import TextEntityAlignment
        attribs.update(height=e.height, rotation=e.angle)
        ent = msp.add_text(e.text, dxfattribs=attribs)
        h = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}[e.align]
        v = {"baseline": "", "bottom": "BOTTOM_", "middle": "MIDDLE_", "top": "TOP_"}[e.valign]
        ent.set_placement(e.pos, align=TextEntityAlignment[v + h])
    if ent is not None and e.color not in (None, M.ADAPTIVE):
        try:
            ent.rgb = _true_color(e.color)
        except (ValueError, IndexError):
            pass


# ============================================================================================
# DXF import
# ============================================================================================
def read_dxf(path, include_paperspace=False, units=None, keep_blocks=True):
    """Entities of a DXF's model space, in inches, plus a report:
    (entities, {"layers": {name: hex color}, "skipped": {dxftype: count}, "units": name}).
    units: the drawing's $INSUNITS when the file's own can't be trusted (a converted DWG)."""
    import ezdxf
    from ezdxf import recover
    try:
        doc = ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        doc, _auditor = recover.readfile(path)
    return read_doc(doc, include_paperspace, units, keep_blocks)


def read_doc(doc, include_paperspace=False, units=None, keep_blocks=True):
    """read_dxf for an ezdxf document already open (a DWG read by dwgread)."""
    if units is None:
        units = int(doc.header.get("$INSUNITS", 0) or 0)
    k = _UNITS.get(units, 1.0)
    layers = {}
    for dl in doc.layers:
        layers[dl.dxf.name] = _dxf_layer_color(dl)
    out, skipped = [], {}
    blocks = {}                 # each block's drawing, read once (_block_parts)
    for de in doc.modelspace():
        _read(de, k, out, skipped, 0, blocks, keep_blocks)
    # some makers' drawings are drawn in a layout (paper space), model space all but empty:
    # then the layouts' drawing comes in too (their viewports don't: they show model space)
    from_layouts = 0
    if include_paperspace or len(out) < PAPER_FALLBACK:
        paper, pskip = [], {}
        for layout in doc.layouts:
            if layout.is_modelspace:
                continue
            for de in layout:
                if de.dxftype() != "VIEWPORT":
                    _read(de, k, paper, pskip, 0, blocks, keep_blocks)
        if include_paperspace or len(paper) > len(out):
            out += paper
            from_layouts = len(paper)
            for t, n in pskip.items():
                skipped[t] = skipped.get(t, 0) + n
    unit_name = {0: "unitless (taken as inches)", 1: "inches", 2: "feet", 4: "millimeters",
                 5: "centimeters", 6: "meters"}.get(units, "units %d (taken as inches)" % units)
    return out, {"layers": layers, "skipped": skipped, "units": unit_name,
                 "from_layouts": from_layouts}


PAPER_FALLBACK = 20     # model space with fewer pieces than this: the layouts are read too


def _dxf_layer_color(dl):
    try:
        rgb = dl.rgb
        if rgb:
            return "#%02x%02x%02x" % tuple(rgb)
    except (AttributeError, TypeError, ValueError):
        pass                            # no true color: the color number below
    c = abs(int(dl.dxf.get("color", 7) or 7))
    if c == 7:
        return M.ADAPTIVE
    try:
        from ezdxf.colors import aci2rgb
        r, g, b = aci2rgb(c)
        return "#%02x%02x%02x" % (r, g, b)
    except (IndexError, TypeError, ValueError):
        return M.ADAPTIVE               # not a known color number: black/white


def _entity_color(de):
    try:
        if de.dxf.hasattr("true_color"):
            r, g, b = de.rgb
            return "#%02x%02x%02x" % (r, g, b)
        c = de.dxf.get("color", 256)
        if c not in (0, 256, 7) and c is not None:
            from ezdxf.colors import aci2rgb
            r, g, b = aci2rgb(int(c))
            return "#%02x%02x%02x" % (r, g, b)
    except (AttributeError, IndexError, TypeError, ValueError):
        pass                            # unreadable color: the layer's
    return None


def _block_parts(de, k, skipped, depth, blocks):
    """A block's drawing in its own coordinates (inches, relative to its base point), read
    once for all its copies: [(entity, its layer was 0)]."""
    name = de.dxf.name
    got = blocks.get(name)
    if got is None:
        blk = de.block()
        if blk is None:
            raise ValueError("block %s is missing" % name)
        bx, by = blk.block.dxf.base_point[0] * k, blk.block.dxf.base_point[1] * k
        parts, left = [], {}
        for sub in blk:
            if sub.dxftype() == "ATTDEF":
                continue                # (the empty field of a block, not drawn on its copies)
            _read(sub, k, parts, left, depth + 1, blocks)
        got = blocks[name] = ([(e.moved(-bx, -by), e.layer == "0") for e in parts], left)
    for t, n in got[1].items():
        skipped[t] = skipped.get(t, 0) + n
    return got[0]


# AutoCAD Electrical's attribute names -> KanzonasCAD's (a panel footprint's P_TAG1 is the tag
# of the schematic device it belongs to; DESC1-3 are its description lines)
ACE_ATTRS = {"TAG1": "TAG", "P_TAG1": "TAG", "TAG": "TAG", "MFG": "MFR", "MFR": "MFR",
             "CAT": "CAT", "DESC1": "DESC", "DESC2": "DESC", "DESC3": "DESC", "DESC": "DESC"}


def _attr_name(tag):
    t = str(tag or "").strip().upper()
    return ACE_ATTRS.get(t, t)


def _dimension(de, P, k, kw):
    """A DXF linear or aligned DIMENSION as KanzonasCAD's own (it measures, its grips move
    its points), when it reads the same: the same type and direction, the same measurement
    (no scale factor: DIMLFAC), its text (an override kept; "<>" stands for the length). None
    otherwise (then taken apart into its lines, arrows and text as before)."""
    d = de.dxf
    kind = int(d.get("dimtype", 0)) & 7
    if kind not in (0, 1) or not d.hasattr("defpoint2") or not d.hasattr("defpoint3"):
        return None
    try:
        ov = de.override()
        if abs(float(ov.get("dimlfac", 1.0) or 1.0) - 1.0) > 1e-9:
            return None
        h = None
        blk = de.get_geometry_block()
        if blk is not None:
            for x in blk:
                if x.dxftype() in ("MTEXT", "TEXT"):
                    h = x.dxf.get("char_height" if x.dxftype() == "MTEXT" else "height")
                    break
        if not h:
            h = float(ov.get("dimtxt", 0.18) or 0.18) * float(ov.get("dimscale", 1.0) or 1.0)
    except (AttributeError, TypeError, ValueError):
        return None
    a, b, loc = P(d.defpoint2), P(d.defpoint3), P(d.defpoint)
    if kind == 0 and G.dist(a, b) > 1e-12:
        # a linear one turned along its two points measures as an aligned one does (ezdxf
        # and some programs save aligned dimensions so)
        along = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0
        ang = float(d.get("angle", 0.0)) % 180.0
        if min(abs(along - ang), 180.0 - abs(along - ang)) < 1e-6 and \
                min(along, 180.0 - along) > 1e-6 and abs(along - 90.0) > 1e-6:
            kind = 1
    text = str(d.get("text", "") or "")
    if text.strip() in ("<>", " "):
        text = ""
    dim = M.Dimension(a, b, loc, "aligned" if kind == 1 else "linear", h * k,
                      text if text != "<>" else "", **dict(kw, layer=kw["layer"]))
    (ux, uy), value = dim.direction()
    if kind == 0:
        ang = float(d.get("angle", 0.0)) % 180.0
        want = (1.0, 0.0) if abs(ang) < 1e-6 or abs(ang - 180.0) < 1e-6 else \
            ((0.0, 1.0) if abs(ang - 90.0) < 1e-6 else None)
        if want is None or (abs(ux - want[0]) > 1e-9 or abs(uy - want[1]) > 1e-9):
            return None                     # (a rotated one, or the other way: as it was)
    m = d.get("actual_measurement")
    if m is not None and abs(m * k - value) > 1e-6 * max(1.0, value):
        return None
    return dim


def _mleaders(de, P, k, kw, out):
    """A MULTILEADER as KanzonasCAD leaders, one per leader line: its note (the MTEXT's
    text) or its balloon (a block's first attribute: the item number) on the first. False
    when it can't be read that way (then taken apart into lines and texts)."""
    try:
        c = de.context
        h = (c.char_height or 0.18) * k
        text, balloon = "", False
        if c.mtext is not None and c.mtext.default_content:
            from ezdxf.tools.text import plain_mtext
            text = plain_mtext(c.mtext.default_content)
        elif c.block is not None:
            vals = [a.text for a in de.block_attribs if getattr(a, "text", "")]
            text, balloon = (vals[0] if vals else ""), True
        made = []
        for leader in c.leaders:
            for line in leader.lines:
                pts = [P(v) for v in line.vertices]
                if leader.last_leader_point is not None:
                    pts.append(P(leader.last_leader_point))
                clean = []
                for q in pts:
                    if not clean or G.dist(q, clean[-1]) > 1e-9:
                        clean.append(q)
                if len(clean) >= 2:
                    made.append(M.Leader(clean, "" if made else text, balloon and not made, h,
                                         **kw))
    except (AttributeError, TypeError, ValueError, IndexError):
        return False
    if not made:
        return False
    out.extend(made)
    return True


def _keepable(de):
    """A block reference kept as a block (not taken apart): a named block (not an anonymous
    one: a dimension's, a table's...), placed with the same scale both ways (mirrored or
    not), lying flat; (scale, angle, mirror) for M.Insert, else None."""
    d = de.dxf
    name = str(d.name)
    from .dwgread import ANON_PREFIX
    if name.startswith("*") or name.startswith(ANON_PREFIX):
        return None
    xs, ys = d.get("xscale", 1.0), d.get("yscale", 1.0)
    ext = d.get("extrusion", (0.0, 0.0, 1.0))
    if abs(abs(xs) - abs(ys)) > 1e-9 * max(1.0, abs(xs)) or abs(xs) < 1e-12 or \
            abs(ext[0]) > 1e-12 or abs(ext[1]) > 1e-12 or ext[2] < 0 or \
            d.get("column_count", 1) > 1 or d.get("row_count", 1) > 1:
        return None
    r = d.get("rotation", 0.0)
    if xs > 0 and ys > 0:
        return abs(xs), r, False
    if xs < 0 and ys < 0:
        return abs(xs), r + 180.0, False
    if ys < 0:
        return abs(xs), r, True                 # (its y flipped: KanzonasCAD's mirror)
    return abs(xs), r + 180.0, True             # (its x flipped: y flipped, turned 180)


def _block_defn(de, k, skipped, depth, blocks):
    """The BlockDef an imported block reference shows, made once per block: its drawing
    (inches, around its base point) and the attribute fields it shows (ATTDEFs). None for a
    block with nothing to draw (AutoCAD Electrical's hidden WD_M...)."""
    key = ("defn", de.dxf.name)
    if key in blocks:
        return blocks[key]
    parts = [e for e, _on0 in _block_parts(de, k, {}, depth, blocks)]
    blk = de.block()
    bx, by = blk.block.dxf.base_point[0] * k, blk.block.dxf.base_point[1] * k
    attrs, seen = [], set()
    tags = set()
    for sub in blk:
        if sub.dxftype() != "ATTDEF":
            continue
        name = _attr_name(sub.dxf.tag)
        tags.add(str(sub.dxf.tag).upper())
        if sub.is_invisible or name in seen or not name:
            continue
        seen.add(name)
        p = sub.dxf.get("align_point") if (sub.dxf.get("halign", 0) or sub.dxf.get("valign", 0)) \
            and sub.dxf.hasattr("align_point") else sub.dxf.insert
        attrs.append({"attr": name, "pos": (p[0] * k - bx, p[1] * k - by),
                      "height": sub.dxf.get("height", 0.125) * k})
    if not parts and not attrs:
        blocks[key] = None
        return None
    # a schematic symbol (AutoCAD Electrical's carry TAG1) or anything else: a footprint
    kind = "symbol" if "TAG1" in tags else "footprint"
    defn = M.BlockDef(str(de.dxf.name), kind, [e.copy(layer="0") for e in parts],
                      attr_texts=attrs, category="Imported")
    blocks[key] = defn
    return defn


def _fast_insert(de):
    """Can a block reference be placed by turning and scaling its block's drawing alone (the
    same scale both ways, not mirrored, lying flat on the page)? Else ezdxf takes it apart."""
    d = de.dxf
    xs, ys = d.get("xscale", 1.0), d.get("yscale", 1.0)
    ext = d.get("extrusion", (0.0, 0.0, 1.0))
    return xs > 0 and abs(xs - ys) <= 1e-9 * max(1.0, abs(xs)) and \
        abs(ext[0]) < 1e-12 and abs(ext[1]) < 1e-12 and ext[2] > 0 and \
        d.get("column_count", 1) <= 1 and d.get("row_count", 1) <= 1


def _read(de, k, out, skipped, depth, blocks=None, keep=False):
    t = de.dxftype()
    layer = de.dxf.get("layer", "0") or "0"
    kw = dict(layer=layer, color=_entity_color(de))

    def P(v):
        return (v[0] * k, v[1] * k)
    try:
        ocs = _ocs(de)
        if t == "LINE":
            out.append(M.Line(P(de.dxf.start), P(de.dxf.end), **kw))
        elif t in ("CIRCLE", "ARC") and ocs is not None:
            # drawn in its own plane (a mirrored block's arcs face down: AutoCAD keeps them
            # so); seen from above: mirrored exactly, or, tilted, its points
            ext = de.dxf.extrusion
            c = P(ocs.to_wcs(de.dxf.center))
            if abs(ext[0]) < 1e-9 and abs(ext[1]) < 1e-9:
                if t == "CIRCLE":
                    out.append(M.Circle(c, de.dxf.radius * k, **kw))
                else:
                    out.append(M.Arc(c, de.dxf.radius * k, 180.0 - de.dxf.end_angle,
                                     180.0 - de.dxf.start_angle, **kw))
            else:
                pts = [P(v) for v in de.flattening(0.002 / max(k, 1e-9))]
                if len(pts) >= 2:
                    out.append(M.Polyline(pts, t == "CIRCLE", **kw))
        elif t in ("LWPOLYLINE", "POLYLINE") and ocs is not None and \
                (t == "LWPOLYLINE" or de.is_2d_polyline):
            from ezdxf import path as ezpath
            pts = [P(v) for v in ezpath.make_path(de).flattening(0.002 / max(k, 1e-9))]
            if len(pts) >= 2:
                out.append(M.Polyline(pts, False, **kw))
        elif t == "CIRCLE":
            out.append(M.Circle(P(de.dxf.center), de.dxf.radius * k, **kw))
        elif t == "ARC":
            out.append(M.Arc(P(de.dxf.center), de.dxf.radius * k, de.dxf.start_angle,
                             de.dxf.end_angle, **kw))
        elif t == "POLYLINE" and (de.is_poly_face_mesh or de.is_polygon_mesh):
            # a mesh: its edges, seen from above
            for sub in de.virtual_entities():
                _read(sub, k, out, skipped, depth + 1, blocks)
        elif t == "POLYLINE" and de.is_3d_polyline:
            # a "3D" polyline (often flat on the sheet: AutoCAD and makers' drawings save them
            # so): its points seen from above (it was left out, and with it most of a drawing)
            pts = [P(v.dxf.location) for v in de.vertices]
            if len(pts) >= 2:
                out.append(M.Polyline(pts, de.is_closed, **kw))
        elif t in ("SOLID", "TRACE", "3DFACE"):
            # a filled triangle or quadrilateral: its outline (corners 0, 1, 3, 2 for a SOLID)
            vs = [de.dxf.get(n) for n in ("vtx0", "vtx1", "vtx2", "vtx3")]
            vs = [v for v in vs if v is not None]
            if ocs is not None and t != "3DFACE":
                vs = [ocs.to_wcs(v) for v in vs]
            if t in ("SOLID", "TRACE") and len(vs) == 4:
                vs = [vs[0], vs[1], vs[3], vs[2]]
            pts = []
            for v in vs:
                q = P(v)
                if not pts or G.dist(q, pts[-1]) > 1e-9:
                    pts.append(q)
            if len(pts) >= 2:
                out.append(M.Polyline(pts, len(pts) > 2, **kw))
        elif t == "HATCH":
            # its boundaries, seen from above (the fill isn't drawn: it would hide what is
            # under it)
            from ezdxf import path as ezpath
            n = len(out)
            for p in ezpath.from_hatch(de):
                pts = [P(v) for v in p.flattening(0.002 / max(k, 1e-9))]
                if len(pts) >= 2:
                    out.append(M.Polyline(pts, False, **kw))
            if len(out) == n:
                skipped[t] = skipped.get(t, 0) + 1
        elif t in ("LWPOLYLINE", "POLYLINE"):
            if t == "POLYLINE" and not de.is_2d_polyline:
                skipped[t] = skipped.get(t, 0) + 1
                return
            has_bulge = any(abs(b) > 1e-12 for b in
                            ([v[4] for v in de.get_points("xyseb")] if t == "LWPOLYLINE"
                             else [v.dxf.get("bulge", 0) for v in de.vertices]))
            if has_bulge:
                for sub in de.virtual_entities():
                    _read(sub, k, out, skipped, depth + 1, blocks)
                    out[-1].layer, out[-1].color = layer, kw["color"]
            else:
                pts = ([P(v) for v in de.get_points("xy")] if t == "LWPOLYLINE"
                       else [P(v.dxf.location) for v in de.vertices])
                if len(pts) >= 2:
                    out.append(M.Polyline(pts, de.is_closed, **kw))
        elif t == "TEXT":
            pos = de.dxf.insert
            align = "left"
            halign = de.dxf.get("halign", 0)
            vnum = de.dxf.get("valign", 0)
            if halign in (1, 4):
                align = "center"
            elif halign == 2:
                align = "right"
            valign = {1: "bottom", 2: "middle", 3: "top"}.get(vnum, "baseline")
            if halign == 4:                         # AutoCAD's "Middle": centered both ways
                valign = "middle"
            if (halign in (1, 2, 4) or vnum) and de.dxf.hasattr("align_point"):
                pos = de.dxf.align_point
            rot = de.dxf.get("rotation", 0.0)
            if ocs is not None:
                # a mirrored block's text: where it is, seen from above, and kept readable
                # (it runs the other way: its other end at the point)
                pos = ocs.to_wcs(pos)
                d = ocs.to_wcs((math.cos(math.radians(rot)), math.sin(math.radians(rot)), 0)) \
                    - ocs.to_wcs((0, 0, 0))
                rot = math.degrees(math.atan2(d[1], d[0]))
                if 90.0 < rot % 360.0 <= 270.0:
                    rot += 180.0
                    align = {"left": "right", "right": "left"}.get(align, align)
            out.append(M.Text(P(pos), de.plain_text(), de.dxf.get("height", 0.125) * k,
                              rot, align, valign, **kw))
        elif t == "MTEXT":
            # (a dimension's number is an MTEXT too: reading its direction as a slice of
            # ezdxf's vector raised, and every MTEXT was skipped, dimension values with them)
            h = de.dxf.get("char_height", 0.125) * k
            d = de.get_text_direction()
            ang = math.degrees(math.atan2(d[1], d[0]))
            lines = de.plain_text().split("\n")
            x, y = P(de.dxf.insert)
            # placed by its attachment point (1-9: top/middle/bottom, left/center/right; a
            # dimension's number is middle center, on its dimension line)
            ap = int(de.dxf.get("attachment_point", 1) or 1)
            row, col = divmod(max(1, min(9, ap)) - 1, 3)
            step = h * 1.6667
            total = h + (len(lines) - 1) * step
            top = (0.0, total / 2, total)[row]          # how far its top is above the point
            align = ("left", "center", "right")[col]
            for i, line in enumerate(lines):
                if line.strip():
                    pos = G.polar((x, y), top - i * step, ang + 90)
                    out.append(M.Text(pos, line, h, ang, align, "top", **kw))
        elif t in ("ELLIPSE", "SPLINE"):
            pts = [P(v) for v in de.flattening(0.002 / max(k, 1e-9))]
            if len(pts) >= 2:
                out.append(M.Polyline(pts, False, **kw))
        elif t == "INSERT" and depth < 12 and de.mcount > 1:
            # a MINSERT (rows and columns of one block): each copy
            for one in de.multi_insert():
                _read(one, k, out, skipped, depth + 1, blocks)
        elif t == "INSERT" and keep and depth == 0 and blocks is not None and \
                _keepable(de) and _block_defn(de, k, skipped, depth, blocks) is not None:
            # kept a block: one object per copy, its attributes as KanzonasCAD's (TAG, DESC,
            # MFR, CAT; AutoCAD Electrical's P_TAG1, DESC1... mapped)
            s, r, mirror = _keepable(de)
            defn = _block_defn(de, k, skipped, depth, blocks)
            vals = {}
            for att in de.attribs:
                name = _attr_name(att.dxf.tag)
                v = att.dxf.get("text", "")
                if name and v and v.strip("-"):
                    vals[name] = (vals[name] + " " + v) if name == "DESC" and \
                        vals.get(name) else v
            out.append(M.Insert(defn.name, (de.dxf.insert[0] * k, de.dxf.insert[1] * k), r,
                                s, mirror, vals, defn, layer=layer, color=kw["color"]))
            # a value its block has no field for (no ATTDEF) still shows where it stands
            shown = {a["attr"] for a in defn.attr_texts}
            for att in de.attribs:
                if _attr_name(att.dxf.tag) not in shown:
                    _read(att, k, out, skipped, depth + 1, blocks)
        elif t == "INSERT" and depth < 12 and blocks is not None and _fast_insert(de):
            # the block's drawing read once, then turned, scaled and moved for each copy
            # (taking each copy apart again was most of the time of opening a drawing made
            # of blocks: a panel of terminals, 100,000 pieces)
            s = de.dxf.get("xscale", 1.0)
            r = de.dxf.get("rotation", 0.0)
            ix, iy = de.dxf.insert[0] * k, de.dxf.insert[1] * k
            c, sn = math.cos(math.radians(r)), math.sin(math.radians(r))

            def place(q):
                x, y = q[0] * s, q[1] * s
                return (ix + x * c - y * sn, iy + x * sn + y * c)
            for e, on_0 in _block_parts(de, k, skipped, depth, blocks):
                w = e._map(place, rot=r, factor=s, mirror=None)
                if on_0:
                    w.layer = layer         # (layer 0 inside a block: the reference's layer)
                out.append(w)
            for att in de.attribs:
                _read(att, k, out, skipped, depth + 1, blocks)
        elif t == "LEADER" and len(de.vertices) >= 2:
            # a leader: KanzonasCAD's own (its text, an MTEXT of its own, comes in by itself)
            out.append(M.Leader([P(v) for v in de.vertices], "", False, 0.1, **kw))
        elif t in ("MLEADER", "MULTILEADER") and _mleaders(de, P, k, kw, out):
            pass
        elif t == "DIMENSION" and depth == 0 and _dimension(de, P, k, kw) is not None:
            out.append(_dimension(de, P, k, kw))
        elif t in ("INSERT", "DIMENSION", "ARC_DIMENSION", "LARGE_RADIAL_DIMENSION", "LEADER",
                   "MLEADER", "MULTILEADER", "MLINE") and depth < 12:
            # (AutoCAD's multileader is MULTILEADER: it was left out)
            for sub in de.virtual_entities():
                n = len(out)
                _read(sub, k, out, skipped, depth + 1, blocks)
                if t == "INSERT":
                    # entities on layer 0 inside a block take the block reference's layer
                    for e in out[n:]:
                        if e.layer == "0":
                            e.layer = layer
            if t == "INSERT":
                for att in de.attribs:
                    _read(att, k, out, skipped, depth + 1, blocks)
        elif t == "ATTRIB":
            if not de.is_invisible:
                out.append(M.Text(P(de.dxf.insert), de.plain_text(),
                                  de.dxf.get("height", 0.125) * k, de.dxf.get("rotation", 0.0),
                                  **kw))
        elif t == "POINT":
            skipped[t] = skipped.get(t, 0) + 1
        elif depth < 12 and _proxy_parts(de, k, out, skipped, depth, layer):
            pass
        else:
            skipped[t] = skipped.get(t, 0) + 1
    except Exception:                   # (reported to the user: "Skipped: X (unreadable)")
        skipped[t + " (unreadable)"] = skipped.get(t + " (unreadable)", 0) + 1


def _ocs(de):
    """A planar entity's own coordinate system when it isn't the page's (its extrusion not
    straight up: a mirrored block's arcs, circles, polylines and text), else None."""
    try:
        if not de.dxf.hasattr("extrusion"):
            return None
        ext = de.dxf.extrusion
    except AttributeError:
        return None
    if abs(ext[0]) < 1e-9 and abs(ext[1]) < 1e-9 and ext[2] > 0:
        return None
    return de.ocs()


def _proxy_parts(de, k, out, skipped, depth, layer):
    """An object of a type KanzonasCAD doesn't know (AutoCAD Electrical's, Mechanical's,
    Civil's... saved with its look, "proxy graphics"): the lines, arcs and texts of that
    look. True when it gave any."""
    if not hasattr(de, "virtual_entities"):
        return False
    try:
        subs = list(de.virtual_entities())
    except Exception:       # (no proxy graphics or unreadable: then reported as left out)
        return False
    n = len(out)
    for sub in subs:
        _read(sub, k, out, skipped, depth + 1)
    for e in out[n:]:
        if e.layer == "0":
            e.layer = layer
    return len(out) > n


# ============================================================================================
# DWG import: built in with ezdwg (MIT, R13-2018); the ODA File Converter, when installed, only
# as a fallback for a file ezdwg can't read
# ============================================================================================
class DwgError(Exception):
    """A DWG that couldn't be read, with what was tried."""


def oda_converter():
    """The ODA File Converter's program, when it is installed, else None."""
    import glob
    import shutil
    if sys.platform.startswith("win"):
        found = []
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if base:
                found += glob.glob(os.path.join(base, "ODA", "ODAFileConverter*",
                                                "ODAFileConverter.exe"))
        return sorted(found)[-1] if found else None
    return shutil.which("ODAFileConverter")


def _dwg_with_ezdwg(path, folder):
    """(the DXF ezdwg made of it, the drawing's $INSUNITS, what it left out)."""
    import ezdwg
    src = ezdwg.read(path)
    units = int(src.header_variables().get("insunits") or 0)
    out = os.path.join(folder, "drawing.dxf")
    res = ezdwg.to_dxf(src, out)
    return out, units, dict(res.skipped_by_type or {})


def _dwg_with_oda(path, folder, program):
    """The DXF the ODA File Converter made of it (it converts folders: a folder of its own)."""
    import shutil
    import subprocess
    src = os.path.join(folder, "in")
    dst = os.path.join(folder, "out")
    os.makedirs(src)
    os.makedirs(dst)
    shutil.copy(path, os.path.join(src, "drawing.dwg"))
    subprocess.run([program, src, dst, "ACAD2018", "DXF", "0", "1", "drawing.dwg"],
                   check=True, timeout=300, capture_output=True)
    out = os.path.join(dst, "drawing.dxf")
    if not os.path.isfile(out):
        raise DwgError("the ODA File Converter made no DXF")
    return out


def read_dwg(path):
    """Entities of a DWG's model space, in inches, plus the report read_dxf gives (and
    "reader": which one read it)."""
    import shutil
    import subprocess
    import tempfile
    folder = tempfile.mkdtemp(prefix="kzcad-dwg")
    try:
        try:
            # object by object, blocks kept (dwgread): ezdwg's own conversion to DXF
            # explodes blocks and loses their scale, attributes and parts
            from . import dwgread
            doc, units, left = dwgread.read(path)
            ents, rep = read_doc(doc, units=units)
            for k, n in left.items():
                rep["skipped"][k] = rep["skipped"].get(k, 0) + n
            rep["reader"] = "KanzonasCAD"
            return ents, rep
        except ImportError:
            first = "KanzonasCAD's DWG reader (ezdwg) isn't installed"
        except Exception as ex:         # (told on the command line; the older way next)
            first = "KanzonasCAD's DWG reader couldn't read it (%s)" % ex
        try:
            dxf, units, left = _dwg_with_ezdwg(path, folder)
            ents, rep = read_dxf(dxf, units=units)
            for k, n in left.items():
                rep["skipped"][k] = rep["skipped"].get(k, 0) + n
            rep["reader"] = "ezdwg (converted to DXF: %s)" % first
            return ents, rep
        except ImportError:
            pass
        except Exception as ex:         # (any failure of the reader: told, then the fallback)
            first = "%s; converted to DXF, it failed too (%s)" % (first, ex)
        program = oda_converter()
        if program is None:
            raise DwgError("%s. If the ODA File Converter is installed, KanzonasCAD tries it "
                           "too; or save the drawing as DXF in the program that made it."
                           % first)
        try:
            ents, rep = read_dxf(_dwg_with_oda(path, folder, program))
        except (OSError, subprocess.SubprocessError, DwgError) as ex:
            raise DwgError("%s, and the ODA File Converter failed too (%s)." % (first, ex))
        rep["reader"] = "ODA File Converter"
        return ents, rep
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def read_drawing(path):
    """A DXF or DWG's model space (by its extension)."""
    if path.lower().endswith(".dwg"):
        return read_dwg(path)
    return read_dxf(path)


def import_dxf(project, sheet, path, at=None, anchor="center"):
    """Add a DXF's or DWG's model space to a sheet (one undoable step). Returns the report of
    read_dxf plus "count", "ids" (the objects added) and "bbox" (where they are). at: a point
    to put the middle of the drawing on (a file dropped on the drawing), or with anchor
    "left" the middle of its left side (the next of several dropped, beside the one before);
    None keeps the drawing's own coordinates."""
    ents, rep = read_drawing(path)
    return add_drawing(project, sheet, ents, rep, path, at, anchor)


def _own_blocks(ed, project, ents):
    """The imported blocks put in the project (its own copies, as a placed library block's);
    one of the same name already there and different keeps its place: the imported one is
    renamed ("name (2)"), and its references with it."""
    renamed, done = {}, {}
    out = []
    for e in ents:
        if not isinstance(e, M.Insert) or e.defn is None:
            out.append(e)
            continue
        key = id(e.defn)
        if key not in done:
            defn, name = e.defn, e.defn.name
            have = project.blocks.get(name)
            if have is not None and not have.same_as(defn):
                n = 2
                while "%s (%d)" % (name, n) in project.blocks:
                    if project.blocks["%s (%d)" % (name, n)].same_as(defn):
                        break
                    n += 1
                name = "%s (%d)" % (name, n)
                defn = M.BlockDef.from_dict(dict(defn.to_dict(), name=name))
            if name not in project.blocks:
                ed.block(defn)
            done[key] = project.blocks[name]
            renamed[key] = name
        defn = done[key]
        out.append(M.Insert(defn.name, e.pos, e.angle, e.scale, e.mirror, e.attrs, defn,
                            e.tag_h, layer=e.layer, color=e.color))
    return out


def add_drawing(project, sheet, ents, rep, path, at=None, anchor="center"):
    """The part of import_dxf after reading: the entities added to the sheet, one undoable
    step (their layers made when missing)."""
    bb = None
    for e in ents:
        bb = G.bbox_union(bb, e.bbox())
    if at is not None and bb is not None:
        dx = at[0] - (bb[0] if anchor == "left" else (bb[0] + bb[2]) / 2)
        dy = at[1] - (bb[1] + bb[3]) / 2
        ents = [e.moved(dx, dy) for e in ents]
        bb = (bb[0] + dx, bb[1] + dy, bb[2] + dx, bb[3] + dy)
    ids = []
    with project.edit("Import DWG" if path.lower().endswith(".dwg") else "Import DXF") as ed:
        for name, color in rep["layers"].items():
            if name not in project.layers:
                ed.layer(name, None, M.Layer(name, color).to_dict())
        ents = _own_blocks(ed, project, ents)
        for e in ents:
            if e.layer not in project.layers:
                ed.layer(e.layer, None, M.Layer(e.layer).to_dict())
            ids.append(ed.add(sheet, e).id)
    rep["count"] = len(ents)
    rep["ids"] = ids
    rep["bbox"] = bb
    return rep


# ============================================================================================
# PDF
# ============================================================================================
def export_pdf(project, path, sheets=None, line_width=0.008, mono=True):
    """One page per sheet at its real size: black on white paper (mono False keeps the
    layers' colors). Returns the page count."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPainter, QPageSize, QPageLayout, QPdfWriter
    from .render import SheetRenderer
    sheets = list(sheets or project.sheets)
    writer = QPdfWriter(path)
    writer.setCreator("KanzonasCAD")
    writer.setTitle(project.fields.get("Project", "") or os.path.basename(path))
    writer.setResolution(600)
    painter = None
    try:
        for i, s in enumerate(sheets):
            w, h = s.paper_inches()
            size = QPageSize(QSizeF(w, h), QPageSize.Inch, "", QPageSize.ExactMatch)
            layout = QPageLayout(size, QPageLayout.Portrait if h > w else QPageLayout.Landscape,
                                 QMarginsF(0, 0, 0, 0))
            layout.setOrientation(QPageLayout.Portrait)
            writer.setPageLayout(layout)
            if painter is None:
                painter = QPainter(writer)
            else:
                writer.newPage()
            painter.setRenderHint(QPainter.Antialiasing, True)
            dpi = writer.resolution()
            painter.resetTransform()
            painter.translate(0, h * dpi)
            # a scaled panel sheet: its real-size drawing shrunk onto the paper (line widths
            # stay paper widths)
            painter.scale(dpi * s.scale, -dpi * s.scale)
            with printing():            # ({Print date}: now)
                SheetRenderer(project, s, dark=False, mono=mono).paint(
                    painter, pen_width=line_width * s.k())
    finally:
        if painter is not None:
            painter.end()
    return len(sheets)
