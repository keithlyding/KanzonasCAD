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


def _fp(name, category, w, h, ents=(), description="", rail=True):
    """A footprint w x h inches around its middle: its outline, what's drawn on it, its label
    spot above the middle (clear of the rail), and the rail through its middle."""
    hw, hh = w / 2.0, h / 2.0
    size = "%g x %g in (%g x %g mm)" % (round(w, 2), round(h, 2), round(w / MM), round(h / MM))
    d = BlockDef(name, "footprint", [_rect(-hw, -hh, hw, hh)] + list(ents),
                 tag_pos=(0.0, min(hh * 0.55, hh - 0.25)) if h > 1.0 else (0.0, 0.0),
                 category="Generic/" + category,
                 description=("%s, typical %s: check the maker's drawing" % (description, size))
                 if description else "Typical %s: check the maker's drawing" % size,
                 builtin=True, rail_pos=(0.0, 0.0) if rail else None)
    return d


def _screws(w, h, n, inset=0.18, r=None):
    """n wire screws across the top and the bottom."""
    r = r or min(0.07, w / (n * 3.0))
    out = []
    for i in range(n):
        x = -w / 2.0 + w * (i + 0.5) / n
        out.append(Circle((x, h / 2.0 - inset), r))
        out.append(Circle((x, -h / 2.0 + inset), r))
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
    # ---- protection ----------------------------------------------------------------------------
    for n in (1, 2, 3):
        w = n * P
        out.append(_fp("Breaker %d-pole (DIN)" % n, "Protection", w, H,
                       _poles(w, H, n) + _toggle(w),
                       "Miniature circuit breaker, %d pole(s)" % n))
    for n in (1, 3):
        w = n * P
        out.append(_fp("Fuse holder %d-pole (DIN)" % n, "Protection", w, 81 * MM,
                       _poles(w, 81 * MM, n) + [_rect(-w / 2 + 0.06, -0.45, w / 2 - 0.06, 0.45)],
                       "Fuse holder for 10 x 38 mm fuses, %d pole(s)" % n))
    out.append(_fp("Motor protector (DIN)", "Protection", 45 * MM, H,
                   _screws(45 * MM, H, 3) + [Circle((0.0, 0.1), 0.25)],
                   "Motor protection circuit breaker (manual motor starter), 3 pole"))
    out.append(_fp("Surge protector 1-pole (DIN)", "Protection", P, H, _screws(P, H, 1),
                   "Surge protective device, 1 pole"))
    out.append(_fp("Disconnect, rotary 3-pole (DIN)", "Protection", 3 * P, 80 * MM,
                   _poles(3 * P, 80 * MM, 3) + [Circle((0.0, 0.0), 0.35),
                                                Line((-0.28, 0.0), (0.28, 0.0))],
                   "Rotary disconnect switch, 3 pole, about 32 A"))
    # ---- control ---------------------------------------------------------------------------
    for name, w, h, what in (("Contactor 9-18 A", 45, 80, "Contactor, 3 pole, 9 to 18 A"),
                             ("Contactor 25-38 A", 54, 90, "Contactor, 3 pole, 25 to 38 A")):
        w, h = w * MM, h * MM
        out.append(_fp(name, "Control", w, h,
                       _screws(w, h, 3) + [_rect(-w * 0.3, -0.25, w * 0.3, 0.25)], what))
    out.append(_fp("Overload relay 9-18 A", "Control", 45 * MM, 66 * MM,
                   _screws(45 * MM, 66 * MM, 3, inset=0.15) + [Circle((0.0, 0.0), 0.15)],
                   "Overload relay, mounted under its contactor or on the rail"))
    for name, h, what in (("Relay, ice cube 8-pin with base", 75, "8-pin plug-in relay on its "
                                                                  "DIN-rail base"),
                          ("Relay, ice cube 14-pin with base", 80, "14-pin plug-in relay on its "
                                                                   "DIN-rail base")):
        w, h = 27 * MM, h * MM
        out.append(_fp(name, "Control", w, h,
                       _screws(w, h, 2, inset=0.12) + [_rect(-w * 0.4, -0.55, w * 0.4, 0.55)],
                       what))
    out.append(_fp("Relay, slim interface 6 mm", "Control", 6.2 * MM, H,
                   _screws(6.2 * MM, H, 1, inset=0.15), "Slim interface relay, 6.2 mm"))
    out.append(_fp("Timer relay 22.5 mm", "Control", 22.5 * MM, H,
                   _screws(22.5 * MM, H, 2) + [Circle((0.0, 0.2), 0.12)],
                   "Timer or monitoring relay, 22.5 mm"))
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
        out.append(_fp(name, "Terminals", w, h, ents, what))
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
