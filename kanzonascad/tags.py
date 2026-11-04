"""Device tags by page number, worked out by the program (no Qt).

A device is a placed schematic symbol whose role is "device" or "parent" (a coil, a pushbutton,
a fuse...) and whose symbol has a tag prefix (CR, M, PB...). Its tag is the prefix, the page
number of its sheet and a two-digit count on that page: CR601, CR602, M601; on page 12, CR1201.

- A device placed without a tag gets the lowest free count for its prefix on its page.
- A tag typed by hand is locked (attribute TAG_LOCK): numbering never changes it.
- Renumber sheet gives the unlocked devices of a sheet the counts 01, 02... in the sheet's
  numbering order (across then down, or down then across).
- When a sheet's page number changes (typed, or by moving sheets), its unlocked tags follow:
  CR601 becomes CR701 (sync_pages, run at the end of every edit that touched sheets).
- Every device also carries a hidden id (attribute DEV) that survives renaming: cross-references
  and panel footprints will link through it.
"""

import re
import uuid

from .model import Insert

ORDERS = {"across": "Across, then down", "down": "Down, then across"}


def is_device(e):
    """A placed symbol that gets its own tag."""
    d = getattr(e, "defn", None)
    return (isinstance(e, Insert) and d is not None and d.kind == "symbol"
            and d.role in ("device", "parent") and bool(d.prefix))


def locked(e):
    return e.attrs.get("TAG_LOCK") == "1"


def split(tag, prefix):
    """(page, count) of a tag made as prefix + page + two digits, else None."""
    m = re.fullmatch(re.escape(prefix) + r"(\d+?)(\d\d)", tag or "")
    if not m:
        return None
    return m.group(1), int(m.group(2))


def make(prefix, page, count):
    return "%s%s%02d" % (prefix, page, count)


def used_counts(project, prefix, page, skip=()):
    """Counts already taken for prefix on page, over the whole project (a tag typed by hand on
    another sheet still takes its number)."""
    out = set()
    for s in project.sheets:
        for e in s.entities.values():
            if e.id in skip or not isinstance(e, Insert):
                continue
            got = split(e.attrs.get("TAG", ""), prefix)
            if got and got[0] == page:
                out.add(got[1])
    return out


def lowest_free(taken):
    n = 1
    while n in taken:
        n += 1
    return n


def new_attrs(project, sheet, defn, attrs):
    """The attributes of a device about to be placed on sheet: its tag (if it has none) and
    its hidden id."""
    out = dict(attrs or {})
    if defn is None or defn.kind != "symbol" or defn.role not in ("device", "parent") \
            or not defn.prefix:
        return out
    out.setdefault("DEV", uuid.uuid4().hex[:12])
    if not out.get("TAG"):
        page = project.sheet_number(sheet)
        out["TAG"] = make(defn.prefix, page,
                          lowest_free(used_counts(project, defn.prefix, page)))
    return out


def order_key(sheet, how):
    """Sorting key of a point for a sheet's numbering order (by zone, then position)."""
    def key(p):
        z = sheet.zone_at(p[0], p[1])
        rows = sheet.row_labels()
        cols = sheet.col_labels()
        r = rows.index(z[0]) if z else 0
        c = cols.index(z[1]) if z else 0
        if how == "down":
            return (c, r, -p[1], p[0])
        return (r, c, -p[1], p[0])
    return key


def renumber_sheet(ed, project, sheet):
    """Give the sheet's unlocked devices the counts 01, 02... per prefix, in the sheet's order.
    Locked tags keep theirs (and their numbers are skipped). Returns how many changed."""
    page = project.sheet_number(sheet)
    key = order_key(sheet, sheet.number_order)
    devices = [e for e in sheet.entities.values() if is_device(e)]
    changed = 0
    for prefix in sorted({e.defn.prefix for e in devices}):
        group = [e for e in devices if e.defn.prefix == prefix and not locked(e)]
        group.sort(key=lambda e: key(e.pos))
        taken = used_counts(project, prefix, page, skip={e.id for e in group})
        n = 0
        for e in group:
            n = lowest_free(taken | set(range(1, n + 1)))
            tag = make(prefix, page, n)
            attrs = dict(e.attrs)
            attrs.setdefault("DEV", uuid.uuid4().hex[:12])
            if attrs.get("TAG") != tag or attrs != e.attrs:
                attrs["TAG"] = tag
                ed.change(sheet, e.copy(attrs=attrs))
                changed += 1
    return changed


def sync_pages(ed, project):
    """Unlocked device tags whose page part isn't their sheet's page number any more (the sheet
    was renumbered or moved) take the right page, keeping their count when it's free."""
    for s in project.sheets:
        page = project.sheet_number(s)
        for e in list(s.entities.values()):
            if not is_device(e) or locked(e):
                continue
            got = split(e.attrs.get("TAG", ""), e.defn.prefix)
            if got is None or got[0] == page:
                continue
            taken = used_counts(project, e.defn.prefix, page, skip={e.id})
            n = got[1] if got[1] not in taken else lowest_free(taken)
            attrs = dict(e.attrs, TAG=make(e.defn.prefix, page, n))
            ed.change(s, e.copy(attrs=attrs))


def retag_copies(project, sheet, ents):
    """Devices about to be added to sheet as copies (Copy, Paste, Mirror keeping the original):
    each unlocked one gets a free tag of this page (its count kept when that's free here, so
    CR601 pasted on page 7 becomes CR701) and every copy a new hidden id. A locked tag is kept
    as typed."""
    page = project.sheet_number(sheet)
    planned = {}                                   # prefix -> counts given in this batch
    out = []
    for e in ents:
        if is_device(e):
            attrs = dict(e.attrs, DEV=uuid.uuid4().hex[:12])
            if not locked(e):
                prefix = e.defn.prefix
                taken = used_counts(project, prefix, page) | planned.setdefault(prefix, set())
                got = split(attrs.get("TAG", ""), prefix)
                n = got[1] if got and got[1] not in taken else lowest_free(taken)
                planned[prefix].add(n)
                attrs["TAG"] = make(prefix, page, n)
            e = e.copy(attrs=attrs)
        e.id = None                     # (a copy: a new object, whatever kind it is)
        out.append(e)
    return out
