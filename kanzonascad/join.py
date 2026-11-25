"""Join (AutoCAD's JOIN; the owner, 0.26: "Unite / join lines"): lines, arcs and polylines that
touch end to end become one object. No Qt: the command (commands.JoinCmd) asks for the
objects and puts plan()'s answer in one edit.

- Lines in a line that touch end to end become one line; arcs of one circle that touch end to
  end, one arc (a whole circle when they go all the way round).
- Other touching chains of lines and polylines become one polyline (closed when the chain
  closes on itself).
- Two ends touch when they are within TOL of each other (the drawing's tolerance, as wires'
  ends join). Nothing joins where three or more ends meet (a branch: which way would it go?),
  nor where a piece doubles back over the one before it (an overlap), nor an arc with a line
  (polylines here are straight).
- What could not be joined is said: ends a little apart (a gap), collinear lines lying over
  each other (an overlap), branches, arcs meeting lines.
- Wires are left out: a wire carried on from another wire's end already joins it as it is
  drawn (cleanup), and Clean up wires joins the others; joining two wires is a change of what
  is connected, which only the wire tools make. Closed polylines, circles and the rest are
  left out too.

The work goes through a hash of the ends (cells of their size), never a walk of every pair:
thousands of objects join at once."""

import math

from . import geometry as G
from . import model as M

TOL = 1e-6                  # (ends this close touch: wires.TOL)
GAP = 0.03                  # (ends this far apart on paper, or closer, are a gap worth saying)
SAY = 4                     # (places named for each kind of fault; the rest counted)


def _key(p, cell):
    return (math.floor(p[0] / cell), math.floor(p[1] / cell))


class _Ends:
    """Points kept in cells of a size, so the ones near a point are found at once."""

    def __init__(self, cell):
        self.cell = cell
        self.cells = {}

    def add(self, p, item):
        self.cells.setdefault(_key(p, self.cell), []).append((p, item))

    def near(self, p, r):
        kx, ky = _key(p, self.cell)
        n = int(math.ceil(r / self.cell))
        for i in range(kx - n, kx + n + 1):
            for j in range(ky - n, ky + n + 1):
                for q, item in self.cells.get((i, j), ()):
                    if G.dist(p, q) <= r:
                        yield q, item


class _Piece:
    """One object taking part: its points from end to end (an arc: its two ends)."""
    __slots__ = ("e", "pts", "nodes", "arc")

    def __init__(self, e):
        self.e = e
        self.arc = isinstance(e, M.Arc)
        if self.arc:
            self.pts = [e.start_point(), e.end_point()]
        elif isinstance(e, M.Line):
            self.pts = [e.p1, e.p2]
        else:
            self.pts = list(e.points)
        self.nodes = [None, None]

    def ends(self):
        return self.pts[0], self.pts[-1]

    def length(self):
        if self.arc:
            return math.radians(G.sweep(self.e.start, self.e.end)) * self.e.radius
        return sum(G.dist(a, b) for a, b in zip(self.pts, self.pts[1:]))


def _unit(a, b):
    L = G.dist(a, b)
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 0 else (0.0, 0.0)


def _straight_on(u, v):
    """Do directions u (into a point) and v (out of it) carry on in one line, the same way?"""
    return abs(u[0] * v[1] - u[1] * v[0]) <= 1e-9 and u[0] * v[0] + u[1] * v[1] > 0


def _back_over(u, v):
    """Does v (out of a point) go straight back along u (into it)?"""
    return abs(u[0] * v[1] - u[1] * v[0]) <= 1e-9 and u[0] * v[0] + u[1] * v[1] < 0


def _where(p):
    return "%s,%s" % (M.fmt_inches(p[0], 3), M.fmt_inches(p[1], 3))


def joinable(e):
    """Can Join take it: a line, an arc or an open polyline (not a wire)?"""
    if isinstance(e, M.Wire):
        return False
    if isinstance(e, M.Line):
        return G.dist(e.p1, e.p2) > TOL
    if isinstance(e, M.Arc):
        return e.radius > TOL
    return type(e) is M.Polyline and not e.closed and len(e.points) >= 2


def plan(ents, k=1.0):
    """What joining ents does: ([(new entity, [ids of the objects it takes the place of])],
    [what couldn't be joined, as lines to say]). k: the sheet's drawing units per paper inch
    (the gaps worth saying are GAP on paper)."""
    pieces = [_Piece(e) for e in ents if joinable(e)]
    notes = []
    left = [e for e in ents if not joinable(e)]
    wires = sum(1 for e in left if isinstance(e, M.Wire))
    if wires:
        notes.append("%d wire%s left out: wires join by themselves where one carries on from "
                     "another's end (Clean up wires joins the rest)" % (wires, "" if wires == 1
                                                                        else "s"))
    others = len(left) - wires
    if others:
        notes.append("%d other object%s left out (Join takes lines, arcs and open polylines)"
                     % (others, "" if others == 1 else "s"))
    # the ends, gathered where they touch: a node is the ends within TOL of its first one
    grid = _Ends(TOL * 4)
    nodes = []                      # [[point, [(piece, end)]]]
    for pc in pieces:
        for end, q in enumerate(pc.ends()):
            got = next((n for _q, n in grid.near(q, TOL)), None)
            if got is None:
                got = len(nodes)
                nodes.append([q, []])
                grid.add(q, got)
            nodes[got][1].append((pc, end))
            pc.nodes[end] = got
    faults = {"branch": [], "overlap": [], "arc": [], "gap": []}
    # where two ends meet, can the two pieces join there? link[node] = the two (piece, end)
    link = {}
    for i, (q, ends) in enumerate(nodes):
        if len(ends) >= 3:
            faults["branch"].append(q)
            continue
        if len(ends) != 2:
            continue
        (a, ea), (b, eb) = ends
        if a is b:
            if not a.arc:
                link[i] = ends          # (a polyline whose ends touch: closed)
            continue
        if a.arc != b.arc:
            faults["arc"].append(q)
            continue
        if a.arc:
            same = G.dist(a.e.center, b.e.center) <= TOL and abs(a.e.radius - b.e.radius) <= TOL
            # (one's end on the other's start: they go on round the circle the same way)
            # (and don't go on past where the other starts: lying over it)
            if same and ea != eb and G.sweep(a.e.start, a.e.end) + \
                    G.sweep(b.e.start, b.e.end) <= 360.0 + 1e-9:
                link[i] = ends
            elif same:
                faults["overlap"].append(q)
            continue
        u = _unit(*(a.pts[-2:] if ea == 1 else a.pts[1::-1]))       # (into the point)
        v = _unit(*(b.pts[:2] if eb == 0 else b.pts[:-3:-1]))       # (out of it)
        if _back_over(u, v):
            if not (isinstance(a.e, M.Line) and isinstance(b.e, M.Line)):
                faults["overlap"].append(q)     # (two lines: _overlaps finds it)
            continue
        link[i] = ends
    # collinear lines lying over each other without meeting end to end
    faults["overlap"] += _overlaps([pc for pc in pieces if isinstance(pc.e, M.Line)])
    # chains through the links
    seen = set()
    out = []
    for pc in pieces:
        if id(pc) in seen:
            continue
        chain = _chain(pc, link, nodes)
        for c, _rev in chain:
            seen.add(id(c))
        closed = len(chain) > 0 and chain[0][0].nodes[1 if chain[0][1] else 0] in link and \
            _closes(chain, link)
        if len(chain) < 2 and not closed:
            continue
        new = _joined(chain, closed)
        if new is not None:
            out.append((new, [c.e.id for c, _rev in chain]))
    # ends left free, near another free end: a gap
    free = _Ends(GAP * k)
    loose = [(nodes[n][0], n) for n, (_q, ends) in enumerate(nodes) if len(ends) == 1]
    for q, n in loose:
        free.add(q, n)
    said = set()
    for q, n in loose:
        for r, m in free.near(q, GAP * k):
            if m != n and (m, n) not in said and G.dist(q, r) > TOL:
                said.add((n, m))
                faults["gap"].append((G.dist(q, r), q))
    faults["gap"].sort(key=lambda t: -t[0])
    notes += _said(faults)
    return out, notes


def _chain(start, link, nodes):
    """[(piece, reversed)]: the run of linked pieces start is in, from one end to the other
    (round a loop, from start)."""
    def step(pc, end):
        """The piece linked to pc's end, and which of its ends that is, or None."""
        n = pc.nodes[end]
        if n not in link:
            return None
        (a, ea), (b, eb) = link[n]
        if a is pc and ea == end:
            return b, eb
        return a, ea
    # back from start's first end to where the run begins
    first, end_in = start, 0
    guard = 0
    while True:
        got = step(first, end_in)
        if got is None or got[0] is start or guard > len(nodes):
            break
        first, end_in = got[0], 1 - got[1]
        guard += 1
    # then forward
    out = []
    pc, rev = first, end_in == 1
    used = set()
    while pc is not None and id(pc) not in used:
        used.add(id(pc))
        out.append((pc, rev))
        got = step(pc, 0 if rev else 1)
        if got is None:
            break
        pc, rev = got[0], got[1] == 1
    return out


def _closes(chain, link):
    """Does the run come round to where it started (its last piece linked to its first)?"""
    first, rev = chain[0]
    n = first.nodes[1 if rev else 0]
    last, lrev = chain[-1]
    return n in link and last.nodes[0 if lrev else 1] == n


def _joined(chain, closed):
    """The one object a run of pieces becomes (the first drawn of them gives its layer and
    color), or None when it stays as it is."""
    src = min((c.e for c, _r in chain), key=lambda e: e.id if e.id is not None else 0)
    kw = {"layer": src.layer, "color": src.color}
    if chain[0][0].arc:
        # (round the circle the way arcs go, from start to end)
        a = [c.e for c, _r in (reversed(chain) if chain[0][1] else chain)]
        if sum(G.sweep(x.start, x.end) for x in a) > 360.0 + 1e-9:
            return None                 # (round more than once: lying over itself)
        if closed:
            return M.Circle(a[0].center, a[0].radius, **kw)
        return M.Arc(a[0].center, a[0].radius, a[0].start, a[-1].end, **kw)
    pts = []
    for c, rev in chain:
        seq = list(reversed(c.pts)) if rev else list(c.pts)
        pts += seq if not pts else seq[1:]
    if closed:
        pts = pts[:-1]
    # (a joint where the run carries straight on is no corner)
    keep = [pts[0]]
    for i in range(1, len(pts) - 1):
        if not _straight_on(_unit(keep[-1], pts[i]), _unit(pts[i], pts[i + 1])):
            keep.append(pts[i])
    keep.append(pts[-1])
    if closed and len(keep) >= 3 and _straight_on(_unit(keep[-1], keep[0]),
                                                  _unit(keep[0], keep[1])):
        keep = keep[1:]
    if not closed and len(keep) == 2 and all(isinstance(c.e, M.Line) for c, _r in chain):
        return M.Line(keep[0], keep[1], **kw)
    if closed and len(keep) < 3:
        return None
    return M.Polyline(keep, closed, **kw)


def _overlaps(lines):
    """Where collinear lines lie over each other (more than touching): a point in each. The
    lines are put in groups by their direction and their distance from the origin (rounded),
    and each group swept along its line in order, so many lines in a row take no time."""
    out = []
    groups = {}
    for pc in lines:
        a, b = pc.pts
        ang = math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi
        off = -a[0] * math.sin(ang) + a[1] * math.cos(ang)
        groups.setdefault((round(ang * 1e6), round(off * 1e4)), []).append(pc)
    for got in groups.values():
        if len(got) < 2:
            continue
        a, b = got[0].pts
        L = G.dist(a, b)
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        off = -a[0] * uy + a[1] * ux
        spans = sorted(sorted(q[0] * ux + q[1] * uy for q in pc.pts) for pc in got)
        reach = spans[0][1]
        for s0, s1 in spans[1:]:
            hi = min(reach, s1)
            if hi - s0 > TOL:
                m = (s0 + hi) / 2
                out.append((m * ux - off * uy, m * uy + off * ux))
            reach = max(reach, s1)
    return out


def _said(faults):
    """The command line's lines for what couldn't be joined."""
    out = []

    def places(pts):
        return ", ".join(_where(q) for q in pts[:SAY]) + (
            " and %d more" % (len(pts) - SAY) if len(pts) > SAY else "")
    gaps = faults["gap"]
    if gaps:
        out.append("Not joined, %d gap%s (ends close but not touching; the widest %s at %s): "
                   "move an end onto the other (the Endpoint snap)" % (
                       len(gaps), "" if len(gaps) == 1 else "s", M.fmt_inches(gaps[0][0], 4),
                       _where(gaps[0][1])))
    if faults["overlap"]:
        out.append("Not joined, %d overlap%s (one lying back over the other) at %s" % (
            len(faults["overlap"]), "" if len(faults["overlap"]) == 1 else "s",
            places(faults["overlap"])))
    if faults["branch"]:
        out.append("Not joined, %d branch%s (three or more ends meet) at %s" % (
            len(faults["branch"]), "" if len(faults["branch"]) == 1 else "es",
            places(faults["branch"])))
    if faults["arc"]:
        out.append("Not joined, %d arc%s meeting a line or polyline at %s (polylines here are "
                   "straight)" % (len(faults["arc"]), "" if len(faults["arc"]) == 1 else "s",
                                  places(faults["arc"])))
    return out
