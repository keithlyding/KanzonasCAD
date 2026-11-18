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

from . import geometry as G
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


def _same_pt(p, q):
    return abs(p[0] - q[0]) <= TOL and abs(p[1] - q[1]) <= TOL


def _unit(p, q):
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = (dx * dx + dy * dy) ** 0.5
    return (dx / d, dy / d) if d > 1e-12 else None


def _legs(w, p):
    """The ways w leaves p (unit vectors), and how p is on w: "end", "corner" (one of its
    bends) or "middle" (along a straight piece)."""
    pts = w.points
    if _same_pt(p, pts[0]) or _same_pt(p, pts[-1]):
        seq = pts if _same_pt(p, pts[0]) else pts[::-1]
        for q in seq[1:]:
            u = _unit(p, q)
            if u is not None:
                return [u], "end"
        return [], "end"
    for q in pts[1:-1]:
        if _same_pt(p, q):
            k = next(i for i, r in enumerate(pts) if _same_pt(p, r))
            legs = [u for u in (_unit(p, pts[k - 1]), _unit(p, pts[k + 1])) if u is not None]
            return legs, "corner"
    for q, r in zip(pts, pts[1:]):
        if G.dist_to_segment(p, q, r) <= TOL:
            u = _unit(q, r)
            if u is not None:
                return [u, (-u[0], -u[1])], "middle"
    return [], "middle"


def _straight(u, v):
    return u[0] * v[0] + u[1] * v[1] < -0.999


def tap_at(sheet, a, p, b):
    """a's end p, on wire b: is a tapped off b there? On b's middle, yes. On one of b's
    bends, unless a carries straight on from b's piece there (b then is the one turning off:
    both one run). End to end, a is a tap when two other ends there make a straight run
    through p and b is one of them (a bus ending at a drop and going on: the owner's
    drawing, 0.18.3, M207's L1)."""
    la, _ = _legs(a, p)
    lb, how = _legs(b, p)
    if how == "middle":
        return True
    if not la:
        return False
    if how == "corner":
        return not any(_straight(la[0], u) for u in lb)
    ends = []
    for o in _touching(sheet, p):
        if o.kind == "wire" and (_same_pt(p, o.points[0]) or _same_pt(p, o.points[-1])):
            got, _ = _legs(o, p)
            if got:
                ends.append((o.id, got[0]))
    runs = [(x, y) for i, (x, u) in enumerate(ends) for y, v in ends[i + 1:]
            if _straight(u, v)]
    if len(runs) != 1:
        return False
    return a.id not in runs[0] and b.id in runs[0]


def _adjacent(sheet, w, split_taps=False, tapped_out=None):
    """Ids of the wires w connects with: one whose middle or end w ends on, or one that ends
    on w (its middle or end). split_taps: a wire tapped off another (tap_at) is not joined to
    it (numbered apart: tap_numbers "suffix" or "own") unless it keeps that wire's number
    (same_num). tapped_out: a dict given {(tap id, tapped id): the tap's end there} of the
    taps kept apart, w's own and those off w."""
    def apart(a, p, b):
        # (a's end p tapped off b, a with a number of its own: not one group for numbering,
        # the owner, 0.17.2)
        return (a.own_num or (split_taps and not a.same_num)) and tap_at(sheet, a, p, b)
    near = {}
    for p in (w.points[0], w.points[-1]):
        for o in _touching(sheet, p):
            if o is not w and o.kind == "wire" and o.touches(p, TOL):
                near[o.id] = o
    x0, y0, x1, y1 = w.bbox()
    for o in sheet.query((x0 - TOL, y0 - TOL, x1 + TOL, y1 + TOL)):
        if o is not w and o.kind == "wire" and o.id not in near and any(
                w.touches(q, TOL) for q in (o.points[0], o.points[-1])):
            near[o.id] = o
    out = set()
    for o in near.values():
        # (each place they meet: joined there unless one is tapped off the other; one end
        # joined and the other tapping is a tap too, the battery, 0.18.3, seed 37)
        pts = [p for p in (w.points[0], w.points[-1]) if o.touches(p, TOL)]
        pts += [q for q in (o.points[0], o.points[-1]) if w.touches(q, TOL) and
                not any(_same_pt(q, r) for r in pts)]
        for p in pts:
            tw = (_same_pt(p, w.points[0]) or _same_pt(p, w.points[-1])) and apart(w, p, o)
            to = (_same_pt(p, o.points[0]) or _same_pt(p, o.points[-1])) and apart(o, p, w)
            if tw and tapped_out is not None:
                _note_tap(tapped_out, (w.id, o.id), p)
            if to and tapped_out is not None:
                _note_tap(tapped_out, (o.id, w.id), p)
            if not tw and not to:
                out.add(o.id)
    return out


def _note_tap(found, k, p):
    """A tap (tap id, tapped id) at p kept, at the lower of its ends when both tap: the same
    whichever wire is looked at first."""
    p = tuple(p)
    q = found.get(k)
    if q is None or p < q:
        found[k] = p


def taps(sheet, w):
    """The wire w taps off (tap_at, at one of w's ends), or None."""
    for p in (w.points[0], w.points[-1]):
        for o in _touching(sheet, p):
            if o is w or o.kind != "wire" or o.id == w.id or not o.touches(p, TOL):
                continue
            if tap_at(sheet, w, p, o):
                return o
    return None


def tap_mode(project):
    """How a wire tapped off another is numbered: "same", "suffix" or "own"."""
    m = project.settings.get("tap_numbers", "same")
    return m if m in ("same", "suffix", "own") else "same"


def _sheet_groups(sheet, split_taps=False):
    """Wires of one sheet joined end to end / end to middle: {wire id: root id} (kept per
    sheet version). Which wires connect is kept per sheet and brought up to date for the
    wires an edit added, changed or removed only (entities are values: a changed wire is a
    new object), so an edit on a big sheet doesn't measure every wire again."""
    sfx = "_split" if split_taps else ""
    got = getattr(sheet, "_wire_groups" + sfx, None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    cur = {w.id: w for w in sheet.wires()}
    st = getattr(sheet, "_wire_adj" + sfx, None)
    if st is None:
        pairs = {}
        adj = {i: _adjacent(sheet, w, split_taps, pairs) for i, w in cur.items()}
    else:
        old, adj, pairs = st
        # (a wire whose points are the same, its number changed say, connects the same)
        stale = [i for i, w in cur.items() if old.get(i) is not w and
                 (old.get(i) is None or old[i].points != w.points or
                  old[i].own_num != w.own_num or old[i].same_num != w.same_num)]
        stale += [i for i in old if i not in cur]
        # (and the wires ending where they end, before and after: whether a drop there is a
        # tap depends on every end there, a run straight through; tap_at)
        more = set()
        for i in stale:
            for x in (old.get(i), cur.get(i)):
                if x is None:
                    continue
                for q in (x.points[0], x.points[-1]):
                    more.update(o.id for o in _touching(sheet, q)
                                if o.kind == "wire" and o.id in cur)
        have = set(stale)
        stale += [i for i in more if i not in have]
        for i in stale:
            for n in adj.pop(i, ()):
                ns = adj.get(n)
                if ns is not None:
                    ns.discard(i)
        if pairs and stale:
            gone = set(stale)
            for k in [k for k in pairs if k[0] in gone or k[1] in gone]:
                del pairs[k]
        for i in stale:
            w = cur.get(i)
            if w is None:
                continue
            a = _adjacent(sheet, w, split_taps, pairs)
            adj[i] = a
            for n in a:
                adj.setdefault(n, set()).add(i)
    setattr(sheet, "_wire_adj" + sfx, (cur, adj, pairs))
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
    setattr(sheet, "_wire_groups" + sfx, (sheet.version, out))
    return out


def _pin_wires(sheet, ins, roots):
    """{pin name: sheet-local group root} of the wires ending on each of the symbol's pins."""
    out = {}
    for name, p in ins.pin_points():
        for o in _touching(sheet, p):
            if o.kind == "wire" and o.id in roots and o.touches(p, TOL):
                out.setdefault(name, roots[o.id])
    return out


def wire_order(project, sheet):
    """The numbering order wire numbers take on a sheet: the tags' (Sheet.number_order), or
    across and down when the sheet (or, as it says, the project) has them not follow it."""
    follow = sheet.wire_order_tags
    if follow is None:
        follow = bool(project.settings.get("wire_order_tags", True))
    if follow or sheet.number_order != "wires":
        return sheet.number_order
    return "across"


def _summary(sheet, how=None, taps_mode="same"):
    """What numbering needs to know of one sheet, kept until the sheet changes: its local
    groups {root: (sort key, [wires], [numbers], locked number or None)}, its off-sheet
    connectors' groups [(name, root)], its distribution blocks [(input root, [output
    roots])] and its taps [(tapped root, tap root, sort key of where it taps)] (tap_numbers
    "suffix": numbered from the wire they tap)."""
    how = how or sheet.number_order
    sig = (sheet.version, how, sheet.size, sheet.cols, sheet.rows,
           sheet.col_start, sheet.row_start, sheet.number_from, taps_mode)
    got = getattr(sheet, "_num_summary", None)
    if got is not None and got[0] == sig:
        return got[1]
    roots = _sheet_groups(sheet, taps_mode != "same")
    zsig = sig[1:] + (sheet.scale, sheet.reserve) + (
        (sheet.version,) if how == "wires" else ())
    cache = getattr(sheet, "_num_keys", None)
    if cache is None or cache[0] != zsig:
        cache = sheet._num_keys = (zsig, {})
    known = cache[1]
    key = tags.order_key(sheet, how)
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
    tapl = []
    if taps_mode == "suffix":
        # (the taps kept apart, found with the wires' connections: only the wires an edit
        # touched are looked at again; one per tap, off the lowest id it taps)
        ws = sheet.entities
        one = {}
        for (a, b), q in sheet._wire_adj_split[2].items():
            if a in roots and b in roots and (a not in one or b < one[a][0]):
                one[a] = (b, q)
        for a, (b, q) in one.items():
            if ws[a].own_num or roots[a] == roots[b]:
                continue                # (a number of its own, asked for: not from the wire)
            k = known.get(q)
            if k is None:
                k = known[q] = key(q)
            tapl.append((roots[b], roots[a], k))
    out = (local, links, dists, tapl)
    sheet._num_summary = (sig, out)
    return out


def _count(num):
    got = split(num)
    return got[1] if got else 0


def groups(project):
    """({group key: [(sheet, wire)...]}, distribution links [(input group, [output groups in
    pin order])]) of the whole project."""
    gs, _info, dist, _taps = _assemble(project)
    return {k: [(s, w) for s, ws in nodes for w in ws] for k, nodes in gs.items()}, dist


def _assemble(project):
    """Local groups joined across sheets by off-sheet connectors: {group key: [(sheet,
    [wires])]}, {group key: [home order, page sheet, numbers, locked]}, distribution links,
    taps [(tapped group, tap group, (sheet index, sort key))]."""
    u = _Union()
    names = {}
    sums = []
    mode = tap_mode(project)
    for i, s in enumerate(project.sheets):
        local, links, dists, tapl = _summary(s, wire_order(project, s), mode)
        sums.append((i, s, local, dists, tapl))
        for name, r in links:
            names.setdefault(name, []).append((s.id, r))
    for nodes in names.values():
        for n in nodes[1:]:
            u.join(nodes[0], n)
    find = (lambda n: u.find(n) if n in u.up else n)
    gs, info = {}, {}
    for i, s, local, _d, _t in sums:
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
    dist, tapped = [], []
    for i, s, _local, dists, tapl in sums:
        for a, bs in dists:
            dist.append((find((s.id, a)), [find((s.id, b)) for b in bs]))
        for a, b, k in tapl:
            tapped.append((find((s.id, a)), find((s.id, b)), (i, k)))
    return gs, info, dist, tapped


# ---- numbering -------------------------------------------------------------------------------
def sync(ed, project, renumber=None):
    """Give every group its number (see the module's notes); renumber: a sheet (or several:
    Update numbers and cross-references, 0.18) whose
    unlocked groups are numbered again from 001."""
    if not enabled(project):
        return
    gs, info, dist, tapped = _assemble(project)
    again = [] if renumber is None else [renumber] if not isinstance(renumber, (list, tuple,
                                                                               set)) \
        else list(renumber)
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
                outputs.setdefault(o, (src, letters(i)))
    # taps (tap_numbers "suffix"): the tapped wire's number with -1, -2... in the numbering
    # order of where they tap; a tap off a tap, a, b...
    by_src = {}
    for src, o, k in sorted(tapped, key=lambda t: t[2]):
        if o != src and o not in outputs and o not in by_src.get(src, ()):
            by_src.setdefault(src, []).append(o)
    for src, outs in by_src.items():
        for i, o in enumerate(outs):
            outputs.setdefault(o, (src, i, "tap"))
    _break_loops(outputs, info)
    want = dict(fixed)
    # groups keep a number of theirs when it's right (of their page, not taken earlier)
    todo = []
    for g in order:
        if g in want or g in outputs:
            continue
        pg = page[g]
        mine = taken.setdefault(pg, set())
        have = [] if info[g][1] in again else info[g][2]
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
        for o, how in outputs.items():
            if o in fixed:
                continue
            src = how[0]
            base = want.get(src)
            if base:
                if len(how) == 3:               # (a tap: -1, -2...; off a tap: a, b...)
                    v = base + (letters(how[1]).lower() if "-" in base
                                else "-%d" % (how[1] + 1))
                else:
                    v = base + how[1]
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


def _break_loops(outputs, info):
    """Outputs whose numbers come from each other round a loop (two wires each tapping the
    other's middle) would have none: the first of the loop in numbering order is numbered as
    a wire of its own (the battery, 0.18.3, seed 37)."""
    done = set()
    for o in sorted(outputs, key=lambda g: info[g][0]):
        path, x = [], o
        while x in outputs and x not in done and x not in path:
            path.append(x)
            x = outputs[x][0]
        if x in path:
            loop = path[path.index(x):]
            first = min(loop, key=lambda g: info[g][0])
            del outputs[first]
        done.update(path)


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


def set_locks(ed, sheet, wires, lock):
    """Lock (or unlock) the numbers of these wires' groups as they are: Wire.num_lock, as the
    Wire number window's "Lock this number" (a group is one number: all its wires). Returns
    how many wires changed."""
    n = 0
    for w in wires:
        cur = sheet.entities.get(w.id, w)
        if cur.num and cur.num_lock != lock:
            ed.change(sheet, cur.copy(num_lock=lock))
            n += 1
    return n


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


def match_arrow_layers(ed, project, name):
    """The wires at a pair's destination arrows (name) take the layer of the wire at its
    source arrow: the wire they continue (the owner, 0.18.4: "if I add a destination arrow,
    not only should the wire number change, but its layer needs to match the source layer
    as well"). All of each one's joined wires on its sheet. Returns how many changed."""
    ends = connectors(project).get(name, [])
    src = None
    for s, c in ends:
        if c.block == ARROWS[0]:
            src = next((w for _n, q in c.pin_points() for w in s.query_point(q, TOL)
                        if getattr(w, "kind", "") == "wire" and w.touches(q, TOL)), None)
            if src is not None:
                break
    if src is None:
        return 0
    n = 0
    for s, c in ends:
        if c.block != ARROWS[1]:
            continue
        roots = _sheet_groups(s)
        mine = {roots.get(w.id) for _n, q in c.pin_points() for w in s.query_point(q, TOL)
                if getattr(w, "kind", "") == "wire" and w.touches(q, TOL)}
        for w in list(s.wires()):
            if roots.get(w.id) in mine and w.layer != src.layer:
                ed.change(s, w.copy(layer=src.layer))
                n += 1
    return n


def wire_end(sheet, wire, p):
    """(sheet, end point, direction out) of the end of wire nearer p."""
    a, b = wire.points[0], wire.points[-1]
    if math.hypot(p[0] - a[0], p[1] - a[1]) <= math.hypot(p[0] - b[0], p[1] - b[1]):
        q, r = a, wire.points[1]
    else:
        q, r = b, wire.points[-2]
    L = math.hypot(q[0] - r[0], q[1] - r[1]) or 1.0
    return sheet, tuple(q), ((q[0] - r[0]) / L, (q[1] - r[1]) / L)


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
        sheet._num_leaders = (None, [])
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
    leaders = []
    taken = []                          # (the numbers placed so far: boxes)
    busy = _busy_points(sheet)

    def text_at(num, q, a, b, side=1.0, off=0.4):
        """The number beside the piece a-b at q: over it (side 1) or under it (-1), left of
        or right of it when it runs up and down, off text heights away."""
        if abs(a[1] - b[1]) > abs(a[0] - b[0]):
            return Text((q[0] - side * h * off, q[1]), num, h, 90.0, "center")
        return Text((q[0], q[1] + side * h * off - (h if side < 0 else 0.0)), num, h, 0.0,
                    "center")

    def put(num, q, a, b):
        t = text_at(num, q, a, b)
        out.append(t)
        taken.append(t.bbox())

    def clear(box, skip=()):
        """Does nothing on the sheet (another wire, a symbol and its texts, a line) or a number
        placed already come into box?"""
        g = 0.1 * h
        r = (box[0] - g, box[1] - g, box[2] + g, box[3] + g)
        for o in taken:
            if o[0] < r[2] and o[2] > r[0] and o[1] < r[3] and o[3] > r[1]:
                return False
        for e in sheet.query(r):
            if e.id not in skip and e.crosses(r):
                return False
        return True

    def place(num, ws, around=None):
        """The number of the wires ws where it comes into nothing (the owner, 0.18.1: "wire
        numbers need to try to move to be out of the way. If no room, a little line and wire
        number off the wire line can be used"): along their straight pieces, longest first
        (around: the point it should be near), over then under each; else set off to the side
        with a short line back to the wire; else where it always went."""
        own = {w.id for w in ws}
        pieces = [(a, b) for w in ws for a, b in zip(w.points, w.points[1:])
                  if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 1e-9]
        if not pieces:
            return
        if around is None:
            pieces.sort(key=lambda ab: -(abs(ab[0][0] - ab[1][0]) + abs(ab[0][1] - ab[1][1])))
        else:
            pieces.sort(key=lambda ab: _seg_dist(around, ab[0], ab[1]))
        pieces = pieces[:6]
        first = None
        for a, b in pieces:
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            mid = _clear_spot(a, b, busy) if around is None else \
                _closest_on(around, a, b)
            spots = [mid] + [(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
                             for f in (0.3, 0.7, 0.15, 0.85) if L * f > 2 * h]
            for q in spots:
                for side in (1.0, -1.0):
                    t = text_at(num, q, a, b, side)
                    if first is None:
                        first = t
                    if clear(t.bbox(), own):
                        out.append(t)
                        taken.append(t.bbox())
                        return
        # no room beside it: off to the side, a little line back to the wire
        a, b = pieces[0]
        q = _clear_spot(a, b, busy) if around is None else _closest_on(around, a, b)
        for off in (2.5, 4.0, 6.0):
            for side in (1.0, -1.0):
                t = text_at(num, q, a, b, side, off)
                if clear(t.bbox(), own):
                    out.append(t)
                    taken.append(t.bbox())
                    tb = t.bbox()
                    # (from the wire to the number's near edge)
                    if abs(a[1] - b[1]) > abs(a[0] - b[0]):
                        end = (tb[2], q[1]) if side > 0 else (tb[0], q[1])
                    else:
                        end = (q[0], tb[1]) if side > 0 else (q[0], tb[3])
                    leaders.append((tuple(q), end))
                    return
        out.append(first)
        taken.append(first.bbox())
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
                    place(num, [w], around=q)
                ended = True
        for w in ws:
            for t in w.labels:
                if t <= w.length() + 1e-9:
                    q, i = w.at_length(t)
                    put(num, q, w.points[i], w.points[i + 1])
        if ended:
            continue
        place(num, ws)
    sheet._num_labels = (sig, out)
    sheet._num_leaders = (sig, leaders)
    return out


def label_leaders(project, sheet):
    """[(from, to)]: the short lines from a wire to its number where it had to be set off to
    the side (labels)."""
    labels(project, sheet)
    got = getattr(sheet, "_num_leaders", None)
    return got[1] if got is not None else []


def _seg_dist(p, a, b):
    q = _closest_on(p, a, b)
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _closest_on(p, a, b):
    """The point of the piece a-b nearest p."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return (a[0] + t * dx, a[1] + t * dy)


def gauge_labels(project, sheet):
    """A wire layer's gauge (Layers: AWG) beside its wires, and its insulation color (Wire
    color) where a wire is set to show it (Wire color label): one label per run of joined wires
    on the layer, on its longest straight piece, on the other side of the wire from its
    number (under it, or right of it when upright), smaller (Gauge label height; the owner,
    0.18.4: "Maybe text size needs to be smaller. And I don't think we need to include the
    wire color")."""
    if not project.settings.get("wire_gauge_shown", True) or sheet is project.title_block:
        return []
    shown = {n: lay.wire_label() for n, lay in project.layers.items() if lay.wire_label()}
    h = float(project.settings.get("wire_number_height", 0.08)) * sheet.k()
    gh = float(project.settings.get("wire_gauge_height", 0.06)) * sheet.k()
    every = project.settings.get("wire_gauge_each", "group") == "each"
    sig = (sheet.version, sheet.scale, h, gh, tuple(sorted(shown.items())), every,
           tuple(sorted((n, lay.wire_color) for n, lay in project.layers.items())))
    got = getattr(sheet, "_gauge_labels", None)
    if got is not None and got[0] == sig:
        return got[1]
    # (a wire of a size of its own, Wire size, shows it in place of its layer's: one label
    # for each run of joined wires of one layer and one size)
    from .model import gauge_text
    labeled = []
    for w in sheet.wires():
        if not (w.awg or w.layer in shown):
            continue
        lay = project.layers.get(w.layer)
        g = str(w.awg or (lay.awg if lay is not None else "")).strip()
        color = lay.wire_color if lay is not None and w.show_color else ""
        if g or color:
            labeled.append((w, gauge_text(g) if g else "", color or ""))
    if not labeled:
        sheet._gauge_labels = (sig, [])
        return []
    roots = _sheet_groups(sheet)
    parts = {}
    for w, g, color in labeled:
        parts.setdefault((roots.get(w.id, w.id), w.layer, g, color), []).append(w)
    busy = _busy_points(sheet)
    out = []
    bests = []
    for (_r, _layer, g, color), ws in parts.items():
        best = None
        for w in ws:
            for a, b in zip(w.points, w.points[1:]):
                d = abs(a[0] - b[0]) + abs(a[1] - b[1])
                if best is None or d > best[0]:
                    best = (d, a, b)
        if best is not None:
            bests.append((g, [color], best[1], best[2]))
    if not every:
        bests = _one_per_bundle(bests, BUNDLE_GAP * sheet.k())
    for g, colors, a, b in bests:
        text = " ".join(t for t in (g, ", ".join(c for c in colors if c)) if t)
        mx, my = _clear_spot(a, b, busy)
        if abs(a[1] - b[1]) > abs(a[0] - b[0]):
            out.append(Text((mx + h * 0.4 + gh, my), text, gh, 90.0, "center"))
        else:
            out.append(Text((mx, my - h * 0.4 - gh), text, gh, 0.0, "center"))
    sheet._gauge_labels = (sig, out)
    return out


BUNDLE_GAP = 0.75      # wires side by side this close (paper inches) share one gauge label


def _one_per_bundle(bests, gap):
    """Of the runs' labeled pieces [(gauge, [color], a, b)], one for each bundle: runs of one
    gauge whose pieces run side by side, the same way, no farther apart than gap and along
    each other for at least half the shorter one (the conductors from a starter to a drive,
    a bus). The bundle's label goes on its outside wire (the rightmost of upright ones, the
    lowest of those across: labels go right of upright wires and under the others) and names
    their colors once each, in order across the bundle (top to bottom, left to right): 12 AWG
    BRN, ORG, YEL. The owner, 0.18.4: "I don't need 12awg black on every wire ... Can this
    intuitively mark the gauge and color of one wire instead of all of them?"; for a bus of
    three colors, "one label per group", the colors listed."""
    rows = {}
    for i, (g, _c, a, b) in enumerate(bests):
        up = abs(a[1] - b[1]) > abs(a[0] - b[0])
        if up and abs(a[0] - b[0]) > 1e-6 or not up and abs(a[1] - b[1]) > 1e-6:
            continue                    # (slanted: labeled on its own)
        across = a[0] if up else a[1]   # (where it is, across its way)
        lo, hi = sorted((a[1], b[1]) if up else (a[0], b[0]))
        rows.setdefault((g, up), []).append((across, lo, hi, i))
    up_ = list(range(len(bests)))

    def find(i):
        while up_[i] != i:
            up_[i] = up_[up_[i]]
            i = up_[i]
        return i
    for items in rows.values():
        items.sort()
        for k, (x, lo, hi, i) in enumerate(items):
            for x2, lo2, hi2, j in items[k + 1:]:
                if x2 - x > gap:
                    break
                if min(hi, hi2) - max(lo, lo2) >= 0.5 * min(hi - lo, hi2 - lo2) > 0:
                    up_[find(j)] = find(i)
    members = {}
    for i, (g, colors, a, b) in enumerate(bests):
        up = abs(a[1] - b[1]) > abs(a[0] - b[0])
        # (the outside one: farthest right, or lowest; the colors in order across)
        members.setdefault(find(i), []).append((a[0] if up else -a[1], i))
    out = []
    for r in sorted(members, key=lambda r: min(i for _s, i in members[r])):
        ms = sorted(members[r])
        g, _c, a, b = bests[ms[-1][1]]
        colors = []
        for _s, i in ms:
            for c in bests[i][1]:
                if c not in colors:
                    colors.append(c)
        out.append((g, colors, a, b))
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
