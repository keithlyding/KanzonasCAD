"""DXF import and export (through ezdxf, imported only when used), DWG import (ezdwg, imported
only when used) and PDF export (Qt's own PDF writer: vector lines and outlined text, one page
per sheet at its real size)."""

import math
import os
import sys

from . import model as M
from . import geometry as G
from .sheetframe import frame_entities, FRAME_LAYER

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
    for e in sheet.entities.values():
        # block references go out as their lines and texts, on the reference's layer
        ents.extend(e.exploded() if isinstance(e, (M.Insert, M.Dimension)) else [e])
    if include_frame:
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
def read_dxf(path, include_paperspace=False, units=None):
    """Entities of a DXF's model space, in inches, plus a report:
    (entities, {"layers": {name: hex color}, "skipped": {dxftype: count}, "units": name}).
    units: the drawing's $INSUNITS when the file's own can't be trusted (a converted DWG)."""
    import ezdxf
    from ezdxf import recover
    try:
        doc = ezdxf.readfile(path)
    except ezdxf.DXFStructureError:
        doc, _auditor = recover.readfile(path)
    if units is None:
        units = int(doc.header.get("$INSUNITS", 0) or 0)
    k = _UNITS.get(units, 1.0)
    layers = {}
    for dl in doc.layers:
        layers[dl.dxf.name] = _dxf_layer_color(dl)
    out, skipped = [], {}
    for de in doc.modelspace():
        _read(de, k, out, skipped, 0)
    unit_name = {0: "unitless (taken as inches)", 1: "inches", 2: "feet", 4: "millimeters",
                 5: "centimeters", 6: "meters"}.get(units, "units %d (taken as inches)" % units)
    return out, {"layers": layers, "skipped": skipped, "units": unit_name}


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


def _read(de, k, out, skipped, depth):
    t = de.dxftype()
    layer = de.dxf.get("layer", "0") or "0"
    kw = dict(layer=layer, color=_entity_color(de))

    def P(v):
        return (v[0] * k, v[1] * k)
    try:
        if t == "LINE":
            out.append(M.Line(P(de.dxf.start), P(de.dxf.end), **kw))
        elif t == "CIRCLE":
            out.append(M.Circle(P(de.dxf.center), de.dxf.radius * k, **kw))
        elif t == "ARC":
            out.append(M.Arc(P(de.dxf.center), de.dxf.radius * k, de.dxf.start_angle,
                             de.dxf.end_angle, **kw))
        elif t in ("LWPOLYLINE", "POLYLINE"):
            if t == "POLYLINE" and not de.is_2d_polyline:
                skipped[t] = skipped.get(t, 0) + 1
                return
            has_bulge = any(abs(b) > 1e-12 for b in
                            ([v[4] for v in de.get_points("xyseb")] if t == "LWPOLYLINE"
                             else [v.dxf.get("bulge", 0) for v in de.vertices]))
            if has_bulge:
                for sub in de.virtual_entities():
                    _read(sub, k, out, skipped, depth + 1)
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
            out.append(M.Text(P(pos), de.plain_text(), de.dxf.get("height", 0.125) * k,
                              de.dxf.get("rotation", 0.0), align, valign, **kw))
        elif t == "MTEXT":
            h = de.dxf.get("char_height", 0.125) * k
            ang = math.degrees(math.atan2(*reversed(de.get_text_direction()[:2])))
            lines = de.plain_text().split("\n")
            x, y = P(de.dxf.insert)
            for i, line in enumerate(lines):
                if line.strip():
                    pos = G.polar((x, y), h * (1 + i * 1.6667), ang - 90)
                    out.append(M.Text(pos, line, h, ang, **kw))
        elif t in ("ELLIPSE", "SPLINE"):
            pts = [P(v) for v in de.flattening(0.002 / max(k, 1e-9))]
            if len(pts) >= 2:
                out.append(M.Polyline(pts, False, **kw))
        elif t in ("INSERT", "DIMENSION", "LEADER", "MLEADER") and depth < 12:
            for sub in de.virtual_entities():
                n = len(out)
                _read(sub, k, out, skipped, depth + 1)
                if t == "INSERT":
                    # entities on layer 0 inside a block take the block reference's layer
                    for e in out[n:]:
                        if e.layer == "0":
                            e.layer = layer
            if t == "INSERT":
                for att in de.attribs:
                    _read(att, k, out, skipped, depth + 1)
        elif t == "ATTRIB":
            if not de.is_invisible:
                out.append(M.Text(P(de.dxf.insert), de.plain_text(),
                                  de.dxf.get("height", 0.125) * k, de.dxf.get("rotation", 0.0),
                                  **kw))
        elif t == "POINT":
            skipped[t] = skipped.get(t, 0) + 1
        else:
            skipped[t] = skipped.get(t, 0) + 1
    except Exception:                   # (reported to the user: "Skipped: X (unreadable)")
        skipped[t + " (unreadable)"] = skipped.get(t + " (unreadable)", 0) + 1


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
            dxf, units, left = _dwg_with_ezdwg(path, folder)
            ents, rep = read_dxf(dxf, units=units)
            for k, n in left.items():
                rep["skipped"][k] = rep["skipped"].get(k, 0) + n
            rep["reader"] = "ezdwg"
            return ents, rep
        except ImportError:
            first = "KanzonasCAD's DWG reader (ezdwg) isn't installed"
        except Exception as ex:         # (any failure of the reader: told, then the fallback)
            first = "KanzonasCAD's DWG reader couldn't read it (%s)" % ex
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


def import_dxf(project, sheet, path):
    """Add a DXF's or DWG's model space to a sheet (one undoable step). Returns the report of
    read_dxf plus "count"."""
    ents, rep = read_drawing(path)
    with project.edit("Import DWG" if path.lower().endswith(".dwg") else "Import DXF") as ed:
        for name, color in rep["layers"].items():
            if name not in project.layers:
                ed.layer(name, None, M.Layer(name, color).to_dict())
        for e in ents:
            if e.layer not in project.layers:
                ed.layer(e.layer, None, M.Layer(e.layer).to_dict())
            ed.add(sheet, e)
    rep["count"] = len(ents)
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
            SheetRenderer(project, s, dark=False, mono=mono).paint(
                painter, pen_width=line_width * s.k())
    finally:
        if painter is not None:
            painter.end()
    return len(sheets)
