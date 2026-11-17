"""Wire numbers (no Qt): the page number and three digits, 6001, one per connected group of
wires.

- A group is every wire joined end to end or end to middle (a T). A symbol's pins don't join
  wires: the number changes through a device or a terminal.
- Off-sheet connectors (blocks whose wiring is "link") with the same name join their wires
  into one group, whatever sheets they're on: it keeps the number of the sheet it starts on
  (the first in the project's order).
- Through a distribution block (wiring "distribution"), the wires on its other pins take the
  number of the wire on its first pin with A, B, C... added (6001A, 6001B... Z, AA, AB...).
- Numbers are given in each sheet's numbering order (across then down, or down then across)
  and kept: drawing more doesn't renumber what's there. A group without one takes the lowest
  free number of its page (deleted numbers come back). When two groups join, the lower
  number stays; when a group splits, the part later in order takes a new one. A number whose
  page isn't its group's page any more (the sheet was renumbered) follows, like device tags.
- A number typed by hand is locked (Wire.num_lock): numbering leaves it alone.
- Renumber sheet numbers the sheet's unlocked groups again, 001, 002... in order.

The number shows above the group's longest straight piece on each sheet it's on (labels()).
Project setting "wire_numbers" (on to start) turns all of it off.
"""

import math
import re
from functools import lru_cache

from . import tags
from .model import Text

TOL = 1e-6
_NUM = re.compile(r"(\d+?)(\d{3})([A-Z]*)")


def enabled(project):
    return bool(project.settings.get("wire_numbers", True))


@lru_cache(maxsize=65536)
def split(num):
    """(page, count, suffix) of a wire number, or None."""
    m = _NUM.fullmatch(num or "")
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None


def make(page, count, suffix=""):
    return "%s%03d%s" % (page, count, suffix)


def letters(i):
    """0 -> A, 25 -> Z, 26 -> AA, 27 -> AB..."""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


# ---- groups ---------------------------------------------------------------------------------
class _Union:
    def __init__(self):
        self.up = {}

    def find(self, a):
        self.up.setdefault(a, a)
        while self.up[a] != a:
            self.up[a] = self.up[self.up[a]]
            a = self.up[a]
        return a

    def join(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.up[rb] = ra


def _touching(sheet, p):
    return sheet.query_point(p, TOL)


def _adjacent(sheet, w):
    """Ids of the wires w connects with: one whose middle or end w ends on, or one that ends
    on w (its middle or end)."""
    def tapped(a, p, b):
        # (a's end p on b's middle, a with a number of its own: not one group for numbering,
        # the owner, 0.17.2)
        return a.own_num and not any(abs(p[0] - q[0]) <= TOL and abs(p[1] - q[1]) <= TOL
                                     for q in (b.points[0], b.points[-1]))
    out = set()
    for p in (w.points[0], w.points[-1]):
        for o in _touching(sheet, p):
            if o is not w and o.kind == "wire" and o.touches(p, TOL) and not tapped(w, p, o):
                out.add(o.id)
    x0, y0, x1, y1 = w.bbox()
    for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if o is w or o.kind != "wire" or o.id in out:
            continue
        for p in (o.points[0], o.points[-1]):
            if w.touches(p, TOL) and not tapped(o, p, w):
                out.add(o.id)
                break
    return out


def taps(sheet, w):
    """The wire w taps off (one of w's ends on the middle of it, not its end), or None."""
    for p in (w.points[0], w.points[-1]):
        for o in _touching(sheet, p):
            if o is w or o.kind != "wire" or o.id == w.id or not o.touches(p, TOL):
                continue
            if not any(abs(p[0] - q[0]) <= TOL and abs(p[1] - q[1]) <= TOL
                       for q in (o.points[0], o.points[-1])):
                return o
    return None


def _sheet_groups(sheet):
    """Wires of one sheet joined end to end / end to middle: {wire id: root id} (kept per
    sheet version). Which wires connect is kept per sheet and brought up to date for the
    wires an edit added, changed or removed only (entities are values: a changed wire is a
    new object), so an edit on a big sheet doesn't measure every wire again."""
    got = getattr(sheet, "_wire_groups", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    cur = {w.id: w for w in sheet.wires()}
    st = getattr(sheet, "_wire_adj", None)
    if st is None:
        adj = {i: _adjacent(sheet, w) for i, w in cur.items()}
    else:
        old, adj = st
        # (a wire whose points are the same, its number changed say, connects the same)
        stale = [i for i, w in cur.items() if old.get(i) is not w and
                 (old.get(i) is None or old[i].points != w.points or
                  old[i].own_num != w.own_num)]
        stale += [i for i in old if i not in cur]
        for i in stale:
            for n in adj.pop(i, ()):
                ns = adj.get(n)
                if ns is not None:
                    ns.discard(i)
        for i in stale:
            w = cur.get(i)
            if w is None:
                continue
            a = _adjacent(sheet, w)
            adj[i] = a
            for n in a:
                adj.setdefault(n, set()).add(i)
    sheet._wire_adj = (cur, adj)
    out = {}
    for i in cur:                       # (each group named by its lowest wire id)
        if i in out:
            continue
        comp, todo = [i], [i]
        out[i] = i
        while todo:
            for n in adj.get(todo.pop(), ()):
                if n not in out:
                    out[n] = i
                    comp.append(n)
                    todo.append(n)
        root = min(comp)
        if root != i:
            for n in comp:
                out[n] = root
    sheet._wire_groups = (sheet.version, out)
    return out


def _pin_wires(sheet, ins, roots):
    """{pin name: sheet-local group root} of the wires ending on each of the symbol's pins."""
    out = {}
    for name, p in ins.pin_points():
        for o in _touching(sheet, p):
            if o.kind == "wire" and o.id in roots and o.touches(p, TOL):
                out.setdefault(name, roots[o.id])
    return out


def _summary(sheet):
    """What numbering needs to know of one sheet, kept until the sheet changes: its local
    groups {root: (sort key, [wires], [numbers], locked number or None)}, its off-sheet
    connectors' groups [(name, root)] and its distribution blocks [(input root, [output
    roots])]."""
    sig = (sheet.version, sheet.number_order, sheet.size, sheet.cols, sheet.rows,
           sheet.col_start, sheet.row_start)
    got = getattr(sheet, "_num_summary", None)
    if got is not None and got[0] == sig:
        return got[1]
    roots = _sheet_groups(sheet)
    zsig = sig[1:] + (sheet.scale, sheet.reserve)
    cache = getattr(sheet, "_num_keys", None)
    if cache is None or cache[0] != zsig:
        cache = sheet._num_keys = (zsig, {})
    known = cache[1]
    key = tags.order_key(sheet, sheet.number_order)
    local = {}
    for w in sheet.wires():
        r = roots[w.id]
        q = min(w.points[0], w.points[-1])
        k = known.get(q)
        if k is None:
            k = known[q] = key(q)
        g = local.get(r)
        if g is None:
            local[r] = [k, [w], set(), None]
        else:
            if k < g[0]:
                g[0] = k
            g[1].append(w)
        g = local[r]
        if w.num:
            g[2].add(w.num)
            if w.num_lock and g[3] is None:
                g[3] = w.num
    local = {r: (g[0], g[1], sorted(g[2], key=_count), g[3]) for r, g in local.items()}
    links, dists = [], []
    for ins in sheet.inserts():
        d = ins.defn
        if d is None or not d.wiring:
            continue
        at = _pin_wires(sheet, ins, roots)
        if d.wiring == "link":
            name = ins.attrs.get("TAG", "").strip().upper()
            if name:
                links += [(name, r) for r in at.values()]
        elif d.wiring == "distribution" and d.pins and d.pins[0]["name"] in at:
            dists.append((at[d.pins[0]["name"]],
                          [at[p["name"]] for p in d.pins[1:] if p["name"] in at]))
    out = (local, links, dists)
    sheet._num_summary = (sig, out)
    return out


def _count(num):
    got = split(num)
    return got[1] if got else 0


def groups(project):
    """({group key: [(sheet, wire)...]}, distribution links [(input group, [output groups in
    pin order])]) of the whole project."""
    gs, _info, dist = _assemble(project)
    return {k: [(s, w) for s, ws in nodes for w in ws] for k, nodes in gs.items()}, dist


def _assemble(project):
    """Local groups joined across sheets by off-sheet connectors: {group key: [(sheet,
    [wires])]}, {group key: [home order, page sheet, numbers, locked]}, distribution links."""
    u = _Union()
    names = {}
    sums = []
    for i, s in enumerate(project.sheets):
        local, links, dists = _summary(s)
        sums.append((i, s, local, dists))
        for name, r in links:
            names.setdefault(name, []).append((s.id, r))
    for nodes in names.values():
        for n in nodes[1:]:
            u.join(nodes[0], n)
    find = (lambda n: u.find(n) if n in u.up else n)
    gs, info = {}, {}
    for i, s, local, _d in sums:
        for r, (k, ws, nums, locked) in local.items():
            g = find((s.id, r))
            gs.setdefault(g, []).append((s, ws))
            order = (i, k)
            cur = info.get(g)
            if cur is None:
                info[g] = [order, s, list(nums), locked]
            else:
                if order < cur[0]:
                    cur[0], cur[1] = order, s
                cur[2] = sorted(set(cur[2]) | set(nums), key=_count)
                cur[3] = cur[3] or locked
    dist = []
    for _i, s, _local, dists in sums:
        for a, bs in dists:
            dist.append((find((s.id, a)), [find((s.id, b)) for b in bs]))
    return gs, info, dist


# ---- numbering -------------------------------------------------------------------------------
def sync(ed, project, renumber=None):
    """Give every group its number (see the module's notes); renumber: a sheet whose
    unlocked groups are numbered again from 001."""
    if not enabled(project):
        return
    gs, info, dist = _assemble(project)
    order = sorted(info, key=lambda g: info[g][0])
    page = {}
    taken = {}                                  # page -> counts used
    fixed = {}                                  # group -> number (locked)
    for g in order:
        page[g] = project.sheet_number(info[g][1])
        locked = info[g][3]
        if locked:
            fixed[g] = locked
            got = split(locked)
            if got:
                taken.setdefault(got[0], set()).add(got[1])
    outputs = {}
    for src, outs in dist:
        for i, o in enumerate(outs):
            if o != src:
                outputs.setdefault(o, (src, i))
    want = dict(fixed)
    # groups keep a number of theirs when it's right (of their page, not taken earlier)
    todo = []
    for g in order:
        if g in want or g in outputs:
            continue
        pg = page[g]
        mine = taken.setdefault(pg, set())
        have = [] if renumber is not None and info[g][1] is renumber else info[g][2]
        for n in have:
            got = split(n)
            if got and got[0] == pg and not got[2] and got[1] not in mine:
                want[g] = n
                mine.add(got[1])
                break
        else:
            todo.append(g)
    nxt = {}
    for g in todo:                              # (in order: the lowest free numbers)
        pg = page[g]
        used = taken.setdefault(pg, set())
        n = nxt.get(pg, 1)
        while n in used:
            n += 1
        used.add(n)
        nxt[pg] = n + 1
        want[g] = make(pg, n)
    # distribution outputs: the input's number with a letter (chains follow, in order)
    for _ in range(len(outputs) + 1):
        changed = False
        for o, (src, i) in outputs.items():
            if o in fixed:
                continue
            base = want.get(src)
            if base:
                v = base + letters(i)
                if want.get(o) != v:
                    want[o] = v
                    changed = True
        if not changed:
            break
    for g, nodes in gs.items():
        num = want.get(g)
        if num is None:
            continue
        nums = info[g][2]
        if len(nums) == 1 and nums[0] == num and all(
                w.num == num for _s, ws in nodes for w in ws):
            continue
        for s, ws in nodes:
            for w in ws:
                if w.num != num:
                    ed.change(s, w.copy(num=num, num_lock=w.num_lock and g in fixed))


def set_number(ed, project, sheet, wire, num, lock=True):
    """A number typed for the group of wire, locked (or not: numbering may change it, the
    owner, 0.17.5: "should there be a checkbox to check locked or unlocked?"), or "" to give
    it back to numbering."""
    gs, _dist = groups(project)
    for ws in gs.values():
        if any(s is sheet and w.id == wire.id for s, w in ws):
            for s, w in ws:
                ed.change(s, w.copy(num=num or None, num_lock=bool(num) and lock))
            return


# ---- a number typed that another wire has: a cross-reference (0.17.5) ------------------------
def group_of(project, sheet, wire):
    """(group key, [(sheet, wire)]) of the group wire is in, or None."""
    gs, _dist = groups(project)
    for k, ws in gs.items():
        if any(s is sheet and w.id == wire.id for s, w in ws):
            return k, ws
    return None


def others_numbered(project, sheet, wire, num):
    """The groups other than wire's whose wires carry num: [(group key, [(sheet, wire)])]."""
    gs, _dist = groups(project)
    mine = group_of(project, sheet, wire)
    return [(k, ws) for k, ws in gs.items() if (mine is None or k != mine[0])
            and any(w.num == num for _s, w in ws)]


def open_end(nodes, first=None):
    """(sheet, point, direction out) of a wire end in nodes ([(sheet, wire)]) that connects
    to nothing (no pin, no other wire): where a connector goes. first: a wire to look at
    before the others (the one double-clicked). None when every end is connected."""
    from .wires import connects_at
    order = sorted(nodes, key=lambda t: 0 if first is not None and t[1].id == first.id else 1)
    for s, w in order:
        for i, j in ((-1, -2), (0, 1)):
            q, r = w.points[i], w.points[j]
            if not connects_at(s, q, exclude=w.id):
                L = math.hypot(q[0] - r[0], q[1] - r[1]) or 1.0
                return s, tuple(q), ((q[0] - r[0]) / L, (q[1] - r[1]) / L)
    return None


ARROWS = ("Source arrow", "Destination arrow")


def number_at(sheet, ins):
    """The number of the wire on a connector's pin ("" when none)."""
    for _n, q in ins.pin_points():
        for w in sheet.query_point(q, TOL):
            if getattr(w, "kind", "") == "wire" and w.num and w.touches(q, TOL):
                return w.num
    return ""


def new_link_name(project):
    """The lowest connector name nobody uses yet (A, B... Z, AA...)."""
    got = connectors(project)
    i = 0
    while letters(i) in got:
        i += 1
    return letters(i)


def cross_reference(ed, project, here, there, out_def, in_def, source):
    """Join two wire ends by a pair of off-sheet connectors of a new name: here and there are
    (sheet, point, direction out) (open_end); source: here is where the wire leaves (an
    Source arrow, pointing out) and there where it arrives (Destination arrow);
    else the other way round. Each sits on its end, turned to point along the wire. Returns
    the name."""
    from .model import Insert, Layer, ADAPTIVE
    name = new_link_name(project)
    for (s, q, d), defn in ((here, out_def if source else in_def),
                            (there, in_def if source else out_def)):
        if defn.name not in project.blocks:
            ed.block(defn)
        d2 = project.blocks[defn.name]
        tag_h = project.settings.get("tag_height", 0.1) * s.k()
        ins = Insert(d2.name, q, math.degrees(math.atan2(d[1], d[0])) % 360.0, 1.0, False,
                     {"TAG": name}, d2, tag_h, layer="SYMBOLS")
        if ins.layer not in project.layers:
            ed.layer(ins.layer, None, Layer(ins.layer, ADAPTIVE).to_dict())
        ed.add(s, ins)
    return name


# ---- showing ---------------------------------------------------------------------------------
def labels(project, sheet):
    """The wire numbers shown on a sheet: one per group part, above (or left of, when
    upright) its longest straight piece; a wire of it longer than the project's
    "wire_label_ends" (paper inches; 0: off) shows it near both its ends instead (the owner,
    0.17.2: "On long stretches of wire, I need to be able to insert wire labels in multiple
    places, preferably automatically but also manually"); and each wire again where Wire
    number label put one (Wire.labels). Worked out, never stored: the number is always the
    wire's own."""
    if not enabled(project) or sheet is project.title_block:
        return []
    got = getattr(sheet, "_num_labels", None)
    ends_at = float(project.settings.get("wire_label_ends", 6.0) or 0.0)
    sig = (sheet.version, sheet.scale, project.settings.get("wire_number_height", 0.08),
           ends_at)
    if got is not None and got[0] == sig:
        return got[1]
    k = sheet.k()
    h = float(project.settings.get("wire_number_height", 0.08)) * k
    roots = _sheet_groups(sheet)
    parts = {}
    for w in sheet.wires():
        if w.num:
            parts.setdefault((roots[w.id], w.num), []).append(w)
    out = []
    busy = _busy_points(sheet)

    def put(num, q, a, b):
        if abs(a[1] - b[1]) > abs(a[0] - b[0]):
            out.append(Text((q[0] - h * 0.4, q[1]), num, h, 90.0, "center"))
        else:
            out.append(Text((q[0], q[1] + h * 0.4), num, h, 0.0, "center"))
    for (_r, num), ws in parts.items():
        ended = False
        if ends_at > 0:
            for w in ws:
                L = w.length()
                if L <= ends_at * k:
                    continue
                # (near each end: an inch in on paper, or a quarter of a shorter run's way)
                d = min(1.0 * k, L / 4.0)
                for t in (d, L - d):
                    q, i = w.at_length(t)
                    put(num, q, w.points[i], w.points[i + 1])
                ended = True
        for w in ws:
            for t in w.labels:
                if t <= w.length() + 1e-9:
                    q, i = w.at_length(t)
                    put(num, q, w.points[i], w.points[i + 1])
        if ended:
            continue
        best = None
        for w in ws:
            for a, b in zip(w.points, w.points[1:]):
                d = abs(a[0] - b[0]) + abs(a[1] - b[1])
                if best is None or d > best[0]:
                    best = (d, a, b)
        if best is None:
            continue
        _d, a, b = best
        put(num, _clear_spot(a, b, busy), a, b)
    sheet._num_labels = (sig, out)
    return out


def gauge_labels(project, sheet):
    """A wire layer's gauge and color (Layers: AWG, Wire color) beside its wires: one label
    per run of joined wires on the layer, on its longest straight piece, on the other side of
    the wire from its number (under it, or right of it when upright), a little smaller."""
    if not project.settings.get("wire_gauge_shown", True) or sheet is project.title_block:
        return []
    shown = {n: lay.wire_label() for n, lay in project.layers.items() if lay.wire_label()}
    if not shown:
        return []
    h = float(project.settings.get("wire_number_height", 0.08)) * sheet.k()
    sig = (sheet.version, sheet.scale, h, tuple(sorted(shown.items())))
    got = getattr(sheet, "_gauge_labels", None)
    if got is not None and got[0] == sig:
        return got[1]
    roots = _sheet_groups(sheet)
    parts = {}
    for w in sheet.wires():
        if w.layer in shown:
            parts.setdefault((roots.get(w.id, w.id), w.layer), []).append(w)
    busy = _busy_points(sheet)
    out = []
    for (_r, layer), ws in parts.items():
        best = None
        for w in ws:
            for a, b in zip(w.points, w.points[1:]):
                d = abs(a[0] - b[0]) + abs(a[1] - b[1])
                if best is None or d > best[0]:
                    best = (d, a, b)
        if best is None:
            continue
        _d, a, b = best
        mx, my = _clear_spot(a, b, busy)
        g = h * 0.85
        if abs(a[1] - b[1]) > abs(a[0] - b[0]):
            out.append(Text((mx + h * 0.4 + g, my), shown[layer], g, 90.0, "center"))
        else:
            out.append(Text((mx, my - h * 0.4 - g), shown[layer], g, 0.0, "center"))
    sheet._gauge_labels = (sig, out)
    return out


_CELL = 0.5


def _busy_points(sheet):
    """Where wires cross or join on a sheet, in cells of _CELL inches: {cell: [point]}."""
    from . import crossings, wires
    out = {}
    pts = [p for p, _s, _o in crossings.found(sheet)] + list(wires.junctions(sheet))
    for p in pts:
        out.setdefault((int(p[0] // _CELL), int(p[1] // _CELL)), []).append(p)
    return out


def _clear_spot(a, b, busy):
    """The middle of the longest stretch of the piece a-b with no crossing or junction on it
    (so a wire number doesn't sit on a crossing's gap or loop, or on a dot); the middle of the
    piece when nothing is on it."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-9:
        return a
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    ts = [0.0, L]
    i0, i1 = sorted((int(a[0] // _CELL), int(b[0] // _CELL)))
    j0, j1 = sorted((int(a[1] // _CELL), int(b[1] // _CELL)))
    if (i1 - i0 + 3) * (j1 - j0 + 3) > len(busy):
        # (a piece longer than the cells in use: those cells, not every one along it; a wire
        # a million inches long took two million steps on every repaint, the Linux build's
        # battery, seed 306)
        near = [q for (i, j), qs in busy.items()
                if i0 - 1 <= i <= i1 + 1 and j0 - 1 <= j <= j1 + 1 for q in qs]
    else:
        near = [q for i in range(i0 - 1, i1 + 2) for j in range(j0 - 1, j1 + 2)
                for q in busy.get((i, j), ())]
    for q in near:
        t = (q[0] - a[0]) * ux + (q[1] - a[1]) * uy
        if 1e-6 < t < L - 1e-6 and abs((q[0] - a[0]) * uy - (q[1] - a[1]) * ux) <= 1e-6:
            ts.append(t)
    if len(ts) == 2:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    ts.sort()
    gaps = [(ts[k + 1] - ts[k], -abs((ts[k] + ts[k + 1]) / 2 - L / 2), k)
            for k in range(len(ts) - 1)]
    _g, _c, k = max(gaps)
    t = (ts[k] + ts[k + 1]) / 2
    return (a[0] + ux * t, a[1] + uy * t)


# ---- off-sheet connectors -------------------------------------------------------------------
def connectors(project):
    """{name: [(sheet, connector)]} of the project's off-sheet connectors."""
    out = {}
    for s in project.sheets:
        for e in s.inserts():
            if e.defn is not None and e.defn.wiring == "link":
                name = e.attrs.get("TAG", "").strip().upper()
                if name:
                    out.setdefault(name, []).append((s, e))
    return out


def next_name(project, sheet):
    """The name offered for a new connector: one waiting for its other end on another sheet
    (the first in order), else the lowest unused A, B... Z, AA..."""
    got = connectors(project)
    for name in sorted(got, key=lambda n: (len(n), n)):
        ends = got[name]
        if len(ends) == 1 and ends[0][0] is not sheet:
            return name
    i = 0
    while letters(i) in got:
        i += 1
    return letters(i)
