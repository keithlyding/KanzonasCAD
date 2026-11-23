"""Arrays that stay arrays (the owner, Nov 2026: "Yes I want to be able to edit an array"; asked:
mostly its spacing; the copies stay linked until it is unlinked; copies added take tags of their
own, copies kept keep theirs; wires on copies taken away stay where they are, unconnected).

An array is kept on its sheet (Sheet.arrays, saved with it): how it was made (rows and columns
or round a center, with their spacing or angle), the objects it was made from (its source) and
its copies by their place in it. A copy is still the array's while it is exactly where and as
the array puts it: one moved, turned, stretched or erased on its own has left the array, and
Edit array leaves it alone (decided while the owner was away: editing one copy takes it out,
rather than changing every copy). An array whose source is gone is no longer one.

The model has no Qt: this is used by the commands, the tests and the battery alike."""

from . import model as M

TOL = 1e-6


def offsets(mode, vals):
    """[(dx, dy, angle)] of an array's copies (not its source), in their order: rows and
    columns (mode "R": rows, columns, row spacing, column spacing), or round a center ("P":
    how many in all, the angle they fill)."""
    out = []
    if mode == "R":
        rows, cols, dr, dc = (list(vals) + [0, 0, 0, 0])[:4]
        for r in range(int(rows)):
            for c in range(int(cols)):
                if r or c:
                    out.append((c * dc, r * dr, 0.0))
    elif mode == "P" and vals:
        n = int(vals[0])
        fill = vals[1] if len(vals) > 1 else 360.0
        step = fill / n if abs(abs(fill) - 360.0) < 1e-9 else \
            (fill / (n - 1) if n > 1 else 0.0)
        for i in range(1, n):
            out.append((0.0, 0.0, step * i))
    return out


def place(e, off, center=None):
    """A copy of e where an array's copy at off goes (no id)."""
    dx, dy, ang = off
    c = e.rotated(tuple(center), ang) if ang else e.moved(dx, dy)
    c.id = None
    return c


def _shape(e):
    """What says where and how an object is, not what it is called: its stored form without
    its id and, for a symbol, its tag and links (a copy has a tag of its own) and which of them
    are hidden (a contact block on a pushbutton's dashed line hides its tag, its copies off the
    line show theirs: they were taken for copies that had left the array, and Edit array left
    them where they were; the battery, 0.22.5, seed 469)."""
    d = e.to_dict()
    d.pop("id", None)
    if isinstance(e, M.Insert):
        d.pop("attrs", None)
        d.pop("hidden", None)
    return d


def _same(a, b):
    def close(x, y):
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and \
                not isinstance(x, bool) and not isinstance(y, bool):
            return abs(x - y) <= TOL * max(1.0, abs(x), abs(y))
        if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
            return len(x) == len(y) and all(close(p, q) for p, q in zip(x, y))
        if isinstance(x, dict) and isinstance(y, dict):
            return x.keys() == y.keys() and all(close(x[k], y[k]) for k in x)
        return x == y
    return close(_shape(a), _shape(b))


def record(ed, sheet, mode, vals, center, source, copies):
    """Keep an array just made: source the ids it was made from, copies {index: [ids, in the
    source's order]} (index: its place in offsets)."""
    arrays = dict(sheet.arrays)
    aid = str(max([int(k) for k in arrays] + [0]) + 1)
    arrays[aid] = {"mode": mode, "vals": list(vals),
                   "center": list(center) if center is not None else None,
                   "source": list(source),
                   "items": {str(i): list(ids) for i, ids in copies.items()}}
    ed.sheet_meta(sheet, arrays=arrays)
    return aid


def alive(sheet, aid):
    a = sheet.arrays.get(aid)
    return a is not None and all(i in sheet.entities for i in a["source"])


def members(sheet, aid):
    """{index: [ids]} of an array's copies still its own: every object of the copy there and
    exactly where and as the array puts it."""
    a = sheet.arrays[aid]
    src = [sheet.entities[i] for i in a["source"]]
    offs = offsets(a["mode"], a["vals"])
    out = {}
    for key, ids in a["items"].items():
        i = int(key)
        if i >= len(offs) or len(ids) != len(src):
            continue
        if all(j in sheet.entities and _same(sheet.entities[j], place(e, offs[i], a["center"]))
               for e, j in zip(src, ids)):
            out[i] = list(ids)
    return out


def find(sheet, eid):
    """The array an object is part of (its source, or a copy still its own), or None."""
    for aid, a in sheet.arrays.items():
        if not alive(sheet, aid):
            continue
        if eid in a["source"]:
            return aid
        if any(eid in ids for ids in members(sheet, aid).values()):
            return aid
    return None


def edit(ed, project, sheet, aid, vals):
    """The array made again with new numbers (its spacing, rows and columns, count or angle):
    copies still its own moved to their new places (keeping their tags), those past the new
    count erased, new ones added with tags of their own (tags.retag_copies); copies that left
    it stay as they are. Returns (moved, added, erased)."""
    from .tags import retag_copies
    a = sheet.arrays[aid]
    src = [sheet.entities[i] for i in a["source"]]
    have = members(sheet, aid)
    new_offs = offsets(a["mode"], vals)
    items, moved, added, erased = {}, 0, 0, 0
    for i, ids in sorted(have.items()):
        if i < len(new_offs):
            for e, j in zip(src, ids):
                c = place(e, new_offs[i], a["center"])
                c.id = j
                old = sheet.entities[j]
                if isinstance(old, M.Insert):
                    c = c.copy(attrs=dict(old.attrs))
                if not _same(c, old):
                    ed.change(sheet, c)
                    moved += 1
            items[str(i)] = list(ids)
        else:
            for j in ids:
                ed.remove(sheet, j)
                erased += 1
    taken = {int(k) for k in a["items"]} - set(have)      # (left the array: their places kept)
    for i, off in enumerate(new_offs):
        if i in have or i in taken:
            continue
        made = retag_copies(project, sheet, [place(e, off, a["center"]) for e in src])
        items[str(i)] = [ed.add(sheet, c).id for c in made]
        added += len(made)
    arrays = dict(sheet.arrays)
    arrays[aid] = dict(a, vals=list(vals), items=items)
    ed.sheet_meta(sheet, arrays=arrays)
    return moved, added, erased


def unlink(ed, sheet, aid):
    """The array forgotten: its copies stay where they are, objects of their own."""
    arrays = dict(sheet.arrays)
    arrays.pop(aid, None)
    ed.sheet_meta(sheet, arrays=arrays)
