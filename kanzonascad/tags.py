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
- A footprint on a panel sheet belongs to a device the same way (asked as it is placed:
  footprint_candidates) and shows its tag, following it when it is renumbered.
- In a project of IEC 60617 symbols (Project properties, Schematic) a device's tag is made of
  its IEC 81346-2 class letter instead of its symbol's US prefix (prefix_for(): K601 for a
  relay, Q601 for a contactor or a breaker, X601 for a terminal strip; IEC_LETTERS). The symbol's
  prefix still says what kind of device it is to the program (PLC, TB...). A tag made of the
  other letters (one from before the project's standard was changed, No said to retagging)
  is kept as it is and still follows its page (tag_prefix); Renumber sheet and a copy give the
  project's letters, and so does Yes when the standard is changed (retag_letters). A device or
  contact with no tag yet shows the project's letter and "?" (K?: BlockDef.tag_letter).
"""

import re
import uuid

from .model import DashBox, Insert, RATING_FIELDS
from .symbols_iec import standard_of

ORDERS = {"across": "Across, then down", "down": "Down, then across",
          "wires": "Along the wires, from a source (Numbering source)"}


def is_device(e):
    """A placed symbol that gets its own tag."""
    d = getattr(e, "defn", None)
    return (isinstance(e, Insert) and d is not None and d.kind == "symbol"
            and d.role in ("device", "parent") and bool(d.prefix))


# {US prefix (a symbol's): its IEC 81346-2:2019 class letter} (an IEC project's tags). The
# classes, by what an object does (IEC 81346-2:2019, Table 1), as public summaries give them
# (found by web search, Nov 2026: https://en.wikipedia.org/wiki/IEC_81346,
# https://tagsight.io/learn/what-is-iec-81346, https://fasecad.com/iec-81346-reference-designation;
# the standard's own text, sold by the IEC, not read: the subclasses in brackets are the
# likeliest, not checked):
#   K processing signals or information: control relays, timing relays, PLCs (KF);
#   Q controlled switching of a flow of energy: contactors (their coil and main contacts, one
#     device), circuit breakers, motor protection breakers, disconnectors (QA, QB);
#   S turning a manual action into a signal: pushbuttons, selector switches, E-stops (SF);
#   B turning a physical property into a signal: limit (position), pressure, temperature and
#     float switches, sensors (BG, BP, BT, BL);
#   F protecting against dangerous conditions: fuses, overload relays (FA, FC);
#   P presenting information: pilot lights (PF);
#   M providing mechanical energy: motors, actuating solenoids (MA, MB);
#   T converting energy, keeping its kind: transformers, power supplies (AC/DC), drives
#     (frequency converters) (TA, TB);
#   R restricting or stabilizing a flow of energy: line and load reactors (RA; 0.30, the
#     motor-circuit UDTs' Reactor 3-pole, tagged LR in a JIC project);
#   X connecting: terminal strips, distribution blocks (XD).
# A prefix not here (one of your own) is kept as it is in an IEC project too.
IEC_LETTERS = {"CR": "K", "TR": "K", "PLC": "K",
               "M": "Q", "CB": "Q", "DS": "Q",
               "PB": "S", "SS": "S",
               "LS": "B", "FS": "B", "TS": "B",
               "FU": "F", "OL": "F",
               "LT": "P",
               "MTR": "M", "SOL": "M",
               "T": "T", "PS": "T", "VFD": "T", "LR": "R",
               "TB": "X", "DB": "X", "PDB": "X"}
# (PS is both a power supply and a pressure switch's prefix: the switch, the one with contacts
# of its own, a parent, is a sensor)
IEC_ROLE_LETTERS = {("PS", "parent"): "B"}


def prefix_for(project, defn, standard=None):
    """What a device of defn's tag is made of in project: its symbol's prefix (CR, M, PB...), or
    its IEC 81346-2 letter (IEC_LETTERS) in a project of IEC 60617 symbols. standard: as if the
    project's symbol standard were that one ("jic" or "iec")."""
    if standard is None:
        standard = standard_of(project) if project is not None else "jic"
    if not defn.prefix or standard != "iec":
        return defn.prefix
    return _letter(defn)


def _letter(defn):
    return IEC_ROLE_LETTERS.get((defn.prefix, defn.role)) or IEC_LETTERS.get(defn.prefix,
                                                                             defn.prefix)


def tag_prefix(project, e, standard=None):
    """The prefix device e's tag is made of: the project's (prefix_for()), or, for a tag made
    of the other standard's letters (from before the project's standard was changed), those.
    standard: as prefix_for's."""
    pre = prefix_for(project, e.defn, standard)
    tag = e.attrs.get("TAG", "")
    for other in (pre, e.defn.prefix, _letter(e.defn)):
        if other and split(tag, other) is not None:
            return other
    return pre


def other_letters(project, e, standard=None):
    """Device e is unlocked and its tag is made of the other standard's letters (CR601 in a
    project of IEC 60617 symbols, K601 in a JIC one): Yes to "Retag the unlocked devices"
    gives it the project's (retag_letters). standard: as prefix_for's."""
    if not is_device(e) or locked(e):
        return False
    pre = tag_prefix(project, e, standard)
    return pre != prefix_for(project, e.defn, standard) and \
        split(e.attrs.get("TAG", ""), pre) is not None


def to_retag(project, standard=None):
    """[(sheet, device)]: the devices other_letters() finds in project."""
    return [(s, e) for s in project.sheets for e in s.inserts()
            if other_letters(project, e, standard)]


def retag_letters(ed, project):
    """The project's symbol standard was changed (Project properties) and Yes said to "Retag
    the unlocked devices with the <new> letters?": every unlocked device whose tag is made of
    the other standard's letters takes the project's, its page and count kept when free
    (CR601 becomes K601; TR601 beside it K602), as Update numbers fixes a sheet (fix_sheet).
    Contacts, terminals (X601-1) and the arrows' devices follow it as for any new tag; locked
    tags stay. Returns how many changed."""
    return sum(fix_sheet(ed, project, s, letters=True) for s in project.sheets)


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


def used_counts(project, prefix, page, skip=(), on=None):
    """Counts already taken for prefix on page, over the whole project (a tag typed by hand on
    another sheet still takes its number). Only devices count: a contact's tag is its device's,
    and so is a footprint's (counted, a drive's footprint and its power section on another
    sheet, still tagged VFD201, made Renumber sheet skip 201: VFD204 one time, back to VFD201
    the next once they had followed; the owner, Nov 2026, "I never know what they're going to
    do"). skip: ids of devices on sheet on (or on every sheet when on is None) not to count:
    ids are a sheet's own, so another sheet's device with the same id still counts (the long
    battery, 0.18, seed 3152: two DS404 after Update numbers)."""
    out = set()
    for s in project.sheets:
        for e in s.inserts():
            if (e.id in skip and (on is None or s is on)) or not is_device(e):
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
        pre = prefix_for(project, defn)
        out["TAG"] = make(pre, page, lowest_free(used_counts(project, pre, page)))
    return out


def _rk(p):
    return (round(p[0], 6), round(p[1], 6))


def wire_walk(sheet):
    """{point: order} of the points the wires reach from the sheet's numbering source
    (Sheet.number_from: a symbol, a disconnect say), walked as one traces a drawing by eye
    (the owner, 0.18: "Can it track my bus?"): from the source's pins along its wires; at a tap
    or a tee every turn first, then straight on; into a symbol at a pin and out of its other
    pins (in its pins' order). So each branch off a bus is walked through (its devices and
    their wires) before the bus goes on to the next one, however the bus winds round the
    sheet. None when there is no source. Kept until the sheet changes."""
    src = sheet.entities.get(sheet.number_from) if sheet.number_from is not None else None
    if src is None or getattr(src, "kind", "") != "insert" or not src.pin_points():
        return None
    got = getattr(sheet, "_wire_walk", None)
    if got is not None and got[0] == (sheet.version, sheet.number_from):
        return got[1]
    from .wires import TOL
    adj = {}                                     # node -> [(node, direction or None, rank)]

    def link(a, b, d, rank):
        adj.setdefault(a, []).append((b, d, rank))
    wires = sheet.wires()
    stops = {}                                   # wire id -> [length along it]
    for w in wires:
        for q in (w.points[0], w.points[-1]):
            for x in sheet.query_point(q, TOL):
                if getattr(x, "kind", "") == "wire" and x.id != w.id and x.touches(q, TOL):
                    stops.setdefault(x.id, []).append(x.length_at(q))
    pins = {}
    for e in sheet.inserts():
        pp = [q for _n, q in e.pin_points()]
        for q in pp:
            pins[_rk(q)] = e
            for x in sheet.query_point(q, TOL):
                if getattr(x, "kind", "") == "wire" and x.touches(q, TOL):
                    stops.setdefault(x.id, []).append(x.length_at(q))
        for a in pp:
            for b in pp:
                if a != b:
                    link(_rk(a), _rk(b), None, 0)      # (through the symbol: first)
    for w in wires:
        corners, run = [0.0], 0.0
        for a, b in zip(w.points, w.points[1:]):
            run += ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            corners.append(run)
        cut = sorted(set(round(t, 9) for t in corners + stops.get(w.id, [])))
        pts = [w.at_length(t)[0] for t in cut]
        for a, b in zip(pts, pts[1:]):
            L = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
            if L <= TOL:
                continue
            d = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            link(_rk(a), _rk(b), d, 1)
            link(_rk(b), _rk(a), (-d[0], -d[1]), 1)
    order = {}
    stack = [(_rk(q), None) for _n, q in reversed(src.pin_points())]
    while stack:
        node, din = stack.pop()
        if node in order:
            continue
        order[node] = len(order)
        nxt = []
        for b, d, rank in adj.get(node, ()):
            if b in order:
                continue
            straight = d is not None and din is not None and \
                abs(d[0] - din[0]) < 1e-6 and abs(d[1] - din[1]) < 1e-6
            # (through a symbol first, then the turns, then straight on)
            turn = 0 if d is None else (2 if straight else 1)
            ang = 0.0 if d is None else (d[0] * 2 + d[1])
            nxt.append(((turn, -ang), b, d))
        nxt.sort(key=lambda t: t[0])
        for _k, b, d in reversed(nxt):
            stack.append((b, d))
    sheet._wire_walk = ((sheet.version, sheet.number_from), order)
    return order


def order_key(sheet, how):
    """Sorting key of a point for a sheet's numbering order (by zone, then position; along
    the wires: by wire_walk, the points it doesn't reach after, by zone). key(p, pins): a
    symbol's key is its first pin's in the walk."""
    rows = {n: i for i, n in enumerate(sheet.row_labels())}
    cols = {n: i for i, n in enumerate(sheet.col_labels())}
    walk = wire_walk(sheet) if how == "wires" else None

    def zone(p):
        z = sheet.zone_at(p[0], p[1])
        r = rows.get(z[0], 0) if z else 0
        c = cols.get(z[1], 0) if z else 0
        if how == "down":
            return (c, r, -p[1], p[0])
        return (r, c, -p[1], p[0])

    def key(p, pins=()):
        if walk is not None:
            got = [walk[_rk(q)] for q in list(pins) + [p] if _rk(q) in walk]
            if got:
                return (0, min(got), 0.0, 0.0)
            return (1,) + zone(p)
        return zone(p)
    return key


def renumber_sheet(ed, project, sheet):
    """Give the sheet's unlocked devices the counts 01, 02... per prefix (the project's: an IEC
    project's letters, prefix_for()), in the sheet's order. Locked tags keep theirs (and their
    numbers are skipped). Returns how many changed."""
    page = project.sheet_number(sheet)
    key = order_key(sheet, sheet.number_order)
    devices = [e for e in sheet.entities.values() if is_device(e)]
    pos = {e.id: key(e.pos, [q for _n, q in e.pin_points()]) for e in devices}
    changed = 0
    pre = {e.id: prefix_for(project, e.defn) for e in devices}
    # (every unlocked device here is given a tag: the one it has holds no count, of any
    # prefix; the battery, seed 2903: a contactor's JIC M101 in an IEC project, about to be
    # Q101, held 01 for the motors numbered before it, M sorting before Q)
    mine = {e.id for e in devices if not locked(e)}
    for p in sorted(set(pre.values())):
        group = [e for e in devices if pre[e.id] == p and not locked(e)]
        group.sort(key=lambda e: pos[e.id])
        taken = used_counts(project, p, page, skip=mine, on=sheet)
        n = 0
        for e in group:
            n = lowest_free(taken | set(range(1, n + 1)))
            tag = make(p, page, n)
            attrs = dict(e.attrs)
            attrs.setdefault("DEV", uuid.uuid4().hex[:12])
            if attrs.get("TAG") != tag or attrs != e.attrs:
                attrs["TAG"] = tag
                ed.change(sheet, e.copy(attrs=attrs))
                changed += 1
    return changed


def set_locks(ed, sheet, ents, lock):
    """Lock (or unlock) the tags of the devices among ents (contacts take their device's):
    TAG_LOCK, as a device's "Lock this tag". Returns how many changed."""
    n = 0
    for e in ents:
        if not is_device(e) or locked(e) == lock:
            continue
        attrs = dict(e.attrs)
        if lock:
            attrs["TAG_LOCK"] = "1"
        else:
            attrs.pop("TAG_LOCK", None)
        ed.change(sheet, e.copy(attrs=attrs))
        n += 1
    return n


def fix_sheet(ed, project, sheet, letters=False):
    """Update numbers and cross-references' "keep, only fix" (0.18): the sheet's unlocked
    devices keep their tags; one with no tag (or only its prefix and ?) or a tag not of this
    sheet's page takes one (its count kept when free here, else the lowest free one). letters:
    only the devices whose tags are made of the other standard's letters (other_letters) are
    fixed, given the project's (retag_letters). Returns how many changed."""
    page = project.sheet_number(sheet)
    changed = 0
    key = order_key(sheet, sheet.number_order)
    # (a tag two devices have is fixed too: the later in order takes a free one; the tags of
    # other sheets' devices and of this sheet's locked ones are kept)
    seen = {e.attrs.get("TAG", "") for s in project.sheets for e in s.inserts()
            if is_device(e) and (s is not sheet or locked(e))}
    for e in sorted((e for e in sheet.entities.values() if is_device(e) and not locked(e)),
                    key=lambda e: key(e.pos, [q for _n, q in e.pin_points()])):
        # (a tag of the other standard's letters is kept, and fixed in them; with letters,
        # given the project's)
        if letters:
            if not other_letters(project, e):
                continue
            pre = prefix_for(project, e.defn)
            got = split(e.attrs.get("TAG", ""), tag_prefix(project, e))
        else:
            pre = tag_prefix(project, e)
            got = split(e.attrs.get("TAG", ""), pre)
            if got is not None and got[0] == page and e.attrs.get("TAG") not in seen:
                seen.add(e.attrs["TAG"])
                continue
        taken = used_counts(project, pre, page, skip={e.id}, on=sheet)
        if got is not None and got[0] == page and not letters:
            taken.add(got[1])                   # (a duplicate: not its own count again)
        n = got[1] if got is not None and got[1] not in taken else lowest_free(taken)
        attrs = dict(e.attrs, TAG=make(pre, page, n))
        attrs.setdefault("DEV", uuid.uuid4().hex[:12])
        seen.add(attrs["TAG"])
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
            pre = tag_prefix(project, e)
            got = split(e.attrs.get("TAG", ""), pre)
            if got is None or got[0] == page:
                continue
            taken = used_counts(project, pre, page, skip={e.id}, on=s)
            n = got[1] if got[1] not in taken else lowest_free(taken)
            attrs = dict(e.attrs, TAG=make(pre, page, n))
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
            # (a lock on no tag keeps nothing: the copy gets one, or it would be a device
            # with no tag a footprint links to, showing none; the long battery, 0.25, seed
            # 4913: a block made with Make block, its tags locked, then copied)
            if not locked(e) or not (attrs.get("TAG") or "").strip():
                # (in the project's letters: a JIC device pasted into an IEC project, CR601,
                # becomes K701; its count kept when free)
                pre = prefix_for(project, e.defn)
                taken = used_counts(project, pre, page) | planned.setdefault(pre, set())
                got = split(attrs.get("TAG", ""), tag_prefix(project, e))
                n = got[1] if got and got[1] not in taken else lowest_free(taken)
                planned[pre].add(n)
                attrs["TAG"] = make(pre, page, n)
            e = e.copy(attrs=attrs)
        elif numbered(e) and any(e.attrs.get(a) for a in NUMBER_ATTRS):
            # a copied terminal takes the next free number on its strip (an outlet, on its
            # distribution block)
            e = e.copy(attrs={k: v for k, v in e.attrs.items() if k not in NUMBER_ATTRS})
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


def is_footprint(e):
    d = getattr(e, "defn", None)
    return isinstance(e, Insert) and d is not None and d.kind == "footprint"


def footprint_candidates(project, cat=""):
    """[(sheet, device)] a footprint about to be placed can be (the owner, 0.16: "I need parts
    to auto label when inserting footprints"): the devices no footprint is yet (linked, or
    with its tag), one with the footprint's catalog number first, then in page order and,
    on a page, by tag."""
    linked, tagged = set(), set()
    for s in project.sheets:
        for e in s.inserts():
            if is_footprint(e):
                if e.attrs.get("PARENT"):
                    linked.add(e.attrs["PARENT"])
                if e.attrs.get("TAG"):
                    tagged.add(e.attrs["TAG"].strip().upper())
    cat = (cat or "").strip().upper()
    out = []
    for i, s in enumerate(project.sheets):
        for e in s.inserts():
            dev, tag = e.attrs.get("DEV"), e.attrs.get("TAG", "").strip()
            if not is_device(e) or not dev or dev in linked or tag.upper() in tagged:
                continue
            same = bool(cat) and e.attrs.get("CAT", "").strip().upper() == cat
            m = re.match(r"([A-Za-z]*)(\d*)", tag)
            out.append(((0 if same else 1, i, m.group(1), int(m.group(2) or 0), tag), s, e))
    out.sort(key=lambda t: t[0])
    return [(s, e) for _k, s, e in out]


# a device's attributes its footprint has too, kept the same both ways (the owner, 0.18.1:
# "once linked, I should be able to see and show the attributes from the linked schematic
# device"; asked: edit from either): its ratings
LINKED_ATTRS = tuple(RATING_FIELDS) + ("RATING",)


def linked_values(attrs, device):
    """attrs with the device's ratings (LINKED_ATTRS): its values, none where it has none."""
    out = dict(attrs or {})
    for k in LINKED_ATTRS:
        v = device.attrs.get(k, "")
        if v:
            out[k] = v
        else:
            out.pop(k, None)
    return out


# a footprint block's own properties, the default for every copy of it
OWN_FIELDS = {"MFR": "manufacturer", "CAT": "catalog", "DESC": "description"}


def own_default(defn, key):
    """What a footprint block says for key (MFR, CAT, DESC) where a copy has none ("")."""
    return str(getattr(defn, OWN_FIELDS[key], "") or "") if defn is not None else ""


def link_footprint(attrs, device, defn=None):
    """A footprint's attributes as the footprint of device: its id and tag, its ratings, and
    the device's manufacturer, catalog number and description where neither the footprint
    copy nor its block (defn, Properties...) has one: the footprint's own come first (the
    owner, 0.18.6: "shouldn't it default to the footprint settings?")."""
    out = dict(attrs or {})
    out["PARENT"] = device.attrs["DEV"]
    out["TAG"] = device.attrs.get("TAG", "")
    for k in OWN_FIELDS:
        if not out.get(k) and not own_default(defn, k) and device.attrs.get(k):
            out[k] = device.attrs[k]
    return linked_values(out, device)


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
            if not is_child(e) and not (is_footprint(e) and e.attrs.get("PARENT")):
                continue                # (a footprint follows the device it was placed as)
            dev = e.attrs.get("PARENT")
            got = index.get(dev) if dev else None
            fp = is_footprint(e)
            if got is not None:
                want = link_attrs(e.attrs, got[1])
                if fp:
                    want = linked_values(want, got[1])      # (its device's ratings too)
                if want != e.attrs:
                    ed.change(s, e.copy(attrs=want))
            elif e.attrs.get("TAG"):
                p = by_tag.get(e.attrs["TAG"].upper())
                if p is not None:
                    want = link_attrs(e.attrs, p)
                    ed.change(s, e.copy(attrs=linked_values(want, p) if fp else want))
        # dashed boxes that belong to a device show its tag, as contacts do
        for e in list(s.entities.values()):
            if not is_linked_box(e):
                continue
            dev = e.attrs.get("PARENT")
            got = index.get(dev) if dev else None
            if got is not None:
                if got[1].attrs.get("TAG", "") != e.tag():
                    ed.change(s, e.copy(attrs=link_attrs(e.attrs, got[1])))
            elif e.tag() and not dev:
                p = by_tag.get(e.tag().upper())
                if p is not None:
                    ed.change(s, e.copy(attrs=link_attrs(e.attrs, p)))
    number_terminals(ed, project)
    # contacts placed or linked to another device: their pin numbers there (13-14, 21-22...)
    from .pinnumbers import number_contacts
    number_contacts(ed, project)


def is_linked_box(e):
    """A dashed box that belongs to a device (or names one by its tag)."""
    return isinstance(e, DashBox) and bool(e.attrs.get("PARENT") or e.attrs.get("TAG"))


def device_choices(project):
    """[(sheet, device)] a dashed box (or a contact) can belong to, in page order and by tag
    on a page: the Belongs to list."""
    out = []
    for i, s in enumerate(project.sheets):
        for e in s.inserts():
            if is_device(e) and e.attrs.get("DEV"):
                tag = e.attrs.get("TAG", "")
                m = re.match(r"([A-Za-z]*)(\d*)", tag)
                out.append(((i, m.group(1), int(m.group(2) or 0), tag), s, e))
    out.sort(key=lambda t: t[0])
    return [(s, e) for _k, s, e in out]


# (the attributes a child numbers itself by on its parent: a terminal's on its strip, an outlet's
# on its power distribution block, PDB1-1, PDB1-2...)
NUMBER_ATTRS = ("TERM", "OUTLET")


def number_attr(e):
    """The attribute a contact-like symbol is numbered by on its device (TERM, OUTLET), or
    None."""
    d = getattr(e, "defn", None)
    if d is None:
        return None
    if d.wiring == "pdb" and d.role == "child":
        return "OUTLET"                 # (shown in its tag: PDB1-1)
    return next((a["attr"] for a in d.attr_texts if a["attr"] in NUMBER_ATTRS), None)


def numbered(e):
    """A contact-like symbol numbered on its device (a terminal on its strip: TERM; an outlet
    on its distribution block: OUTLET)."""
    return number_attr(e) is not None


def number_terminals(ed, project):
    """Terminals on a strip (outlets on a distribution block) without a number take the
    lowest free one there (1, 2, 3...); a number typed stays."""
    by_strip = {}
    for s in project.sheets:
        for e in s.inserts():
            if is_child(e) and numbered(e) and e.attrs.get("PARENT"):
                by_strip.setdefault((e.attrs["PARENT"], number_attr(e)), []).append((s, e))
    for (_parent, attr), items in by_strip.items():
        used = set()
        for _s, e in items:
            v = e.attrs.get(attr, "")
            if v.isdigit():
                used.add(int(v))
        for s, e in sorted(items, key=lambda se: (project.sheets.index(se[0]),
                                                   order_key(se[0], se[0].number_order)(
                                                       se[1].pos))):
            if e.attrs.get(attr):
                continue
            n = 1
            while n in used:
                n += 1
            used.add(n)
            ed.change(s, e.copy(attrs=dict(e.attrs, **{attr: str(n)})))
