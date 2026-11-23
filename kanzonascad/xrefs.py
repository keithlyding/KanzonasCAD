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
            project.zone_format, project.settings.get("xref_height"),
            project.settings.get("xref_device", True),
            tuple(s.xref_device for s in project.sheets),
            # (by ladder or by grid, 0.22: the rung numbers come with the sheets' versions)
            project.settings.get("referencing"), project.settings.get("ladder_numbers"),
            tuple(getattr(s, "referencing", None) for s in project.sheets))


def shows_device(project, sheet, ins):
    """Whether an arrow shows the device at its wire's other end under its reference: the
    arrow's own choice (XDEV "1" or "0"), else its sheet's (Sheet properties), else the
    project's (Project properties; the owner, 0.19.3: a project setting, a sheet setting
    that can override it, and one on each arrow that can override both)."""
    own = ins.attrs.get("XDEV")
    if own in ("1", "0"):
        return own == "1"
    if getattr(sheet, "xref_device", None) is not None:
        return bool(sheet.xref_device)
    return bool(project.settings.get("xref_device", True))


def _group_of(sheet, c):
    """The sheet-local wire group root of the wire on a connector's pin, or None."""
    from . import wirenums
    _d, wire = _wire_in(sheet, c)
    if wire is None:
        return None
    return wirenums._sheet_groups(sheet).get(wire.id)


def _straight_to(sheet, root, skip):
    """The one (insert, pin) a sheet-local wire group lands on, or None when it lands on none
    or more than one (a T), or carries on through a connector; skip: the connector or
    terminal it was reached from."""
    from . import pull, wirenums
    lands = [(i, p) for i, p in pull._sheet_landings(sheet).get(root, ()) if i is not skip]
    if len(lands) != 1:
        return None
    roots = wirenums._sheet_groups(sheet)
    for e in sheet.inserts():
        if e is not skip and e.defn is not None and e.defn.wiring == "link" and \
                root in wirenums._pin_wires(sheet, e, roots).values():
            return None                 # (the wire goes on: through another connector)
    return lands[0]


def far_device(sheet, c):
    """The device the wire on an arrow's pin goes straight to on the arrow's sheet: its tag
    (VFD201), or None when that wire tees off, lands on nothing or carries on to another
    connector (the owner, 0.19.5: "If there's a T, I don't need to see a device. I really
    just want to be able to look at the source page and know the downstream device is the plc
    without having to flip there"). Terminals are passed through to the device past them (the
    owner, 0.19.6); a terminal with nothing straight past it, or a T there, is shown itself
    (TB1-12)."""
    from . import pull, wirenums
    root = _group_of(sheet, c)
    if root is None:
        return None
    got = _straight_to(sheet, root, c)
    if got is None:
        return None
    roots = wirenums._sheet_groups(sheet)
    seen = set()
    while pull.is_terminal(got[0]) and id(got[0]) not in seen:
        ins, pin = got
        seen.add(id(ins))
        past = [r for name, r in wirenums._pin_wires(sheet, ins, roots).items()
                if name != pin and r != root]
        nxt = _straight_to(sheet, past[0], ins) if len(set(past)) == 1 else None
        if nxt is None:
            break                       # (nothing straight past it: the terminal itself)
        root, got = past[0], nxt
    ins, pin = got
    if pull.is_terminal(ins):
        return pull.landing_name(ins, pin)
    return (ins.attrs.get("TAG", "") or "").strip() or ins.block


def arrow_pairs(project, ends):
    """{id(arrow): [(sheet, other arrow)]} for the source and destination arrows of one name:
    each arrow with only its neighbors in the chain, not every arrow of that name (the owner,
    0.19.5: "the exact previous or next wire"; a wire carried page 4 -> 5 -> 6 has a
    destination and a source on page 5, on one wire). Each source takes the first
    destination after it in the project's order (sheets, then across and down) that isn't on
    its own wire (none: it waits, "?"); a destination left over (one source carried to two
    sheets, or a destination drawn before its source) takes the source just before it, else
    the first one after. A destination and a source on one wire on a sheet are one run,
    ordered where it starts."""
    from .wirenums import ARROWS
    pos = {s.id: i for i, s in enumerate(project.sheets)}
    arrows = [(s, e) for s, e in ends if e.block in ARROWS]
    group = {id(e): (s.id, _group_of(s, e)) for s, e in arrows}
    # (a destination and a source on one wire on a sheet are one run of it, a ladder's rail
    # down the sheet: ordered where the run starts, not each where it is, or a source at a
    # ladder's foot came after the next ladder's head and skipped it; the owner, 0.19.11, page
    # 8: "I want the source of the left ladder to feed the right ladder, then move on to
    # another sheet from the right ladder. But cross references are all jacked up")
    run_at = {}
    for s, e in arrows:
        k = tags.order_key(s, "across")(e.pos)
        g = group[id(e)]
        if g[1] is not None and (g not in run_at or k < run_at[g]):
            run_at[g] = k

    def key(item):
        s, e = item
        own = tags.order_key(s, "across")(e.pos)
        return (pos.get(s.id, 0), run_at.get(group[id(e)], own), own)
    srcs = sorted(((s, e) for s, e in arrows if e.block == ARROWS[0]), key=key)
    dsts = sorted(((s, e) for s, e in arrows if e.block == ARROWS[1]), key=key)

    def apart(a, b):
        ga, gb = group[id(a[1])], group[id(b[1])]
        return ga[1] is None or ga != gb
    out = {id(e): [] for _s, e in srcs + dsts}
    taken = set()
    # (a destination linked by hand to a source arrow, first: that pair holds whatever the
    # order, and that source takes no other one by itself)
    from .wirenums import linked_source
    by_id = {id(e): (s, e) for s, e in srcs}
    spoken = set()
    for d in dsts:
        got = linked_source(project, d[1])
        if got is not None and id(got[1]) in by_id:
            sv = by_id[id(got[1])]
            taken.add(id(d[1]))
            spoken.add(id(sv[1]))
            out[id(sv[1])].append(d)
            out[id(d[1])].append(sv)
    for sv in srcs:
        if id(sv[1]) in spoken:
            continue
        free = [d for d in dsts if id(d[1]) not in taken and apart(sv, d)]
        after = [d for d in free if key(d) > key(sv)]
        # (only forward: a source with none after it waits ("?") rather than taking one
        # before it that its own source feeds; a destination before its only source is
        # paired with it below, by the destination)
        got = after[0] if after else None
        if got is not None:
            taken.add(id(got[1]))
            out[id(sv[1])].append(got)
            out[id(got[1])].append(sv)
    for d in dsts:
        if id(d[1]) in taken:
            continue
        cands = [sv for sv in srcs if apart(sv, d)]
        before = [sv for sv in cands if key(sv) < key(d)]
        got = before[-1] if before else (cands[0] if cands else None)
        if got is not None:
            out[id(d[1])].append(got)
            out[id(got[1])].append(d)
    # (an arrow left with none: when every arrow of its name is on its one wire, a pair drawn
    # on one wire, the other half there; else none, "?": a source still waiting for its
    # destination, at the end of a run carried over several sheets)
    for _s, e in arrows:
        if out[id(e)] or group[id(e)][1] is None or \
                any(group[id(oc)] != group[id(e)] for _os, oc in arrows):
            continue
        out[id(e)] = [(os_, oc) for os_, oc in arrows
                      if oc.block != e.block and group[id(oc)] == group[id(e)]]
    for k in out:
        out[k].sort(key=key)
    return out


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
    joined = {s.id: _joined(project, s)[1] for s in project.sheets}
    key = _order(project)
    for dev, (s, parent) in index.items():
        if parent.attrs.get("XREF") == "0":
            continue
        # (a contact block joined to it by the dashed line isn't listed: the line shows it,
        # as in the owner's print, 0.19.10)
        items = sorted((c for c in children.get(dev, []) if c[1].attrs.get("XREF") != "0"
                        and c[1].id not in joined.get(c[0].id, ())), key=key)
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
        pairs = arrow_pairs(project, ends) if any(c.block in ARROWS for _s, c in ends) else {}
        for s, c in ends:
            hh = hk[s.id]
            pair = [(os_, oc) for os_, oc in ends if oc is not c]
            if c.block in ARROWS:
                # (an arrow shows only its other half's place: a source its next destination,
                # a destination its source, not the others of that name; the owner, 0.18.4:
                # "just the source and destination for that specific wire location", and
                # 0.19.5: "the exact previous or next wire")
                pair = pairs.get(id(c), [])
            others = [_where(project, os_, oc) for os_, oc in pair]
            text = ", ".join(others) if others else "?"
            if c.block not in ARROWS:
                # (outside the connector, away from its wire, whichever way it is turned: the
                # owner, 0.18, "Wire cross references need to always be outside the
                # connector, away from the wire")
                got = _outside(s, c, text, hh)
                if got is None:
                    bb = c.bbox()
                    got = ((bb[0] + bb[2]) / 2.0, bb[1] - GAP - hh)
                out[s.id].append((round(got[0], 6), round(got[1], 6), text, hh))
                continue
            # a source or destination arrow: its wire's number and the other's place
            # (2046 / 7-A2), past the arrow's far end, away from its wire (the owner, 0.17.5:
            # arrows "connected" to the line, so nothing written over it); and, on a second
            # line, the device at the other end of that wire (the owner, 0.19.3: "I can see
            # that the switch connection goes to page x but also that it goes to device x")
            num = number_at(s, c)
            if num:
                text = "%s / %s" % (num, text)
            lines = [text]
            if shows_device(project, s, c):
                far = []
                for os_, oc in pair:
                    n = far_device(os_, oc)
                    if n and n not in far:
                        far.append(n)
                if far:
                    lines.append(", ".join(far))
            for item in _arrow_lines(s, c, lines, hh):
                out[s.id].append(item)
    for s, c in contacts:
        if tags.number_attr(c) == "TERM":
            continue                    # (a terminal shows its number, not where its strip is;
            #                              an outlet shows where its distribution block is)
        if c.id in joined[s.id]:
            continue                    # (joined to its device by the dashed line)
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


LINKED = ("PB", "SS")            # contact blocks drawn joined to their device (xrefs.links)
_links = {"sig": None, "by_sheet": {}}


def links(project, sheet):
    """The dashed lines joining a pushbutton (an emergency stop, a selector switch) to its
    contact blocks in the same column on its sheet, as one operator works them all: [(a, b)],
    from the device through the farthest block (the owner, 0.19.10, his print's E-stop with
    two NC blocks and an NO one; asked: drawn by itself when stacked, following them when
    they move). Worked out from the drawing, as the cross-references are."""
    return _joined(project, sheet)[0]


def _joined(project, sheet):
    """(links, ids of the contact blocks they join) on one sheet, kept until it changes."""
    sig = _signature(project)
    if _links["sig"] != sig:
        _links["sig"], _links["by_sheet"] = sig, {}
    got = _links["by_sheet"].get(sheet.id)
    if got is None:
        got = _links["by_sheet"][sheet.id] = joined_now(sheet)
    return got


def joined_now(sheet):
    """(links, ids of the contact blocks they join) on one sheet, worked out now (not kept:
    the edit hook asks in the middle of an edit, model.Edit)."""
    out, ids = [], set()
    parents, blocks = {}, []
    for e in sheet.inserts():
        d = e.defn
        if d is None or d.kind != "symbol":
            continue
        if d.role == "parent" and e.attrs.get("DEV"):
            parents[e.attrs["DEV"]] = e
        elif d.role == "child" and d.prefix in LINKED and e.attrs.get("PARENT"):
            blocks.append(e)
    tol = 1e-3 * sheet.k()
    by_parent = {}
    for b in blocks:
        par = parents.get(b.attrs["PARENT"])
        if par is not None:
            by_parent.setdefault(par.attrs["DEV"], (par, []))[1].append(b)
    for par, kids in by_parent.values():
        across = abs(math.sin(math.radians(par.angle))) < 1e-9  # (rungs across: a column)
        ax = 0 if across else 1                                  # (the coordinate kept)
        col = [b for b in kids if abs(b.pos[ax] - par.pos[ax]) <= tol and
               abs(math.sin(math.radians(b.angle - par.angle))) < 1e-9]
        if not col:
            continue
        ids.update(b.id for b in col)
        along = [b.pos[1 - ax] for b in col] + [par.pos[1 - ax]]
        lo, hi = min(along), max(along)
        if across:
            out.append(((par.pos[0], lo), (par.pos[0], hi)))
        else:
            out.append(((lo, par.pos[1]), (hi, par.pos[1])))
    return out, ids


def sync_block_tags(ed, sheets):
    """Contact blocks on a dashed line show no tag of their own, as in the owner's print (the
    line shows where they belong; the owner, 0.19.11: "Yes"); one taken off the line shows it
    again. Only a tag hidden here (TAGLINK) comes back: one hidden by hand stays hidden."""
    for s in sheets:
        _lines, ids = joined_now(s)
        for e in list(s.inserts()):
            d = e.defn
            if d is None or d.role != "child" or d.prefix not in LINKED:
                continue
            mine = e.attrs.get("TAGLINK") == "1"
            if e.id in ids and "TAG" not in e.hidden:
                attrs = dict(e.attrs, TAGLINK="1")
                ed.change(s, e.copy(hidden=frozenset(e.hidden) | {"TAG"}, attrs=attrs))
            elif e.id not in ids and mine:
                attrs = dict(e.attrs)
                attrs.pop("TAGLINK", None)
                ed.change(s, e.copy(hidden=frozenset(e.hidden) - {"TAG"}, attrs=attrs))


def dashes(a, b, k=1.0):
    """A dashed line from a to b as its dashes: [(p, q)], 1/16 inch dashes and gaps on paper."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L <= 1e-12:
        return []
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    d = 0.0625 * k
    out, t = [], 0.0
    while t < L:
        e = min(t + d, L)
        out.append(((a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e)))
        t += 2 * d
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


def _arrow_lines(sheet, c, lines, hh):
    """An arrow's reference as drawn, a line each: placed as one block (its widest line),
    the second line on the side away from the arrow, each line starting at the arrow's side
    of the block (a long second line doesn't push the first one away). On a wire running up
    and down the text is turned with it (the owner, 0.18.3: "I need the verbiage to be the
    same orientation as I make the arrow")."""
    widths = [text_width(t, hh) for t in lines]
    wide = lines[widths.index(max(widths))]
    tw = max(widths)
    bb = c.bbox()
    step = hh * LINE
    # (the whole block clear of the wire, not its first line alone: a second line over the
    # arrow grew up onto a wire looping round it, the battery, 0.19.11, seed 152)
    extra = step * (len(lines) - 1)
    got = _along(sheet, c, wide, hh, extra)
    if got is not None:
        # (turned 90 degrees: a line under another is to its right, a line's length runs up)
        x0, y0 = got
        if x0 < (bb[0] + bb[2]) / 2.0 - 1e-9:
            x0 -= step * (len(lines) - 1)        # (left of the arrow: the block grows left)
        tb = text_item((x0, y0, wide, hh, 90.0)).bbox()
        out = []
        for i, (t, w) in enumerate(zip(lines, widths)):
            dy = 0.0
            if tb[1] >= bb[3] - 1e-9:
                dy = (w - tw) / 2.0              # (past the tip upward: from its bottom end)
            elif tb[3] <= bb[1] + 1e-9:
                dy = (tw - w) / 2.0              # (past the tip downward: from its top end)
            out.append((round(x0 + i * step, 6), round(y0 + dy, 6), t, hh, 90.0))
        return out
    got = _outside(sheet, c, wide, hh, extra)
    if got is None:
        got = ((bb[0] + bb[2]) / 2.0, bb[1] - GAP - hh)
    x0, y0 = got
    if y0 > bb[3] - 1e-9:
        y0 += step * (len(lines) - 1)            # (over the arrow: the block grows up)
    out = []
    for i, (t, w) in enumerate(zip(lines, widths)):
        dx = 0.0
        if x0 - tw / 2.0 >= bb[2] - 1e-9:
            dx = (w - tw) / 2.0                  # (right of the arrow: from its left end)
        elif x0 + tw / 2.0 <= bb[0] + 1e-9:
            dx = (tw - w) / 2.0                  # (left of it: from its right end)
        out.append((round(x0 + dx, 6), round(y0 - i * step, 6), t, hh))
    return out


def text_item(item):
    """A reference as drawn (x, y, text, height[, angle]): a centered Text."""
    return Text((item[0], item[1]), item[2], item[3], item[4] if len(item) > 4 else 0.0,
                "center")


def _along(sheet, c, text, hh, extra=0.0):
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
            tb = _grown(Text(q, text, hh, 90.0, "center").bbox(), extra, 0,
                        q[0] + off[0] < (bb[0] + bb[2]) / 2.0)
            if not any(segment_hits_rect(a, b, tb)
                       for a, b in zip(wire.points, wire.points[1:])):
                return q
    return (tip[0][0] - off[0], tip[0][1] - off[1])


def _grown(tb, extra, axis, back):
    """A text's box grown by extra (the lines under its first: a block of lines) the way the
    block grows: along x (turned text) or y; back: toward smaller x (left of the arrow) or,
    level, upward is the other way (over the arrow the block grows up)."""
    if extra <= 0:
        return tb
    x0, y0, x1, y1 = tb
    if axis == 0:
        return (x0 - extra, y0, x1, y1) if back else (x0, y0, x1 + extra, y1)
    return (x0, y0, x1, y1 + extra) if back else (x0, y0 - extra, x1, y1)


def _outside(sheet, c, text, hh, extra=0.0):
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
            tb = _grown(Text(q, text, hh, 0.0, "center").bbox(), extra, 1, q[1] > bb[3] - 1e-9)
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
