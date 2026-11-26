"""Allen-Bradley devices (the owner, Nov 2026: "lean heavy on the Allen Bradley stuff"): the
symbols, footprints and parts for the Rockwell Automation families a US panel is commonly built
from. No Qt here.

- Symbols drawn here in the JIC/NFPA style, from the standard conventions (symbols_jic.py's
  pieces), never from Rockwell's or anyone's drawings: a motor protection circuit breaker
  (Bulletin 140M), an electronic overload relay (Bulletin 193 / E300) and its contacts, a
  three-position selector switch, a pilot light showing its color, and PLC I/O modules drawn
  whole (ControlLogix 1756, CompactLogix 1769, Compact 5000 5069, POINT I/O 1734). A module's
  terminals are named by point (0, 1, 2...): its terminal block's own numbers and commons are
  on Rockwell's wiring diagram for it (Edit block renames its terminals).
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
                          _io_terminals)

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


def ab_io_modules():
    """The Allen-Bradley PLC I/O modules drawn whole (symbols_jic.io_module), their terminals
    named by point."""
    return [io_module("%s module" % cat, _io_terminals(word, n),
                      "%s (%s); terminals named by point: its terminal numbers and commons "
                      "are on Rockwell's wiring diagram (Edit block renames them)" % (desc, fam),
                      cat, AB, fam, right=word == "OUT")
            for cat, fam, desc, word, n in IO]


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
