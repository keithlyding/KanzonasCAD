"""What AutoCAD Electrical itself keeps in a drawing, for DXF export with its names
(fileio.export_dxf, ace_names): its drawing settings block WD_M (which layers hold wires), each
wire as LINEs pointing at their wire number's block WD_WNH, its crossings as two LINEs with a
gap (and a loop ARC) that point at each other, and a WDDOT block at each junction. Written as an
AutoCAD Electrical 2027 drawing the owner saved holds them (Nov 2026), so Scoot, its wire
numbers and its gaps take KanzonasCAD's wires for its own. Needs ezdxf (imported by the caller).
"""

import math

from . import model as M
from .fileio import _true_color

# WD_M's attributes, in its block's order, with AutoCAD Electrical's defaults (the owner's
# drawing: its WD_M block)
WD_M = (
    ('XREF_STYLE', '0'), ('XREF_FLAGS', '0'), ('XREF_UNUSEDSTYLE', '0'), ('XREF_FILLWITH', ''),
    ('XREF_SORT', '0'), ('XREF_TXTBTWN', ','), ('XREF_GRAPHIC', '0'), ('XREF_GRAPHICSTYLE', '0'),
    ('XREF_CONTACTMAP', 'NO,NC,NONC'), ('XREF_TBLSTYLE', 'Standard'), ('XREF_TBLTITLE', '%T'),
    ('XREF_TBLINDEX', '1,2,3,5'),
    ('XREF_TBLFLDNAMS', 'W1,T1,TYPE,T2,W2,REF,SH,SHDWGNAM,FILENAME,FULLFILENAME'),
    ('XREF_TBLCOLJUST', 'L,L,L,L,L,L,L,L,L,L'), ('WNUM_OFFSET', '0.0'), ('WNUM_FLAGS', '1'),
    ('WNUM_GAP', ''), ('SORTMODE', ''), ('LOCBOX_LAY', 'LOCBOX'),
    ('FAN_INOUT_LAYS', '_MULTI_WIRE'), ('FAN_INOUT_STYLE', '1'), ('MISC_DATA', ''),
    ('WIREREF_LAY', 'WIREREF'), ('IEC_PROJ', ''), ('IEC_INST', ''), ('IEC_LOC', ''),
    ('TAGFIXED_LAY', 'TAGFIXED'), ('GAP_STYLE', '1'), ('MISC_FLAGS', '0'), ('ALT_XREFFMT', '%N'),
    ('SHEETDWGNAME', ''), ('COMP_LAY', 'SYMS'), ('LINK_LAY', 'LINK'), ('ARROW_STYLE', '1'),
    ('PLC_STYLE', '1'), ('MISC_LAY', 'MISC'), ('CDESC_LAY', 'DESCCHILD'),
    ('CXREF_LAY', 'XREFCHILD'), ('WLEADERS', '0'), ('POS_LAY', 'POS'), ('LOC_LAY', 'LOC'),
    ('TAG_LAY', 'TAGS'), ('XREF_LAY', 'XREF'), ('DESC_LAY', 'DESC'), ('TERM_LAY', 'TERMS'),
    ('WIREFIXED_LAY', 'WIREFIXED'), ('FEATURE_SCL', '1.0'), ('UNIT_SCL', '1.0'),
    ('WIRECOPY_LAY', 'WIRECOPY'), ('WIRENO_LAY', 'WIRENO'), ('WIRELAYS', 'WIRES'),
    ('DRWRUNG', '0'), ('RUNGINC', '1'), ('XY_DELIM', '-'), ('SHEET', ''), ('HORIZ_FIRST', '1'),
    ('CHAR_V', '1'), ('CHAR_H', 'A'), ('DISTV', '2.0'), ('DISTH', '2.0'), ('DATUMY', ''),
    ('DATUMX', ''), ('PH3SPACE', '0.5'), ('XREFFMT', '%N'), ('TAG-RSUF', ',A,B,C,D,E,F,G,H,J'),
    ('TAG-START', '1'), ('WIRE-RSUF', ',A,B,C,D,E,F,G,H,J,K,L,M,N'), ('WIRE-START', '1'),
    ('TAGFMT', '%F%N'), ('TAGMODE', 'R'), ('WIREFMT', '%N'), ('WIREMODE', 'R'), ('WINC', '1'),
    ('DLADW', '4.5'), ('RUNGDIST', '0.75'), ('REFNUMS', '1'), ('RUNGHORV', 'H'),
)
DOT_RADII = (0.0300000000000003, 0.0187012496499282, 0.0092948236686489)   # (WDDOT's circles)
GAP = 0.05                  # half a crossing's gap, and its loop's radius (paper inches)
WIRENO_LAY, DOT_LAY, MISC_LAY, COPY_LAY = "WIRENO", "SYMS", "MISC", "WIRECOPY"
APPIDS = ("VIA_WD_WNPTR", "VIA_WD_HDL", "VIA_WD_GAP10", "VIA_WD_GAP11")
STYLE = "WD"


def wire_layers(project):
    """The layers the project's wires are on, and WIRES: AutoCAD Electrical's WIRELAYS."""
    out = ["WIRES"]
    for sh in project.sheets:
        for w in sh.wires():
            lay = w.layer or "0"
            if lay.upper() not in {n.upper() for n in out}:
                out.append(lay)
    return out


def prepare(doc, project):
    """The layers, text style and application names AutoCAD Electrical's data uses, made in a
    new drawing; returns the wire layers (upper case) nothing else may be on."""
    for name in (WIRENO_LAY, DOT_LAY, MISC_LAY, COPY_LAY):
        if not doc.layers.has_entry(name):
            doc.layers.add(name)
    if not doc.styles.has_entry(STYLE):
        doc.styles.new(STYLE, dxfattribs={"font": "romans.shx"})
    for a in APPIDS:
        if not doc.appids.has_entry(a):
            doc.appids.new(a)
    return {n.upper() for n in wire_layers(project)}


def _ptr(h):
    return [(1002, "{"), (1005, h), (1002, "}")]


def write_wires(msp, sheet, wires, jumps, jump_ids, k):
    """Each wire as one LINE a straight run, cut where it jumps another (a gap of 2 * GAP at
    the crossing, its pieces pointing at each other as AutoCAD Electrical's do), and a loop
    ARC over each loop crossing, on the jumping wire's layer (jump_ids: crossings.jump_wires,
    the jumps' wires). Returns ({wire id: [LINE]},
    [(piece before a gap, piece after it)])."""
    from .crossings import cut_wire
    r = GAP * k
    lines, gaps = {}, []
    for w in wires:
        pieces = cut_wire(w, jumps, r) if jumps else [list(w.points)]
        mine, prev = [], None
        for pts in pieces:
            first = None
            for a, b in zip(pts, pts[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-9:
                    continue
                ent = msp.add_line(a, b, dxfattribs={"layer": w.layer or "0"})
                if w.color not in (None, M.ADAPTIVE):
                    ent.rgb = _true_color(w.color)
                mine.append(ent)
                if first is None:
                    first = ent
                    if prev is not None:
                        gaps.append((prev, ent))
                prev = ent
        lines[w.id] = mine
    for (p, u, _cu, st), (jid, _cid) in zip(jumps, jump_ids):
        if st != "loop":
            continue
        w = sheet.entities.get(jid) if jid is not None else None
        # (from the wire's direction round to its other way: the left half for an up and down
        # wire, as AutoCAD Electrical's, the top half for an across one)
        a0 = math.degrees(math.atan2(u[1], u[0]))
        msp.add_arc(p, r, a0, a0 + 180.0,
                    dxfattribs={"layer": (w.layer if w is not None else None) or "WIRES"})
    return lines, gaps


def link_gaps(gaps):
    """The xdata of a crossing's two pieces: each its own handle (VIA_WD_HDL), the one before
    the gap the next one's (VIA_WD_GAP11), the one after it the one before's (VIA_WD_GAP10)."""
    tags = {}
    for a, b in gaps:
        for e in (a, b):
            tags.setdefault(e, {})["VIA_WD_HDL"] = e.dxf.handle
        tags[b]["VIA_WD_GAP10"] = a.dxf.handle
        tags[a]["VIA_WD_GAP11"] = b.dxf.handle
    for e, got in tags.items():
        for app in ("VIA_WD_HDL", "VIA_WD_GAP10", "VIA_WD_GAP11"):
            if app in got:
                e.set_xdata(app, _ptr(got[app]))


def _define_wnh(doc):
    """WD_WNH, AutoCAD Electrical's wire number block (as its own): ten hidden user fields
    W01USER...W10USER and the number, WIRENO."""
    blk = doc.blocks.new(name="WD_WNH")
    for i in range(1, 11):
        y = 0.0078125 * (11 - i)
        a = blk.add_attdef("W%02dUSER" % i, insert=(0.0, y),
                           dxfattribs={"height": 0.005, "style": STYLE, "layer": "0"})
        a.dxf.halign = 1
        a.dxf.align_point = (0.0, y)
        a.is_invisible = True
    a = blk.add_attdef("WIRENO", insert=(0.0, 0.0625),
                       dxfattribs={"height": 0.125, "width": 0.8, "style": STYLE, "layer": "0",
                                   "linetype": "Continuous"})
    a.dxf.halign = 1
    a.dxf.align_point = (0.0, 0.0625)


def write_numbers(doc, msp, spots, lines, k):
    """Each wire number as a WD_WNH on layer WIRENO, its point on the wire and its WIRENO where
    the program shows the number; every LINE of its wires points at it (VIA_WD_WNPTR). A
    number shown again on the same wires (near both ends of a long run, or placed by hand)
    goes on layer WIRECOPY as a text, as AutoCAD Electrical keeps copies of a number."""
    from ezdxf.enums import TextEntityAlignment
    done = set()
    copies = []
    for t, q, ids in spots:
        if ids in done:
            copies.append(t.copy(layer=COPY_LAY))
            continue
        done.add(ids)
        if "WD_WNH" not in doc.blocks:
            _define_wnh(doc)
        ref = msp.add_blockref("WD_WNH", q, dxfattribs={"layer": WIRENO_LAY,
                                                         "xscale": k, "yscale": k})
        for i in range(1, 11):
            at = (q[0], q[1] + 0.0078125 * (11 - i) * k)
            a = ref.add_attrib("W%02dUSER" % i, "", insert=at,
                               dxfattribs={"height": 0.005 * k, "style": STYLE,
                                           "layer": MISC_LAY})
            a.set_placement(at, align=TextEntityAlignment.CENTER)
            a.is_invisible = True
        a = ref.add_attrib("WIRENO", t.text, insert=t.pos,
                           dxfattribs={"height": t.height, "rotation": t.angle, "width": 0.8,
                                       "style": STYLE, "layer": WIRENO_LAY})
        h = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}[t.align]
        v = {"baseline": "", "bottom": "BOTTOM_", "middle": "MIDDLE_", "top": "TOP_"}[t.valign]
        a.set_placement(t.pos, align=TextEntityAlignment[v + h])
        for wid in ids:
            for ln in lines.get(wid, ()):
                ln.set_xdata("VIA_WD_WNPTR", _ptr(ref.dxf.handle))
    return copies


def write_dots(doc, msp, points, k):
    """A WDDOT (AutoCAD Electrical's junction dot: three circles) on layer SYMS at each dot."""
    if not points:
        return
    if "WDDOT" not in doc.blocks:
        blk = doc.blocks.new(name="WDDOT")
        for rad in DOT_RADII:
            blk.add_circle((0.0, 0.0), rad, dxfattribs={"layer": "0"})
    for p in points:
        msp.add_blockref("WDDOT", p, dxfattribs={"layer": DOT_LAY, "xscale": k, "yscale": k})


def write_settings(doc, msp, layers, k):
    """WD_M, AutoCAD Electrical's drawing settings, at 0,0 on layer 0 (once: a drawing with
    one already keeps its own): its defaults, with WIRELAYS the wire layers, crossings as
    loops (GAP_STYLE 1), wire numbers on WIRENO and the sheet's scale as FEATURE_SCL. Without
    it AutoCAD Electrical puts in its own, whose WIRELAYS doesn't list the wire layers, and
    Scoot says "Line entity not on a Wire layer"."""
    if "WD_M" in doc.blocks:
        return
    vals = dict(WD_M, WIRELAYS=",".join(layers), GAP_STYLE="1", WIRENO_LAY=WIRENO_LAY,
                FEATURE_SCL=repr(float(k)))
    blk = doc.blocks.new(name="WD_M")
    for i, (tag, val) in enumerate(WD_M):
        a = blk.add_attdef(tag, insert=(0.0, -0.02 * i),
                           dxfattribs={"height": 0.01, "style": STYLE, "layer": "0"})
        a.dxf.text = val
        a.is_invisible = True
    ref = msp.add_blockref("WD_M", (0.0, 0.0), dxfattribs={"layer": "0"})
    for i, (tag, _val) in enumerate(WD_M):
        a = ref.add_attrib(tag, vals[tag], insert=(0.0, -0.02 * i),
                           dxfattribs={"height": 0.01, "style": STYLE, "layer": "0"})
        a.is_invisible = True
