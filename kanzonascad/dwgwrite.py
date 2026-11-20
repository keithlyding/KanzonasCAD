"""DWG files written by KanzonasCAD itself, as AutoCAD 2000 (AC1015) drawings (the owner, Nov
2026: "You write it. Don't rely on some third party tool"), from the Open Design Alliance's Open
Design Specification for .dwg files (its sections 3, 9, 10, 20, 21, 22, 23 and 26). Written from
that description; no code or text of it is copied here.

The file, in order: the file header with its section locators; the header variables; the
classes; the padding; the objects (the tables and dictionaries every drawing has, then the
drawing's own entities); the object map; the object free space and template sections; the
second file header; an empty preview. Every object is written with absolute handle references.

So far (milestone 1): lines on layer 0 in model space. No Qt."""

import datetime
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
T_BLOCK, T_ENDBLK, T_LINE, T_DICTIONARY = 4, 5, 19, 42
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
FIRST_ENTITY = 0x24

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
           prev=0, nxt=0):
    """An entity: in model space when owner is 0 (no owner reference), else owned by it
    (a block's BLOCK and ENDBLK). Color, linetype and plot style ByLayer."""
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
    w.CMC(256)
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


def layer(handle, name, color=7):
    def data(w):
        _entry(w, name)
        w.BS(16 | (LW_DEFAULT << 5))    # (plotted, lineweight Default, on, thawed)
        w.CMC(color)
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


def line(handle, start, end, layer_handle, prev=0, nxt=0):
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
    return entity(T_LINE, handle, data, layer_handle, prev=prev, nxt=nxt)


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

def _extents(lines):
    pts = [p for ln in lines for p in ln]
    if not pts:
        return (BIG,) * 3, (-BIG,) * 3
    return (tuple(min(p[i] for p in pts) for i in range(3)),
            tuple(max(p[i] for p in pts) for i in range(3)))


def drawing_objects(lines, ext):
    """[(handle, object bytes)]: the tables and dictionaries, model and paper space, and
    the lines (in model space, layer 0)."""
    lh = list(range(FIRST_ENTITY, FIRST_ENTITY + len(lines)))
    nod_items = {"ACAD_GROUP": H["GROUPS"], "ACAD_LAYOUT": H["LAYOUTS"],
                 "ACAD_MLINESTYLE": H["MLINESTYLES"], "ACAD_PLOTSETTINGS": H["PLOTSETTINGS"],
                 "ACAD_PLOTSTYLENAME": H["PLOTSTYLES"]}
    nod = H["NOD"]
    (x0, y0, _z0), (x1, y1, _z1) = ext if lines else ((0.0, 0.0, 0.0), (12.0, 9.0, 0.0))
    aspect = 1.5
    height = max(y1 - y0, (x1 - x0) / aspect, 1e-6) * 1.1
    out = [
        (H["BLOCK_CONTROL"], table_control(T_BLOCK_CONTROL, H["BLOCK_CONTROL"], [],
                                           [H["MSPACE"], H["PSPACE"]])),
        (H["LAYER_CONTROL"], table_control(T_LAYER_CONTROL, H["LAYER_CONTROL"],
                                           [H["LAYER0"]])),
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
        (H["LAYER0"], layer(H["LAYER0"], "0")),
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
    for i, (h, (a, b)) in enumerate(zip(lh, lines)):
        out.append((h, line(h, a, b, H["LAYER0"], lh[i - 1] if i else 0,
                            lh[i + 1] if i + 1 < len(lh) else 0)))
    return out


def _point(p):
    p = tuple(float(c) for c in p)
    return p if len(p) == 3 else p + (0.0,)


def dwg_bytes(lines, when=None, guids=None):
    """An AutoCAD 2000 DWG file holding lines [(start, end)] (points (x, y) or (x, y, z), in
    inches) in model space on layer 0."""
    lines = [(_point(a), _point(b)) for a, b in lines]
    when = when or datetime.datetime.now()
    guids = guids or ["{%s}" % str(uuid.uuid4()).upper() for _k in range(2)]
    ext = _extents(lines)
    objects = drawing_objects(lines, ext)
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


def write_dwg(path, lines):
    """Write lines [(start, end)] to path as an AutoCAD 2000 DWG (see dwg_bytes)."""
    data = dwg_bytes(lines)
    with open(path, "wb") as f:
        f.write(data)
