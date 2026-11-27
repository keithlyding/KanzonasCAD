"""The wire layer a new wire takes from the pin it starts on (the owner, 0.22.1: "Yes, on the
auto wire layer", to the mapping offered: PLC I/O on 24VDC BLU, commons on BLU-WHT, motor and
drive terminals on 480 V, 120 V control on 120V RED; and per-pin defaults in the block editor).

A pin's own wire layer (Pins..., in a block's tab) comes first; else the block's kind says:
  - a PLC module's input or output point (or a PLC input or output symbol), its V or +VDC:
    24VDC BLU; its common (C, COM, DC COM 1, GND-0, RTN-n, ANLG Com, 0V, -V): 24VDC BLU-WHT;
  - a motor's or drive's power terminal (L1-L3, T1-T3, U, V, W): 480V BLK; its ground (PE,
    GND): 480V GRN;
  - a control transformer's H terminals: 480V BLK; X1: 120V RED; X2: 120V WHT;
  - a power supply's L: 120V RED; N: 120V WHT; +: 24VDC BLU; -: 24VDC BLU-WHT.
Only a layer the project has is used (Add wire layers puts the preset's in), and only while
Project properties' "A wire takes its layer from the pin it starts on" is on.

No Qt here."""

import re

from . import geometry as G

_TERMINAL = re.compile(r"^(\S+)\s+(.+)$")
# (an analog channel's voltage or current terminal too, V IN 0+, IOUT-2; and the Allen-Bradley
# modules' commons and supplies as Rockwell prints them, 0.29: DC COM 1, GND-0, RTN OUT-0,
# ANLG COM, DC NEUT, LA-, an analog return, I RTN-0, V/I IN 0-; +VDC, DC-0(+), +24V DC, LA+)
_POINT = re.compile(r"^([VI] ?)?(IN|OUT)([ -]?\d+)?\+?$")
_COMMON = re.compile(r"^(C|COM\S*|DC ?COM( \d+)?|RTN\S*|RTN OUT-\d+|I RTN-\d+|V/I IN \d+-|"
                     r"GND-\d+|ANLG COM|DC NEUT|LA-|0 ?V|-V|DC-|V-)$")
_SUPPLY = re.compile(r"^(V|\+V|V\+|24 ?V|\+24 ?V( DC)?|\+?VDC|DC\+|DC-\d+\(\+\)|LA\+)$")
_POWER = re.compile(r"^([LT][1-3]|[UVW][12]?)$")
_GROUND = re.compile(r"^(PE\d*|GND|G|GRD)$")


def enabled(project):
    return bool(project.settings.get("wire_layer_auto", True))


def _terminal_texts(defn):
    """{pin name: what the block's text beside it says it is} ("3  IN 3": IN 3)."""
    names = {p["name"] for p in defn.pins}
    out = {}
    for e in defn.entities:
        if getattr(e, "kind", "") == "text":
            m = _TERMINAL.match(e.text.strip())
            if m and m.group(1) in names:
                out.setdefault(m.group(1), m.group(2).strip().upper())
    return out


def block_layer(defn, pin):
    """The layer the block's kind gives a wire on pin (its name), or None."""
    pre = (defn.prefix or "").upper()
    name = str(pin).strip().upper()
    if pre == "PLC":
        what = _terminal_texts(defn).get(pin, name)
        if _POINT.match(what) or _SUPPLY.match(what):
            return "24VDC BLU"
        if _COMMON.match(what):
            return "24VDC BLU-WHT"
        return None
    if pre in ("MTR", "VFD"):
        if _GROUND.match(name):
            return "480V GRN"
        return "480V BLK" if _POWER.match(name) else None
    if pre == "T":
        if name.startswith("H"):
            return "480V BLK"
        return {"X1": "120V RED", "X2": "120V WHT"}.get(name)
    if pre == "PS":
        return {"L": "120V RED", "L1": "120V RED", "N": "120V WHT", "+": "24VDC BLU",
                "-": "24VDC BLU-WHT"}.get(name)
    return None


def pin_layer(project, defn, pin):
    """The layer a wire started on this pin goes on, or None: the pin's own, else the block's
    kind's, either only when the project has that layer."""
    if defn is None:
        return None
    own = next((p.get("layer") for p in defn.pins if p["name"] == pin), None)
    for name in (own, block_layer(defn, pin)):
        if name and name in project.layers:
            return name
    return None


def pins_at(sheet, q, tol):
    """[(insert, pin name)] of the symbols' pins at q."""
    out = []
    for o in sheet.query_point(q, tol):
        if getattr(o, "kind", "") != "insert" or getattr(o, "defn", None) is None:
            continue
        for name, p in o.pin_points():
            if G.dist(p, q) <= tol:
                out.append((o, name))
    return out


def layer_for(project, sheet, pts, tol):
    """(layer, insert, pin) a wire through pts takes from its start's pin, else its end's;
    None when neither says (or the setting is off)."""
    if not enabled(project) or len(pts) < 2:
        return None
    for q in (pts[0], pts[-1]):
        for ins, name in pins_at(sheet, q, tol):
            got = pin_layer(project, ins.defn, name)
            if got is not None:
                return got, ins, name
    return None
