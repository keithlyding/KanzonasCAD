"""DWG files written by KanzonasCAD itself, as AutoCAD 2000 (AC1015) drawings (the owner, Nov
2026: "You write it. Don't rely on some third party tool"), from the Open Design Alliance's Open
Design Specification for .dwg files (its sections 3, 9, 10, 20, 21, 22, 23 and 26). Written from
that description; no code or text of it is copied here.

The file, in order: the file header with its section locators; the header variables; the
classes; the padding; the objects (the tables and dictionaries every drawing has, then the
drawing's own entities); the object map; the object free space and template sections; the
second file header; an empty preview. Every object is written with absolute handle references.

What it writes (milestone 2): layers (color, on/off, frozen, locked; linetype Continuous) and,
in model space, lines, lightweight polylines (open or closed, with bulges), circles, arcs and
single-line texts (style Standard; left, centered or right), each on a layer, its color ByLayer
or a color index. The drawing comes as a plain description (see dwg_bytes), not as
KanzonasCAD's model objects. No Qt."""

import datetime
import math
import struct
import uuid

from .dwgbits import BitWriter, MC, MS, crc8

VERSION = b"AC1015"
CODEPAGE = 30                         # (ANSI_1252, the code page our texts are written in)

# the 16-byte sentinels that open and close the sections
S_HEADER = bytes.fromhex("CF7B1F23FDDE38A95F7C68B84E6D335F")
E_HEADER = bytes.fromhex("3084E0DC0221C756A0839747B192CCA0")
S_CLASSES = bytes.fromhex("8DA1C4B8C4A9F8C5C0DCF45FE7CFB68A")
E_CLASSES = bytes.fromhex("725E3B473B56073A3F230BA018304975")
S_FILE_HEADER_END = bytes.fromhex("95A04E2899821AE55E41E05F9D3A4D00")
S_SECOND = bytes.fromhex("D47B21CE28939FBF53244009123CAA01")
E_SECOND = bytes.fromhex("2B84DE31D76C6040ACDBBFF6EDC355FE")
S_IMAGE = bytes.fromhex("1F256D07D43628289D57CA3F9D44102B")
E_IMAGE = bytes.fromhex("E0DA92F82BC9D7D762A835C062BBEFD4")

# what the file header's checksum is XORed with, by how many section locators it has
LOCATOR_XOR = {3: 0xA598, 4: 0x8101, 5: 0x3CC4, 6: 0x8461}

# object types (fixed numbers; the classes' objects are numbered from 500, in CLASSES order)
T_TEXT, T_BLOCK, T_ENDBLK, T_ARC, T_CIRCLE, T_LINE = 1, 4, 5, 17, 18, 19
T_DICTIONARY, T_LWPLINE = 42, 77
T_BLOCK_CONTROL, T_BLOCK_HEADER, T_LAYER_CONTROL, T_LAYER = 48, 49, 50, 51
T_STYLE_CONTROL, T_STYLE, T_LTYPE_CONTROL, T_LTYPE = 52, 53, 56, 57
T_VIEW_CONTROL, T_UCS_CONTROL, T_VPORT_CONTROL, T_VPORT = 60, 62, 64, 65
T_APPID_CONTROL, T_APPID, T_DIMSTYLE_CONTROL, T_DIMSTYLE = 66, 67, 68, 69
T_VX_CONTROL, T_MLINESTYLE = 70, 73
# (dxf name, C++ class name): their type is 500 + their place here
CLASSES = [("ACDBDICTIONARYWDFLT", "AcDbDictionaryWithDefault"),
           ("ACDBPLACEHOLDER", "AcDbPlaceHolder"),
           ("LAYOUT", "AcDbLayout")]
T_DICTIONARYWDFLT, T_PLACEHOLDER, T_LAYOUT = 500, 501, 502

# handle reference codes
SOFT_OWNER, HARD_OWNER, SOFT_PTR, HARD_PTR = 2, 3, 4, 5

# the handles of the objects every drawing has (as AutoCAD numbers them, mostly)
H = dict(BLOCK_CONTROL=0x1, LAYER_CONTROL=0x2, STYLE_CONTROL=0x3, LTYPE_CONTROL=0x5,
         VIEW_CONTROL=0x6, UCS_CONTROL=0x7, VPORT_CONTROL=0x8, APPID_CONTROL=0x9,
         DIMSTYLE_CONTROL=0xA, VX_CONTROL=0xB, NOD=0xC, GROUPS=0xD, MLINESTYLES=0xE,
         NORMAL=0xF, LAYER0=0x10, STANDARD=0x11, ACAD=0x12, BYBLOCK=0x13, BYLAYER=0x14,
         CONTINUOUS=0x15, MLSTANDARD=0x16, PLOTSTYLES=0x17, LAYOUTS=0x18, PLOTSETTINGS=0x19,
         MSPACE=0x1A, PSPACE=0x1B, MS_BLOCK=0x1C, MS_ENDBLK=0x1D, PS_BLOCK=0x1E,
         PS_ENDBLK=0x1F, MODEL=0x20, LAYOUT1=0x21, DIMSTANDARD=0x22, ACTIVE=0x23)
FIRST_FREE = 0x24                      # (the first handle for the drawing's layers, then entities)

LW_BYLAYER, LW_DEFAULT = 29, 31        # (lineweight indexes: ByLayer, Default)
BIG = 1e20


# ---- objects -------------------------------------------------------------------------------

def _finish(w, rl_pos, handles_at):
    """An object's bytes: its size, what was written, its checksum."""
    w.put_RL(rl_pos, handles_at)
    body = MS(len(w.bytes())) + w.bytes()
    return body + struct.pack("<H", crc8(0xC0C1, body))


def obj(type_code, handle, owner, data, refs=(), reactors=()):
    """A non-entity object: data(w) writes its own data, refs are its own handle references
    [(code, handle)] after the owner, reactors and (no) extension dictionary."""
    w = BitWriter()
    w.BS(type_code)
    rl = w.bit_size()
    w.RL(0)
    w.H(0, handle)
    w.BS(0)                             # (no extended data)
    w.BL(len(reactors))
    data(w)
    at = w.bit_size()
    w.H(SOFT_PTR, owner)
    for r in reactors:
        w.H(SOFT_PTR, r)
    w.H(HARD_OWNER, 0)
    for code, h in refs:
        w.H(code, h)
    return _finish(w, rl, at)


def entity(type_code, handle, data, layer, owner=0, refs=(), lineweight=LW_BYLAYER,
           prev=0, nxt=0, color=256):
    """An entity: in model space when owner is 0 (no owner reference), else owned by it
    (a block's BLOCK and ENDBLK). Its color a color index (256 ByLayer); linetype and plot
    style ByLayer."""
    w = BitWriter()
    w.BS(type_code)
    rl = w.bit_size()
    w.RL(0)
    w.H(0, handle)
    w.BS(0)                             # (no extended data)
    w.B(0)                              # (no graphic)
    w.BB(0 if owner else 2)             # (entity mode: owner given, or model space)
    w.BL(0)                             # (no reactors)
    w.B(0)                              # (previous and next entity given below)
    w.CMC(color)
    w.BD(1.0)                           # (linetype scale)
    w.BB(0)                             # (linetype ByLayer)
    w.BB(0)                             # (plot style ByLayer)
    w.BS(0)                             # (visible)
    w.RC(lineweight)
    data(w)
    at = w.bit_size()
    if owner:
        w.H(SOFT_PTR, owner)
    w.H(HARD_OWNER, 0)
    w.H(SOFT_PTR, prev)
    w.H(SOFT_PTR, nxt)
    w.H(HARD_PTR, layer)
    for code, h in refs:
        w.H(code, h)
    return _finish(w, rl, at)


def _bds(w, p):
    """A point (or vector) as bitdoubles."""
    for c in p:
        w.BD(c)


def _2rd(w, p):
    w.RD(p[0])
    w.RD(p[1])


def _entry(w, name):
    """A table entry's name and xref fields (not from an xref)."""
    w.T(name)
    w.B(0)                              # (the 64 bit of its flags)
    w.BS(0)                             # (xref index + 1)
    w.B(0)                              # (not xref dependent)


def table_control(type_code, handle, entries, extra=(), more=None):
    """A table's control object: entries are its soft-owned records, extra hard-owned ones
    (ByLayer, ByBlock, model and paper space)."""
    def data(w):
        w.BL(len(entries))
        if more is not None:
            w.RC(more)
    refs = [(SOFT_OWNER, h) for h in entries] + [(HARD_OWNER, h) for h in extra]
    return obj(type_code, handle, 0, data, refs)


def dictionary(handle, owner, items, reactors=(), default=None):
    """A dictionary {name: handle} (with default: a dictionary with a default entry)."""
    names = sorted(items)

    def data(w):
        w.BL(len(names))
        w.BS(1)                         # (cloning: keep existing)
        w.RC(0)                         # (entries soft owned)
        for n in names:
            w.T(n)
    refs = [(SOFT_OWNER, items[n]) for n in names]
    if default is None:
        return obj(T_DICTIONARY, handle, owner, data, refs, reactors)
    return obj(T_DICTIONARYWDFLT, handle, owner, data, refs + [(HARD_PTR, default)],
               reactors)


def layer(handle, name, color=7, on=True, frozen=False, locked=False):
    """A layer. Off is kept twice, as AutoCAD reads it: the flags' 2 bit and a negative color
    (the flags: 1 frozen, 2 off, 8 locked, 16 plotted, then the lineweight)."""
    def data(w):
        _entry(w, name)
        w.BS((1 if frozen else 0) | (0 if on else 2) | (8 if locked else 0) | 16 |
             (LW_DEFAULT << 5))
        w.CMC(color if on else -color)
    return obj(T_LAYER, handle, H["LAYER_CONTROL"], data,
               [(HARD_PTR, 0), (HARD_PTR, H["NORMAL"]), (HARD_PTR, H["CONTINUOUS"]),
                (HARD_PTR, 0)])


def style(handle, name):
    def data(w):
        _entry(w, name)
        w.B(0)                          # (not vertical)
        w.B(0)                          # (a font, not shapes)
        w.BD(0.0)                       # (height not fixed)
        w.BD(1.0)                       # (width factor)
        w.BD(0.0)                       # (oblique angle)
        w.RC(0)                         # (generation)
        w.BD(0.2)                       # (last height used)
        w.T("txt")
        w.T("")
    return obj(T_STYLE, handle, H["STYLE_CONTROL"], data, [(HARD_PTR, 0)])


def ltype(handle, name, description):
    def data(w):
        _entry(w, name)
        w.T(description)
        w.BD(0.0)                       # (pattern length)
        w.RC(ord("A"))
        w.RC(0)                         # (no dashes: solid)
        w.raw(bytes(256))               # (the text area of complex dashes)
    return obj(T_LTYPE, handle, H["LTYPE_CONTROL"], data, [(HARD_PTR, 0)])


def appid(handle, name):
    def data(w):
        _entry(w, name)
        w.RC(0)
    return obj(T_APPID, handle, H["APPID_CONTROL"], data, [(HARD_PTR, 0)])


# the dimension variables of the Standard style (inches), as the header and DIMSTYLE hold them
DIM = dict(DIMPOST="", DIMAPOST="", DIMSCALE=1.0, DIMASZ=0.18, DIMEXO=0.0625, DIMDLI=0.38,
           DIMEXE=0.18, DIMRND=0.0, DIMDLE=0.0, DIMTP=0.0, DIMTM=0.0, DIMTOL=0, DIMLIM=0,
           DIMTIH=1, DIMTOH=1, DIMSE1=0, DIMSE2=0, DIMTAD=0, DIMZIN=0, DIMAZIN=0, DIMTXT=0.18,
           DIMCEN=0.09, DIMTSZ=0.0, DIMALTF=25.4, DIMLFAC=1.0, DIMTVP=0.0, DIMTFAC=1.0,
           DIMGAP=0.09, DIMALTRND=0.0, DIMALT=0, DIMALTD=2, DIMTOFL=0, DIMSAH=0, DIMTIX=0,
           DIMSOXD=0, DIMCLRD=0, DIMCLRE=0, DIMCLRT=0, DIMADEC=0, DIMDEC=4, DIMTDEC=4,
           DIMALTU=2, DIMALTTD=2, DIMAUNIT=0, DIMFRAC=0, DIMLUNIT=2, DIMDSEP=ord("."),
           DIMTMOVE=0, DIMJUST=0, DIMSD1=0, DIMSD2=0, DIMTOLJ=1, DIMTZIN=0, DIMALTZ=0,
           DIMALTTZ=0, DIMUPT=0, DIMFIT=3, DIMLWD=-2, DIMLWE=-2)


def _dims_a(w, d):
    """The dimension variables the header and DIMSTYLE share up to DIMSOXD, in that order."""
    for k in ("DIMSCALE", "DIMASZ", "DIMEXO", "DIMDLI", "DIMEXE", "DIMRND", "DIMDLE", "DIMTP",
              "DIMTM"):
        w.BD(d[k])
    for k in ("DIMTOL", "DIMLIM", "DIMTIH", "DIMTOH", "DIMSE1", "DIMSE2"):
        w.B(d[k])
    for k in ("DIMTAD", "DIMZIN", "DIMAZIN"):
        w.BS(d[k])
    for k in ("DIMTXT", "DIMCEN", "DIMTSZ", "DIMALTF", "DIMLFAC", "DIMTVP", "DIMTFAC",
              "DIMGAP", "DIMALTRND"):
        w.BD(d[k])
    w.B(d["DIMALT"])
    w.BS(d["DIMALTD"])
    for k in ("DIMTOFL", "DIMSAH", "DIMTIX", "DIMSOXD"):
        w.B(d[k])


def _dims_b(w, d):
    """From DIMADEC to DIMALTTZ (both orders agree there)."""
    for k in ("DIMADEC", "DIMDEC", "DIMTDEC", "DIMALTU", "DIMALTTD", "DIMAUNIT", "DIMFRAC",
              "DIMLUNIT", "DIMDSEP", "DIMTMOVE", "DIMJUST"):
        w.BS(d[k])
    w.B(d["DIMSD1"])
    w.B(d["DIMSD2"])
    for k in ("DIMTOLJ", "DIMTZIN", "DIMALTZ", "DIMALTTZ"):
        w.BS(d[k])


def dimstyle(handle, name):
    def data(w):
        _entry(w, name)
        w.T(DIM["DIMPOST"])
        w.T(DIM["DIMAPOST"])
        _dims_a(w, DIM)
        for k in ("DIMCLRD", "DIMCLRE", "DIMCLRT"):
            w.BS(DIM[k])
        _dims_b(w, DIM)
        w.B(DIM["DIMUPT"])
        w.BS(DIM["DIMFIT"])
        w.BS(DIM["DIMLWD"])
        w.BS(DIM["DIMLWE"])
        w.B(0)
    return obj(T_DIMSTYLE, handle, H["DIMSTYLE_CONTROL"], data,
               [(HARD_PTR, 0), (HARD_PTR, H["STANDARD"]), (HARD_PTR, 0), (HARD_PTR, 0),
                (HARD_PTR, 0), (HARD_PTR, 0)])


def vport(handle, center, height, aspect):
    def data(w):
        _entry(w, "*Active")
        w.BD(height)
        w.BD(aspect * height)           # (stored times the height)
        _2rd(w, center)
        _bds(w, (0.0, 0.0, 0.0))        # (target)
        _bds(w, (0.0, 0.0, 1.0))        # (direction: plan view)
        w.BD(0.0)                       # (twist)
        w.BD(50.0)                      # (lens length)
        w.BD(0.0)                       # (front clip)
        w.BD(0.0)                       # (back clip)
        w.bits(0b0001, 4)               # (view mode 0: its fourth bit is the opposite of 16)
        w.RC(0)                         # (render mode)
        _2rd(w, (0.0, 0.0))
        _2rd(w, (1.0, 1.0))
        w.B(0)                          # (UCSFOLLOW)
        w.BS(1000)                      # (circle zoom)
        w.B(1)                          # (fast zoom)
        w.bits(0b11, 2)                 # (UCS icon on, at the origin)
        w.B(0)                          # (grid off)
        _2rd(w, (0.5, 0.5))
        w.B(0)                          # (snap off)
        w.B(0)                          # (snap style)
        w.BS(0)                         # (isoplane)
        w.BD(0.0)                       # (snap angle)
        _2rd(w, (0.0, 0.0))             # (snap base)
        _2rd(w, (0.5, 0.5))             # (snap spacing)
        w.B(0)
        w.B(1)                          # (UCS per viewport)
        _bds(w, (0.0, 0.0, 0.0))
        _bds(w, (1.0, 0.0, 0.0))
        _bds(w, (0.0, 1.0, 0.0))
        w.BD(0.0)                       # (UCS elevation)
        w.BS(0)                         # (not orthographic)
    return obj(T_VPORT, handle, H["VPORT_CONTROL"], data,
               [(HARD_PTR, 0), (HARD_PTR, 0), (HARD_PTR, 0)])


def mlinestyle(handle, owner):
    def data(w):
        w.T("Standard")
        w.T("")
        w.BS(0)                         # (flags)
        w.CMC(256)                      # (fill color ByLayer)
        w.BD(1.5707963267948966)        # (start and end angles: square)
        w.BD(1.5707963267948966)
        w.RC(2)
        for off in (0.5, -0.5):
            w.BD(off)
            w.CMC(256)
            w.BS(32767)                 # (linetype ByLayer)
    return obj(T_MLINESTYLE, handle, owner, data, reactors=(owner,))


def block_header(handle, name, block, endblk, layout, first=0, last=0):
    def data(w):
        _entry(w, name)
        w.B(0)                          # (not anonymous)
        w.B(0)                          # (no attribute definitions)
        w.B(0)                          # (not an xref)
        w.B(0)                          # (not overlaid)
        w.B(0)                          # (loaded)
        _bds(w, (0.0, 0.0, 0.0))        # (base point)
        w.T("")                         # (xref path)
        w.RC(0)                         # (no block references)
        w.T("")                         # (description)
        w.BL(0)                         # (no preview)
    return obj(T_BLOCK_HEADER, handle, H["BLOCK_CONTROL"], data,
               [(HARD_PTR, 0), (HARD_OWNER, block), (SOFT_PTR, first), (SOFT_PTR, last),
                (HARD_OWNER, endblk), (HARD_PTR, layout)])


def layout(handle, owner, name, tab, flags, block, ext, plot_type):
    def data(w):
        w.T("")                         # (page setup)
        w.T("none_device")
        w.BS(flags)
        for _k in range(4):
            w.BD(0.0)                   # (margins, mm)
        w.BD(215.9)                     # (paper: letter, mm)
        w.BD(279.4)
        w.T("Letter_(8.50_x_11.00_Inches)")
        _bds(w, (0.0, 0.0))             # (plot origin)
        w.BS(0)                         # (paper units: inches)
        w.BS(0)                         # (no rotation)
        w.BS(plot_type)
        _bds(w, (0.0, 0.0))             # (plot window)
        _bds(w, (0.0, 0.0))
        w.T("")                         # (plot view)
        w.BD(1.0)                       # (custom scale)
        w.BD(1.0)
        w.T("")                         # (plot style table)
        w.BS(0)                         # (scaled to fit)
        w.BD(1.0)
        _bds(w, (0.0, 0.0))             # (paper image origin)
        w.T(name)
        w.BL(tab)
        w.BS(1)                         # (PSLTSCALE)
        _bds(w, (0.0, 0.0, 0.0))        # (UCS origin)
        _2rd(w, (0.0, 0.0))             # (limits)
        _2rd(w, (12.0, 9.0))
        _bds(w, (0.0, 0.0, 0.0))        # (insertion base)
        _bds(w, (1.0, 0.0, 0.0))
        _bds(w, (0.0, 1.0, 0.0))
        w.BD(0.0)                       # (elevation)
        w.BS(0)                         # (not orthographic)
        _bds(w, ext[0])
        _bds(w, ext[1])
    return obj(T_LAYOUT, handle, owner, data,
               [(SOFT_PTR, block), (SOFT_PTR, 0), (HARD_PTR, 0), (HARD_PTR, 0)],
               reactors=(owner,))


def line(handle, e, layer_handle, prev=0, nxt=0):
    start, end = e["start"], e["end"]

    def data(w):
        z0 = start[2] == 0.0 and end[2] == 0.0
        w.B(1 if z0 else 0)
        w.RD(start[0])
        w.DD(end[0], start[0])
        w.RD(start[1])
        w.DD(end[1], start[1])
        if not z0:
            w.RD(start[2])
            w.DD(end[2], start[2])
        w.BT(0.0)
        w.BE(0.0, 0.0, 1.0)
    return entity(T_LINE, handle, data, layer_handle, prev=prev, nxt=nxt, color=e["color"])


def lwpolyline(handle, e, layer_handle, prev=0, nxt=0):
    pts, bulges = e["points"], e["bulges"]
    has_bulges = any(bulges)
    # (flags: 16 bulges given, 512 closed; no width, elevation, thickness or extrusion)
    flags = (16 if has_bulges else 0) | (512 if e["closed"] else 0)

    def data(w):
        w.BS(flags)
        w.BL(len(pts))
        if has_bulges:
            w.BL(len(bulges))
        _2rd(w, pts[0])
        for a, b in zip(pts, pts[1:]):
            w.DD(b[0], a[0])
            w.DD(b[1], a[1])
        if has_bulges:
            for v in bulges:
                w.BD(v)
    return entity(T_LWPLINE, handle, data, layer_handle, prev=prev, nxt=nxt,
                  color=e["color"])


def circle(handle, e, layer_handle, prev=0, nxt=0):
    def data(w):
        _bds(w, e["center"])
        w.BD(e["radius"])
        w.BT(0.0)
        w.BE(0.0, 0.0, 1.0)
        if e["type"] == "ARC":
            w.BD(e["start_angle"])
            w.BD(e["end_angle"])
    code = T_ARC if e["type"] == "ARC" else T_CIRCLE
    return entity(code, handle, data, layer_handle, prev=prev, nxt=nxt, color=e["color"])


HALIGN = {"left": 0, "center": 1, "right": 2}


def text(handle, e, layer_handle, prev=0, nxt=0):
    """A single-line text in the Standard style: baseline, its anchor point left, centered or
    right; the insertion point (where AutoCAD starts it) worked out from an estimate of its
    width, the anchor kept as its alignment point."""
    ins, anchor, rot = _text_start(e), e["insert"], e["rotation"]
    halign = HALIGN[e["align"]]
    # (data flags: what is left out: 1 elevation 0, 2 no alignment point, 4 oblique 0,
    # 8 rotation 0, 16 width factor 1, 32 generation 0, 64 left, 128 baseline)
    flags = 0x04 | 0x10 | 0x20 | 0x80
    flags |= 0x01 if anchor[2] == 0.0 else 0
    flags |= 0x02 | 0x40 if halign == 0 else 0
    flags |= 0x08 if rot == 0.0 else 0

    def data(w):
        w.RC(flags)
        if not flags & 0x01:
            w.RD(anchor[2])
        _2rd(w, ins)
        if not flags & 0x02:
            w.DD(anchor[0], ins[0])
            w.DD(anchor[1], ins[1])
        w.BE(0.0, 0.0, 1.0)
        w.BT(0.0)
        if not flags & 0x08:
            w.RD(rot)
        w.RD(e["height"])
        w.T(e["text"])
        if not flags & 0x40:
            w.BS(halign)
    return entity(T_TEXT, handle, data, layer_handle, refs=[(HARD_PTR, H["STANDARD"])],
                  prev=prev, nxt=nxt, color=e["color"])


WRITERS = {"LINE": line, "LWPOLYLINE": lwpolyline, "CIRCLE": circle, "ARC": circle,
           "TEXT": text}


def _block_ends(block, endblk, owner, name):
    def named(w):
        w.T(name)
    return [(block, entity(T_BLOCK, block, named, H["LAYER0"], owner=owner)),
            (endblk, entity(T_ENDBLK, endblk, lambda w: None, H["LAYER0"], owner=owner))]


# ---- the header variables ------------------------------------------------------------------

def _julian(t):
    """A date and time as AutoCAD keeps it: (Julian day, milliseconds into the day)."""
    day = t.date().toordinal() + 1721425
    ms = ((t.hour * 60 + t.minute) * 60 + t.second) * 1000 + t.microsecond // 1000
    return day, ms


def header_vars(ext, seed, when, guids):
    """The header variables (R2000's list, in order), as bytes padded to a whole byte."""
    w = BitWriter()
    w.BD(412148564080.0)
    for v in (1.0, 1.0, 1.0):
        w.BD(v)
    for _k in range(4):
        w.T("")
    w.BL(24)
    w.BL(0)
    w.H(HARD_PTR, 0)                    # (current viewport's entity header: none)
    # DIMASO DIMSHO PLINEGEN ORTHOMODE REGENMODE FILLMODE QTEXTMODE PSLTSCALE LIMCHECK
    # USRTIMER SKPOLY ANGDIR SPLFRAME MIRRTEXT WORLDVIEW TILEMODE PLIMCHECK VISRETAIN
    # DISPSILH PELLIPSE
    for v in (1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 0):
        w.B(v)
    # PROXYGRAPHICS TREEDEPTH LUNITS LUPREC AUNITS AUPREC ATTMODE PDMODE USERI1-5
    # SPLINESEGS SURFU SURFV SURFTYPE SURFTAB1 SURFTAB2 SPLINETYPE SHADEDGE SHADEDIF
    # UNITMODE MAXACTVP ISOLINES CMLJUST TEXTQLTY
    for v in (1, 3020, 2, 4, 0, 0, 1, 0, 0, 0, 0, 0, 0, 8, 6, 6, 6, 6, 6, 6, 3, 70, 0, 64,
              4, 0, 50):
        w.BS(v)
    # LTSCALE TEXTSIZE TRACEWID SKETCHINC FILLETRAD THICKNESS ANGBASE PDSIZE PLINEWID
    # USERR1-5 CHAMFERA-D FACETRES CMLSCALE CELTSCALE
    for v in (1.0, 0.2, 0.05, 0.1, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.5,
              0.5, 1.0, 0.0, 0.5, 1.0, 1.0):
        w.BD(v)
    w.T("acad")                         # (MENUNAME)
    day, ms = _julian(when)
    for v in (day, ms, day, ms, 0, 0, 0, 0):    # (TDCREATE TDUPDATE TDINDWG TDUSRTIMER)
        w.BL(v)
    w.CMC(256)                          # (CECOLOR ByLayer)
    w.H(0, seed)                        # (HANDSEED)
    for h in (H["LAYER0"], H["STANDARD"], H["BYLAYER"], H["DIMSTANDARD"], H["MLSTANDARD"]):
        w.H(HARD_PTR, h)                # (CLAYER TEXTSTYLE CELTYPE DIMSTYLE CMLSTYLE)
    w.BD(0.0)                           # (PSVPSCALE)
    for e in (((BIG,) * 3, (-BIG,) * 3), ext):      # (paper space, then model space)
        _bds(w, (0.0, 0.0, 0.0))        # (INSBASE)
        _bds(w, e[0])
        _bds(w, e[1])
        _2rd(w, (0.0, 0.0))             # (LIMMIN LIMMAX)
        _2rd(w, (12.0, 9.0))
        w.BD(0.0)                       # (ELEVATION)
        _bds(w, (0.0, 0.0, 0.0))        # (UCSORG UCSXDIR UCSYDIR)
        _bds(w, (1.0, 0.0, 0.0))
        _bds(w, (0.0, 1.0, 0.0))
        w.H(HARD_PTR, 0)                # (UCSNAME)
        w.H(HARD_PTR, 0)                # (UCSORTHOREF)
        w.BS(0)                         # (UCSORTHOVIEW)
        w.H(HARD_PTR, 0)                # (UCSBASE)
        for _k in range(6):
            _bds(w, (0.0, 0.0, 0.0))    # (the orthographic UCS origins)
    w.T(DIM["DIMPOST"])
    w.T(DIM["DIMAPOST"])
    _dims_a(w, DIM)
    for k in ("DIMCLRD", "DIMCLRE", "DIMCLRT"):
        w.CMC(DIM[k])
    _dims_b(w, DIM)
    w.B(DIM["DIMUPT"])
    w.BS(DIM["DIMFIT"])                 # (DIMATFIT)
    for h in (H["STANDARD"], 0, 0, 0, 0):   # (DIMTXSTY DIMLDRBLK DIMBLK DIMBLK1 DIMBLK2)
        w.H(HARD_PTR, h)
    w.BS(DIM["DIMLWD"])
    w.BS(DIM["DIMLWE"])
    for k in ("BLOCK_CONTROL", "LAYER_CONTROL", "STYLE_CONTROL", "LTYPE_CONTROL",
              "VIEW_CONTROL", "UCS_CONTROL", "VPORT_CONTROL", "APPID_CONTROL",
              "DIMSTYLE_CONTROL", "VX_CONTROL"):
        w.H(HARD_OWNER, H[k])
    w.H(HARD_PTR, H["GROUPS"])
    w.H(HARD_PTR, H["MLINESTYLES"])
    w.H(HARD_OWNER, H["NOD"])
    w.BS(1)                             # (TSTACKALIGN)
    w.BS(70)                            # (TSTACKSIZE)
    w.T("")                             # (HYPERLINKBASE)
    w.T("")                             # (STYLESHEET)
    for k in ("LAYOUTS", "PLOTSETTINGS", "PLOTSTYLES"):
        w.H(HARD_PTR, H[k])
    # CELWEIGHT ByLayer, lineweights not shown, EXTNAMES, color-dependent plot styles
    w.BL(LW_BYLAYER | 0x0200 | 0x0800 | 0x2000)
    w.BS(1)                             # (INSUNITS: inches)
    w.BS(0)                             # (CEPSNTYPE: ByLayer)
    w.T(guids[0])                       # (FINGERPRINTGUID)
    w.T(guids[1])                       # (VERSIONGUID)
    for k in ("PSPACE", "MSPACE", "BYLAYER", "BYBLOCK", "CONTINUOUS"):
        w.H(HARD_PTR, H[k])
    for _k in range(4):
        w.BS(0)
    return w.bytes()


def _framed(start, data, end):
    """A section framed by its sentinels: its size, its data, the checksum of both."""
    body = struct.pack("<I", len(data)) + data
    return start + body + struct.pack("<H", crc8(0xC0C1, body)) + end


def classes_section():
    w = BitWriter()
    for i, (dxf, cpp) in enumerate(CLASSES):
        w.BS(500 + i)
        w.BS(0)                         # (proxy flags)
        w.T("ObjectDBX Classes")
        w.T(cpp)
        w.T(dxf)
        w.B(0)                          # (not a zombie)
        w.BS(0x1F3)                     # (makes objects)
    return _framed(S_CLASSES, w.bytes(), E_CLASSES)


def object_map(entries):
    """The object map: [(handle, file offset)] in handle order, in pieces of at most 2032
    bytes, each starting again from handle 0 and offset 0, then an empty piece."""
    out, piece, last_h, last_at = bytearray(), bytearray(), 0, 0

    def close(piece):
        sized = struct.pack(">H", len(piece) + 2) + piece
        return sized + struct.pack(">H", crc8(0xC0C1, sized))
    for h, at in sorted(entries):
        pair = MC(h - last_h) + MC(at - last_at)
        if len(piece) + len(pair) + 2 > 2032:
            out += close(piece)
            piece, last_h, last_at = bytearray(), 0, 0
            pair = MC(h) + MC(at)
        piece += pair
        last_h, last_at = h, at
    out += close(piece)
    out += close(bytearray())
    return bytes(out)


def free_space(count, when, objects_at):
    """The object free space section (section 3): 53 bytes, as the specification gives
    them."""
    day, ms = _julian(when)
    out = struct.pack("<iIIII", 0, count, day, ms, objects_at) + bytes([4])
    for v in (0x32, 0x64, 0x200, 0xFFFFFFFF):
        out += struct.pack("<II", v, 0)
    return out


def second_header(at, sections, seed):
    """The second file header (a copy of the locators and the main handles)."""
    w = BitWriter()
    w.BL(at)
    w.raw(VERSION)
    w.raw(bytes(6))
    w.bits(0, 4)
    w.raw(bytes([0x18, 0x78, 0x01, len(sections)]))
    for nr, (addr, size) in enumerate(sections):
        w.RC(nr)
        w.BL(addr)
        w.BL(size)
    handles = [seed, H["BLOCK_CONTROL"], H["LAYER_CONTROL"], H["STYLE_CONTROL"],
               H["LTYPE_CONTROL"], H["VIEW_CONTROL"], H["UCS_CONTROL"], H["VPORT_CONTROL"],
               H["APPID_CONTROL"], H["DIMSTYLE_CONTROL"], H["VX_CONTROL"], H["NOD"],
               H["MLSTANDARD"], H["GROUPS"]]
    w.BS(len(handles))
    for i, h in enumerate(handles):
        hb = h.to_bytes(max(1, (h.bit_length() + 7) // 8), "big")
        w.RC(len(hb))
        w.RC(i)
        w.raw(hb)
    data = w.bytes()
    body = struct.pack("<I", len(data) + 2) + data
    return S_SECOND + body + struct.pack("<H", crc8(0xC0C1, body)) + E_SECOND


# ---- the drawing ---------------------------------------------------------------------------

def nearest_aci(rgb):
    """The color index (1-255) nearest a true color (r, g, b): AutoCAD 2000 drawings keep
    only color indexes."""
    from ezdxf.colors import aci2rgb
    return min(range(1, 256),
               key=lambda i: sum((a - b) ** 2 for a, b in zip(aci2rgb(i), rgb)))


def _color(c, what, allow_logical=True):
    """A color index from an index or an (r, g, b) (None: ByLayer)."""
    if c is None:
        c = 256
    if isinstance(c, (tuple, list)):
        return nearest_aci(tuple(int(v) for v in c))
    lo = 0 if allow_logical else 1
    hi = 256 if allow_logical else 255
    if not isinstance(c, int) or not lo <= c <= hi:
        raise ValueError("%s: color %r isn't a color index %d-%d or (r, g, b)"
                         % (what, c, lo, hi))
    return c


def _point(p, n=3):
    p = tuple(float(c) for c in p)
    if len(p) == 2 and n == 3:
        p += (0.0,)
    if len(p) != n or not all(math.isfinite(c) for c in p):
        raise ValueError("not a point: %r" % (p,))
    return p


def _positive(e, key):
    v = float(e[key])
    if not (math.isfinite(v) and v > 0.0):
        raise ValueError("%s: %s must be above 0, not %r" % (e["type"], key, v))
    return v


BAD_NAME = set('<>/\\":;?*|,=`')


def _layer(la):
    name = str(la["name"])
    if not name or name != name.strip() or BAD_NAME & set(name):
        raise ValueError("layer name %r can't be used in AutoCAD" % name)
    out = dict(name=name, color=_color(la.get("color", 7), "layer " + name, False),
               on=bool(la.get("on", True)), frozen=bool(la.get("frozen", False)),
               locked=bool(la.get("locked", False)))
    if name == "0" and out["frozen"]:
        raise ValueError("layer 0 is the current layer: it can't be frozen")
    return out


def _entity(e):
    """An entity description checked and completed (see dwg_bytes)."""
    kind = str(e.get("type", "")).upper()
    if kind not in WRITERS:
        raise ValueError("can't write a %r to DWG" % e.get("type"))
    out = dict(type=kind, layer=str(e.get("layer", "0")),
               color=_color(e.get("color"), kind))
    if kind == "LINE":
        out.update(start=_point(e["start"]), end=_point(e["end"]))
    elif kind == "LWPOLYLINE":
        pts = [_point(p, 2) for p in e["points"]]
        if len(pts) < 2:
            raise ValueError("LWPOLYLINE: two points at least")
        bulges = [float(b) for b in e.get("bulges") or [0.0] * len(pts)]
        if len(bulges) != len(pts) or not all(math.isfinite(b) for b in bulges):
            raise ValueError("LWPOLYLINE: one bulge for each point")
        out.update(points=pts, bulges=bulges, closed=bool(e.get("closed", False)))
    elif kind in ("CIRCLE", "ARC"):
        out.update(center=_point(e["center"]), radius=_positive(e, "radius"))
        if kind == "ARC":
            out.update(start_angle=float(e["start_angle"]) % math.tau,
                       end_angle=float(e["end_angle"]) % math.tau)
    else:
        align = str(e.get("align", "left")).lower()
        if align not in HALIGN:
            raise ValueError("TEXT: align is left, center or right, not %r" % align)
        txt = str(e["text"])
        if not txt or "\n" in txt or "\r" in txt:
            raise ValueError("TEXT: one line of text, not %r" % txt)
        out.update(text=txt, insert=_point(e["insert"]), height=_positive(e, "height"),
                   rotation=float(e.get("rotation", 0.0)) % math.tau, align=align)
    return out


def _drawing(entities, layers):
    """The layers and entities checked: every layer an entity is on (and 0) in the layer
    table, which comes first; a layer named twice (AutoCAD's names ignore case) refused."""
    lays = [_layer(la) for la in layers]
    ents = [_entity(e) for e in entities]
    known = {la["name"].upper(): la["name"] for la in lays}
    if len(known) != len(lays):
        raise ValueError("a layer is named twice")
    if "0" not in known:
        lays.insert(0, _layer({"name": "0"}))
        known["0"] = "0"
    else:
        lays.sort(key=lambda la: la["name"] != "0")
    for e in ents:
        name = known.get(e["layer"].upper())
        if name is None:
            la = _layer({"name": e["layer"]})
            lays.append(la)
            name = known[e["layer"].upper()] = la["name"]
        e["layer"] = name
    return ents, lays


def _text_width(e):
    """An estimate of a text's width (the Standard style's txt font: about one height per
    character, less the space after the last)."""
    return max(len(e["text"]) - 1.0 / 3.0, 0.0) * e["height"]


def _text_start(e):
    """Where a text starts (its insertion point) from its anchor and alignment."""
    x, y, _z = e["insert"]
    back = _text_width(e) * {0: 0.0, 1: 0.5, 2: 1.0}[HALIGN[e["align"]]]
    return x - back * math.cos(e["rotation"]), y - back * math.sin(e["rotation"])


def _arc_points(c, r, a0, a1):
    """The points that bound an arc from a0 to a1 (counterclockwise): its ends and the
    quadrant points it passes."""
    sweep = (a1 - a0) % math.tau or math.tau
    angles = [a0, a0 + sweep] + [k * math.pi / 2 for k in range(8)
                                 if 0.0 < (k * math.pi / 2 - a0) % math.tau < sweep]
    return [(c[0] + r * math.cos(a), c[1] + r * math.sin(a), c[2]) for a in angles]


def _bulge_points(p, q, b):
    """The points that bound a polyline segment from p to q with bulge b."""
    if b == 0.0:
        return [p + (0.0,), q + (0.0,)]
    d = math.dist(p, q)
    if d == 0.0:
        return [p + (0.0,)]
    angle = 4.0 * math.atan(b)
    r = d / (2.0 * math.sin(angle / 2.0))
    mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
    h = r * math.cos(angle / 2.0)               # (from the chord's middle to the center)
    nx, ny = -(q[1] - p[1]) / d, (q[0] - p[0]) / d
    c = (mx + h * nx, my + h * ny, 0.0)
    a0 = math.atan2(p[1] - c[1], p[0] - c[0])
    a1 = math.atan2(q[1] - c[1], q[0] - c[0])
    if b < 0.0:
        a0, a1 = a1, a0
    return _arc_points(c, abs(r), a0, a1)


def _entity_points(e):
    kind = e["type"]
    if kind == "LINE":
        return [e["start"], e["end"]]
    if kind == "LWPOLYLINE":
        pts, bs = e["points"], e["bulges"]
        segs = list(zip(pts, pts[1:], bs)) + ([(pts[-1], pts[0], bs[-1])]
                                               if e["closed"] else [])
        return [p for a, b, bulge in segs for p in _bulge_points(a, b, bulge)]
    if kind == "CIRCLE":
        return _arc_points(e["center"], e["radius"], 0.0, 0.0)
    if kind == "ARC":
        return _arc_points(e["center"], e["radius"], e["start_angle"], e["end_angle"])
    (x, y), z = _text_start(e), e["insert"][2]
    w, h, a = _text_width(e), e["height"], e["rotation"]
    ux, uy = math.cos(a), math.sin(a)
    return [(x + dx * ux - dy * uy, y + dx * uy + dy * ux, z)
            for dx in (0.0, w) for dy in (0.0, h)]


def _extents(entities):
    pts = [p for e in entities for p in _entity_points(e)]
    if not pts:
        return (BIG,) * 3, (-BIG,) * 3
    return (tuple(min(p[i] for p in pts) for i in range(3)),
            tuple(max(p[i] for p in pts) for i in range(3)))


def drawing_objects(entities, layers, ext):
    """[(handle, object bytes)]: the tables and dictionaries, model and paper space, the
    layers and the entities (in model space), all checked by _drawing."""
    lay_h = {"0": H["LAYER0"]}
    for k, la in enumerate(la for la in layers if la["name"] != "0"):
        lay_h[la["name"]] = FIRST_FREE + k
    first = FIRST_FREE + len(lay_h) - 1
    lh = list(range(first, first + len(entities)))
    nod_items = {"ACAD_GROUP": H["GROUPS"], "ACAD_LAYOUT": H["LAYOUTS"],
                 "ACAD_MLINESTYLE": H["MLINESTYLES"], "ACAD_PLOTSETTINGS": H["PLOTSETTINGS"],
                 "ACAD_PLOTSTYLENAME": H["PLOTSTYLES"]}
    nod = H["NOD"]
    (x0, y0, _z0), (x1, y1, _z1) = ext if entities else ((0.0, 0.0, 0.0), (12.0, 9.0, 0.0))
    aspect = 1.5
    height = max(y1 - y0, (x1 - x0) / aspect, 1e-6) * 1.1
    out = [
        (H["BLOCK_CONTROL"], table_control(T_BLOCK_CONTROL, H["BLOCK_CONTROL"], [],
                                           [H["MSPACE"], H["PSPACE"]])),
        (H["LAYER_CONTROL"], table_control(T_LAYER_CONTROL, H["LAYER_CONTROL"],
                                           list(lay_h.values()))),
        (H["STYLE_CONTROL"], table_control(T_STYLE_CONTROL, H["STYLE_CONTROL"],
                                           [H["STANDARD"]])),
        (H["LTYPE_CONTROL"], table_control(T_LTYPE_CONTROL, H["LTYPE_CONTROL"],
                                           [H["CONTINUOUS"]], [H["BYLAYER"], H["BYBLOCK"]])),
        (H["VIEW_CONTROL"], table_control(T_VIEW_CONTROL, H["VIEW_CONTROL"], [])),
        (H["UCS_CONTROL"], table_control(T_UCS_CONTROL, H["UCS_CONTROL"], [])),
        (H["VPORT_CONTROL"], table_control(T_VPORT_CONTROL, H["VPORT_CONTROL"],
                                           [H["ACTIVE"]])),
        (H["APPID_CONTROL"], table_control(T_APPID_CONTROL, H["APPID_CONTROL"],
                                           [H["ACAD"]])),
        (H["DIMSTYLE_CONTROL"], table_control(T_DIMSTYLE_CONTROL, H["DIMSTYLE_CONTROL"],
                                              [H["DIMSTANDARD"]], more=0)),
        (H["VX_CONTROL"], table_control(T_VX_CONTROL, H["VX_CONTROL"], [])),
        (nod, dictionary(nod, 0, nod_items)),
        (H["GROUPS"], dictionary(H["GROUPS"], nod, {}, (nod,))),
        (H["MLINESTYLES"], dictionary(H["MLINESTYLES"], nod, {"Standard": H["MLSTANDARD"]},
                                      (nod,))),
        (H["NORMAL"], obj(T_PLACEHOLDER, H["NORMAL"], H["PLOTSTYLES"], lambda w: None,
                          reactors=(H["PLOTSTYLES"],))),
        (H["STANDARD"], style(H["STANDARD"], "Standard")),
        (H["ACAD"], appid(H["ACAD"], "ACAD")),
        (H["BYBLOCK"], ltype(H["BYBLOCK"], "ByBlock", "")),
        (H["BYLAYER"], ltype(H["BYLAYER"], "ByLayer", "")),
        (H["CONTINUOUS"], ltype(H["CONTINUOUS"], "Continuous", "Solid line")),
        (H["MLSTANDARD"], mlinestyle(H["MLSTANDARD"], H["MLINESTYLES"])),
        (H["PLOTSTYLES"], dictionary(H["PLOTSTYLES"], nod, {"Normal": H["NORMAL"]}, (nod,),
                                     default=H["NORMAL"])),
        (H["LAYOUTS"], dictionary(H["LAYOUTS"], nod, {"Model": H["MODEL"],
                                                      "Layout1": H["LAYOUT1"]}, (nod,))),
        (H["PLOTSETTINGS"], dictionary(H["PLOTSETTINGS"], nod, {}, (nod,))),
        (H["MSPACE"], block_header(H["MSPACE"], "*Model_Space", H["MS_BLOCK"],
                                   H["MS_ENDBLK"], H["MODEL"],
                                   lh[0] if lh else 0, lh[-1] if lh else 0)),
        (H["PSPACE"], block_header(H["PSPACE"], "*Paper_Space", H["PS_BLOCK"],
                                   H["PS_ENDBLK"], H["LAYOUT1"])),
    ]
    out += _block_ends(H["MS_BLOCK"], H["MS_ENDBLK"], H["MSPACE"], "*Model_Space")
    out += _block_ends(H["PS_BLOCK"], H["PS_ENDBLK"], H["PSPACE"], "*Paper_Space")
    out += [
        (H["MODEL"], layout(H["MODEL"], H["LAYOUTS"], "Model", 0, 1712, H["MSPACE"], ext, 0)),
        (H["LAYOUT1"], layout(H["LAYOUT1"], H["LAYOUTS"], "Layout1", 1, 688, H["PSPACE"],
                              ((BIG,) * 3, (-BIG,) * 3), 5)),
        (H["DIMSTANDARD"], dimstyle(H["DIMSTANDARD"], "Standard")),
        (H["ACTIVE"], vport(H["ACTIVE"], ((x0 + x1) / 2, (y0 + y1) / 2), height, aspect)),
    ]
    for la in layers:
        h = lay_h[la["name"]]
        out.append((h, layer(h, la["name"], la["color"], la["on"], la["frozen"],
                             la["locked"])))
    for i, (h, e) in enumerate(zip(lh, entities)):
        out.append((h, WRITERS[e["type"]](h, e, lay_h[e["layer"]], lh[i - 1] if i else 0,
                                          lh[i + 1] if i + 1 < len(lh) else 0)))
    return out


def dwg_bytes(entities, layers=(), when=None, guids=None):
    """An AutoCAD 2000 DWG file of entities in model space, on layers (inches).

    layers: [{"name", "color": a color index 1-255 or (r, g, b) (kept as the nearest index),
    "on", "frozen", "locked"}]; layer 0 and any layer an entity names are added if missing
    (white, on).
    entities: dicts with "type", "layer" (default "0"), "color" (None or 256 ByLayer, 0
    ByBlock, 1-255, or (r, g, b)), and by type: LINE "start", "end"; LWPOLYLINE "points"
    [(x, y)], "closed", "bulges" (optional, one per point); CIRCLE "center", "radius"; ARC
    "center", "radius", "start_angle", "end_angle" (radians, counterclockwise); TEXT "text"
    (one line), "insert" (the point it is aligned on), "height", "rotation" (radians),
    "align" ("left", "center" or "right"). Points are (x, y) or (x, y, z).
    Raises ValueError for what AutoCAD couldn't take."""
    entities, layers = _drawing(entities, layers)
    when = when or datetime.datetime.now()
    guids = guids or ["{%s}" % str(uuid.uuid4()).upper() for _k in range(2)]
    ext = _extents(entities)
    objects = drawing_objects(entities, layers, ext)
    seed = max(h for h, _o in objects) + 1

    n_loc = 5
    head_len = 0x19 + 9 * n_loc + 2 + 16
    header = _framed(S_HEADER, header_vars(ext, seed, when, guids), E_HEADER)
    classes = classes_section()
    at_header = head_len
    at_classes = at_header + len(header)
    at_objects = at_classes + len(classes) + 0x200
    body, offsets, pos = bytearray(), [], at_objects
    for h, data in objects:
        offsets.append((h, pos))
        body += data
        pos += len(data)
    omap = object_map(offsets)
    at_map = pos
    at_free = at_map + len(omap)
    free = free_space(len(objects), when, at_objects)
    at_template = at_free + len(free)
    template = struct.pack("<hH", 0, 0)             # (no description; MEASUREMENT English)
    at_second = at_template + len(template)
    sections = [(at_header, len(header)), (at_classes, len(classes)), (at_map, len(omap)),
                (at_free, len(free)), (at_template, len(template))]
    second = second_header(at_second, sections, seed)
    at_image = at_second + len(second)
    image = S_IMAGE + struct.pack("<I", 1) + bytes([0]) + E_IMAGE

    fh = bytearray(VERSION + bytes(6) + bytes([1]))
    fh += struct.pack("<I", at_image)
    fh += bytes(2)
    fh += struct.pack("<h", CODEPAGE)
    fh += struct.pack("<I", n_loc)
    for nr, (addr, size) in enumerate(sections):
        fh += struct.pack("<BII", nr, addr, size)
    fh += struct.pack("<H", crc8(0, fh) ^ LOCATOR_XOR[n_loc])
    fh += S_FILE_HEADER_END
    return (bytes(fh) + header + classes + bytes(0x200) + bytes(body) + omap + free +
            template + second + image)


def write_dwg(path, entities, layers=()):
    """Write entities on layers to path as an AutoCAD 2000 DWG (see dwg_bytes)."""
    data = dwg_bytes(entities, layers)
    with open(path, "wb") as f:
        f.write(data)
