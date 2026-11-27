"""Contact pin numbers (0.28; the owner, Nov 27 2026: "13/14 and 21/22"). No Qt.

A contact placed is numbered the way the makers mark their contacts (Schneider TeSys, Sprecher +
Schuh CA7: NO 13-14, NC 21-22): the first digit is the contact's sequence number on its device,
the second what it is: 1-2 normally closed, 3-4 normally open, 5-6 a timed normally closed
contact, 7-8 a timed normally open one (EN 50005's "special function" digits). Its device's
first NO contact is 13-14 and its first NC 21-22 (sequences 1 and 2, as a contactor's own
auxiliary contacts are marked, whichever is drawn first); every other contact takes the
lowest sequence number no contact of that device uses, across the whole project (31-32 NC,
33-34 NO, 43-44...). An overload relay's contacts (an OL contact symbol) are 95-96 (NC) and 97-98
(NO) while those are free on their device.

What counts: a schematic symbol with a contact kind (Contact NO, NC, the timed ones, a
pushbutton's or a selector switch's contact blocks, a pushbutton, limit switch... itself) and
two pins whose block names are numbers (1 and 2 on the program's own): a contactor's power
contacts (L1-T3) keep their names. Its device: the device it belongs to (PARENT), or itself for
a pushbutton or a switch, or none for a contact on its own (numbered as the first of its kind).

When: a contact added to the drawing without numbers of its own (placed, pasted, copied from a
drawing of before 0.28) is numbered; one that joins a device (added with its numbers, as Copy
and Paste make it, or linked to another device) keeps them unless another contact of that device
has one of them, then it takes the next free pair. Numbers typed (the attributes window's Pin
numbers, the Properties panel) are kept as typed. Drawings of before 0.28 keep their numbers
(1 and 2): nothing is numbered on opening, or for being moved or edited.

The numbers are the copy's attributes TERM01 and TERM02 (Insert.pin_number), AutoCAD Electrical's
names for a symbol's pin numbers, so they go out to DXF as its attributes and come back."""

from . import tags
from .model import Insert, PIN_NUMBER

# the second digits of a contact's pair, by its kind
SECOND = {"NC": ("1", "2"), "NO": ("3", "4"), "NCTO": ("5", "6"), "NCTC": ("5", "6"),
          "NOTC": ("7", "8"), "NOTO": ("7", "8")}
# the sequence a device's first contact of a kind takes, when free
FIRST = {"NO": 1, "NC": 2}
# an overload relay's contacts
OVERLOAD = {"NC": ("95", "96"), "NO": ("97", "98")}


def attr(i):
    """The attribute holding a copy's number for its block's pin i (0 the first): TERM01..."""
    return PIN_NUMBER % (i + 1)


def numberable(e):
    """Whether a placed symbol is a contact numbered on its device (see the module)."""
    d = getattr(e, "defn", None)
    if not isinstance(e, Insert) or d is None or d.kind != "symbol" or \
            d.contact not in SECOND or len(d.pins) != 2:
        return False
    return all(p["name"].isdigit() for p in d.pins) and not tags.numbered(e)


def own(e):
    """A copy's own pin numbers [first, second], or None when it has none (it shows its
    block's)."""
    got = [e.attrs.get(attr(i), "") for i in range(2)]
    return got if all(got) else None


def numbers(e):
    """The numbers a contact shows, its pins' in order (its own, else its block's names)."""
    return [e.pin_number(p["name"]) for p in e.defn.pins]


def with_numbers(attrs, nums):
    """attrs with these pin numbers (none, or blanks: the block's names again)."""
    out = {k: v for k, v in (attrs or {}).items()
           if not (len(k) == 6 and k.startswith("TERM") and k[4:].isdigit())}
    nums = [str(n).strip() for n in (nums or ())]
    if any(nums):
        for i, n in enumerate(nums):
            if n:
                out[attr(i)] = n
    return out


def parse(text):
    """Pin numbers typed ("13, 14", "13-14", "13 14", "13/14"): [first, second], or [] when
    blank; None when it isn't two of them."""
    parts = [t for t in str(text or "").replace(",", " ").replace("/", " ").replace(
        "-", " ").split() if t]
    if not parts:
        return []
    return parts if len(parts) == 2 else None


def text(e):
    """A contact's numbers as people read them: "13-14" ("" for one showing its block's)."""
    got = own(e)
    return "-".join(got) if got else ""


def sequence(name):
    """The sequence number of a contact's pin number (13: 1, 95: 9, 101: 10), or None."""
    name = str(name)
    return int(name[:-1]) if len(name) >= 2 and name.isdigit() else None


def is_overload(e):
    return (e.defn.prefix or "").upper() == "OL"


def pair(e, others):
    """The numbers a contact takes on a device whose other contacts are others."""
    used = set()
    for o in others:
        used.update(numbers(o))
    seqs = {sequence(n) for n in used} - {None}
    kind = e.defn.contact
    mark = "NC" if kind.startswith("NC") else "NO"
    if is_overload(e):
        a, b = OVERLOAD[mark]
        if a not in used and b not in used:
            return [a, b]
    lo, hi = SECOND[kind]
    seq = FIRST.get(kind)
    if seq is None or seq in seqs:
        seq = 1
        while seq in seqs:
            seq += 1
    return ["%d%s" % (seq, lo), "%d%s" % (seq, hi)]


def device_of(e):
    """The key of the device a contact is numbered on (its device's hidden id), or None."""
    if tags.is_child(e):
        return e.attrs.get("PARENT") or None
    if tags.is_device(e):
        return e.attrs.get("DEV") or None
    return None


def by_device(project):
    """{device key: [(sheet, contact's id)]} of every numbered contact in the project."""
    out = {}
    for s in project.sheets:
        for e in s.inserts():
            if numberable(e):
                k = device_of(e)
                if k:
                    out.setdefault(k, []).append((s, e.id))
    return out


def number_contacts(ed, project):
    """Number the contacts this edit added or linked to another device (see the module):
    run with the other bookkeeping when an edit ends (tags.sync_children)."""
    todo = []
    for op in ed.ops:
        if op[0] != "ent" or not op[4] or op[4].get("kind") != "insert":
            continue
        s = project.sheet_by_id(op[1])
        e = s.entities.get(op[2]) if s is not None else None
        if e is None or not numberable(e):
            continue
        before = op[3] if op[3] and op[3].get("kind") == "insert" else None
        had = (before or {}).get("attrs", {})
        mine = own(e)
        if before is None:
            todo.append((s, e.id, mine is None))
        elif mine is not None and had.get("PARENT") != e.attrs.get("PARENT") and \
                all(had.get(attr(i)) == e.attrs.get(attr(i)) for i in range(2)):
            todo.append((s, e.id, False))       # (joined a device: kept unless taken there)
    if not todo:
        return
    groups = None
    for s, eid, fresh in todo:
        e = s.entities.get(eid)
        if e is None:
            continue
        if groups is None:
            groups = by_device(project)
        k = device_of(e)
        others = []
        for sh, oid in groups.get(k, ()) if k else ():
            o = sh.entities.get(oid)
            if o is not None and not (sh is s and oid == eid) and device_of(o) == k:
                others.append(o)
        if not fresh:
            taken = set()
            for o in others:
                taken.update(numbers(o))
            if not taken & set(own(e)):
                continue
        ed.change(s, e.copy(attrs=with_numbers(e.attrs, pair(e, others))))
