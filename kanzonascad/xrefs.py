"""Cross-references, worked out from the drawing (no Qt), never stored as text while they're
automatic.

- Under a device that has contacts (a coil, a pushbutton operator...): one line per contact,
  "NO 6-D3" / "NC 7-B2", in sheet order then zone order.
- Under each contact: where its device is ("6-D1"), or "?" when it isn't linked to one.
- Under an off-sheet connector: where the connectors of the same name are ("7-A2"), or "?"
  when it has no other end yet.
- A device's listing can be switched off (attribute XREF = "0" on the device), and each
  contact can be left out of its device's listing (XREF = "0" on the contact).

They follow every change. Two ways to hold them still:
- the project setting "Update cross-references automatically" off: every sheet shows what
  the last Update cross-references worked out;
- a sheet's Freeze cross-references (an issued sheet): it shows what they were when it was
  frozen, until it is unfrozen.
Either way, out_of_date() lists the sheets whose shown references differ from the drawing
(the status bar says so).

A reference is a plain tuple (x, y, text, height): saved in the sheet as it is while held.
"""

import math

from .model import Insert, Text, text_width
from . import tags

MARK = {"NO": "NO", "NC": "NC", "NOTC": "NO", "NOTO": "NO", "NCTO": "NC", "NCTC": "NC"}
GAP = 0.05                      # between a symbol's box and its first line
LINE = 1.35                     # line spacing, as a share of the text height

_cache = {"sig": None, "by_sheet": {}}


def _signature(project):
    return (tuple((s.id, s.version, project.sheet_number(s), s.size, s.scale, s.cols, s.rows,
                   s.col_start, s.row_start) for s in project.sheets),
            project.zone_format, project.settings.get("xref_height"))


def _where(project, sheet, e):
    q = e.pos if isinstance(e, Insert) else e.points[0]     # (a dashed box: its first corner)
    return project.zone_text(sheet, q[0], q[1]) or "%s-?" % project.sheet_number(sheet)


def _order(project):
    pos = {s.id: i for i, s in enumerate(project.sheets)}

    def key(item):
        s, e = item
        k = tags.order_key(s, "across")(e.pos if isinstance(e, Insert) else e.points[0])
        return (pos.get(s.id, 0), k)
    return key


def live_all(project):
    """{sheet id: [(x, y, text, height)]} worked out from the drawing now (kept until the
    project changes)."""
    sig = _signature(project)
    if _cache["sig"] == sig:
        return _cache["by_sheet"]
    h = float(project.settings.get("xref_height", 0.08))
    index = tags.devices(project)
    children = {}                                   # parent DEV -> [(sheet, contact)]
    contacts = []
    boxes = []
    for s in project.sheets:
        for e in s.inserts():
            if tags.is_child(e):
                contacts.append((s, e))
                dev = e.attrs.get("PARENT")
                if dev in index:
                    children.setdefault(dev, []).append((s, e))
        for e in s.entities.values():
            if tags.is_linked_box(e):
                boxes.append((s, e))
                dev = e.attrs.get("PARENT")
                if dev in index:
                    children.setdefault(dev, []).append((s, e))
    out = {s.id: [] for s in project.sheets}
    hk = {s.id: h * s.k() for s in project.sheets}     # (paper height on scaled sheets)
    key = _order(project)
    for dev, (s, parent) in index.items():
        if parent.attrs.get("XREF") == "0":
            continue
        items = sorted((c for c in children.get(dev, []) if c[1].attrs.get("XREF") != "0"),
                       key=key)
        if not items:
            continue
        hh = hk[s.id]
        bb = parent.bbox()
        x = (bb[0] + bb[2]) / 2.0
        y = bb[1] - GAP - hh
        for cs, c in items:
            mark = MARK.get(c.defn.contact, "") if isinstance(c, Insert) else ""
            text = ("%s %s" % (mark, _where(project, cs, c))).strip()
            out[s.id].append((round(x, 6), round(y, 6), text, hh))
            y -= hh * LINE
    # off-sheet connectors: where the same name's other ends are
    from .wirenums import connectors, ARROWS, number_at
    for name, ends in connectors(project).items():
        for s, c in ends:
            hh = hk[s.id]
            pair = [(os_, oc) for os_, oc in ends if oc is not c]
            if c.block in ARROWS:
                # (an arrow shows only its other half's place: a source its destinations, a
                # destination its source, not the other destinations of that name; the owner,
                # 0.18.4: "just the source and destination for that specific wire location")
                want = ARROWS[1] if c.block == ARROWS[0] else ARROWS[0]
                pair = [(os_, oc) for os_, oc in pair if oc.block == want] or pair
            others = [_where(project, os_, oc) for os_, oc in pair]
            text = ", ".join(others) if others else "?"
            if c.block in ARROWS:
                # a source or destination arrow: its wire's number and the other's place
                # (2046 / 7-A2), past the arrow's far end, away from its wire (the owner,
                # 0.17.5: arrows "connected" to the line, so nothing written over it)
                num = number_at(s, c)
                if num:
                    text = "%s / %s" % (num, text)
            # (outside the connector, away from its wire, whichever way it is turned: the
            # owner, 0.18, "Wire cross references need to always be outside the connector,
            # away from the wire")
            if c.block in ARROWS:
                # (an arrow on a wire running up and down: its text turned with it, as that
                # wire's number reads; the owner, 0.18.3: "I need the verbiage to be the same
                # orientation as I make the arrow")
                got = _along(s, c, text, hh)
                if got is not None:
                    out[s.id].append((round(got[0], 6), round(got[1], 6), text, hh, 90.0))
                    continue
            got = _outside(s, c, text, hh)
            if got is None:
                bb = c.bbox()
                got = ((bb[0] + bb[2]) / 2.0, bb[1] - GAP - hh)
            out[s.id].append((round(got[0], 6), round(got[1], 6), text, hh))
    for s, c in contacts:
        if tags.numbered(c):
            continue                    # (a terminal shows its number, not where its strip is)
        hh = hk[s.id]
        got = index.get(c.attrs.get("PARENT")) if c.attrs.get("PARENT") else None
        text = _where(project, got[0], got[1]) if got is not None else "?"
        if c.attr_at.get("@XREF"):
            # (dragged to a place of its own by its grip: centered there)
            q = c.xref_point()
            out[s.id].append((round(q[0], 6), round(q[1] - 0.35 * hh, 6), text, hh))
            continue
        bb = c.bbox()
        out[s.id].append((round((bb[0] + bb[2]) / 2.0, 6), round(bb[1] - GAP - hh, 6), text, hh))
    # beside a dashed box's tag: where its device is ("PDB1  1-B2")
    for s, b in boxes:
        hh = hk[s.id]
        got = index.get(b.attrs.get("PARENT")) if b.attrs.get("PARENT") else None
        text = _where(project, got[0], got[1]) if got is not None else "?"
        x, y = b.tag_point()
        x += text_width(b.tag(), b.height) + hh * 0.6 + text_width(text, hh) / 2
        out[s.id].append((round(x, 6), round(y, 6), text, hh))
    _cache["sig"], _cache["by_sheet"] = sig, out
    return out


def _wire_in(sheet, c):
    """(The way the wire comes into the connector's pin (a unit vector), that wire), or
    (None, None) when no wire ends on it."""
    from .wires import TOL
    pin = c.pin_points()[0][1]
    for w in sheet.query_point(pin, TOL):
        if getattr(w, "kind", "") != "wire":
            continue
        for i, j in ((0, 1), (-1, -2)):
            q, r = w.points[i], w.points[j]
            if abs(q[0] - pin[0]) <= TOL and abs(q[1] - pin[1]) <= TOL:
                L = math.hypot(q[0] - r[0], q[1] - r[1])
                if L > TOL:
                    return ((q[0] - r[0]) / L, (q[1] - r[1]) / L), w
    return None, None


def text_item(item):
    """A reference as drawn (x, y, text, height[, angle]): a centered Text."""
    return Text((item[0], item[1]), item[2], item[3], item[4] if len(item) > 4 else 0.0,
                "center")


def _along(sheet, c, text, hh):
    """Where an arrow's text turned 90 degrees is centered (its insertion point) when its
    wire runs up and down: past the arrow's tip, in line with the wire, reading up as a
    wire number does on such a wire; beside the arrow, turned, when its own wire is in the
    way there. None for a wire running across (its text stays level) or no wire."""
    from .geometry import segment_hits_rect
    d, wire = _wire_in(sheet, c)
    if d is None or abs(d[1]) <= abs(d[0]):
        return None
    pin = c.pin_points()[0][1]
    bb = c.bbox()
    gap = 0.4 * hh
    tw = text_width(text, hh)
    probe = Text((0.0, 0.0), text, hh, 90.0, "center").bbox()
    off = ((probe[0] + probe[2]) / 2.0, (probe[1] + probe[3]) / 2.0)
    half = (probe[2] - probe[0]) / 2.0
    ymid = (bb[1] + bb[3]) / 2.0
    out = 1.0 if d[1] > 0 else -1.0
    tip = ((pin[0], (bb[3] + gap + tw / 2.0) if out > 0 else (bb[1] - gap - tw / 2.0)),
           (0.0, out))
    right = ((bb[2] + gap + half, ymid), (1.0, 0.0))
    left = ((bb[0] - gap - half, ymid), (-1.0, 0.0))
    for step in (0.0, 1.5, 3.0, 4.5, 6.0):
        for (x, y), (ux, uy) in (tip, right, left):
            q = (x + ux * step * hh - off[0], y + uy * step * hh - off[1])
            tb = Text(q, text, hh, 90.0, "center").bbox()
            if not any(segment_hits_rect(a, b, tb)
                       for a, b in zip(wire.points, wire.points[1:])):
                return q
    return (tip[0][0] - off[0], tip[0][1] - off[1])


def _outside(sheet, c, text, hh):
    """Where a connector's (or arrow's) text is centered: past the connector's far side from
    its wire, the way the wire comes into its pin and on out (beside it when the wire runs
    across, under or over it when the wire runs up and down); None when no wire ends on it."""
    from .geometry import segment_hits_rect
    pin = c.pin_points()[0][1]
    d, wire = _wire_in(sheet, c)
    if d is None:
        return None
    bb = c.bbox()
    gap = 0.4 * hh
    tw = text_width(text, hh)
    mid = (bb[0] + bb[2]) / 2.0
    # (each spot with the way it moves out from the connector)
    right = ((bb[2] + gap + tw / 2.0, pin[1] - 0.35 * hh), (1.0, 0.0))
    left = ((bb[0] - gap - tw / 2.0, pin[1] - 0.35 * hh), (-1.0, 0.0))
    over = ((mid, bb[3] + gap), (0.0, 1.0))
    under = ((mid, bb[1] - gap - hh), (0.0, -1.0))
    if abs(d[0]) >= abs(d[1]):
        # the wire comes in across: past its far end first, then over or under it
        spots = [right if d[0] > 0 else left, over, under]
    else:
        spots = [((pin[0], over[0][1]), over[1]) if d[1] > 0 else
                 ((pin[0], under[0][1]), under[1]), right, left]
    # (the first of them clear of its own wire, a little farther out where the wire passes
    # close: a wire that comes back round past the connector, the long battery, seed 3152,
    # and one wrapped round three sides of it, seed 3263)
    for step in (0.0, 1.5, 3.0, 4.5, 6.0):
        for (x, y), (ux, uy) in spots:
            q = (x + ux * step * hh, y + uy * step * hh)
            tb = Text(q, text, hh, 0.0, "center").bbox()
            if not any(segment_hits_rect(a, b, tb)
                       for a, b in zip(wire.points, wire.points[1:])):
                return q
    return spots[0][0]


def live(project, sheet):
    return live_all(project).get(sheet.id, [])


def held(project, sheet):
    """True when the sheet shows kept references instead of live ones."""
    return bool(sheet.xref_frozen) or not project.settings.get("xref_auto", True)


def shown(project, sheet):
    """The references drawn on the sheet."""
    if sheet is project.title_block:
        return []
    if held(project, sheet):
        return list(sheet.xref_shown or [])
    return live(project, sheet)


def out_of_date(project):
    """The sheets whose drawn references aren't what the drawing says now."""
    return [s for s in project.sheets
            if held(project, s) and list(s.xref_shown or []) != live(project, s)]


def texts(project, sheet):
    """The references drawn on the sheet, as centered texts."""
    return [text_item(t) for t in shown(project, sheet)]


def update(ed, project, sheets=None):
    """Update cross-references: the held sheets (all but frozen ones, unless named) take what
    the drawing says now. Returns how many sheets changed."""
    n = 0
    for s in (sheets if sheets is not None else project.sheets):
        if sheets is None and s.xref_frozen:
            continue
        now = live(project, s)
        if list(s.xref_shown or []) != now:
            ed.sheet_meta(s, xref_shown=[list(t) for t in now])
            n += 1
    return n


def freeze(ed, project, sheet, on):
    """Freeze (keep the references as they are now) or unfreeze a sheet."""
    if on:
        ed.sheet_meta(sheet, xref_frozen=True,
                      xref_shown=[list(t) for t in live(project, sheet)])
    else:
        ed.sheet_meta(sheet, xref_frozen=False)


def set_auto(ed, project, on):
    """Turn automatic cross-references on or off; turned off, every sheet keeps what it shows
    now (frozen sheets keep theirs)."""
    if not on:
        for s in project.sheets:
            if not s.xref_frozen:
                ed.sheet_meta(s, xref_shown=[list(t) for t in live(project, s)])
    ed.project_settings({"xref_auto": bool(on)})
