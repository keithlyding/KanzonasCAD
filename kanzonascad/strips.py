"""Terminal strips (the roadmap's item 4: "strips, jumpers, a strip editor, a terminal plan
report"). No Qt.

A terminal is a placed schematic symbol with a terminal number (its TERM attribute: the
Terminal symbol, or a block of your own with one). Terminals sharing a strip make a terminal
strip: those linked to a Terminal strip device (PARENT, its hidden id: they show its tag, TB1)
are its terminals, and a terminal on no strip device yet goes by its own tag. The same number
shown twice (on two sheets, say) is one terminal: its wires from every place it is drawn.

What the drawing can't say is kept per strip in the project's settings ("strips", by the strip
device's hidden id, or "tag:TB1" for a strip with no device): the order of its terminals when
it isn't their number order, its spare terminals (numbers on the strip with nothing drawn) and
its jumpers (each a list of the terminal numbers it bridges). Everything else is worked out from
the drawing each time, never kept: each terminal's wires and what they land on.

Each terminal has two sides, its two pins (as the block is drawn: the left one, then the right
one). The internal side is the one wired inside the strip's location (the panel), the external
side the one going out of it (to a device of another location: the field, a junction box): the
left side is internal unless the locations say it goes out and the right side doesn't. With no
locations given, left is internal and right external, as drawn.

The Terminal strips window (strip_window.StripEditorDialog) edits a Layout of each strip and writes
them back with apply, as one step to undo; the terminal plan is plan_rows."""

import re

from . import pull
from . import tags
from . import wirenums

SETTING = "strips"
PLAN_HEAD = ["Strip", "Terminal", "Internal wire", "Internal to", "External wire",
             "External to", "Jumper", "Where"]
TAG_KEY = "tag:"                # (a strip with no strip device: kept by its tag)


_DIGITS = re.compile(r"(\d+)")


def natural(t):
    """A number's sort key, its digits by value (TB2 before TB10), as pull._natural."""
    return [int(x) if x.isdigit() else x for x in _DIGITS.split(t or "")]


def is_terminal(e):
    """A placed schematic symbol numbered on a strip (its TERM attribute)."""
    d = getattr(e, "defn", None)
    return d is not None and d.kind == "symbol" and getattr(e, "kind", "") == "insert" and \
        pull.is_terminal(e)


def is_strip_device(e):
    """A Terminal strip symbol (a parent device with the prefix TB), placed."""
    d = getattr(e, "defn", None)
    return tags.is_device(e) and d.role == "parent" and d.prefix == "TB"


def key_of(e, devs=None):
    """The key a terminal's strip is kept by: its strip device's hidden id, else "tag:" and its
    tag."""
    par = (e.attrs.get("PARENT") or "").strip()
    if par and (devs is None or par in devs):
        return par
    return TAG_KEY + (e.attrs.get("TAG") or "").strip().upper()


def jumper_name(i):
    return "J%d" % (i + 1)


class Side:
    """One side of a terminal: its pin, the wire numbers on it, and what those wires land on
    [(sheet, symbol, pin)] (the terminal itself left out)."""

    def __init__(self, pin):
        self.pin = pin
        self.wires = []
        self.to = []

    def add(self, other):
        for n in other.wires:
            if n not in self.wires:
                self.wires.append(n)
        for t in other.to:
            if not any(t[0] is x[0] and t[1] is x[1] and t[2] == x[2] for x in self.to):
                self.to.append(t)


class Row:
    """A terminal of a strip: its number ("" while it has none), spare (on the strip, not
    drawn), where it is drawn [(sheet, terminal)], its internal and external sides (Side, or
    None) and its jumper's index (or None)."""

    def __init__(self, num, spare=False):
        self.num = num
        self.spare = spare
        self.places = []
        self.inside = None
        self.outside = None
        self.jumper = None


class Strip:
    """A terminal strip: key (as kept in the settings), tag, its strip device (sheet, insert)
    or None, its location, its terminals in order (rows) and its jumpers [[numbers]]."""

    def __init__(self, key, tag):
        self.key = key
        self.tag = tag
        self.dev = None
        self.loc = ""
        self.rows = []
        self.jumpers = []


def layout(project, strip):
    """What the settings keep of a strip: {"order", "spares", "jumpers"} (each may be left
    out); a strip that has since got a strip device still finds what was kept by its tag."""
    kept = project.settings.get(SETTING) or {}
    got = kept.get(strip.key)
    if got is None:
        got = kept.get(TAG_KEY + strip.tag.upper())
    return got if isinstance(got, dict) else {}


def ordered(nums, stored):
    """nums in the stored order; those it doesn't have yet at their place by number (after the
    last one numbered below them)."""
    have = set(nums)
    out, seen = [], set()
    for n in stored or ():
        n = str(n)
        if n in have and n not in seen:
            out.append(n)
            seen.add(n)
    new = sorted((n for n in nums if n not in seen), key=natural)
    if not out:
        return new
    keys = [natural(m) for m in out]
    for n in new:
        k = natural(n)
        at = 0
        for i, m in enumerate(keys):
            if m < k:
                at = i + 1
        out.insert(at, n)
        keys.insert(at, k)
    return out


def clean_jumpers(groups, have):
    """Jumpers as kept, each the numbers it bridges that the strip has (one left alone bridges
    nothing: dropped), a terminal in two of them making them one."""
    out = []
    for g in groups or ():
        nums = []
        for n in g or ():
            n = str(n)
            if n in have and n not in nums:
                nums.append(n)
        mine = [o for o in out if set(o) & set(nums)]
        for o in mine:
            out.remove(o)
            nums = o + [n for n in nums if n not in o]
        if nums:
            out.append(nums)
    return [g for g in out if len(g) >= 2]


def _nets(project):
    """{(sheet id, wire group root): net} of the wire groups (wirenums._sheet_groups) that go on
    to other groups through off-sheet connectors and source and destination arrows (those of
    one name are one wire, as wire numbering joins them), and {net: [(sheet id, root)]}. A
    group in neither is a net of its own."""
    up = {}

    def find(k):
        while up.get(k, k) != k:
            up[k] = up.get(up[k], up[k])
            k = up[k]
        return k
    first = {}
    for s in project.sheets:
        roots = None
        for ins in s.inserts():
            d = ins.defn
            if d is None or d.wiring != "link":
                continue
            name = (ins.attrs.get("TAG") or "").strip().upper()
            if not name:
                continue
            if roots is None:
                roots = wirenums._sheet_groups(s)
            for rs in wirenums._pin_groups(s, ins, roots).values():
                for r in rs:
                    k = (s.id, r)
                    up.setdefault(k, k)
                    if name not in first:
                        first[name] = k
                    else:
                        a, b = find(first[name]), find(k)
                        if a != b:
                            up[b] = a
    net_of, members = {}, {}
    for k in up:
        n = find(k)
        net_of[k] = n
        members.setdefault(n, []).append(k)
    return net_of, members


def _landings(sheet):
    """{sheet-local wire group root: [(symbol, pin)]} of every pin wires end on (as
    pull._sheet_landings, but every group on a pin: two wires landed on one pin are two groups,
    and each lands there), kept until the sheet changes."""
    got = getattr(sheet, "_strip_landings", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    roots = wirenums._sheet_groups(sheet)
    out = {}
    for ins in sheet.inserts():
        d = ins.defn
        if d is None or not d.pins or d.kind != "symbol" or d.wiring == "link":
            continue
        for pin, rs in wirenums._pin_groups(sheet, ins, roots).items():
            for r in rs:
                out.setdefault(r, []).append((ins, pin))
    sheet._strip_landings = (sheet.version, out)
    return out


def _pins(ins):
    """The terminal's pins as its block is drawn: [left pin name, right pin name] (one pin:
    [it]; none: [])."""
    d = ins.defn
    names = [p["name"] for p in sorted(d.pins or (), key=lambda p: (p["pos"][0], -p["pos"][1]))]
    if len(names) > 1:
        return [names[0], names[-1]]
    return names


def pin_wires(ctx, s, q):
    """[(wire, net)] of the wires on a pin at q of sheet s, each with its net (a wire group
    joined across sheets: _nets), in the order the sheet's index gives them."""
    roots = ctx["roots"](s)
    out = []
    for o in s.query_point(q, wirenums.TOL):
        if getattr(o, "kind", "") != "wire" or o.id not in roots or not o.touches(q, wirenums.TOL):
            continue
        k = (s.id, roots[o.id])
        out.append((o, ctx["net_of"].get(k, k)))
    return out


def net_landings(ctx, net):
    """[(sheet, symbol, pin)] of every pin a net lands on, on every sheet it is on."""
    out = []
    for sid, r in ctx["members"].get(net, [net]):
        sh = ctx["sheets"].get(sid)
        if sh is None:
            continue
        for x, xp in _landings(sh).get(r, ()):
            out.append((sh, x, xp))
    return out


def _side(ctx, s, ins, pin, q):
    side = Side(pin)
    nets = []
    for o, n in pin_wires(ctx, s, q):
        if ctx["numbered"]:
            num = o.num or "?"
            if num not in side.wires:
                side.wires.append(num)
        if n not in nets:
            nets.append(n)
    for n in nets:
        for sh, x, xp in net_landings(ctx, n):
            if x is ins and xp == pin and sh is s:
                continue
            if not any(x is t[1] and xp == t[2] for t in side.to):
                side.to.append((sh, x, xp))
    return side


def _goes_out(side, loc):
    """Whether a side's wires land in another location than loc (the strip's)."""
    if side is None or not loc:
        return False
    return any(pull.location_of(sh, x) and pull.location_of(sh, x) != loc
               for sh, x, _p in side.to)


def context(project):
    """What working out terminals' sides needs of the project (its wire nets across sheets),
    once for many terminals (sides)."""
    net_of, members = _nets(project)
    return {"net_of": net_of, "members": members, "roots": wirenums._sheet_groups,
            "sheets": {s.id: s for s in project.sheets},
            "numbered": wirenums.enabled(project)}


def find(project, wires=True):
    """[Strip] of the project, by tag (TB? last: terminals on no strip yet), each with its
    terminals in order; wires: each terminal's sides worked out too (the Terminal strips
    window lists the strips without, and works out a strip's when it shows it: sides)."""
    found = {}
    devs = tags.devices(project)
    for s in project.sheets:
        for e in s.inserts():
            if is_terminal(e):
                key = key_of(e, devs)
                tag = (devs[key][1] if key in devs else e).attrs.get("TAG") or ""
                tag = tag.strip()
                st = found.get(key)
                if st is None:
                    st = found[key] = (Strip(key, tag or "TB?"), {}, [])
                num = (e.attrs.get("TERM") or "").strip()
                if num:
                    st[1].setdefault(num, []).append((s, e))
                else:
                    st[2].append((s, e))
            elif is_strip_device(e) and e.attrs.get("DEV"):
                key = e.attrs["DEV"]
                if key not in found:
                    found[key] = (Strip(key, (e.attrs.get("TAG") or "").strip() or "TB?"),
                                  {}, [])
    ctx = context(project) if wires else None
    out = []
    for key, (st, nums, loose) in found.items():
        if key in devs:
            st.dev = devs[key]
            st.loc = pull.location_of(*devs[key])
        kept = layout(project, st)
        spares = [str(n) for n in kept.get("spares") or () if str(n) and str(n) not in nums]
        spares = list(dict.fromkeys(spares))
        order = ordered(list(nums) + spares, kept.get("order"))
        spare_set = set(spares)
        for n in order:
            r = Row(n, n in spare_set)
            r.places = list(nums.get(n, ()))
            st.rows.append(r)
        for s, e in loose:
            r = Row("")
            r.places = [(s, e)]
            st.rows.append(r)
        if not st.loc:
            for r in st.rows:
                if r.places:
                    st.loc = pull.location_of(*r.places[0])
                    break
        st.jumpers = clean_jumpers(kept.get("jumpers"), set(order))
        at = {n: i for i, g in enumerate(st.jumpers) for n in g}
        for r in st.rows:
            r.jumper = at.get(r.num) if r.num else None
            if ctx is not None:
                sides(ctx, st, r)
        out.append(st)
    out.sort(key=lambda st: (st.tag == "TB?", natural(st.tag.upper()), st.key))
    return out


def sides(ctx, strip, row):
    """A terminal's internal and external sides, from every place it is drawn (once: a row
    that has them keeps them)."""
    if row.inside is not None or row.outside is not None:
        return
    for s, e in row.places:
        names = _pins(e)
        pts = dict(e.pin_points())
        got = [_side(ctx, s, e, n, pts[n]) for n in names if n in pts]
        if not got:
            continue
        loc = strip.loc
        if len(got) == 2 and _goes_out(got[0], loc) and not _goes_out(got[1], loc):
            got.reverse()
        if len(got) == 1 and _goes_out(got[0], loc):
            got.insert(0, None)
        for i, side in enumerate(got):
            if side is None:
                continue
            mine = row.inside if i == 0 else row.outside
            if mine is None:
                if i == 0:
                    row.inside = side
                else:
                    row.outside = side
            else:
                mine.add(side)


def to_text(project, strip, side):
    """What a side lands on: "CR1:A1, M1:T1 (FIELD)": each landing (TB1-4 for another
    terminal), with its location when it isn't the strip's."""
    if side is None:
        return ""
    return landings_text(side.to, strip.loc)


def landings_text(landings, loc, most=None):
    """Landings [(sheet, symbol, pin)] as written: "CR1:A1, M1:T1 (FIELD)", each once, in
    natural order, with its location when it isn't loc; with most given and more of them than
    that, the first most - 1 and how many more ("CR1:A2, CR2:A2 +4")."""
    names = []
    for sh, x, pin in landings:
        n = pull.landing_name(x, pin)
        there = pull.location_of(sh, x)
        if there and there != loc:
            n += " (%s)" % there
        if n not in names:
            names.append(n)
    names = sorted(names, key=natural) if len(names) > 1 else names
    if most is not None and len(names) > most:
        return "%s +%d" % (", ".join(names[:most - 1]), len(names) - most + 1)
    return ", ".join(names)


def wires_text(side):
    return ", ".join(side.wires) if side is not None else ""


def jumper_text(strip, row):
    """A terminal's jumper: "J1: 1, 2, 3" (its name and the terminals it bridges)."""
    if row.jumper is None:
        return ""
    return "%s: %s" % (jumper_name(row.jumper), ", ".join(strip.jumpers[row.jumper]))


def where_text(project, row):
    """Where a terminal is drawn (6-B3, 7-A1), or "spare"."""
    if row.spare:
        return "spare"
    out = []
    for s, e in row.places:
        t = project.zone_text(s, e.pos[0], e.pos[1]) or project.sheet_number(s)
        if t not in out:
            out.append(t)
    return ", ".join(out)


def plan_rows(project, strips=None):
    """The terminal plan: a row per terminal of every strip, in each strip's order: strip,
    terminal, internal side (wires, what they land on), external side, jumper, where."""
    rows = []
    for st in strips if strips is not None else find(project):
        for r in st.rows:
            rows.append([st.tag, r.num or "?", wires_text(r.inside),
                         to_text(project, st, r.inside), wires_text(r.outside),
                         to_text(project, st, r.outside), jumper_text(st, r),
                         where_text(project, r)])
    return rows


def table(project):
    """(header, rows) of the terminal plan (report sheets, Save as CSV or Excel)."""
    return PLAN_HEAD, plan_rows(project)


# ---- editing a strip (the Terminal strips window) ----------------------------------------------
class Layout:
    """A strip as it is being edited: its rows in order, each {"num", "orig" (its number in the
    drawing: None for a spare added here), "spare", "places" [(sheet id, terminal id)], "jumper"
    (a jumper's id, or None), "row" (the Row it came from, or None)}."""

    def __init__(self, strip):
        self.key = strip.key
        self.tag = strip.tag
        self.rows = []
        self._next_jumper = len(strip.jumpers)
        for r in strip.rows:
            self.rows.append({"num": r.num, "orig": r.num if not r.spare else None,
                              "spare": r.spare, "places": [(s.id, e.id) for s, e in r.places],
                              "jumper": r.jumper, "row": r})
        self.start = self.state()

    def state(self):
        # (which terminal has which number, not the numbers alone: a strip turned round and
        # renumbered reads 1, 2, 3... as before)
        return ([(tuple(r["places"]), r["orig"], r["num"], r["spare"]) for r in self.rows],
                self.jumpers())

    def changed(self):
        return self.state() != self.start

    def numbers(self):
        return {r["num"] for r in self.rows if r["num"]}

    def move(self, picked, delta):
        """The picked rows (indexes) one place up (delta -1) or down (+1), as a block where
        they meet the end. Returns their indexes after."""
        picked = sorted(set(i for i in picked if 0 <= i < len(self.rows)))
        if not picked or delta not in (-1, 1):
            return picked
        if (delta < 0 and picked[0] == 0) or (delta > 0 and picked[-1] == len(self.rows) - 1):
            return picked
        for i in (picked if delta < 0 else reversed(picked)):
            self.rows[i + delta], self.rows[i] = self.rows[i], self.rows[i + delta]
        return self._loose_last([i + delta for i in picked])

    def _loose_last(self, keep=()):
        """The terminals with no number yet kept after the numbered ones, as the drawing puts
        them (find: a strip's order is kept by number, so one with none can't be placed among
        them; 0.30: a UDT's terminals placed on no strip are three such, and one numbered in
        the middle of them read back at the top). Returns where the rows at keep are now."""
        rows = [self.rows[i] for i in keep]
        self.rows = [r for r in self.rows if r["num"] or r["spare"]] + \
            [r for r in self.rows if not (r["num"] or r["spare"])]
        return [next(j for j, x in enumerate(self.rows) if x is r) for r in rows]

    def renumber(self, start=1):
        """Every terminal (spares too) numbered start, start + 1... in the order shown."""
        for i, r in enumerate(self.rows):
            r["num"] = str(start + i)

    def free_number(self):
        """The number after the highest whole number on the strip (1 on an empty one)."""
        top = 0
        for n in self.numbers():
            if n.isdigit():
                top = max(top, int(n))
        return str(top + 1)

    def add_spare(self, after=None):
        """A spare terminal (free_number) after row after (at the end when None). Returns its
        index."""
        at = len(self.rows) if after is None or not 0 <= after < len(self.rows) else after + 1
        self.rows.insert(at, {"num": self.free_number(), "orig": None, "spare": True,
                              "places": [], "jumper": None, "row": None})
        return self._loose_last([at])[0]

    def remove_spares(self, picked):
        """The picked spare terminals taken off the strip (a drawn one stays: erase it on the
        drawing). Returns how many."""
        gone = [i for i in set(picked) if 0 <= i < len(self.rows) and self.rows[i]["spare"]]
        for i in sorted(gone, reverse=True):
            del self.rows[i]
        self._tidy()
        return len(gone)

    def set_number(self, i, num):
        """Row i's number typed. Returns why it can't be (empty, or another terminal's), else
        None."""
        num = (num or "").strip()
        if not num:
            return "A terminal needs a number."
        if any(j != i and r["num"] == num for j, r in enumerate(self.rows)):
            return "%s-%s is already on the strip." % (self.tag, num)
        self.rows[i]["num"] = num
        self._loose_last()
        return None

    def add_jumper(self, picked):
        """One jumper bridging the picked terminals (and those already jumpered to them).
        Returns whether there is one (it takes two terminals)."""
        picked = [i for i in set(picked) if 0 <= i < len(self.rows)]
        if len(picked) < 2:
            return False
        old = {self.rows[i]["jumper"] for i in picked} - {None}
        jid = self._next_jumper
        self._next_jumper += 1
        for r in self.rows:
            if r["jumper"] in old:
                r["jumper"] = jid
        for i in picked:
            self.rows[i]["jumper"] = jid
        return True

    def remove_jumper(self, picked):
        """The picked terminals taken off their jumpers (one left alone bridges nothing).
        Returns how many."""
        n = 0
        for i in set(picked):
            if 0 <= i < len(self.rows) and self.rows[i]["jumper"] is not None:
                self.rows[i]["jumper"] = None
                n += 1
        self._tidy()
        return n

    def _tidy(self):
        count = {}
        for r in self.rows:
            if r["jumper"] is not None:
                count[r["jumper"]] = count.get(r["jumper"], 0) + 1
        for r in self.rows:
            if r["jumper"] is not None and count[r["jumper"]] < 2:
                r["jumper"] = None

    def jumpers(self):
        """[[numbers]] of the jumpers, in the order of their first terminal."""
        out, at = [], {}
        for r in self.rows:
            j = r["jumper"]
            if j is None or not r["num"]:
                continue
            if j not in at:
                at[j] = len(out)
                out.append([])
            out[at[j]].append(r["num"])
        return [g for g in out if len(g) >= 2]

    def jumper_names(self):
        """{row index: "J1"...} as jumpers() names them."""
        names, out = {}, {}
        for i, r in enumerate(self.rows):
            j = r["jumper"]
            if j is None or not r["num"]:
                continue
            if j not in names:
                names[j] = jumper_name(len(names))
            out[i] = names[j]
        return out

    def problem(self):
        """Why the strip can't be written back (two terminals with one number), or None."""
        seen = set()
        for r in self.rows:
            if r["num"] in seen:
                return "%s-%s is on the strip twice." % (self.tag, r["num"])
            if r["num"]:
                seen.add(r["num"])
        return None

    def kept(self):
        """What the settings keep of the strip ({} when it is all as the drawing says)."""
        nums = [r["num"] for r in self.rows if r["num"]]
        out = {}
        if nums != sorted(nums, key=natural):
            out["order"] = nums
        spares = [r["num"] for r in self.rows if r["spare"] and r["num"]]
        if spares:
            out["spares"] = spares
        js = self.jumpers()
        if js:
            out["jumpers"] = js
        return out


def apply(ed, project, layouts):
    """The strips edited written back in one edit: the terminals' new numbers on the drawing
    (every place each is drawn) and each strip's order, spares and jumpers in the settings.
    Returns how many terminals were renumbered."""
    sheets = {s.id: s for s in project.sheets}
    n = 0
    kept = dict(project.settings.get(SETTING) or {})
    for lay in layouts:
        for r in lay.rows:
            if r["spare"] or r["num"] == r["orig"] or not r["num"]:
                continue
            for sid, eid in r["places"]:
                s = sheets.get(sid)
                e = s.entities.get(eid) if s is not None else None
                if e is not None and is_terminal(e):
                    ed.change(s, e.copy(attrs=dict(e.attrs, TERM=r["num"])))
                    n += 1
        mine = lay.kept()
        if lay.key.startswith(TAG_KEY) or TAG_KEY + lay.tag.upper() in kept:
            kept.pop(TAG_KEY + lay.tag.upper(), None)
        if mine:
            kept[lay.key] = mine
        else:
            kept.pop(lay.key, None)
    if kept != (project.settings.get(SETTING) or {}):
        ed.project_settings({SETTING: kept})
    return n
