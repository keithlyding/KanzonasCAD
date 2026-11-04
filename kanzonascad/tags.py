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
- Every device also carries a hidden id (attribute DEV) that survives renaming: contacts,
  cross-references and panel footprints link through it.
- A contact (role "child") belongs to a device through that id and shows its tag (below).
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
    another sheet still takes its number). Contacts don't count: their tag is their device's."""
    out = set()
    for s in project.sheets:
        for e in s.inserts():
            if e.id in skip or is_child(e):
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
    rows = {n: i for i, n in enumerate(sheet.row_labels())}
    cols = {n: i for i, n in enumerate(sheet.col_labels())}

    def key(p):
        z = sheet.zone_at(p[0], p[1])
        r = rows.get(z[0], 0) if z else 0
        c = cols.get(z[1], 0) if z else 0
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
        elif numbered(e) and e.attrs.get("TERM"):
            # a copied terminal takes the next free number on its strip
            e = e.copy(attrs={k: v for k, v in e.attrs.items() if k != "TERM"})
        e.id = None                     # (a copy: a new object, whatever kind it is)
        out.append(e)
    return out


# ---- contacts and their parent ------------------------------------------------------------
# A contact (a symbol whose role is "child": a relay contact, an overload contact...) belongs
# to a parent device (a coil, a pushbutton operator...) through the parent's hidden id: its
# attribute PARENT holds the parent's DEV. It shows the parent's tag (kept in its TAG, which
# follows the parent: sync_children). A contact with a tag but no parent yet links itself to
# the device that takes that tag later.

def is_child(e):
    d = getattr(e, "defn", None)
    return isinstance(e, Insert) and d is not None and d.kind == "symbol" and d.role == "child"


def devices(project):
    """{hidden id: (sheet, device)} of every device in the project."""
    out = {}
    for s in project.sheets:
        for e in s.inserts():
            if is_device(e) and e.attrs.get("DEV"):
                out[e.attrs["DEV"]] = (s, e)
    return out


def parent_of(project, child, index=None):
    """(sheet, parent device) of a contact, or None (not linked, or its parent is gone)."""
    dev = child.attrs.get("PARENT")
    if not dev:
        return None
    return (index if index is not None else devices(project)).get(dev)


def candidates(project, sheet, prefix, pos):
    """The devices a contact can belong to, as (sheet, device): parents (coils, operators)
    before plain devices, those with the contact's own prefix first (a CR contact: CR coils,
    then M, TR... coils, since a contactor's auxiliary contact is the same symbol), then this
    sheet before the others, nearest first."""
    out = []
    for i, s in enumerate(project.sheets):
        for e in s.inserts():
            if is_device(e) and e.attrs.get("DEV"):
                here = s is sheet
                d = ((e.pos[0] - pos[0]) ** 2 + (e.pos[1] - pos[1]) ** 2) if here else 0.0
                out.append(((0 if e.defn.role == "parent" else 1,
                             0 if e.defn.prefix == prefix else 1, 0 if here else 1, i, d,
                             e.attrs.get("TAG", "")), s, e))
    out.sort(key=lambda t: t[0])
    return [(s, e) for _k, s, e in out]


def find_tag(project, tag, prefix=None):
    """(sheet, device) whose tag is tag (and prefix, when given), or None."""
    tag = (tag or "").strip().upper()
    if not tag:
        return None
    for s in project.sheets:
        for e in s.inserts():
            if is_device(e) and e.attrs.get("TAG", "").upper() == tag \
                    and (prefix is None or e.defn.prefix == prefix):
                return s, e
    return None


def link_attrs(attrs, parent):
    """attrs of a contact linked to parent (a device), or unlinked when parent is None (its
    tag kept as it is)."""
    out = dict(attrs or {})
    if parent is None:
        out.pop("PARENT", None)
    else:
        out["PARENT"] = parent.attrs["DEV"]
        out["TAG"] = parent.attrs.get("TAG", "")
    return out


def sync_children(ed, project):
    """Contacts show their parent's tag; a contact with a tag and no parent (never linked, or
    its device was deleted) links itself to a device that has that tag now."""
    index = devices(project)
    by_tag = {}
    for dev, (_s, e) in index.items():
        by_tag.setdefault(e.attrs.get("TAG", "").upper(), e)
    for s in project.sheets:
        for e in list(s.inserts()):
            if not is_child(e):
                continue
            dev = e.attrs.get("PARENT")
            got = index.get(dev) if dev else None
            if got is not None:
                if got[1].attrs.get("TAG", "") != e.attrs.get("TAG", ""):
                    ed.change(s, e.copy(attrs=link_attrs(e.attrs, got[1])))
            elif e.attrs.get("TAG"):
                p = by_tag.get(e.attrs["TAG"].upper())
                if p is not None:
                    ed.change(s, e.copy(attrs=link_attrs(e.attrs, p)))
    number_terminals(ed, project)


def numbered(e):
    """A contact-like symbol numbered on its device (a terminal on its strip: TERM)."""
    d = getattr(e, "defn", None)
    return d is not None and any(a["attr"] == "TERM" for a in d.attr_texts)


def number_terminals(ed, project):
    """Terminals on a strip without a number take the lowest free one on that strip (1, 2,
    3...); a number typed stays."""
    by_strip = {}
    for s in project.sheets:
        for e in s.inserts():
            if is_child(e) and numbered(e) and e.attrs.get("PARENT"):
                by_strip.setdefault(e.attrs["PARENT"], []).append((s, e))
    for items in by_strip.values():
        used = set()
        for _s, e in items:
            v = e.attrs.get("TERM", "")
            if v.isdigit():
                used.add(int(v))
        for s, e in sorted(items, key=lambda se: (project.sheets.index(se[0]),
                                                   order_key(se[0], se[0].number_order)(
                                                       se[1].pos))):
            if e.attrs.get("TERM"):
                continue
            n = 1
            while n in used:
                n += 1
            used.add(n)
            ed.change(s, e.copy(attrs=dict(e.attrs, TERM=str(n))))
