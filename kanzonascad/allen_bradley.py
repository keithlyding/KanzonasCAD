"""Allen-Bradley devices (the owner, Nov 2026: "lean heavy on the Allen Bradley stuff"): the
symbols, footprints and parts for the Rockwell Automation families a US panel is commonly built
from. No Qt here.

- Symbols drawn here in the JIC/NFPA style, from the standard conventions (symbols_jic.py's
  pieces), never from Rockwell's or anyone's drawings: a motor protection circuit breaker
  (Bulletin 140M), an electronic overload relay (Bulletin 193 / E300) and its contacts, a
  three-position selector switch, a pilot light showing its color, and PLC I/O modules drawn
  whole (ControlLogix 1756, CompactLogix 1769, Compact 5000 5069, POINT I/O 1734). A module's
  pins are named by Rockwell's terminal (screw) numbers, the point beside each ("2  IN 0"),
  for a module whose terminal assignment is in TERMINALS, taken from Rockwell's own wiring
  diagram for it (the owner, Nov 27 2026: "Both"; a 1769 module's by position from the top,
  Rockwell printing none on its blocks); any other module's pins are named by point
  (0, 1, 2...), its commons left out (Edit block renames its terminals). Wire numbers by
  address and Import I/O list read the point from the text beside the pin, so they work
  either way.
- Footprints of the parts with no generic one near their size: PowerFlex 525 drives by frame
  (Rockwell's published nominal widths and heights), and approximate outlines of the PLC
  modules, controllers and chassis, named "(approximate)": draw them from Rockwell's dimension
  drawing (Make block, or Edit block on one of these) before laying out a real panel.
- Parts (Library, Parts tab; built in, read only: a part of yours with the same id takes its
  place): catalog numbers as data, each with its symbol and a footprint, and in its notes what
  to check in Rockwell's selection guide before ordering (coil voltage, current range).
"""

from .footprints_generic import MM, _fp, _rect, _screws
from .library import Part
import math

from .model import Arc, Circle, Line, Text
from .symbols_jic import (PIN, POLES, RATING3_Y, TAG, TAG3_Y, _contact, _heater, _heater_link,
                          _link, _pb_terminals, _rating, _sym, _three, _three_pins, io_module,
                          _io_terminals, show_contact_pins)

AB = "Allen-Bradley"
CHECK = "Check Rockwell's selection guide before ordering"


# ---- symbols -------------------------------------------------------------------------------
def _cb_pole():
    o = []
    _pb_terminals(o)
    o.append(Arc((0, -0.05), 0.16, 30, 150))
    return o


def _ct_pole():
    """An electronic overload's pole: the wire through its current sensor (a circle)."""
    return [Line((-PIN, 0.0), (PIN, 0.0)), Circle((0.0, 0.0), 0.0625)]


def _positions(out, closed):
    """A three-position selector's positions over its contact: a tick for each (left, middle,
    right), an X over those it is closed in (JIC's truth marks)."""
    for i, x in enumerate((-0.1, 0.0, 0.1)):
        out.append(Line((x, 0.17), (x, 0.2)))
        if i in closed:
            out.append(Text((x, 0.21), "X", 0.05, align="center"))


def _selector3(closed):
    o = []
    _pb_terminals(o)
    o.append(Line((-0.125, 0.03125), (0.09375, 0.15625)))
    _positions(o, closed)
    return o


def ab_symbols():
    S = []
    # a motor protection circuit breaker (manual motor starter, Bulletin 140M): breaker poles
    # and their thermal elements, L1-L3 in, T1-T3 out 1" away; its auxiliary contacts belong
    # to it
    o = _three(_cb_pole) + _link(0.0, 0.6, -0.4) + \
        [e._map(lambda q: (q[0] + 2 * PIN, q[1])) for e in _three(_heater)] + \
        [e._map(lambda q: (q[0] + 2 * PIN, q[1])) for e in _heater_link()]
    S.append(_sym("Motor protection circuit breaker 3-pole", "JIC/Motor control", o, "parent",
                  "", "CB",
                  [{"name": "L%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)] +
                  [{"name": "T%d" % (i + 1), "pos": (3 * PIN, y)} for i, y in enumerate(POLES)],
                  tag=(PIN, TAG3_Y),
                  description="Motor protection circuit breaker (manual motor starter): "
                              "breaker poles with their thermal trip, three poles (Allen-Bradley "
                              "140M and the like); its auxiliary contacts belong to it",
                  attr_texts=_rating(2 * PIN, RATING3_Y, fields=("AMPS", "HP"))))
    # an electronic overload relay (Bulletin 193, E300): the wires through its current sensors
    o = _three(_ct_pole) + [_rect(-0.125, -0.65, 0.125, 0.65)]
    S.append(_sym("Overload relay, electronic 3-pole", "JIC/Motor control", o, "parent", "",
                  "OL", _three_pins(), tag=(0.0, TAG3_Y),
                  description="Electronic overload relay, three poles: the wires through its "
                              "current sensors (Allen-Bradley 193 / E300 and the like); its "
                              "contacts (95-96 trip, 97-98 alarm) belong to it",
                  attr_texts=_rating(y=RATING3_Y - 0.15, fields=("AMPS",))))
    S.append(_sym("Overload contact NO", "JIC/Motor control", _contact(False), "child", "NO",
                  "OL", description="Overload relay contact, normally open (alarm, 97-98)"))
    # a three-position selector switch (Hand-Off-Auto): the operator closed in its left
    # position, its contact blocks closed left or right
    S.append(_sym("Selector switch 3-position", "JIC/Pushbuttons and switches", _selector3({0}),
                  "parent", "NO", "SS", tag=TAG,
                  description="Three-position selector switch (Hand-Off-Auto), maintained: "
                              "closed in its left position (X); its contact blocks belong to it"))
    S.append(_sym("Selector switch 3-position contact, closed left",
                  "JIC/Pushbuttons and switches", _selector3({0}), "child", "NO", "SS",
                  description="A three-position selector switch's contact block, closed in its "
                              "left position"))
    S.append(_sym("Selector switch 3-position contact, closed right",
                  "JIC/Pushbuttons and switches", _selector3({2}), "child", "NO", "SS",
                  description="A three-position selector switch's contact block, closed in its "
                              "right position"))
    # a pilot light with its lens color's letter in it (R, G, A...: COLOR)
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)), Circle((0, 0), 0.125)]
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        o.append(Line((0.16 * math.cos(r), 0.16 * math.sin(r)),
                      (0.22 * math.cos(r), 0.22 * math.sin(r))))
    S.append(_sym("Pilot light with color letter", "JIC/Indicators and loads", o, "device",
                  "", "LT", tag=TAG,
                  description="Pilot light, its lens color's letter in it (COLOR: R red, "
                              "G green, A amber, W white, B blue)",
                  attr_texts=[{"attr": "COLOR", "pos": (0.0, -0.035), "height": 0.08}]))
    show_contact_pins(S)
    S += ab_io_modules()
    return S


# (catalog, family, description, points kind, points)
IO = [
    ("1756-IB16", "ControlLogix", "24V DC sinking input module, 16 points", "IN", 16),
    ("1756-OB16E", "ControlLogix", "24V DC sourcing output module, electronically protected, "
                                   "16 points", "OUT", 16),
    ("1756-IF8", "ControlLogix", "Analog input module, 8 channels (current or voltage)",
     "IN", 8),
    ("1756-OF8", "ControlLogix", "Analog output module, 8 channels (current or voltage)",
     "OUT", 8),
    ("1769-IQ16", "CompactLogix", "24V DC sinking/sourcing input module, 16 points", "IN", 16),
    ("1769-OB16", "CompactLogix", "24V DC sourcing output module, 16 points", "OUT", 16),
    ("1769-OW8", "CompactLogix", "Relay output module, 8 points", "OUT", 8),
    ("1769-IF4", "CompactLogix", "Analog input module, 4 channels (current or voltage)",
     "IN", 4),
    ("1769-OF2", "CompactLogix", "Analog output module, 2 channels (current or voltage)",
     "OUT", 2),
    ("5069-IB16", "Compact 5000 I/O", "24V DC sinking input module, 16 points", "IN", 16),
    ("5069-OB16", "Compact 5000 I/O", "24V DC sourcing output module, 16 points", "OUT", 16),
    ("1734-IB4", "POINT I/O", "24V DC sinking input module, 4 points", "IN", 4),
    ("1734-OB4E", "POINT I/O", "24V DC sourcing output module, electronically protected, "
                               "4 points", "OUT", 4),
]


# {catalog: (Rockwell publication it is from, [(terminal number, what it is)])}: a module's
# terminal block as Rockwell's wiring diagram for it prints it, every screw (points, commons,
# supplies, the ones not used), in terminal-number order. Only from Rockwell's own documents,
# each module's publication, edition, page and where it was read named beside it (read in Nov
# 2026 from mirrors of Rockwell's PDFs: Rockwell's literature library refused the machine these
# were built on). The point beside a terminal is written as Rockwell prints it ("IN-0", "OUT 3",
# "V in 0+", "VOUT-2"): wirenums.io_points reads the point from it. A module not here is drawn
# by point (_io_terminals). The owner's rules (Nov 27 2026): the printed terminal numbers for
# 1756, 1734 and 5069; for 1769, which prints none, the positions 1-18 counted from the top as
# the door label lays them out (alternating right and left column); a pin for every screw,
# "No Connect", "Not used" and NC ones too, named so; none where there is no screw.
TERMINALS = {
    # 1756-UM058G-EN-P, ControlLogix Digital I/O Modules User Manual, November 2012, page 142
    # (https://www.manualsdir.com/manuals/579413/rockwell-automation-1756-xxxx-controllogix-
    # digital-i_o-modules.html?page=142: its labels readable, most terminal numbers lost from
    # the text, those left, 1, 10, 11, 20, fitting); every number from 1492-SG121E-EN-P, I/O
    # Wiring Conversion Systems, PLC-5 1771 to ControlLogix 1756, July 2016, page 24
    # ("1771-IBD to 1756-IB16", https://docs.rs-online.com/591c/A700000007707241.pdf). The
    # 20-pin block: odd terminals in its right column, even in its left; GND-0 (9, 10) and
    # GND-1 (19, 20) each joined inside.
    "1756-IB16": ("1756-UM058G-EN-P, Nov 2012, p. 142; 1492-SG121E-EN-P, Jul 2016, p. 24",
                  [(str(i + 1), "IN-%d" % i) for i in range(8)] +
                  [("9", "GND-0"), ("10", "GND-0")] +
                  [(str(i + 3), "IN-%d" % i) for i in range(8, 16)] +
                  [("19", "GND-1"), ("20", "GND-1")]),
    # 1756-UM058G-EN-P, November 2012, page 162, every number legible
    # (https://www.manualsdir.com/manuals/579413/rockwell-automation-1756-xxxx-controllogix-
    # digital-i_o-modules.html?page=162); the same in 1492-SG121E-EN-P, July 2016, page 51
    # ("1771-OBD to 1756-OB16E"). Group 0 OUT-0 to 7 (RTN OUT-0, DC-0(+)), group 1 OUT-8 to 15.
    "1756-OB16E": ("1756-UM058G-EN-P, Nov 2012, p. 162; 1492-SG121E-EN-P, Jul 2016, p. 51",
                   [(str(i + 1), "OUT-%d" % i) for i in range(8)] +
                   [("9", "RTN OUT-0"), ("10", "DC-0(+)")] +
                   [(str(i + 3), "OUT-%d" % i) for i in range(8, 16)] +
                   [("19", "RTN OUT-1"), ("20", "DC-1(+)")]),
    # 1756-UM009C-EN-P, ControlLogix Analog I/O Modules User Manual, December 2010, pages 74-77
    # (https://www.manualsdir.com/manuals/579376/rockwell-automation-1756-xxxx-controllogix-
    # analog-i_o-modules.html?page=74, and 75-77: its four wiring examples, the same labels).
    # The 36-pin block. Caveat: in the right column (3/5/7, 23-31, 33/35) the source's text ran
    # the labels together ("i RTN-1i RTN-2i RTN-3"); they were split in order from the top,
    # as the left column and the module's pattern have them. Drawn single-ended (8 channels:
    # channel x is IN-x, its return RTN; for current, i RTN-x wired to RTN); differential
    # pairs IN-0(+)/IN-1(-)... All RTN joined inside.
    "1756-IF8": ("1756-UM009C-EN-P, Dec 2010, pp. 74-77",
                 [t for i in range(4) for t in ((str(2 * i + 1), "i RTN-%d" % i),
                                                (str(2 * i + 2), "IN-%d" % i))] +
                 [("9", "RTN"), ("10", "RTN")] +
                 [t for i in range(4, 8) for t in ((str(2 * i + 3), "i RTN-%d" % i),
                                                   (str(2 * i + 4), "IN-%d" % i))] +
                 [(str(i), "Not used") for i in range(19, 27)] +
                 [("27", "RTN"), ("28", "RTN")] +
                 [(str(i), "Not used") for i in range(29, 37)]),
    # 1756-UM009C-EN-P, December 2010, page 158 (its current and voltage examples agree;
    # https://www.manualsdir.com/manuals/579376/rockwell-automation-1756-xxxx-controllogix-
    # analog-i_o-modules.html?page=158). The 20-pin block: channels 0-3 in the right column,
    # 4-7 in the left; a voltage load on VOUT-x and RTN, a current load on IOUT-x and RTN (both
    # are channel x's point); all RTN joined inside.
    "1756-OF8": ("1756-UM009C-EN-P, Dec 2010, p. 158",
                 [("1", "VOUT-0"), ("2", "VOUT-4"), ("3", "IOUT-0"), ("4", "IOUT-4"),
                  ("5", "RTN"), ("6", "RTN"), ("7", "VOUT-1"), ("8", "VOUT-5"),
                  ("9", "IOUT-1"), ("10", "IOUT-5"), ("11", "VOUT-2"), ("12", "VOUT-6"),
                  ("13", "IOUT-2"), ("14", "IOUT-6"), ("15", "RTN"), ("16", "RTN"),
                  ("17", "VOUT-3"), ("18", "VOUT-7"), ("19", "IOUT-3"), ("20", "IOUT-7")]),
    # 1769 blocks: Rockwell prints no screw numbers; the 18 positions counted from the top,
    # right and left columns alternating (the right one higher), as each door label shows.
    # 1769-IN007B-EN-P, Compact 24V dc Sink/Source Input Module Installation Instructions, June
    # 2000: door label page 2, wiring diagram page 8 (https://www.manualsdir.com/manuals/
    # 579509/rockwell-automation-1769-iq16-compact-24v-dc-sink_source-input-module.html?page=8);
    # the same in 1769-SG002C-EN-P, March 2004, page 8
    # (https://docs.rs-online.com/0e60/0900766b804a34cf.pdf). The order turns after DC COM 1:
    # IN 9 above IN 8. Group 1 IN 0-7 with DC COM 1, group 2 IN 8-15 with DC COM 2.
    "1769-IQ16": ("1769-IN007B-EN-P, Jun 2000, pp. 2 and 8",
                  [(str(i + 1), "IN %d" % i) for i in range(8)] + [("9", "DC COM 1")] +
                  [("10", "IN 9"), ("11", "IN 8"), ("12", "IN 11"), ("13", "IN 10"),
                   ("14", "IN 13"), ("15", "IN 12"), ("16", "IN 15"), ("17", "IN 14"),
                   ("18", "DC COM 2")]),
    # 1769-IN054A-EN-P, Compact Solid State 24V dc Source Output Module Installation
    # Instructions, April 2001, page 8 (https://www.manualsdir.com/manuals/579848/rockwell-
    # automation-1769-ob16-compact-solid-state-24v-dc-source-output-module.html?page=8). +VDC
    # to +DC, DC COM to -DC. Caveat: 1769-SG002C-EN-P (page 11) prints the first one "+VAC", a
    # typo: the installation instructions' "+VDC" is used.
    "1769-OB16": ("1769-IN054A-EN-P, Apr 2001, p. 8",
                  [("1", "+VDC")] + [(str(i + 2), "OUT %d" % i) for i in range(16)] +
                  [("18", "DC COM")]),
    # 1769-IN051A-EN-P, Compact AC/DC Relay Output Module Installation Instructions, April
    # 2001: door label page 2, wiring diagram page 8 (https://www.manualsdir.com/manuals/
    # 579415/rockwell-automation-1769-ow8-compact-ac_dc-relay-output-module.html?page=8).
    # Positions 1-4 and 15-18 are drawn blank, no label (not "NC"): pins named "(blank)". Group
    # 1 OUT 0-3 with VAC-VDC 1, group 2 OUT 4-7 with VAC-VDC 2, each to L1 or +DC.
    "1769-OW8": ("1769-IN051A-EN-P, Apr 2001, pp. 2 and 8",
                 [(str(i), "(blank)") for i in range(1, 5)] +
                 [("5", "VAC-VDC 1"), ("6", "OUT 0"), ("7", "OUT 1"), ("8", "OUT 2"),
                  ("9", "OUT 3"), ("10", "VAC-VDC 2"), ("11", "OUT 5"), ("12", "OUT 4"),
                  ("13", "OUT 7"), ("14", "OUT 6")] +
                 [(str(i), "(blank)") for i in range(15, 19)]),
    # 1769-IN048A-EN-P, Compact Analog Input Module (Series B or later) Installation
    # Instructions, December 2000, pages 2 and 11-13 (https://www.manualsdir.com/manuals/
    # 579288/rockwell-automation-1769-if4-compact-series-b-or-later-analog-input-module.html?
    # page=12); the same list in 1769-SG002C-EN-P, page 16. Differential voltage on V in x+
    # and V/I in x-, current on I in x+ and V/I in x- (V in x+ and I in x+ both channel x's
    # point); all ANLG Com joined inside; +24V dc and dc NEUT an optional external supply.
    "1769-IF4": ("1769-IN048A-EN-P, Dec 2000, pp. 2 and 11-13",
                 [t for i in range(4) for t in (
                     (str(4 * i + 1), "V in %d+" % i), (str(4 * i + 2), "V/I in %d-" % i),
                     (str(4 * i + 3), "I in %d+" % i), (str(4 * i + 4), "ANLG Com"))] +
                 [("17", "+24V dc"), ("18", "dc NEUT")]),
    # 1769-UM002B-EN-P, Compact I/O Analog Modules User Manual, July 2005, page 48, Figure 2.19
    # "1769-OF2 Terminal Layout" (https://www.manualsdir.com/manuals/579674/rockwell-automation-
    # 1769-of2-compact-i_o-analog-modules-1769-of8c-compact-i_o-analog-modules-1769-of8v-
    # compact-i_o-analog-modules-1769-if4-compact-i_o-analog-modules-1769-if8-compact-i_o-
    # analog-modules.html?page=48); it agrees with 1769-IN049A-EN-P, December 2000, pages 2
    # and 11. Positions 1-4 and 15-18 are blacked out, no screw: no pin for them. NC (8, 12):
    # not to be used as connection points. Caveat: 1769-SG002C (page 20) prints positions 9
    # and 10 "V out 0+" and "I out 0+" a second time; the manual's "V out 1+", "I out 1+" are
    # used.
    "1769-OF2": ("1769-UM002B-EN-P, Jul 2005, p. 48",
                 [("5", "V out 0+"), ("6", "I out 0+"), ("7", "ANLG Com"), ("8", "NC"),
                  ("9", "V out 1+"), ("10", "I out 1+"), ("11", "ANLG Com"), ("12", "NC"),
                  ("13", "+24V dc"), ("14", "dc NEUT")]),
    # 5069-IN004E-EN-P, Compact 5000 Digital 16-point Sinking Input Modules Installation
    # Instructions, June 2022, page 8, "Wiring Diagram", terminals printed 0-17 from the top
    # (https://docs.plcexchange.net/allen-bradley/compact-5000/5069-IN004_ib16-install.pdf);
    # 5069-UM004H-EN-P, March 2026, page 111 agrees (IN 0-15, then two not used). No common
    # on the block: the inputs return through the module to SA (-) of the SA power terminal
    # block (the controller's, an adapter's or a 5069-FPD's).
    "5069-IB16": ("5069-IN004E-EN-P, Jun 2022, p. 8",
                  [(str(i), "IN %d" % i) for i in range(16)] +
                  [("16", "No Connect"), ("17", "No Connect")]),
    # 5069-IN007E-EN-P, Compact 5000 Digital 16-point Sourcing Output Modules Installation
    # Instructions, June 2022, page 8, "Wiring Diagram"
    # (https://docs.plcexchange.net/allen-bradley/compact-5000/5069-IN007_ob16-install.pdf);
    # 5069-UM004H-EN-P, March 2026, page 112 agrees (OUT 0-15, LA+, LA-). Caveat: this
    # diagram prints no numbers; they are the positions counted from the top, 0-17, as the
    # same 5069-RTB18 block is numbered in 5069-IN004E. LA+ and LA- (24V DC) feed the outputs.
    "5069-OB16": ("5069-IN007E-EN-P, Jun 2022, p. 8 (numbers counted from the top)",
                  [(str(i), "OUT %d" % i) for i in range(16)] +
                  [("16", "LA+"), ("17", "LA-")]),
    # 1734-IN051H-EN-E, POINT I/O Input Modules (1734-IB2, -IB4, -IB8, Series C), April 2013,
    # pages 12 and 14 (https://www.manualsdir.com/manuals/579333/rockwell-automation-1734-
    # ib2_ib4_ib8-series-c-point-i_o-sink-input-module.html?page=14). Channels 0 and 2 with
    # C 4 and V 6, 1 and 3 with C 5 and V 7; V from the module's power bus.
    "1734-IB4": ("1734-IN051H-EN-E, Apr 2013, pp. 12 and 14",
                 [(str(i), "In %d" % i) for i in range(4)] +
                 [("4", "C"), ("5", "C"), ("6", "V"), ("7", "V")]),
    # 1734-IN056H-EN-P, POINT I/O Protected Output Modules (1734-OB2E/OB4E/OB8E, Series C), May
    # 2013, pages 12-13 (https://www.manualsdir.com/manuals/579686/rockwell-automation-1734-
    # ob2e_4e_8e-series-c-point-i_o-protected-output-module-installation-instructions.html?
    # page=13). Commons: channel 0 on 6, 1 on 7, 2 on 4, 3 on 5.
    "1734-OB4E": ("1734-IN056H-EN-P, May 2013, pp. 12-13",
                  [(str(i), "Out %d" % i) for i in range(4)] +
                  [(str(i), "C") for i in range(4, 8)]),
}


def _module_terminals(cat, word, n):
    """(terminals, what the description says of them) of a module: Rockwell's terminal numbers
    (TERMINALS; a 1769 module's positions from the top) or, without them, its points."""
    got = TERMINALS.get(cat)
    if got:
        pub, terms = got
        if cat.startswith("1769-"):
            return terms, ("terminals numbered by position from the top, 1-18 (Rockwell "
                           "prints no screw numbers on a 1769 block), as Rockwell's wiring "
                           "diagram lays them out (%s)" % pub)
        return terms, "terminals as Rockwell's wiring diagram numbers them (%s)" % pub
    return (_io_terminals(word, n), "terminals named by point: its terminal numbers and "
            "commons are on Rockwell's wiring diagram (Edit block renames them)")


def ab_io_modules():
    """The Allen-Bradley PLC I/O modules drawn whole (symbols_jic.io_module): their pins named
    by Rockwell's terminal numbers, the point beside each (TERMINALS), else by point."""
    out = []
    for cat, fam, desc, word, n in IO:
        terms, said = _module_terminals(cat, word, n)
        out.append(io_module("%s module" % cat, terms, "%s (%s); %s" % (desc, fam, said),
                             cat, AB, fam, right=word == "OUT"))
    return out


# ---- footprints ----------------------------------------------------------------------------
# PowerFlex 525 frames: (frame, width, height in mm), Rockwell's published nominal sizes
PF525_FRAMES = [("A", 72, 152), ("B", 87, 180), ("C", 109, 220), ("D", 130, 260),
                ("E", 185, 300)]
# 1756 chassis: (slots, width in mm), approximate
CHASSIS = [(4, 263), (7, 368), (10, 483), (13, 588), (17, 738)]


def _ab_fp(name, family, category, w, h, ents, description, rail=True, nominal=False):
    """A footprint w x h inches; its description says how sure its size is: Rockwell's
    nominal size (nominal), else approximate."""
    d = _fp(name, category, w, h, ents, description, rail)
    d.category = "Allen-Bradley/" + category
    d.manufacturer, d.family = AB, family
    size = "%g x %g in (%g x %g mm)" % (round(w, 2), round(h, 2), round(w / MM), round(h / MM))
    d.description = ("%s: check the dimension drawing for its mounting holes" % description
                     if nominal else "%s, about %s: draw it from Rockwell's dimension drawing "
                     "before laying out a panel" % (description, size))
    return d


def ab_footprints():
    out = []
    for frame, w, h in PF525_FRAMES:
        W, H = w * MM, h * MM
        vents = [Line((-W / 2 + 0.15, y), (W / 2 - 0.15, y))
                 for y in (H / 2 - 0.35, H / 2 - 0.45, H / 2 - 0.55)]
        # (its keypad and display, and its power terminals along the bottom)
        ents = vents + [_rect(-W * 0.3, 0.0, W * 0.3, H * 0.22)] + \
            [Circle((-W / 2 + W * (i + 0.5) / 6, -H / 2 + 0.25), min(0.07, W / 30))
             for i in range(6)]
        out.append(_ab_fp("PowerFlex 525 frame %s" % frame, "PowerFlex 525", "Drives", W, H,
                          ents, "PowerFlex 525 drive, frame %s, %d x %d mm (W x H) as Rockwell "
                                "publishes it nominally" % (frame, w, h), rail=False,
                          nominal=True))
    W, H = 35 * MM, 118 * MM
    out.append(_ab_fp("1769 I/O module (approximate)", "CompactLogix", "PLC", W, H,
                      [Circle((0.0, -H / 2 + 0.3 + 0.22 * i), 0.05) for i in range(10)],
                      "CompactLogix 1769 I/O module, approximate"))
    W, H = 55 * MM, 118 * MM
    out.append(_ab_fp("1769 CompactLogix controller (approximate)", "CompactLogix", "PLC", W,
                      H, [_rect(-W * 0.35, 0.2, W * 0.35, 1.4)],
                      "CompactLogix 1769-L3x controller, approximate"))
    W, H = 35 * MM, 140 * MM
    out.append(_ab_fp("1756 I/O module (approximate)", "ControlLogix", "PLC", W, H,
                      [Circle((0.0, -H / 2 + 0.4 + 0.25 * i), 0.05) for i in range(12)],
                      "ControlLogix 1756 module, as seen in its chassis, approximate",
                      rail=False))
    for slots, w in CHASSIS:
        W, H = w * MM, 137 * MM
        ents = [Line((-W / 2 + W * i / slots, -H / 2 + 0.2), (-W / 2 + W * i / slots,
                                                                 H / 2 - 0.2))
                for i in range(1, slots)] + _screws(W, H, 2, inset=0.12)
        out.append(_ab_fp("1756 chassis, %d slots (approximate)" % slots, "ControlLogix",
                          "PLC", W, H, ents,
                          "ControlLogix 1756 chassis, %d slots, approximate" % slots,
                          rail=False))
    W, H = 22 * MM, 145 * MM
    out.append(_ab_fp("5069 I/O module (approximate)", "Compact 5000 I/O", "PLC", W, H,
                      [Circle((0.0, -H / 2 + 0.4 + 0.25 * i), 0.04) for i in range(9)],
                      "Compact 5000 I/O 5069 module, approximate"))
    W, H = 12 * MM, 76 * MM
    out.append(_ab_fp("1734 POINT I/O module on its base (approximate)", "POINT I/O", "PLC",
                      W, H, [Circle((0.0, -H / 2 + 0.3 + 0.2 * i), 0.03) for i in range(8)],
                      "POINT I/O 1734 module on its terminal base, approximate"))
    return out


# ---- parts ---------------------------------------------------------------------------------
def _part(cat, description, symbol="", footprint="", notes="", id=None):
    return Part(id or "ab-" + cat.lower(), builtin=True, manufacturer=AB, catalog=cat,
                description=description, symbol=symbol, footprint=footprint,
                notes=(notes + ". " if notes else "") + CHECK)


def ab_parts():
    P = []
    # Bulletin 100-C contactors, 120V AC coil (coil code D), auxiliary 1 N.O. (10) or none (00)
    for cat, amps, fp in (("100-C09D10", 9, "Contactor 9-18 A"),
                          ("100-C12D10", 12, "Contactor 9-18 A"),
                          ("100-C16D10", 16, "Contactor 9-18 A"),
                          ("100-C23D10", 23, "Contactor 9-18 A"),
                          ("100-C30D00", 30, "Contactor 25-38 A"),
                          ("100-C37D00", 37, "Contactor 25-38 A"),
                          ("100-C43D00", 43, "Contactor 25-38 A")):
        aux = "1 N.O. auxiliary" if cat.endswith("10") else "no auxiliary"
        P.append(_part(cat, "Contactor, %d A (AC-3), 120V AC coil, %s" % (amps, aux),
                       "Contactor coil", fp, "Coil code D: 120V 60 Hz"))
    P.append(_part("100-FA11", "Auxiliary contact block for 100-C, 1 N.O. 1 N.C., front mount",
                   "Contact NO"))
    P.append(_part("100-FA20", "Auxiliary contact block for 100-C, 2 N.O., front mount",
                   "Contact NO"))
    # Bulletin 140M-C2E motor protection circuit breakers by current range
    for cat, lo, hi in (("140M-C2E-B25", 1.6, 2.5), ("140M-C2E-B40", 2.5, 4.0),
                        ("140M-C2E-B63", 4.0, 6.3), ("140M-C2E-C10", 6.3, 10.0),
                        ("140M-C2E-C16", 10.0, 16.0)):
        P.append(_part(cat, "Motor protection circuit breaker, %g-%g A" % (lo, hi),
                       "Motor protection circuit breaker 3-pole", "Motor protector (DIN)",
                       "Set its dial to the motor's full-load amps"))
    P.append(_part("140M-C-AFA11", "Auxiliary contact for 140M-C, 1 N.O. 1 N.C., front mount",
                   "Contact NO"))
    # E300 electronic overload relays: a sensing module chosen for the motor's current
    P.append(_part("", "E300 electronic overload relay (Bulletin 193), its sensing module "
                       "chosen for the motor's full-load amps",
                   "Overload relay, electronic 3-pole", "Overload relay 9-18 A",
                   "Built from a sensing, a control and a communication module: the catalog "
                   "number depends on all three", id="ab-e300"))
    # Bulletin 700-HA plug-in relays (8-pin, DPDT)
    P.append(_part("700-HA32A1", "Plug-in relay, 8-pin, DPDT, 120V AC coil", "Relay coil",
                   "Relay, ice cube 8-pin with base", "Its socket is ordered on its own"))
    P.append(_part("700-HA32Z24", "Plug-in relay, 8-pin, DPDT, 24V DC coil", "Relay coil",
                   "Relay, ice cube 8-pin with base", "Its socket is ordered on its own"))
    # 800F 22 mm pushbutton contact blocks
    P.append(_part("800F-X10", "Contact block, 1 N.O. (800F 22 mm operators)",
                   "Pushbutton contact NO"))
    P.append(_part("800F-X01", "Contact block, 1 N.C. (800F 22 mm operators)",
                   "Pushbutton contact NC"))
    # 1492-J IEC terminal blocks
    P.append(_part("1492-J3", "Feed-through terminal block, #22-12 AWG, 5 mm wide", "Terminal",
                   "Terminal block 2.5 mm2 (#12 AWG)"))
    P.append(_part("1492-J4", "Feed-through terminal block, #22-10 AWG, 6 mm wide", "Terminal",
                   "Terminal block 4 mm2 (#10 AWG)"))
    P.append(_part("1492-JG3", "Ground terminal block for 1492-J3, green/yellow", "Ground",
                   "Ground terminal 2.5 mm2 (#12 AWG)"))
    P.append(_part("1492-EBJ3", "End barrier for 1492-J3", "", "Terminal end plate"))
    P.append(_part("1492-EAJ35", "End anchor for 35 mm DIN rail", "", "End stop"))
    # 1606-XLP compact 24V DC power supplies
    for cat, watts, fp in (("1606-XLP30E", 30, "Power supply 24 VDC 2.5 A"),
                           ("1606-XLP50E", 50, "Power supply 24 VDC 2.5 A"),
                           ("1606-XLP100E", 100, "Power supply 24 VDC 5 A")):
        P.append(_part(cat, "Power supply, 24V DC, %d W" % watts, "Power supply AC/DC", fp,
                       "Footprint: the generic one nearest its size"))
    # PowerFlex 525 drives, 480V AC three-phase, no filter, IP20
    for cat, hp, amps, frame in (("25B-D1P4N104", "0.5", 1.4, "A"),
                                 ("25B-D2P3N104", "1", 2.3, "A"),
                                 ("25B-D4P0N104", "2", 4.0, "A"),
                                 ("25B-D6P0N104", "3", 6.0, "B"),
                                 ("25B-D010N104", "5", 10.5, "C"),
                                 ("25B-D013N104", "7.5", 13.0, "C"),
                                 ("25B-D017N104", "10", 17.0, "D"),
                                 ("25B-D024N104", "15", 24.0, "D")):
        P.append(_part(cat, "PowerFlex 525 drive, 480V AC, %s HP, %g A, frame %s" % (
            hp, amps, frame), "Variable frequency drive", "PowerFlex 525 frame %s" % frame,
            "Its control terminals: the Drive control terminals symbol"))
    # PLC I/O, controllers and chassis
    for cat, fam, desc, _word, _n in IO:
        fp = {"ControlLogix": "1756 I/O module (approximate)",
              "CompactLogix": "1769 I/O module (approximate)",
              "Compact 5000 I/O": "5069 I/O module (approximate)",
              "POINT I/O": "1734 POINT I/O module on its base (approximate)"}[fam]
        P.append(_part(cat, "%s, %s" % (fam, desc), "%s module" % cat, fp))
    for cat, desc, sym in (("1734-IB8", "POINT I/O, 24V DC sinking input module, 8 points",
                            "1734-IB8 module"),
                           ("1734-OB8E", "POINT I/O, 24V DC sourcing output module, "
                                         "electronically protected, 8 points",
                            "1734-OB8E module")):
        P.append(_part(cat, desc, sym, "1734 POINT I/O module on its base (approximate)"))
    P.append(_part("1756-L83E", "ControlLogix 5580 controller", "",
                   "1756 I/O module (approximate)", "It takes a slot of its chassis"))
    P.append(_part("1756-PA72", "ControlLogix power supply, 120/240V AC", "",
                   "1756 I/O module (approximate)", "Footprint: about its size, not its own"))
    for slots, _w in CHASSIS:
        P.append(_part("1756-A%d" % slots, "ControlLogix chassis, %d slots" % slots, "",
                       "1756 chassis, %d slots (approximate)" % slots))
    P.append(_part("1769-L33ER", "CompactLogix 5370 controller, EtherNet/IP", "",
                   "1769 CompactLogix controller (approximate)"))
    P.append(_part("1734-AENT", "POINT I/O EtherNet/IP adapter", "",
                   "1734 POINT I/O module on its base (approximate)",
                   "Footprint: about its width, not its own"))
    return P
