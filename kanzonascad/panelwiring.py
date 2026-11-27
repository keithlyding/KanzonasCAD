"""Panel wiring (0.28; the roadmap's item 5, the owner's choices of 0.22.1: "yes, a per device
wiring list", and point-to-point as labels on the footprints' terminals, not a drawn diagram).
No Qt.

A **unit** is what the panel builder wires: a device (a coil, a breaker, a PLC card...) with
the symbols that belong to it (its contacts, its I/O points: tags.py's children), or a terminal
of a strip (TB1-4, every place it is drawn: strips.py). Each pin of each of its symbols lands
wires; each wire group on a pin, joined across sheets through off-sheet connectors and source
and destination arrows (strips.context), has its wire number, its size, color and layer, and
the other pins it lands on (the device's own other pins included). Worked out from the
schematic every time, never kept.

The **wiring list** (Device wiring list..., report sheets) is a row per pin and wire group of
every unit, in tag order. Its Footprint column says where the pin is on the unit's footprint,
or why it isn't: no footprint, a footprint with no terminal positions (a footprint block
without pins: Edit block, add pin markers named as the device's pins), or a footprint without
that pin. Nothing is guessed.

A unit's **footprint** is one on a panel sheet linked to its device (PARENT, its hidden id),
or not linked to any but with its tag (as Devices without a footprint counts them); a
terminal's is a footprint with its terminal number (attribute TERM) linked to its strip (or
with the strip's tag). A footprint's terminal positions are its block's pins; one named as a
pin of the unit is that pin.

**Terminal wire labels** (a panel sheet's own setting, the sheet's terminal_labels: decided
per sheet, a door layout sheet stays clear): each footprint terminal labeled with its wire
number and where the wire goes, "6001 → CR101:A1" (a wire to another location shows it:
"6001 → LT1:1 (FIELD)"), a line for each wire group on it, outward from the footprint on the
side the pin is on, read across or upward however the footprint is turned, at the project's
Terminal wire label height (Panel settings, paper inches). Worked out once per change of the
project and kept with it until the next (labels), not on a paint or a mouse move."""

import math

from . import pull, strips, tags, wirenums
from .model import Text, gauge_text

HEAD = ["Device", "Pin", "Wire", "Size", "Color", "Layer", "Goes to", "Location", "Where",
        "Footprint"]
HEIGHT = "fp_wire_label_height"     # the project's setting: paper inches
DEFAULT_HEIGHT = 0.05
ARROW = " → "              # between a wire's number and where it goes
NO_FOOTPRINT = "no footprint"
# a label names this many pins at most: a wire landing on more (a common, a neutral) shows the
# first two and how many more, "CR201:A2, CR202:A2 +4" (the wiring list names them all)
MOST = 3
NO_POSITIONS = "no terminal positions"


def label_height(project):
    """The terminal wire labels' height on paper (Panel settings)."""
    try:
        return float(project.settings.get(HEIGHT, DEFAULT_HEIGHT)) or DEFAULT_HEIGHT
    except (TypeError, ValueError):
        return DEFAULT_HEIGHT


def terminal_block(defn):
    """Whether a footprint block is a terminal's (its name or category says Terminal): placed,
    it is asked which terminal of a strip it is (TB1-4)."""
    return defn is not None and defn.kind == "footprint" and (
        "terminal" in defn.name.lower() or "terminal" in (defn.category or "").lower())


def labels_on(sheet):
    """Whether a sheet shows terminal wire labels (a panel sheet with them turned on)."""
    return sheet.kind == "panel" and bool(getattr(sheet, "terminal_labels", False))


class End:
    """A wire group on a pin: its wires there, their numbers (none while numbering is off) and
    the other pins it lands on [(sheet, symbol, pin)]."""

    def __init__(self):
        self.wires = []
        self.numbers = []
        self.landings = []


class Pin:
    """A pin of a unit's symbol (sheet, symbol, name) and its wire groups [End]."""

    def __init__(self, sheet, ins, name):
        self.sheet = sheet
        self.ins = ins
        self.name = name
        self.ends = []


class Unit:
    """A device with its symbols, or a strip's terminal: key, name (CR101, TB1-4), location,
    symbols [(sheet, symbol)] (the device itself first), its footprints [(sheet, footprint)]
    on panel sheets, and its pins (worked out when first asked for: pins)."""

    def __init__(self, key, name):
        self.key = key
        self.name = name
        self.loc = ""
        self.symbols = []
        self.footprints = []
        self._pins = None


def _unit_key(s, e, devs, strip_tags):
    """(key, name) of the unit a placed symbol is part of, or None (not one: a connector, a
    symbol with no tag of its own and no device)."""
    if strips.is_terminal(e):
        num = (e.attrs.get("TERM") or "").strip()
        key = strips.key_of(e, devs)
        if key.startswith(strips.TAG_KEY) and key[len(strips.TAG_KEY):] in strip_tags:
            key = strip_tags[key[len(strips.TAG_KEY):]]
        tag = ((devs[key][1] if key in devs else e).attrs.get("TAG") or "").strip() or "TB?"
        if not num:
            return ("one", s.id, e.id), tag
        return ("term", key, num), "%s-%s" % (tag, num)
    if tags.is_device(e):
        if e.defn.wiring == "link":
            return None
        dev = e.attrs.get("DEV")
        tag = (e.attrs.get("TAG") or "").strip() or "?"
        return (("dev", dev) if dev else ("one", s.id, e.id)), tag
    if tags.is_child(e):
        par = e.attrs.get("PARENT")
        if par and par in devs:
            return ("dev", par), (devs[par][1].attrs.get("TAG") or "").strip() or "?"
        tag = (e.attrs.get("TAG") or "").strip()
        if tag:
            return ("tag", tag.upper()), tag
        return ("one", s.id, e.id), e.block_name
    return None


def _footprint_key(e, devs, dev_tags, strip_tags):
    """The key of the unit a footprint stands for (as _unit_key), or None."""
    par = e.attrs.get("PARENT") or ""
    tag = (e.attrs.get("TAG") or "").strip().upper()
    term = (e.attrs.get("TERM") or "").strip()
    if term:
        if par and par in devs and strips.is_strip_device(devs[par][1]):
            return ("term", par, term)
        if not par and tag:
            return ("term", strip_tags.get(tag, strips.TAG_KEY + tag), term)
        return None
    if par:
        return ("dev", par) if par in devs else None
    if tag:
        return ("dev", dev_tags[tag]) if tag in dev_tags else ("tag", tag)
    return None


def _signature(project):
    return (tuple((s.id, s.version) for s in project.sheets), wirenums.enabled(project),
            label_height(project),
            tuple((n, lay.awg, lay.wire_color) for n, lay in project.layers.items()))


class Wiring:
    """The project's units (in tag order), by key; the wire nets (strips.context); and the
    terminal wire labels of each sheet, worked out when a sheet asks (labels)."""

    def __init__(self, project):
        self.project = project
        self.ctx = strips.context(project)
        devs = tags.devices(project)
        strip_tags = {}
        dev_tags = {}
        for dev, (_s, e) in devs.items():
            t = (e.attrs.get("TAG") or "").strip().upper()
            if not t:
                continue
            if strips.is_strip_device(e):
                strip_tags.setdefault(t, dev)
            else:
                dev_tags.setdefault(t, dev)
        by_key = {}
        order = {}
        for i, s in enumerate(project.sheets):
            for e in s.inserts():
                d = e.defn
                if d is None or d.kind != "symbol":
                    continue
                got = _unit_key(s, e, devs, strip_tags)
                if got is None:
                    continue
                key, name = got
                u = by_key.get(key)
                if u is None:
                    u = by_key[key] = Unit(key, name)
                main = tags.is_device(e) or strips.is_terminal(e)
                u.symbols.append((s, e))
                order[id(e)] = (0 if main else 1, i, -e.pos[1], e.pos[0])
        for u in by_key.values():
            u.symbols.sort(key=lambda t: order[id(t[1])])
            if u.key[0] == "dev" and u.key[1] in devs:
                u.loc = pull.location_of(*devs[u.key[1]])
            else:
                u.loc = pull.location_of(*u.symbols[0])
        for s in project.sheets:
            if s.kind != "panel":
                continue
            for e in s.inserts():
                if not tags.is_footprint(e):
                    continue
                key = _footprint_key(e, devs, dev_tags, strip_tags)
                if key in by_key:
                    by_key[key].footprints.append((s, e))
        self.by_key = by_key
        self.units = sorted(by_key.values(), key=lambda u: (strips.natural(u.name.upper()),
                                                            str(u.key)))
        self.fp_unit = {(s.id, e.id): u for u in self.units for s, e in u.footprints}
        self._labels = {}

    def pins(self, u):
        """A unit's pins [Pin], each with its wire groups (once: kept with the unit)."""
        if u._pins is not None:
            return u._pins
        ctx = self.ctx
        out = []
        for s, e in u.symbols:
            for name, q in e.pin_points():
                # (named as people read it, a contact by its own number, 13: as its
                # footprint's terminals are)
                pin = Pin(s, e, e.pin_number(name))
                by_net = {}
                for w, net in strips.pin_wires(ctx, s, q):
                    end = by_net.get(net)
                    if end is None:
                        end = by_net[net] = End()
                        pin.ends.append(end)
                        end.landings = [t for t in strips.net_landings(ctx, net)
                                        if not (t[1] is e and t[2] == name and t[0] is s)]
                    end.wires.append(w)
                    if ctx["numbered"]:
                        n = w.num or "?"
                        if n not in end.numbers:
                            end.numbers.append(n)
                out.append(pin)
        u._pins = out
        return out

    def ends_at(self, u, name):
        """Every wire group on the unit's pins named name (its symbols' pins of that name)."""
        return [end for p in self.pins(u) if p.name == name for end in p.ends]

    def labels(self, sheet):
        """The terminal wire labels of a sheet [Text] (none when it doesn't show them)."""
        got = self._labels.get(sheet.id)
        if got is not None:
            return got
        out = []
        if labels_on(sheet):
            h = label_height(self.project) * sheet.k()
            for e in sheet.inserts():
                u = self.fp_unit.get((sheet.id, e.id))
                if u is None:
                    continue
                for name, q in e.pin_points():
                    lines = [label_text(end, u.loc) for end in self.ends_at(u, name)]
                    lines = [t for t in lines if t]
                    if lines:
                        out += place_lines(e, name, q, lines, h)
        self._labels[sheet.id] = out
        return out


def wiring(project):
    """The project's Wiring, kept with the project until it changes (any sheet, the numbering,
    the label height, the wire layers' sizes and colors)."""
    sig = _signature(project)
    got = getattr(project, "_panel_wiring", None)
    if got is not None and got[0] == sig:
        return got[1]
    w = Wiring(project)
    project._panel_wiring = (sig, w)
    return w


def labels(project, sheet):
    """The terminal wire labels drawn on a sheet [Text] (the renderer, DXF, print extents)."""
    if sheet is project.title_block or not labels_on(sheet):
        return []
    return wiring(project).labels(sheet)


def label_text(end, loc):
    """A wire group's label on a footprint terminal: "6001 → CR101:A1, M101:T1 (FIELD)" (its
    number and the other pins it lands on, with their location when it isn't loc; past MOST,
    the first two and how many more); the number alone when it lands nowhere else, the destination alone with numbering off."""
    num = ", ".join(end.numbers)
    to = strips.landings_text(end.landings, loc, MOST)
    if num and to:
        return num + ARROW + to
    if to:
        return ARROW.strip() + " " + to
    return num


def outward(ins, name):
    """The way out of a footprint from its pin name, on the drawing: toward the side of the
    block's box the pin is nearest, measured against the box's half width and half height (a
    thin terminal block's top screw goes out the top, not the side it is a hair from), as
    the copy is turned and flipped. A unit vector."""
    d = ins.defn
    pos = next((p["pos"] for p in d.pins if p["name"] == name), (0.0, 0.0))
    x0, y0, x1, y1 = d.extents()
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    rx = (pos[0] - cx) / max((x1 - x0) / 2.0, 1e-9)
    ry = (pos[1] - cy) / max((y1 - y0) / 2.0, 1e-9)
    if abs(rx) < 1e-9 and abs(ry) < 1e-9:
        ax = (0.0, 1.0)
    elif abs(rx) > abs(ry):
        ax = (1.0 if rx > 0 else -1.0, 0.0)
    else:
        ax = (0.0, 1.0 if ry > 0 else -1.0)
    a = ins.to_world(pos)
    b = ins.to_world((pos[0] + ax[0], pos[1] + ax[1]))
    wx, wy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(wx, wy) or 1.0
    return wx / n, wy / n


def place_lines(ins, name, q, lines, h):
    """Texts of a terminal's label lines: starting just off the pin (name, at q) and running
    out of the footprint, read across (out to the right or left) or upward (out the top or bottom), so
    they stay readable however the footprint is turned; several lines side by side."""
    wx, wy = outward(ins, name)
    gap = 0.4 * h
    if abs(wx) >= abs(wy):
        ang, align = 0.0, "left" if wx > 0 else "right"
        out_v, side = (1.0 if wx > 0 else -1.0, 0.0), (0.0, -1.0)
    else:
        ang, align = 90.0, "left" if wy > 0 else "right"
        out_v, side = (0.0, 1.0 if wy > 0 else -1.0), (1.0, 0.0)
    n = len(lines)
    out = []
    for i, t in enumerate(lines):
        off = (i - (n - 1) / 2.0) * 1.3 * h
        x = q[0] + out_v[0] * gap + side[0] * off
        y = q[1] + out_v[1] * gap + side[1] * off
        out.append(Text((x, y), t, h, ang, align, "middle"))
    return out


# ---- the wiring list --------------------------------------------------------------------------
def footprint_status(project, u, name):
    """What the Footprint column says of a unit's pin: where it is on the unit's footprint
    (its sheet and zone), or why it isn't (no footprint; no terminal positions: its block has
    no pins; no terminal of that name on it)."""
    if not u.footprints:
        return NO_FOOTPRINT
    have = [(s, f) for s, f in u.footprints if any(p["name"] == name for p in f.defn.pins)]
    if have:
        out = []
        for s, f in have:
            q = dict(f.pin_points())[name]
            t = project.zone_text(s, q[0], q[1]) or project.sheet_number(s)
            if t not in out:
                out.append(t)
        return ", ".join(out)
    blocks = sorted({f.block_name for _s, f in u.footprints})
    if not any(f.defn.pins for _s, f in u.footprints):
        return "%s (%s)" % (NO_POSITIONS, ", ".join(blocks))
    return "no terminal %s on %s" % (name, ", ".join(blocks))


def _where(project, s, e):
    return project.zone_text(s, e.pos[0], e.pos[1]) or project.sheet_number(s)


def _join(vals):
    out = []
    for v in vals:
        if v and v not in out:
            out.append(v)
    return ", ".join(out)


def rows(project, w=None):
    """The wiring list: a row per pin and wire group of every unit (an unwired pin: one row,
    its wire columns empty), the units in tag order, each one's pins as its symbols have them
    (the device's own first): device, pin, wire, size, color, layer, goes to, location, where
    (its symbol's zone), footprint (footprint_status)."""
    w = w or wiring(project)
    layers = project.layers
    out = []
    for u in w.units:
        for p in w.pins(u):
            fp = footprint_status(project, u, p.name)
            where = _where(project, p.sheet, p.ins)
            for end in p.ends or [None]:
                if end is None:
                    out.append([u.name, p.name, "", "", "", "", "", u.loc, where, fp])
                    continue
                lays = [layers.get(x.layer) for x in end.wires]
                size = _join(gauge_text(x.awg or (lay.awg if lay is not None else ""))
                             for x, lay in zip(end.wires, lays))
                color = _join(lay.wire_color if lay is not None else "" for lay in lays)
                out.append([u.name, p.name, ", ".join(end.numbers), size, color,
                            _join(x.layer for x in end.wires),
                            strips.landings_text(end.landings, u.loc), u.loc, where, fp])
    return out


def table(project):
    """(header, rows) of the wiring list (report sheets, Save as CSV or Excel)."""
    return HEAD, rows(project)


def without_positions(project, sheet=None):
    """[(sheet, footprint)] of the footprints standing for a device or terminal whose block has
    no terminal positions (no pins), on one sheet or every panel sheet."""
    w = wiring(project)
    out = []
    for u in w.units:
        for s, f in u.footprints:
            if (sheet is None or s is sheet) and not f.defn.pins:
                out.append((s, f))
    return out


def labeled_count(project, sheet):
    """How many footprint terminals on a sheet would carry a label (whether shown or not)."""
    w = wiring(project)
    n = 0
    for e in sheet.inserts():
        u = w.fp_unit.get((sheet.id, e.id))
        if u is None:
            continue
        for name, _q in e.pin_points():
            if any(label_text(end, u.loc) for end in w.ends_at(u, name)):
                n += 1
    return n


def describe_missing(found):
    """The command line's note on footprints without terminal positions: "2 footprints have
    no terminal positions (Breaker 1-pole (DIN): CB101, ...)"; "" when there are none."""
    if not found:
        return ""
    by_block = {}
    for _s, f in found:
        by_block.setdefault(f.block_name, []).append((f.attrs.get("TAG") or "?").strip())
    parts = ["%s: %s" % (b, ", ".join(sorted(set(t), key=strips.natural)))
             for b, t in sorted(by_block.items())]
    n = len(found)
    return ("%d footprint%s ha%s no terminal positions, so no labels (%s); give %s block "
            "pins named as the device's (Edit block)" % (
                n, "" if n == 1 else "s", "s" if n == 1 else "ve", "; ".join(parts),
                "its" if len(by_block) == 1 else "their"))
