"""The program's own IEC 60617 symbols: the core devices drawn after the conventions of IEC
60617 (a coil a rectangle, a contact a blade, a breaker a blade with an X on its fixed contact,
a lamp a circle with an X, a motor an M in a circle...), for a project whose Symbol standard is
IEC 60617 (Project properties, Schematic). Drawn here from code, so nothing is copied from any
other program's library.

They are laid out as the JIC symbols are (symbols_jic.py): for horizontal rungs, pins on the
left and right at y = 0, 1/2 inch apart, the tag above; three-pole ones with their poles 1/2
inch apart, L1/T1 on top. They keep the JIC symbols' prefixes (CR, M, PB, CB, FU, OL...),
which say what kind of device each is to the program; in a project of IEC symbols the tags
are made of the prefixes' IEC 81346-2 letters instead (K, Q, S, F, P, X...: tags.prefix_for),
the JIC and other symbols' too.

In a project of IEC symbols, Insert symbol offers these instead of the JIC symbols they stand
for (IEC_FOR), and the JIC ones in a project of JIC symbols; the program's other symbols (PLC
modules, drives, connectors, arrows...) are offered in both.
"""

from .model import Arc, Circle, Line, Polyline, Text
from .symbols_jic import (PIN, POLE, POLES, RATING3_Y, TAG, TAG3_Y, _box, _link, _pins,
                          _rating, _sym, _three, _three_pins, show_contact_pins)

CAT = "IEC/"
SUFFIX = " (IEC)"

STANDARDS = {"jic": "JIC/NFPA (US)", "iec": "IEC 60617"}

# {IEC symbol: the JIC symbol it stands for}: Insert symbol offers one or the other
IEC_FOR = {}

GAP = 0.09          # a contact's leads end this far either side of its middle
BLADE = (0.11, 0.085)   # where a make contact's blade ends (from the left lead's end)


def standard_of(project):
    """A project's symbol standard: "jic" (JIC/NFPA, US: every project from before 0.29, and
    new ones to start) or "iec" (IEC 60617)."""
    got = project.settings.get("symbol_standard", "jic")
    return got if got in STANDARDS else "jic"


def hidden_builtins(standard):
    """The names of the program's own symbols Insert symbol leaves out for a standard: the
    IEC ones in a JIC project, the JIC ones they stand for in an IEC project."""
    if not IEC_FOR:
        iec_symbols()
    if standard == "iec":
        return set(IEC_FOR.values())
    return set(IEC_FOR)


def _leads(gap, out, y=0.0):
    out.append(Line((-PIN, y), (-gap, y)))
    out.append(Line((gap, y), (PIN, y)))


def _make(out):
    """A make (normally open) contact: the blade from the left lead's end, open."""
    _leads(GAP, out)
    out.append(Line((-GAP, 0.0), BLADE))


def _break(out):
    """A break (normally closed) contact: the blade resting past the right contact's tab."""
    _leads(GAP, out)
    out.append(Line((GAP, 0.0), (GAP, -0.075)))
    out.append(Line((-GAP, 0.0), (0.12, -0.075)))


def _dashes(x, y0, y1, out, dash=0.03, gap=0.025):
    """A dashed line from (x, y0) up to (x, y1): a mechanical link (an actuator)."""
    y = y0
    while y < y1 - 1e-9:
        out.append(Line((x, y), (x, min(y + dash, y1))))
        y += dash + gap


def _actuator(out, nc=False):
    """The dashed actuator from the blade's middle up to an operator at y = 0.2."""
    x = 0.01 if not nc else 0.015
    _dashes(x, 0.045 if not nc else -0.035, 0.2, out)
    return x


def _push(out, x):
    """A push operator (pushbutton, spring return): a bracket open toward the contact."""
    out += [Line((x - 0.05, 0.2), (x + 0.05, 0.2)), Line((x - 0.05, 0.2), (x - 0.05, 0.17)),
            Line((x + 0.05, 0.2), (x + 0.05, 0.17))]


def _turn(out, x):
    """A turn operator (selector switch): a Z-shaped handle."""
    out += [Line((x - 0.05, 0.17), (x - 0.05, 0.2)), Line((x - 0.05, 0.2), (x + 0.05, 0.2)),
            Line((x + 0.05, 0.2), (x + 0.05, 0.23))]


def _mushroom(out, x):
    """An emergency stop's mushroom head."""
    out += [Line((x - 0.08, 0.2), (x + 0.08, 0.2)), Arc((x, 0.2), 0.08, 0, 180)]


def _coil(out, mark=None):
    """A coil: a rectangle across the rung (its leads entering its long sides)."""
    _leads(0.0625, out)
    out.append(_box(-0.0625, -0.125, 0.0625, 0.125))
    if mark == "delay":
        # (slow operating: a box beside the coil with a cross in it, as IEC 60617 marks an
        # on-delay timer's coil)
        out += [_box(0.0625, -0.125, 0.125, 0.125), Line((0.0625, -0.125), (0.125, 0.125)),
                Line((0.0625, 0.125), (0.125, -0.125))]


def _breaker_pole():
    """A circuit breaker pole: a make contact with an X on its fixed contact."""
    o = []
    _make(o)
    d = 0.025
    o += [Line((GAP - d, -d), (GAP + d, d)), Line((GAP - d, d), (GAP + d, -d))]
    return o


def _disconnector_pole():
    """A disconnector (isolator) pole: a make contact with a bar across its fixed contact."""
    o = []
    _make(o)
    o.append(Line((GAP, -0.035), (GAP, 0.035)))
    return o


def _fuse_pole():
    """A fuse: a rectangle along the wire, the wire drawn through it."""
    return [Line((-PIN, 0.0), (PIN, 0.0)), _box(-0.125, -0.05, 0.125, 0.05)]


def _thermal_pole():
    """A thermal overload element: a rectangle on the wire with the thermal effect's step
    (the wire goes in, steps up, across and down, and out) in it."""
    return [Line((-PIN, 0.0), (-0.06, 0.0)), Line((0.06, 0.0), (PIN, 0.0)),
            Polyline([(-0.06, 0.0), (-0.06, 0.04), (0.06, 0.04), (0.06, 0.0)]),
            _box(-0.125, -0.06, 0.125, 0.08)]


def _contact_pole():
    o = []
    _make(o)
    return o


def _iec(jic, name, category, ents, role="device", contact="", prefix="", pins=None, tag=TAG,
         description="", attr_texts=()):
    full = name + SUFFIX
    if jic:
        IEC_FOR[full] = jic
    return _sym(full, CAT + category, ents, role, contact, prefix, pins, tag,
                description=description + " (IEC 60617)", attr_texts=attr_texts)


def iec_symbols():
    IEC_FOR.clear()
    S = []
    # ---- relays and contactors --------------------------------------------------------------
    o = []
    _coil(o)
    S.append(_iec("Relay coil", "Relay coil", "Relays and timers", o, "parent", "", "CR",
                  _pins("A1", "A2"), description="Control relay coil"))
    o = []
    _coil(o)
    S.append(_iec("Contactor coil", "Contactor coil", "Motor control", o, "parent", "", "M",
                  _pins("A1", "A2"), description="Contactor coil"))
    o = []
    _coil(o, "delay")
    S.append(_iec("Timer coil", "Timer coil", "Relays and timers", o, "parent", "", "TR",
                  _pins("A1", "A2"), description="Timing relay coil, delay on operation"))
    o = []
    _make(o)
    S.append(_iec("Contact NO", "Contact NO", "Contacts", o, "child", "NO", "CR",
                  description="Make contact (normally open)"))
    o = []
    _break(o)
    S.append(_iec("Contact NC", "Contact NC", "Contacts", o, "child", "NC", "CR",
                  description="Break contact (normally closed)"))
    # timed: the blade's drag (a half circle on a double line) on the side it acts slowly
    o = []
    _make(o)
    o += [Line((0.0, 0.035), (0.0, 0.15)), Line((0.02, 0.05), (0.02, 0.15)),
          Arc((0.01, 0.19), 0.05, 180, 360)]
    S.append(_iec("Contact NO timed close", "Contact NO timed close", "Relays and timers", o,
                  "child", "NOTC", "TR", description="Make contact, delayed on closing "
                                                     "(on-delay)"))
    o = []
    _break(o)
    o += [Line((0.0, -0.04), (0.0, -0.15)), Line((0.02, -0.05), (0.02, -0.15)),
          Arc((0.01, -0.19), 0.05, 0, 180)]
    S.append(_iec("Contact NC timed open", "Contact NC timed open", "Relays and timers", o,
                  "child", "NCTO", "TR", description="Break contact, delayed on opening "
                                                     "(on-delay)"))
    # ---- pushbuttons and switches -----------------------------------------------------------
    o = []
    _make(o)
    _push(o, _actuator(o))
    S.append(_iec("Pushbutton NO", "Pushbutton NO", "Pushbuttons and switches", o, "parent",
                  "NO", "PB", description="Pushbutton, make contact, spring return"))
    o = []
    _break(o)
    _push(o, _actuator(o, nc=True))
    S.append(_iec("Pushbutton NC", "Pushbutton NC", "Pushbuttons and switches", o, "parent",
                  "NC", "PB", description="Pushbutton, break contact, spring return"))
    o = []
    _break(o)
    _mushroom(o, _actuator(o, nc=True))
    S.append(_iec("Emergency stop NC", "Emergency stop NC", "Pushbuttons and switches", o,
                  "parent", "NC", "PB", tag=(0.0, 0.36),
                  description="Emergency stop, mushroom head, break contact"))
    o = []
    _make(o)
    _turn(o, _actuator(o))
    S.append(_iec("Selector switch 2-position", "Selector switch 2-position",
                  "Pushbuttons and switches", o, "parent", "NO", "SS",
                  description="Selector switch, turned, make contact, stays put"))
    o = []
    _make(o)
    S.append(_iec("Pushbutton contact NO", "Pushbutton contact NO", "Pushbuttons and switches",
                  o, "child", "NO", "PB",
                  description="A pushbutton's (or emergency stop's) contact block, make"))
    o = []
    _break(o)
    S.append(_iec("Pushbutton contact NC", "Pushbutton contact NC", "Pushbuttons and switches",
                  o, "child", "NC", "PB",
                  description="A pushbutton's (or emergency stop's) contact block, break"))
    # ---- protection --------------------------------------------------------------------------
    S.append(_iec("Fuse", "Fuse", "Protection", _fuse_pole(), "device", "", "FU",
                  description="Fuse", attr_texts=_rating(fields=("VOLTS",))))
    S.append(_iec("Circuit breaker 1-pole", "Circuit breaker 1-pole", "Protection",
                  _breaker_pole(), "device", "", "CB", description="Circuit breaker, one pole",
                  attr_texts=_rating(fields=("AMPS", "VOLTS"))))
    S.append(_iec("Disconnect 1-pole", "Disconnector 1-pole", "Protection",
                  _disconnector_pole(), "device", "", "DS",
                  description="Disconnector (isolator), one pole",
                  attr_texts=_rating(fields=("AMPS", "VOLTS"))))
    S.append(_iec("Overload heater", "Thermal overload", "Motor control", _thermal_pole(),
                  "parent", "", "OL", description="Thermal overload relay element",
                  attr_texts=_rating(fields=("AMPS",))))
    o = []
    _break(o)
    x = _actuator(o, nc=True)
    o += [Polyline([(x - 0.04, 0.17), (x - 0.04, 0.2), (x + 0.04, 0.2), (x + 0.04, 0.23)])]
    S.append(_iec("Overload contact NC", "Overload contact NC", "Motor control", o, "child",
                  "NC", "OL", description="Thermal overload relay's break contact"))
    # ---- loads and indicators ----------------------------------------------------------------
    r = 0.1
    o = []
    _leads(r, o)
    d = r * 0.7071
    o += [Circle((0.0, 0.0), r), Line((-d, -d), (d, d)), Line((-d, d), (d, -d))]
    S.append(_iec("Pilot light", "Indicator lamp", "Indicators and loads", o, "device", "",
                  "LT", description="Indicator lamp (signal lamp)"))
    o = []
    _leads(0.1875, o)
    o += [Circle((0.0, 0.0), 0.1875), Text((0.0, -0.01), "M", 0.1, align="center"),
          Text((0.0, -0.11), "1~", 0.06, align="center")]
    S.append(_iec("Motor", "Motor", "Indicators and loads", o, "device", "", "MTR",
                  description="Motor, single-phase",
                  attr_texts=_rating(y=-0.33, fields=("HP", "VOLTS", "FLA"))))
    o = []
    _leads(0.125, o)
    o += [_box(-0.125, -0.0625, 0.125, 0.0625), Line((-0.125, -0.0625), (0.0, 0.0625)),
          Line((0.0, 0.0625), (0.0, -0.0625))]
    S.append(_iec("Solenoid", "Solenoid valve coil", "Indicators and loads", o, "device", "",
                  "SOL", description="Solenoid (an electromechanical actuator's coil)"))
    # a control transformer: two circles crossing, the primary above (H1, H2), the secondary
    # below (X1, X2)
    rc, cy, py = 0.11, 0.08, 0.125
    dx = (rc * rc - (py - cy) ** 2) ** 0.5
    o = [Circle((0.0, cy), rc), Circle((0.0, -cy), rc),
         Line((-PIN, py), (-dx, py)), Line((dx, py), (PIN, py)),
         Line((-PIN, -py), (-dx, -py)), Line((dx, -py), (PIN, -py))]
    S.append(_iec("Control transformer", "Control transformer", "Power", o, "device", "", "T",
                  pins=[{"name": "H1", "pos": (-PIN, py)}, {"name": "H2", "pos": (PIN, py)},
                        {"name": "X1", "pos": (-PIN, -py)}, {"name": "X2", "pos": (PIN, -py)}],
                  tag=(0.0, 0.28), description="Control transformer, two windings",
                  attr_texts=_rating(y=-0.32, fields=("VA", "PRI", "SEC"))))
    # ---- three-phase power -------------------------------------------------------------------
    S.append(_iec("Circuit breaker 3-pole", "Circuit breaker 3-pole", "Power",
                  _three(_breaker_pole) + _link(0.01, 0.58, -0.45), "device", "", "CB",
                  _three_pins(), tag=(0.0, TAG3_Y), description="Circuit breaker, three poles",
                  attr_texts=_rating(y=RATING3_Y, fields=("AMPS", "VOLTS"))))
    S.append(_iec("Disconnect 3-pole", "Disconnector 3-pole", "Power",
                  _three(_disconnector_pole) + _link(0.01, 0.58, -0.45), "device", "", "DS",
                  _three_pins(), tag=(0.0, TAG3_Y),
                  description="Disconnector (isolator), three poles",
                  attr_texts=_rating(y=RATING3_Y, fields=("AMPS", "VOLTS"))))
    S.append(_iec("Fuses 3-pole", "Fuses 3-pole", "Power", _three(_fuse_pole), "device", "",
                  "FU", _three_pins(), tag=(0.0, TAG3_Y), description="Fuses, three poles",
                  attr_texts=_rating(y=RATING3_Y, fields=("VOLTS",))))
    S.append(_iec("Contactor power contacts 3-pole", "Contactor main contacts 3-pole",
                  "Motor control", _three(_contact_pole) + _link(0.01, 0.58, -0.45), "child",
                  "NO", "M", _three_pins(), tag=(0.0, TAG3_Y),
                  description="Main (power) contacts of a contactor, three poles"))
    S.append(_iec("Overload heaters 3-pole", "Thermal overload 3-pole", "Motor control",
                  _three(_thermal_pole) + _link(0.0, POLE - 0.06, 0.08) +
                  _link(0.0, -0.06, -POLE + 0.08), "parent", "", "OL", _three_pins(),
                  tag=(0.0, TAG3_Y), description="Thermal overload relay, three poles",
                  attr_texts=_rating(y=RATING3_Y, fields=("AMPS",))))
    rm, cx = 0.55, 0.625
    o = [Circle((cx, 0.0), rm), Text((cx, 0.0), "M", 0.2, align="center"),
         Text((cx, -0.2), "3~", 0.12, align="center")]
    for y in POLES:
        o.append(Line((-PIN, y), (cx - (rm * rm - y * y) ** 0.5, y)))
    S.append(_iec("Motor 3-phase", "Motor 3-phase", "Power", o, "device", "", "MTR",
                  [{"name": "T%d" % (i + 1), "pos": (-PIN, y)} for i, y in enumerate(POLES)],
                  tag=(cx, TAG3_Y), description="Three-phase motor",
                  attr_texts=_rating(cx, RATING3_Y, fields=("HP", "VOLTS", "FLA"))))
    # ---- wiring ------------------------------------------------------------------------------
    o = [Circle((0.0, 0.0), 0.03125), Line((-0.03125, -0.03125), (0.03125, 0.03125))]
    S.append(_iec("Terminal", "Terminal", "Wiring", o, "child", "", "TB",
                  pins=[{"name": "1", "pos": (-0.03125, 0)}, {"name": "2", "pos": (0.03125, 0)}],
                  tag=(0.0, 0.08), description="A terminal of a terminal strip (numbers itself)",
                  attr_texts=[{"attr": "TERM", "pos": (0.0, -0.13), "height": 0.07}]))
    # protective earth: the earth's three lines in a circle
    o = [Line((0.0, 0.0), (0.0, -0.1)), Circle((0.0, -0.17), 0.1),
         Line((-0.07, -0.13), (0.07, -0.13)), Line((-0.045, -0.17), (0.045, -0.17)),
         Line((-0.02, -0.21), (0.02, -0.21))]
    S.append(_iec("Ground", "Protective earth", "Wiring", o, "device", "", "",
                  pins=[{"name": "1", "pos": (0, 0)}], tag=None,
                  description="Protective earth (PE)"))
    show_contact_pins(S)
    return S
