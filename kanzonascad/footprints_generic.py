"""The program's own panel footprints: generic devices at typical real sizes, so a new panel sheet
has something to place before you draw your own (the owner, Nov 2026: KanzonasCAD shipped 41
symbols and no footprint). Read-only in the library, as the built-in symbols are; a footprint of
yours with the same name takes the place of one of these; Edit block saves your own copy.

Sizes are typical of each kind (DIN-rail devices are 18 mm a pole, 90 mm tall; terminal blocks
5.2 mm for 2.5 mm2, 6.2 mm for 4 mm2...), in inches, not any maker's: for a part you buy, use
its maker's drawing (Make block, or Edit block on one of these). No Qt here.
"""

from .model import BlockDef, Circle, Line, Polyline

MM = 1.0 / 25.4


def _rect(x0, y0, x1, y1):
    return Polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)


def _fp(name, category, w, h, ents=(), description="", rail=True, pins=()):
    """A footprint w x h inches around its middle: its outline, what's drawn on it, its label
    spot above the middle (clear of the rail), the rail through its middle, and its terminal
    positions (pins, named as the matching symbol's: panel wiring labels them)."""
    hw, hh = w / 2.0, h / 2.0
    size = "%g x %g in (%g x %g mm)" % (round(w, 2), round(h, 2), round(w / MM), round(h / MM))
    d = BlockDef(name, "footprint", [_rect(-hw, -hh, hw, hh)] + list(ents),
                 tag_pos=(0.0, min(hh * 0.55, hh - 0.25)) if h > 1.0 else (0.0, 0.0),
                 category="Generic/" + category,
                 description=("%s, typical %s: check the maker's drawing" % (description, size))
                 if description else "Typical %s: check the maker's drawing" % size,
                 builtin=True, rail_pos=(0.0, 0.0) if rail else None, pins=pins)
    return d


def _screw_pins(w, h, top, bottom, inset=0.18):
    """Pins on the screws _screws draws: names top along the top, bottom along the bottom,
    left to right (a 3-pole device: L1 L2 L3 over T1 T2 T3, as its symbol's pins)."""
    out = []
    for names, y in ((top, h / 2.0 - inset), (bottom, -h / 2.0 + inset)):
        n = len(names)
        for i, name in enumerate(names):
            out.append({"name": name, "pos": (-w / 2.0 + w * (i + 0.5) / n, y)})
    return out


LT = (["L1", "L2", "L3"], ["T1", "T2", "T3"])


def _screws(w, h, n, inset=0.18, r=None):
    """n wire screws across the top and the bottom."""
    r = r or min(0.07, w / (n * 3.0))
    out = []
    for i in range(n):
        x = -w / 2.0 + w * (i + 0.5) / n
        out.append(Circle((x, h / 2.0 - inset), r))
        out.append(Circle((x, -h / 2.0 + inset), r))
    return out


def _dots(pins, r=0.06):
    """A screw drawn on each pin (pins at one place: one screw)."""
    seen = []
    for p in pins:
        if p["pos"] not in seen:
            seen.append(p["pos"])
    return [Circle(q, r) for q in seen]


def _relay_pins(w, h, poles, timed=False):
    """A relay's screws, a column a pole: its NC and NO screws along the top (NC the top
    row), its common under them at the bottom over the coil's A1 and A2 (A1 left, A2 right).
    Pole n's common is n1 and n3 (a timer's n5 and n7), its NC screw n2 (n6), its NO n4 (n8)."""
    nc, no = ("5", "6"), ("7", "8")
    if not timed:
        nc, no = ("1", "2"), ("3", "4")
    top, row = h / 2.0 - 0.12, 0.2
    out = []
    for i in range(poles):
        n = str(i + 1)
        x = -w / 2.0 + w * (i + 0.5) / poles
        out += [{"name": n + nc[1], "pos": (x, top)}, {"name": n + no[1], "pos": (x, top - row)},
                {"name": n + nc[0], "pos": (x, -top + row)},
                {"name": n + no[0], "pos": (x, -top + row)}]
    out += [{"name": "A1", "pos": (-w / 4.0, -top)}, {"name": "A2", "pos": (w / 4.0, -top)}]
    return out


def _poles(w, h, n):
    """A modular device of n poles: the poles' joins and screws."""
    out = _screws(w, h, n)
    for i in range(1, n):
        x = -w / 2.0 + w * i / n
        out.append(Line((x, -h / 2.0), (x, h / 2.0)))
    return out


def _toggle(w):
    return [_rect(-w * 0.18, -0.12, w * 0.18, 0.28), Line((-w * 0.18, 0.08), (w * 0.18, 0.08))]


def builtin_footprints():
    P = 18 * MM                         # (one DIN module, 18 mm)
    H = 90 * MM
    out = []
    # (a pole's pins as the symbols name them: a 1-pole breaker or fuse 1 over 2, three
    # poles L1-L3 over T1-T3; no symbol has two poles, so none on those)
    POLE_PINS = {1: (["1"], ["2"]), 2: ([], []), 3: LT}
    # ---- protection ----------------------------------------------------------------------------
    for n in (1, 2, 3):
        w = n * P
        out.append(_fp("Breaker %d-pole (DIN)" % n, "Protection", w, H,
                       _poles(w, H, n) + _toggle(w),
                       "Miniature circuit breaker, %d pole(s)" % n,
                       pins=_screw_pins(w, H, *POLE_PINS[n])))
    for n in (1, 3):
        w = n * P
        out.append(_fp("Fuse holder %d-pole (DIN)" % n, "Protection", w, 81 * MM,
                       _poles(w, 81 * MM, n) + [_rect(-w / 2 + 0.06, -0.45, w / 2 - 0.06, 0.45)],
                       "Fuse holder for 10 x 38 mm fuses, %d pole(s)" % n,
                       pins=_screw_pins(w, 81 * MM, *POLE_PINS[n])))
    out.append(_fp("Motor protector (DIN)", "Protection", 45 * MM, H,
                   _screws(45 * MM, H, 3) + [Circle((0.0, 0.1), 0.25)],
                   "Motor protection circuit breaker (manual motor starter), 3 pole",
                   pins=_screw_pins(45 * MM, H, *LT)))
    out.append(_fp("Surge protector 1-pole (DIN)", "Protection", P, H, _screws(P, H, 1),
                   "Surge protective device, 1 pole"))
    out.append(_fp("Disconnect, rotary 3-pole (DIN)", "Protection", 3 * P, 80 * MM,
                   _poles(3 * P, 80 * MM, 3) + [Circle((0.0, 0.0), 0.35),
                                                Line((-0.28, 0.0), (0.28, 0.0))],
                   "Rotary disconnect switch, 3 pole, about 32 A",
                   pins=_screw_pins(3 * P, 80 * MM, *LT)))
    # ---- control ---------------------------------------------------------------------------
    for name, w, h, what in (("Contactor 9-18 A", 45, 80, "Contactor, 3 pole, 9 to 18 A"),
                             ("Contactor 25-38 A", 54, 90, "Contactor, 3 pole, 25 to 38 A")):
        w, h = w * MM, h * MM
        # (its coil's A1 and A2 on the left side, under and over the power screws; its own
        # auxiliary contacts on the right, NO 13-14 and NC 21-22, as the makers mark them and
        # as its contacts are numbered on the schematic: pinnumbers.py, 0.28)
        x0, x1 = -w / 2.0 + 0.12, w / 2.0 - 0.12
        coil = [{"name": "A1", "pos": (x0, h / 2.0 - 0.5)},
                {"name": "A2", "pos": (x0, -h / 2.0 + 0.5)}]
        aux = [{"name": "13", "pos": (x1, h / 2.0 - 0.5)}, {"name": "14", "pos": (x1, -h / 2.0 + 0.5)},
               {"name": "21", "pos": (x1, h / 2.0 - 0.72)},
               {"name": "22", "pos": (x1, -h / 2.0 + 0.72)}]
        out.append(_fp(name, "Control", w, h,
                       _screws(w, h, 3) + [_rect(-w * 0.3, -0.25, w * 0.3, 0.25)] +
                       _dots(coil + aux), what,
                       pins=_screw_pins(w, h, *LT) + coil + aux))
    # (its contacts on the right, under the T1-T3 screws: NC 95-96, NO 97-98)
    w, h = 45 * MM, 66 * MM
    ol = [{"name": n, "pos": (w / 2.0 - 0.12, y)}
          for n, y in (("97", 0.75), ("95", 0.5), ("96", -0.5), ("98", -0.75))]
    out.append(_fp("Overload relay 9-18 A", "Control", w, h,
                   _screws(w, h, 3, inset=0.15) + [Circle((0.0, 0.0), 0.15)] + _dots(ol),
                   "Overload relay, mounted under its contactor or on the rail",
                   pins=_screw_pins(w, h, *LT, inset=0.15) + ol))
    # relays: a changeover contact a pole, each pole's common, NC and NO screws named as
    # its contacts are numbered on the schematic (pinnumbers.py): pole 1's common is both
    # 11 (of NC contact 11-12) and 13 (of NO contact 13-14), its NC screw 12, its NO screw
    # 14; pole 2's 21/23, 22, 24... (a timer's timed contacts: 15/17, 16, 18); A1 and A2 the
    # coil's
    for name, h, poles, what in (("Relay, ice cube 8-pin with base", 75, 2,
                                  "8-pin plug-in relay on its DIN-rail base, 2 changeover "
                                  "contacts"),
                                 ("Relay, ice cube 14-pin with base", 80, 4,
                                  "14-pin plug-in relay on its DIN-rail base, 4 changeover "
                                  "contacts")):
        w, h = 27 * MM, h * MM
        pins = _relay_pins(w, h, poles)
        out.append(_fp(name, "Control", w, h,
                       [_rect(-w * 0.4, -0.55, w * 0.4, 0.55)] + _dots(pins), what, pins=pins))
    # (one column: NC, NO and common along the top, the coil at the bottom)
    top = H / 2.0 - 0.12
    pins = [{"name": n, "pos": (0.0, y)} for n, y in (
        ("12", top), ("14", top - 0.2), ("11", top - 0.4), ("13", top - 0.4), ("A1", -top + 0.2),
        ("A2", -top))]
    out.append(_fp("Relay, slim interface 6 mm", "Control", 6.2 * MM, H, _dots(pins, 0.05),
                   "Slim interface relay, 6.2 mm, 1 changeover contact", pins=pins))
    pins = _relay_pins(22.5 * MM, H, 2, timed=True)
    out.append(_fp("Timer relay 22.5 mm", "Control", 22.5 * MM, H,
                   [Circle((0.0, 0.2), 0.12)] + _dots(pins),
                   "Timer or monitoring relay, 22.5 mm, 2 changeover contacts", pins=pins))
    # ---- power supplies --------------------------------------------------------------------
    for amps, w in ((2.5, 40), (5, 50), (10, 66)):
        w, h = w * MM, 125 * MM
        vents = [Line((-w / 2 + 0.12, y), (w / 2 - 0.12, y)) for y in (-0.6, -0.45, -0.3)]
        out.append(_fp("Power supply 24 VDC %g A" % amps, "Power supplies", w, h,
                       _screws(w, h, 3) + vents,
                       "24 VDC power supply, %g A (%d W)" % (amps, round(amps * 24))))
    # ---- terminals -------------------------------------------------------------------------
    for name, w, h, what in (("Terminal block 2.5 mm2 (#12 AWG)", 5.2, 47, "Feed-through terminal"),
                             ("Terminal block 4 mm2 (#10 AWG)", 6.2, 47, "Feed-through terminal"),
                             ("Terminal block 10 mm2 (#8 AWG)", 10.2, 54, "Feed-through terminal"),
                             ("Ground terminal 2.5 mm2 (#12 AWG)", 5.2, 47, "Ground terminal "
                                                                            "(green/yellow)"),
                             ("Fuse terminal 2.5 mm2 (#12 AWG)", 8.2, 65, "Fuse terminal for "
                                                                         "5 x 20 mm fuses")):
        w, h = w * MM, h * MM
        ents = _screws(w, h, 1, inset=0.12, r=w * 0.3) + [Line((0.0, -h / 2 + 0.3),
                                                               (0.0, h / 2 - 0.3))]
        if name.startswith("Ground"):
            ents += [Line((-w * 0.35, -0.05 - k * 0.05), (w * 0.35, -0.05 - k * 0.05))
                     for k in range(3)]
        # (pin 1 on the top screw, 2 on the bottom one: a Terminal symbol's left and right)
        out.append(_fp(name, "Terminals", w, h, ents, what,
                       pins=_screw_pins(w, h, ["1"], ["2"], inset=0.12)))
    out.append(_fp("Terminal end plate", "Terminals", 2 * MM, 47 * MM, (),
                   "End plate, closing the open side of the last terminal"))
    out.append(_fp("End stop", "Terminals", 9 * MM, 35 * MM,
                   [Line((-4.5 * MM, 0.0), (4.5 * MM, 0.0))],
                   "End bracket holding terminals and devices on the rail"))
    # ---- PLC -------------------------------------------------------------------------------
    out.append(_fp("PLC CPU (generic)", "PLC", 100 * MM, 100 * MM,
                   [_rect(-1.6, 0.5, 1.6, 1.6)] + [Circle((-1.6 + 0.3 * i, -1.6), 0.06)
                                                   for i in range(11)],
                   "PLC processor"))
    out.append(_fp("PLC I/O module 16-point", "PLC", 25 * MM, 100 * MM,
                   [Circle((0.0, -1.6 + 0.2 * i), 0.05) for i in range(8)],
                   "PLC input or output module, 16 points"))
    # ---- transformers (on the back panel, not the rail) ------------------------------------
    for va, w, h in ((100, 3.0, 2.75), (250, 3.75, 3.4), (500, 4.5, 4.0)):
        out.append(_fp("Control transformer %d VA" % va, "Transformers", w, h,
                       [_rect(-w / 2 + 0.3, -h / 2 + 0.3, w / 2 - 0.3, h / 2 - 0.3)]
                       + _screws(w, h, 4, inset=0.15),
                       "Control transformer, %d VA, mounting feet" % va, rail=False))
    # ---- door devices (22 mm operators; the bezel's size) ----------------------------------
    for name, d, what in (("Pushbutton 22 mm", 30, "Pushbutton, 22 mm hole"),
                          ("Pilot light 22 mm", 30, "Pilot light, 22 mm hole"),
                          ("Selector switch 22 mm", 30, "Selector switch, 22 mm hole"),
                          ("Emergency stop 40 mm", 40, "Emergency stop mushroom, 22 mm hole")):
        r = d * MM / 2.0
        ents = [Circle((0.0, 0.0), r), Circle((0.0, 0.0), 11 * MM)]
        if name.startswith("Selector"):
            ents.append(Line((-r * 0.7, 0.0), (r * 0.7, 0.0)))
        b = _fp(name, "Door devices", 2 * r, 2 * r, (), what, rail=False)
        b.entities = ents                   # (round: no square outline)
        b.tag_pos = (0.0, -r - 0.15)        # (the label under it, as a legend plate)
        out.append(b)
    return out
