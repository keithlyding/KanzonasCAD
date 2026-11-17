"""Duplicate device tags and wire numbers (the owner, 0.18.1: "The sheet needs to warn me if I
duplicate a tag or wire number"; asked: a red mark on the drawing until it is fixed and a
message on the command line when one appears, over the whole project).

- A device tag is a duplicate when two devices anywhere in the project have it (a contact or
  a footprint shows its device's tag: those don't count).
- A wire number is a duplicate when two wire groups have it that aren't one wire (wires
  joined by off-sheet connectors or source and destination arrows are one group, wirenums),
  unless it was kept on purpose ("No: just the same number" when typing it: the project's
  "same_numbers" setting).

Worked out once per change of the project (kept until then), never on a paint or a mouse
move."""

from . import tags
from . import wirenums

_cache = {"sig": None, "got": None}


def _signature(project):
    return (tuple((s.id, s.version) for s in project.sheets),
            tuple(project.settings.get("same_numbers") or ()),
            bool(project.settings.get("wire_numbers", True)))


def find(project):
    """({TAG: [(sheet, device)]}, {number: [[(sheet, wire)] for each group]}): the tags and
    wire numbers used more than once."""
    sig = _signature(project)
    if _cache["sig"] == sig:
        return _cache["got"]
    by_tag = {}
    for s in project.sheets:
        for e in s.inserts():
            t = e.attrs.get("TAG", "").strip().upper()
            if t and "?" not in t and tags.is_device(e):
                by_tag.setdefault(t, []).append((s, e))
    dup_tags = {t: got for t, got in by_tag.items() if len(got) > 1}
    dup_nums = {}
    if wirenums.enabled(project):
        allowed = {str(n) for n in (project.settings.get("same_numbers") or ())}
        by_num = {}
        gs, _dist = wirenums.groups(project)
        for nodes in gs.values():
            nums = {w.num for _s, w in nodes if w.num}
            for n in nums:
                if n not in allowed:
                    by_num.setdefault(n, []).append([(s, w) for s, w in nodes if w.num == n])
        dup_nums = {n: g for n, g in by_num.items() if len(g) > 1}
    _cache["sig"], _cache["got"] = sig, (dup_tags, dup_nums)
    return dup_tags, dup_nums


def describe(project, dup_tags, dup_nums):
    """A line for the command line naming them: "Duplicate tag CR201 (sheets 2, 5); duplicate
    wire number 2004 (sheet 2)"."""
    def where(sheets):
        nums = sorted({project.sheet_number(s) for s in sheets}, key=str)
        return ("sheet " if len(nums) == 1 else "sheets ") + ", ".join(str(n) for n in nums)
    out = ["duplicate tag %s (%s)" % (t, where(s for s, _e in got))
           for t, got in sorted(dup_tags.items())]
    out += ["duplicate wire number %s (%s)" % (n, where(s for g in gs for s, _w in g))
            for n, gs in sorted(dup_nums.items())]
    if not out:
        return ""
    text = "; ".join(out[:4]) + (" and %d more" % (len(out) - 4) if len(out) > 4 else "")
    return text[0].upper() + text[1:]


def marks(project, sheet):
    """[(x0, y0, x1, y1)]: boxes on sheet around each duplicate tag (its tag text, or the
    device when its tag isn't shown) and each label of a duplicate wire number."""
    dup_tags, dup_nums = find(project)
    out = []
    for got in dup_tags.values():
        for s, e in got:
            if s is sheet:
                t = e.tag_text()
                out.append(t.bbox() if t is not None else e.bbox())
    if dup_nums:
        for t in wirenums.labels(project, sheet):
            if t.text in dup_nums:
                out.append(t.bbox())
    return out
