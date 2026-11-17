"""The program's own starter symbols, drawn in the JIC/NFPA (US) style, for horizontal rungs:
pins on the left and right at y = 0, 1/2 inch apart (on the 1/8 inch snap), the tag above.
Drawn here from code, so nothing is copied from any other program's library.

They show in the Library panel under "JIC"; a symbol of yours with the same name replaces
one of them.
"""

import math

from .model import BlockDef, Line, Circle, Arc, Polyline, Text

PIN = 0.25          # pins at x = -PIN and +PIN
# Tags at one height above the wire for every symbol of a kind, so the tags of symbols side by
# side on a rung or on the power lines line up (the owner, with a 3-pole disconnect and fuses
# whose tags didn't: each sat just above its own drawing, 0.64 to 0.72): clear of the tallest
TAG_Y = 0.34        # one-line symbols (pins at y = 0): the emergency stop's mushroom, 0.28
TAG = (0.0, TAG_Y)  # tag position (center of its baseline)
TAG3_Y = 0.75       # three-pole symbols (L1 at y = 1/2): the disconnect's blade, 0.625
# A rating (30A, 5HP, 500VA: the owner, "how do I put in my fuse ratings?") under the symbols
# that have one, at one height for each kind as the tags are; shown once it is typed in
# (the baseline of a 0.08" text; its top 0.08 higher)
RATING_Y = -0.22    # one-line symbols: under the fuse's body (-0.0625)
RATING3_Y = -0.72   # three-pole symbols: under L3's (-0.5) poles (the fuses', -0.5625)


def _rating(x=0.0, y=RATING_Y):
    return [{"attr": "RATING", "pos": (x, y), "height": 0.08}]


FUSE_TEXT = 0.07    # a rating in a fuse's box (1/8" tall): centered, its baseline this low
FUSE_BASE = -0.035


def _in_fuse(poles=(0.0,)):
    """The rating in each fuse's box (a three-pole fuse block: in all three)."""
    return [{"attr": "RATING", "pos": (0.0, y + FUSE_BASE), "height": FUSE_TEXT}
            for y in poles]


def _leads(gap, out):
    """Wire leads from each pin in to +-gap."""
    out.append(Line((-PIN, 0), (-gap, 0)))
    out.append(Line((gap, 0), (PIN, 0)))


def _pins(a="1", b="2"):
    return [{"name": a, "pos": (-PIN, 0)}, {"name": b, "pos": (PIN, 0)}]


def _sym(name, category, ents, role="device", contact="", prefix="", pins=None, tag=TAG,
         description="", wiring="", attr_texts=()):
    return BlockDef(name, "symbol", ents, pins if pins is not None else _pins(), tag, 0.1,
                    category, description, role, contact, prefix, builtin=True, wiring=wiring,
                    attr_texts=attr_texts)


# ---- three-pole power symbols ------------------------------------------------------------------
# Poles 1/2 inch apart (Bus's spacing to start), top to bottom L1/T1, L2/T2, L3/T3: a 3-wire bus
# drawn across lands on their pins.
POLE = 0.5
POLES = (POLE, 0.0, -POLE)


def _three(one):
    """A single pole's drawing (around y = 0) repeated on the three poles."""
    out = []
    for y in POLES:
        for e in one():
            out.append(e._map(lambda q, y=y: (q[0], q[1] + y)))
    return out


def _link(x, top=POLE, bottom=-POLE):
    """The dashed line joining poles that work together."""
    out = []
    y = top - 0.0625
    while y > bottom + 0.0625:
        out.append(Line((x, y), (x, max(y - 0.0625, bottom + 0.0625))))
        y -= 0.125
    return out


def _three_pins(left="L", right="T"):
    return ([{"name": "%s%d" % (left, i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)] +
            [{"name": "%s%d" % (right, i + 1), "pos": (PIN, y)} for i, y in enumerate(POLES)])


def _box(x0, y0, x1, y1):
    return Polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)


def _contact(nc=False):
    out = []
    _leads(0.0625, out)
    out.append(Line((-0.0625, -0.09375), (-0.0625, 0.09375)))
    out.append(Line((0.0625, -0.09375), (0.0625, 0.09375)))
    if nc:
        out.append(Line((-0.125, -0.125), (0.125, 0.125)))
    return out


def _timed(out, closing):
    """The timing arc under a contact (open/closing: its opening points the way it acts)."""
    if closing:
        out.append(Arc((0, -0.25), 0.1, 50, 130))
    else:
        out.append(Arc((0, -0.0625), 0.1, 230, 310))
    out.append(Line((0, -0.09375), (0, -0.15) if closing else (0, -0.1625)))


def _pb_terminals(out):
    out.append(Circle((-0.125, 0), 0.03125))
    out.append(Circle((0.125, 0), 0.03125))
    out.append(Line((-PIN, 0), (-0.15625, 0)))
    out.append(Line((0.15625, 0), (PIN, 0)))


def _coil(out, letter=None):
    _leads(0.125, out)
    out.append(Circle((0, 0), 0.125))
    if letter:
        out.append(Text((0, -0.035), letter, 0.07, align="center"))


HEATER_R = 0.06     # an overload heater's two hooks: their radius, and their centers'
HEATER_D = 0.065    # distance from the middle (the hooks just clear of each other)


def _heater():
    """A thermal overload heater on a wire (the owner, 0.16.2, with a photo of the ones they
    want): two hooks of three quarters of a turn. The first leaves the wire, goes up and over
    and ends below it; the second starts above the wire, goes round under and joins the
    wire out."""
    r, d = HEATER_R, HEATER_D
    return [Line((-PIN, 0), (-d - r, 0)), Line((d + r, 0), (PIN, 0)),
            Arc((-d, 0), r, 270, 180),       # (bottom, right, top, then the left: the wire in)
            Arc((d, 0), r, 90, 0)]           # (top, left, bottom, then the right: the wire out)


def _heater_link():
    """The dashed line joining three heaters, between the poles (not through the middle
    one's hooks)."""
    gap = HEATER_R + 0.03
    return _link(0.0, POLE - gap + 0.0625, gap - 0.0625) + \
        _link(0.0, -gap + 0.0625, -POLE + gap - 0.0625)


# a typical small AC drive's control terminals: (number, what it is)
DRIVE_TERMINALS = [
    ("S1", "Safety 1"), ("S2", "Safety 2"), ("S+", "Safety +24V"),
    ("01", "Stop"), ("02", "DigIn 02 / Start-Run FWD"), ("03", "DigIn 03 / Direction-Run REV"),
    ("04", "Digital Common"), ("05", "DigIn 05"), ("06", "DigIn 06"),
    ("07", "DigIn 07 / Pulse In"), ("08", "DigIn 08"),
    ("11", "+24V DC"), ("12", "+10V DC"), ("13", "0-10V (or +/-10V) Input"),
    ("14", "Analog Common"), ("15", "4-20mA Input"), ("16", "Analog Output"),
    ("17", "Opto Output 1"), ("18", "Opto Output 2"), ("19", "Opto Common"),
    ("R1", "Relay 1 N.O."), ("R2", "Relay 1 Common"), ("R5", "Relay 2 Common"),
    ("R6", "Relay 2 N.C."), ("C1", "RJ45 Shield"), ("C2", "Comm Common")]
ROW = 0.25          # a terminal block's rows


def _terminal_block(name, terminals, prefix, description, width=2.25):
    """A column of terminals: each a pin on the left (x = -PIN), a lead to its box with its
    number, and what it is beside it; all in one outline. A contact of a device with prefix
    (its tag, listed under it)."""
    o, pins = [], []
    n = len(terminals)
    top, bottom = ROW / 2, -(n - 0.5) * ROW
    o.append(_box(-0.125, bottom, width, top))
    o.append(Line((0.125, top), (0.125, bottom)))
    for i, (num, what) in enumerate(terminals):
        y = -i * ROW
        if i:
            o.append(Line((-0.125, y + ROW / 2), (0.125, y + ROW / 2)))
        o.append(Line((-PIN, y), (-0.125, y)))
        o.append(Text((0.0, y - 0.035), num, 0.07, align="center"))
        o.append(Text((0.2, y - 0.035), what, 0.07))
        pins.append({"name": num, "pos": (-PIN, y)})
    return _sym(name, "JIC/Power", o, "child", "", prefix, pins, tag=(width / 2, top + 0.1),
                description=description)


def builtin_symbols():
    S = []
    # ---- relays, contactors, timers ------------------------------------------------------
    o = []
    _coil(o)
    S.append(_sym("Relay coil", "JIC/Relays and timers", o, "parent", "", "CR",
                  _pins("A1", "A2"), description="Control relay coil"))
    o = []
    _coil(o)
    S.append(_sym("Contactor coil", "JIC/Motor control", o, "parent", "", "M",
                  _pins("A1", "A2"), description="Motor starter / contactor coil"))
    o = []
    _coil(o, "TR")
    S.append(_sym("Timer coil", "JIC/Relays and timers", o, "parent", "", "TR",
                  _pins("A1", "A2"), description="Timing relay coil"))
    S.append(_sym("Contact NO", "JIC/Contacts", _contact(False), "child", "NO", "CR",
                  description="Normally open contact"))
    S.append(_sym("Contact NC", "JIC/Contacts", _contact(True), "child", "NC", "CR",
                  description="Normally closed contact"))
    o = _contact(False)
    _timed(o, True)
    S.append(_sym("Contact NO timed close", "JIC/Relays and timers", o, "child", "NOTC", "TR",
                  description="Normally open, timed closed (on-delay)"))
    o = _contact(True)
    _timed(o, False)
    S.append(_sym("Contact NC timed open", "JIC/Relays and timers", o, "child", "NCTO", "TR",
                  description="Normally closed, timed open (on-delay)"))
    # ---- pushbuttons and switches --------------------------------------------------------
    o = []
    _pb_terminals(o)
    o += [Line((-0.15625, 0.09375), (0.15625, 0.09375)), Line((0, 0.09375), (0, 0.21875)),
          Line((-0.0625, 0.21875), (0.0625, 0.21875))]
    S.append(_sym("Pushbutton NO", "JIC/Pushbuttons and switches", o, "parent", "NO", "PB",
                  tag=TAG, description="Pushbutton, normally open"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.15625, -0.0625), (0.15625, -0.0625)), Line((0, -0.0625), (0, 0.21875)),
          Line((-0.0625, 0.21875), (0.0625, 0.21875))]
    S.append(_sym("Pushbutton NC", "JIC/Pushbuttons and switches", o, "parent", "NC", "PB",
                  tag=TAG, description="Pushbutton, normally closed"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.15625, -0.0625), (0.15625, -0.0625)), Line((0, -0.0625), (0, 0.1875)),
          Arc((0, 0.1875), 0.09375, 0, 180), Line((-0.09375, 0.1875), (0.09375, 0.1875))]
    S.append(_sym("Emergency stop NC", "JIC/Pushbuttons and switches", o, "parent", "NC", "PB",
                  tag=TAG, description="Mushroom-head emergency stop, normally closed"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.125, 0.03125), (0.09375, 0.15625)),
          Text((-0.17, 0.2), "OFF", 0.045, align="center"),
          Text((0.17, 0.2), "ON", 0.045, align="center")]
    S.append(_sym("Selector switch 2-position", "JIC/Pushbuttons and switches", o, "parent",
                  "NO", "SS", tag=TAG, description="Two-position selector switch"))

    def sensor(name, prefix, actuator, nc, desc):
        o = []
        _pb_terminals(o)
        if nc:
            o.append(Line((-0.125, -0.03125), (0.15625, -0.0625)))
        else:
            o.append(Line((-0.125, 0.03125), (0.15625, 0.0625)))
        o += actuator
        S.append(_sym(name, "JIC/Sensors", o, "parent", "NC" if nc else "NO", prefix,
                      tag=TAG, description=desc))

    sensor("Limit switch NO", "LS", [Line((0.0, 0.05), (0.0625, 0.15)),
                                     Polyline([(0.03, 0.15), (0.0625, 0.19), (0.095, 0.15)],
                                              True)], False, "Limit switch, normally open")
    sensor("Limit switch NC", "LS", [Line((0.0, -0.05), (0.0625, 0.15)),
                                     Polyline([(0.03, 0.15), (0.0625, 0.19), (0.095, 0.15)],
                                              True)], True, "Limit switch, normally closed")
    sensor("Pressure switch NO", "PS", [Line((0.0, 0.05), (0.0, 0.125)),
                                        Arc((0, 0.1875), 0.0625, 180, 360),
                                        Line((-0.0625, 0.1875), (0.0625, 0.1875))], False,
           "Pressure switch, normally open")
    sensor("Temperature switch NO", "TS", [Line((0.0, 0.05), (0.0, 0.125)),
                                           Polyline([(-0.0625, 0.125), (0.0625, 0.125),
                                                     (0.0, 0.22)], True)], False,
           "Temperature switch, normally open")
    sensor("Float switch NO", "FS", [Line((0.0, 0.05), (0.0, 0.15)),
                                     Circle((0.0, 0.2), 0.05)], False,
           "Float (level) switch, normally open")
    # ---- protection ---------------------------------------------------------------------
    # (a box: its rating shows in it, the owner, 0.16: "all schematic fuses to display fuse
    # rating on the fuse itself"; the line through the box would strike it out)
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)),
         Polyline([(-0.125, -0.0625), (0.125, -0.0625), (0.125, 0.0625), (-0.125, 0.0625)], True)]
    S.append(_sym("Fuse", "JIC/Protection", o, "device", "", "FU", tag=TAG,
                  description="Fuse", attr_texts=_in_fuse()))
    o = []
    _pb_terminals(o)
    o.append(Arc((0, -0.05), 0.16, 30, 150))
    S.append(_sym("Circuit breaker 1-pole", "JIC/Protection", o, "device", "", "CB",
                  tag=TAG, description="Circuit breaker, one pole", attr_texts=_rating()))
    o = []
    _pb_terminals(o)
    o += [Line((-0.125, 0.03125), (0.125, 0.125))]
    S.append(_sym("Disconnect 1-pole", "JIC/Protection", o, "device", "", "DS",
                  tag=TAG, description="Disconnect switch, one pole", attr_texts=_rating()))
    o = _heater()
    S.append(_sym("Overload heater", "JIC/Motor control", o, "parent", "", "OL",
                  tag=TAG, description="Thermal overload heater", attr_texts=_rating()))
    o = _contact(True)
    S.append(_sym("Overload contact NC", "JIC/Motor control", o, "child", "NC", "OL",
                  description="Overload relay contact, normally closed"))
    # ---- loads and indicators -------------------------------------------------------------
    o = []
    _leads(0.125, o)
    o.append(Circle((0, 0), 0.125))
    for a in (45, 135, 225, 315):
        r = math.radians(a)
        o.append(Line((0.16 * math.cos(r), 0.16 * math.sin(r)),
                      (0.22 * math.cos(r), 0.22 * math.sin(r))))
    S.append(_sym("Pilot light", "JIC/Indicators and loads", o, "device", "", "LT",
                  tag=TAG, description="Pilot light"))
    o = []
    _leads(0.1875, o)
    o += [Circle((0, 0), 0.1875), Text((0, -0.04), "MTR", 0.08, align="center")]
    S.append(_sym("Motor", "JIC/Indicators and loads", o, "device", "", "MTR", tag=TAG,
                  description="Motor", attr_texts=_rating(y=-0.33)))
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)),
         Polyline([(-0.125, -0.0625), (0.125, -0.0625), (0.125, 0.0625), (-0.125, 0.0625)], True),
         Line((-0.125, -0.0625), (0.125, 0.0625))]
    S.append(_sym("Solenoid", "JIC/Indicators and loads", o, "device", "", "SOL", tag=TAG,
                  description="Solenoid"))
    o = []
    for i in range(3):          # primary, then secondary below
        o.append(Arc((-0.125 + 0.125 * i, 0.0625), 0.0625, 0, 180))
        o.append(Arc((-0.125 + 0.125 * i, -0.0625), 0.0625, 180, 360))
    o += [Line((-0.25, 0.0625), (-0.1875, 0.0625)), Line((0.1875, 0.0625), (0.25, 0.0625)),
          Line((-0.25, -0.0625), (-0.1875, -0.0625)), Line((0.1875, -0.0625), (0.25, -0.0625)),
          Line((-0.1875, 0.0), (0.1875, 0.0))]
    S.append(_sym("Control transformer", "JIC/Power", o, "device", "", "T",
                  pins=[{"name": "H1", "pos": (-0.25, 0.0625)}, {"name": "H2", "pos": (0.25, 0.0625)},
                        {"name": "X1", "pos": (-0.25, -0.0625)}, {"name": "X2", "pos": (0.25, -0.0625)}],
                  tag=(0.0, 0.18), description="Control power transformer",
                  attr_texts=_rating(y=-0.24)))
    # ---- three-phase power ------------------------------------------------------------------
    def cb_pole():
        o = []
        _pb_terminals(o)
        o.append(Arc((0, -0.05), 0.16, 30, 150))
        return o

    def ds_pole():
        o = []
        _pb_terminals(o)
        o.append(Line((-0.125, 0.03125), (0.125, 0.125)))
        return o

    def fu_pole():
        return [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)),
                _box(-0.125, -0.0625, 0.125, 0.0625)]

    def heater_pole():
        return _heater()

    S.append(_sym("Circuit breaker 3-pole", "JIC/Power", _three(cb_pole) + _link(0, 0.6, -0.4),
                  "device", "", "CB", _three_pins(), tag=(0.0, TAG3_Y),
                  description="Circuit breaker, three poles", attr_texts=_rating(y=RATING3_Y)))
    S.append(_sym("Disconnect 3-pole", "JIC/Power", _three(ds_pole) + _link(0.0, 0.58, -0.42),
                  "device", "", "DS", _three_pins(), tag=(0.0, TAG3_Y),
                  description="Disconnect switch, three poles", attr_texts=_rating(y=RATING3_Y)))
    S.append(_sym("Fuses 3-pole", "JIC/Power", _three(fu_pole), "device", "", "FU",
                  _three_pins(), tag=(0.0, TAG3_Y), description="Fuses, three poles",
                  attr_texts=_in_fuse(POLES)))
    S.append(_sym("Contactor power contacts 3-pole", "JIC/Motor control",
                  _three(lambda: _contact(False)) + _link(0.0, 0.4, -0.4), "child", "NO", "M",
                  _three_pins(), tag=(0.0, TAG3_Y),
                  description="Main (power) contacts of a contactor, three poles"))
    S.append(_sym("Overload heaters 3-pole", "JIC/Motor control",
                  _three(heater_pole) + _heater_link(), "parent", "", "OL",
                  _three_pins(), tag=(0.0, TAG3_Y),
                  description="Thermal overload heaters, three poles",
                  attr_texts=_rating(y=RATING3_Y)))
    # two devices in one symbol, as they're bought and wired (the owner, 0.16.2: "Please add
    # 3ph disconnect with fuses and 3phase starter with overloads as symbols"): the second
    # half drawn 1/2" on, L1-L3 in on the left, T1-T3 out 1" away
    def shifted(one, dx=2 * PIN):
        return [e._map(lambda q: (q[0] + dx, q[1])) for e in _three(one)]

    o = _three(ds_pole) + _link(0.0, 0.58, -0.42) + shifted(fu_pole)
    S.append(_sym("Fused disconnect 3-pole", "JIC/Power", o, "device", "", "DS",
                  [{"name": "L%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)] +
                  [{"name": "T%d" % (i + 1), "pos": (3 * PIN, y)} for i, y in enumerate(POLES)],
                  tag=(PIN, TAG3_Y), description="Fused disconnect switch, three poles",
                  attr_texts=[dict(a, pos=(a["pos"][0] + 2 * PIN, a["pos"][1]))
                              for a in _in_fuse(POLES)]))
    # a contactor's power contacts and its overload heaters: a contact of the starter's coil
    # (Contactor coil, M), which lists it; the overload contact belongs to the coil too
    o = _three(lambda: _contact(False)) + _link(0.0, 0.4, -0.4) + shifted(heater_pole) + \
        [e._map(lambda q: (q[0] + 2 * PIN, q[1])) for e in _heater_link()]
    S.append(_sym("Starter 3-pole", "JIC/Motor control", o, "child", "NO", "M",
                  [{"name": "L%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)] +
                  [{"name": "T%d" % (i + 1), "pos": (3 * PIN, y)} for i, y in enumerate(POLES)],
                  tag=(PIN, TAG3_Y),
                  description="Motor starter: contactor power contacts and overload heaters, "
                              "three poles (a contact of its Contactor coil)",
                  attr_texts=_rating(2 * PIN, RATING3_Y)))
    # a drive's control terminals (the owner, 0.16: "Add the drive terminal symbol"): a
    # contact of its Variable frequency drive (its tag, listed under it), one terminal a row
    # 1/4" apart, wires landing on the left, each terminal's number in its box and what it
    # is beside it (Edit block changes the list)
    S.append(_terminal_block("Drive control terminals", DRIVE_TERMINALS, "VFD",
                             "Control terminals of a variable frequency drive (a contact of "
                             "its Variable frequency drive)"))
    r, cx = 0.55, 0.625                 # (the circle clear of the pins, every lead reaching it)
    o = [Circle((cx, 0), r), Text((cx, -0.06), "MTR", 0.15, align="center")]
    for y in POLES:
        x = cx - math.sqrt(r * r - y * y)
        o.append(Line((-PIN, y), (x, y)))
    S.append(_sym("Motor 3-phase", "JIC/Power", o, "device", "", "MTR",
                  [{"name": "T%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)],
                  tag=(cx, TAG3_Y), description="Three-phase motor",
                  attr_texts=_rating(cx, RATING3_Y)))
    o = [_box(-0.125, -0.75, 1.125, 0.75), Text((0.5, -0.06), "VFD", 0.15, align="center")]
    o += [Line((-PIN, y), (-0.125, y)) for y in POLES]
    o += [Line((1.125, y), (1.25, y)) for y in POLES]
    S.append(_sym("Variable frequency drive", "JIC/Power", o, "device", "", "VFD",
                  [{"name": "L%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)] +
                  [{"name": "T%d" % (i + 1), "pos": (1.25, y)} for i, y in enumerate(POLES)],
                  tag=(0.5, 0.85), description="Variable frequency drive (VFD): L1-L3 in, "
                                                "T1-T3 to the motor",
                  attr_texts=_rating(0.5, -0.90)))
    o = [_box(-0.125, -0.375, 0.875, 0.375), Text((0.375, 0.04), "AC", 0.08, align="center"),
         Line((0.2, -0.02), (0.55, -0.02)), Text((0.375, -0.16), "DC", 0.08, align="center"),
         Line((-PIN, 0.25), (-0.125, 0.25)), Line((-PIN, -0.25), (-0.125, -0.25)),
         Line((0.875, 0.25), (1.0, 0.25)), Line((0.875, -0.25), (1.0, -0.25)),
         Text((-0.06, 0.27), "L", 0.06, align="center"), Text((-0.06, -0.23), "N", 0.06,
                                                                   align="center"),
         Text((0.80, 0.27), "+", 0.06, align="center"), Text((0.80, -0.23), "-", 0.06,
                                                              align="center")]
    S.append(_sym("Power supply AC/DC", "JIC/Power", o, "device", "", "PS",
                  [{"name": "L", "pos": (-PIN, 0.25)}, {"name": "N", "pos": (-PIN, -0.25)},
                   {"name": "+", "pos": (1.0, 0.25)}, {"name": "-", "pos": (1.0, -0.25)}],
                  tag=(0.375, 0.47), description="Power supply, AC in, DC out (24 V say)",
                  attr_texts=_rating(0.375, -0.52)))
    # ---- PLC: a card, and its input and output points (linked to it as contacts to a coil) --
    o = [_box(-0.375, -0.25, 0.375, 0.25), Text((0, -0.04), "PLC I/O", 0.09, align="center")]
    S.append(_sym("PLC I/O card", "JIC/PLC", o, "parent", "", "PLC", pins=[],
                  tag=(0.0, 0.34), description="A PLC input or output card: its points list "
                                               "under it, as a coil's contacts"))
    addr = [{"attr": "ADDR", "pos": (0.25, -0.17), "height": 0.07}]
    o = [Line((-PIN, 0), (0.0, 0)), _box(0.0, -0.09375, 0.5, 0.09375),
         Text((0.25, -0.03), "IN", 0.07, align="center")]
    S.append(_sym("PLC input", "JIC/PLC", o, "child", "", "PLC",
                  [{"name": "IN", "pos": (-PIN, 0)}], tag=(0.25, 0.14),
                  description="PLC input point (its address: double-click, ADDR)",
                  attr_texts=addr))
    o = [_box(-0.5, -0.09375, 0.0, 0.09375), Line((0.0, 0), (PIN, 0)),
         Text((-0.25, -0.03), "OUT", 0.07, align="center")]
    S.append(_sym("PLC output", "JIC/PLC", o, "child", "", "PLC",
                  [{"name": "OUT", "pos": (PIN, 0)}], tag=(-0.25, 0.14),
                  description="PLC output point (its address: double-click, ADDR)",
                  attr_texts=[{"attr": "ADDR", "pos": (-0.25, -0.17), "height": 0.07}]))
    # ---- wiring ---------------------------------------------------------------------------
    # terminals belong to a terminal strip (TB601) and number themselves 1, 2, 3 on it
    o = [_box(-0.375, -0.125, 0.375, 0.125), Text((0, -0.03), "TERMINALS", 0.07,
                                                    align="center")]
    S.append(_sym("Terminal strip", "JIC/Wiring", o, "parent", "", "TB", pins=[],
                  tag=(0.0, 0.2), description="A terminal strip: its terminals list under it "
                                              "and take its tag"))
    S.append(_sym("Terminal", "JIC/Wiring", [Circle((0, 0), 0.03125)], "child", "", "TB",
                  pins=[{"name": "1", "pos": (-0.03125, 0)}, {"name": "2", "pos": (0.03125, 0)}],
                  tag=(0.0, 0.08), description="A terminal of a terminal strip (numbers itself)",
                  attr_texts=[{"attr": "TERM", "pos": (0.0, -0.13), "height": 0.07}]))
    o = [Line((0, 0), (0, -0.125)), Line((-0.125, -0.125), (0.125, -0.125)),
         Line((-0.08, -0.17), (0.08, -0.17)), Line((-0.035, -0.215), (0.035, -0.215))]
    S.append(_sym("Ground", "JIC/Wiring", o, "device", "", "", pins=[{"name": "1", "pos": (0, 0)}],
                  tag=None, description="Ground"))
    # a distribution block: one wire in on the left, four out on the right (their numbers take
    # the incoming wire's, with A, B, C, D added)
    outs = (0.375, 0.125, -0.125, -0.375)
    o = [Polyline([(-0.125, -0.5), (0.125, -0.5), (0.125, 0.5), (-0.125, 0.5)], True),
         Line((-0.25, 0), (-0.125, 0))]
    o += [Line((0.125, y), (0.25, y)) for y in outs]
    S.append(_sym("Distribution block 4-way", "JIC/Wiring", o, "device", "", "DB",
                  pins=[{"name": "IN", "pos": (-0.25, 0)}] +
                  [{"name": "OUT%d" % (i + 1), "pos": (0.25, y)} for i, y in enumerate(outs)],
                  tag=(0.0, 0.58), description="Distribution block, one in, four out",
                  wiring="distribution"))
    # an off-sheet connector: the wire goes on at the connector(s) of the same name elsewhere
    o = [Polyline([(0, 0.0625), (0.25, 0.0625), (0.3125, 0), (0.25, -0.0625), (0, -0.0625)],
                  True)]
    S.append(_sym("Off-sheet connector", "JIC/Wiring", o, "device", "", "",
                  pins=[{"name": "1", "pos": (0, 0)}], tag=(0.15625, 0.1),
                  description="Off-sheet connector: the wire continues at the connector of "
                              "the same name", wiring="link"))
    return S
