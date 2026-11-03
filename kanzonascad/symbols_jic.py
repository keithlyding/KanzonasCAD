"""The program's own starter symbols, drawn in the JIC/NFPA (US) style, for horizontal rungs:
pins on the left and right at y = 0, 1/2 inch apart (on the 1/8 inch snap), the tag above.
Drawn here from code, so nothing is copied from any other program's library.

They show in the Library panel under "JIC"; a symbol of yours with the same name replaces
one of them.
"""

import math

from .model import BlockDef, Line, Circle, Arc, Polyline, Text

PIN = 0.25          # pins at x = -PIN and +PIN
TAG = (0.0, 0.22)   # tag position (center of its baseline)


def _leads(gap, out):
    """Wire leads from each pin in to +-gap."""
    out.append(Line((-PIN, 0), (-gap, 0)))
    out.append(Line((gap, 0), (PIN, 0)))


def _pins(a="1", b="2"):
    return [{"name": a, "pos": (-PIN, 0)}, {"name": b, "pos": (PIN, 0)}]


def _sym(name, category, ents, role="device", contact="", prefix="", pins=None, tag=TAG,
         description=""):
    return BlockDef(name, "symbol", ents, pins if pins is not None else _pins(), tag, 0.1,
                    category, description, role, contact, prefix, builtin=True)


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
                  tag=(0.0, 0.3), description="Pushbutton, normally open"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.15625, -0.0625), (0.15625, -0.0625)), Line((0, -0.0625), (0, 0.21875)),
          Line((-0.0625, 0.21875), (0.0625, 0.21875))]
    S.append(_sym("Pushbutton NC", "JIC/Pushbuttons and switches", o, "parent", "NC", "PB",
                  tag=(0.0, 0.3), description="Pushbutton, normally closed"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.15625, -0.0625), (0.15625, -0.0625)), Line((0, -0.0625), (0, 0.1875)),
          Arc((0, 0.1875), 0.09375, 0, 180), Line((-0.09375, 0.1875), (0.09375, 0.1875))]
    S.append(_sym("Emergency stop NC", "JIC/Pushbuttons and switches", o, "parent", "NC", "PB",
                  tag=(0.0, 0.34), description="Mushroom-head emergency stop, normally closed"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.125, 0.03125), (0.09375, 0.15625)),
          Text((-0.17, 0.2), "OFF", 0.045, align="center"),
          Text((0.17, 0.2), "ON", 0.045, align="center")]
    S.append(_sym("Selector switch 2-position", "JIC/Pushbuttons and switches", o, "parent",
                  "NO", "SS", tag=(0.0, 0.3), description="Two-position selector switch"))

    def sensor(name, prefix, actuator, nc, desc):
        o = []
        _pb_terminals(o)
        if nc:
            o.append(Line((-0.125, -0.03125), (0.15625, -0.0625)))
        else:
            o.append(Line((-0.125, 0.03125), (0.15625, 0.0625)))
        o += actuator
        S.append(_sym(name, "JIC/Sensors", o, "parent", "NC" if nc else "NO", prefix,
                      tag=(0.0, 0.3), description=desc))

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
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)),
         Polyline([(-0.125, -0.0625), (0.125, -0.0625), (0.125, 0.0625), (-0.125, 0.0625)], True),
         Line((-0.125, 0), (0.125, 0))]
    S.append(_sym("Fuse", "JIC/Protection", o, "device", "", "FU", tag=(0.0, 0.14),
                  description="Fuse"))
    o = []
    _pb_terminals(o)
    o.append(Arc((0, -0.05), 0.16, 30, 150))
    S.append(_sym("Circuit breaker 1-pole", "JIC/Protection", o, "device", "", "CB",
                  tag=(0.0, 0.2), description="Circuit breaker, one pole"))
    o = []
    _pb_terminals(o)
    o += [Line((-0.125, 0.03125), (0.125, 0.125))]
    S.append(_sym("Disconnect 1-pole", "JIC/Protection", o, "device", "", "DS",
                  tag=(0.0, 0.22), description="Disconnect switch, one pole"))
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0))]
    k = 0.0625
    o.append(Arc((-0.125 + k, 0), k, 0, 180))
    o.append(Arc((0.125 - k, 0), k, 180, 360))
    S.append(_sym("Overload heater", "JIC/Motor control", o, "parent", "", "OL",
                  tag=(0.0, 0.16), description="Thermal overload heater"))
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
                  tag=(0.0, 0.27), description="Pilot light"))
    o = []
    _leads(0.1875, o)
    o += [Circle((0, 0), 0.1875), Text((0, -0.04), "MTR", 0.08, align="center")]
    S.append(_sym("Motor", "JIC/Indicators and loads", o, "device", "", "MTR", tag=(0.0, 0.26),
                  description="Motor"))
    o = [Line((-PIN, 0), (-0.125, 0)), Line((0.125, 0), (PIN, 0)),
         Polyline([(-0.125, -0.0625), (0.125, -0.0625), (0.125, 0.0625), (-0.125, 0.0625)], True),
         Line((-0.125, -0.0625), (0.125, 0.0625))]
    S.append(_sym("Solenoid", "JIC/Indicators and loads", o, "device", "", "SOL", tag=(0.0, 0.14),
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
                  tag=(0.0, 0.18), description="Control power transformer"))
    # ---- wiring ---------------------------------------------------------------------------
    S.append(_sym("Terminal", "JIC/Wiring", [Circle((0, 0), 0.03125)], "device", "", "TB",
                  pins=[{"name": "1", "pos": (-0.03125, 0)}, {"name": "2", "pos": (0.03125, 0)}],
                  tag=(0.0, 0.08), description="Terminal"))
    o = [Line((0, 0), (0, -0.125)), Line((-0.125, -0.125), (0.125, -0.125)),
         Line((-0.08, -0.17), (0.08, -0.17)), Line((-0.035, -0.215), (0.035, -0.215))]
    S.append(_sym("Ground", "JIC/Wiring", o, "device", "", "", pins=[{"name": "1", "pos": (0, 0)}],
                  tag=None, description="Ground"))
    return S
