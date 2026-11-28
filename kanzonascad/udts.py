"""UDTs (no Qt): circuit types with choices, optional parts and ratings, placed as ordinary
objects (the owner, Nov 2026: a whole motor circuit, "manual starter is swappable with fuses,
things could be removed and added (like line/load reactors), and ratings could be assigned for
all devices ... as if it was a bunch of individual parts like normal"; named "UDT" as in PLCs
and Ignition, the owner's choice).

A UDT is a saved circuit (circuits.py) whose objects are its members, each with a role (r1,
r2...) that stays the same through every edit of the UDT, and:

- slots: a choice between alternatives (Protection: Manual starter or Fuses), each member of a
  slot belonging to one alternative; an optional part is a slot of two, Included and Left out,
  the second holding the wires that bridge the gap so the circuit stays connected;
- values: what it is worked out from (HP, VOLTS, PHASE, FLA), each with its default;
- rating rules: a device's attribute (RATING, AMPS, HP...) worked out from the values
  (nec_tables.py): a value copied, the motor's table current, a percent of it rounded up to
  the next standard size, or a fixed text.

Placed, its members are ordinary objects of the sheet (their own tags, wire numbers,
cross-references, parts: reports, terminal strips and the battery see them as any others),
tied together by the placed UDT kept on their sheet (Sheet.udts, saved with it, as arrays
are): {group id: its UDT (by the key of the copy kept in Sheet.udt_types), where it was put,
its choices, values, rating rules and overridden ratings, and which object plays each role}.

Changed (UDT properties...), it is rebuilt in place in one undo step: members that stay are
left as they are (tags, wire numbers kept), those of an alternative no longer chosen go, those
of the one chosen are added with the sheet's next tags, and the ratings are worked out again.
A member edited by hand (moved on its own, its attributes typed) keeps the edit: where the
rebuild would take it away or replace it, it is left as it is, no longer the UDT's, and the
rebuild warns. A rating typed over is overridden: kept through rebuilds until set back to
automatic. Each placed UDT has its own values, rules and ratings (the owner, Nov 2026: "ratings
of the motor ckts should have the option of being applied to all instances but not by
default, as most will have at minimum, subtle differences"): apply_all_plans is that option.

    <library>/udts/<name>.kzudt    one file a UDT (JSON)
"""

import copy
import hashlib
import json
import math
import uuid

from . import circuits as CI
from . import geometry as G
from . import model as M
from . import nec_tables as NEC

FORMAT = "kanzonascad-udt"
VERSION = 1
SUFFIX = ".kzudt"
FOLDER = "udts"

INCLUDED, LEFT_OUT = "Included", "Left out"
TOL = 1e-6

# what a rating rule works a value out as
RULES = {"value": "A value of the UDT", "flc": "Motor full-load current (NEC table)",
         "fla": "Motor FLA (typed, else the table's)",
         "percent": "Percent of the motor current, rounded up", "text": "Fixed text"}
# a placed member's attributes the program changes by itself: never a hand edit
_OWN_ATTRS = {"TAG", "DEV", "PARENT", "TAG_LOCK", "FROM", "TERM", "OUTLET", "TAGLINK"}


# ---- the UDT ---------------------------------------------------------------------------------
class Udt:
    """A UDT: its name, category and description, its members ([{role, slot, alt, entity}],
    entities around its base point (0, 0)), the blocks and layers they use, its slots
    ([{name, alternatives, default, optional}]), values ([{key, label, default}]) and rating
    rules ([{role, attr, rule, of, percent, round, text}])."""

    def __init__(self, name, category="", description="", members=(), blocks=(), layers=(),
                 slots=(), values=(), ratings=(), builtin=False):
        self.name = str(name).strip()
        self.category = str(category or "").strip()
        self.description = str(description or "").strip()
        self.members = []
        for m in members:
            ent = {k: v for k, v in copy.deepcopy(m["entity"]).items() if k != "id"}
            self.members.append({"role": str(m["role"]), "slot": str(m.get("slot") or ""),
                                 "alt": str(m.get("alt") or ""), "entity": ent})
        self.blocks = [copy.deepcopy(d) for d in blocks]
        self.layers = [copy.deepcopy(d) for d in layers]
        self.slots = []
        for s in slots:
            alts = [str(a) for a in s.get("alternatives", [])]
            if not alts:
                continue
            dflt = str(s.get("default") or alts[0])
            self.slots.append({"name": str(s["name"]), "alternatives": alts,
                               "default": dflt if dflt in alts else alts[0],
                               "optional": bool(s.get("optional", False))})
        self.values = [{"key": str(v["key"]).strip().upper(),
                        "label": str(v.get("label") or v["key"]),
                        "default": str(v.get("default", ""))} for v in values
                       if str(v.get("key", "")).strip()]
        self.ratings = [clean_rule(r) for r in ratings if r.get("role") and r.get("attr")]
        self.builtin = bool(builtin)
        self._defs = None

    def to_dict(self):
        return {"format": FORMAT, "version": VERSION, "name": self.name,
                "category": self.category, "description": self.description,
                "members": copy.deepcopy(self.members), "blocks": copy.deepcopy(self.blocks),
                "layers": copy.deepcopy(self.layers), "slots": copy.deepcopy(self.slots),
                "values": copy.deepcopy(self.values), "ratings": copy.deepcopy(self.ratings)}

    @classmethod
    def from_dict(cls, d, builtin=False):
        if d.get("format") != FORMAT:
            raise ValueError("not a KanzonasCAD UDT")
        if int(d.get("version", 1)) > VERSION:
            raise ValueError("saved by a newer KanzonasCAD")
        return cls(d["name"], d.get("category", ""), d.get("description", ""),
                   d.get("members", []), d.get("blocks", []), d.get("layers", []),
                   d.get("slots", []), d.get("values", []), d.get("ratings", []), builtin)

    def copy(self, **changes):
        d = self.to_dict()
        d.update(changes)
        return Udt.from_dict(d)

    def key(self):
        """What it is, as a short text: two UDTs alike in every way have the same key (the
        copy a sheet keeps of it is found by it)."""
        d = self.to_dict()
        raw = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def defs(self):
        if self._defs is None:
            self._defs = {b["name"]: M.BlockDef.from_dict(b) for b in self.blocks}
        return self._defs

    def slot(self, name):
        for s in self.slots:
            if s["name"] == name:
                return s
        return None

    def member(self, role):
        for m in self.members:
            if m["role"] == role:
                return m
        return None

    def next_role(self):
        n = 0
        for m in self.members:
            if m["role"].startswith("r") and m["role"][1:].isdigit():
                n = max(n, int(m["role"][1:]))
        return "r%d" % (n + 1)

    def choices(self, choices=None):
        """{slot: alternative}: those given that are this UDT's, the defaults for the rest."""
        got = choices or {}
        return {s["name"]: got[s["name"]] if got.get(s["name"]) in s["alternatives"]
                else s["default"] for s in self.slots}

    def is_active(self, m, choices):
        """Is member m part of the UDT with these choices?"""
        if not m["slot"]:
            return True
        s = self.slot(m["slot"])
        return s is not None and choices.get(s["name"], s["default"]) == m["alt"]

    def active(self, choices):
        ch = self.choices(choices)
        return [m for m in self.members if self.is_active(m, ch)]

    def default_values(self, values=None):
        """{key: value}: those given, the defaults for the rest."""
        got = {str(k).upper(): str(v) for k, v in (values or {}).items()}
        return {v["key"]: got.get(v["key"], v["default"]) for v in self.values}

    def circuit(self, choices=None, members=None):
        """A saved circuit of its members with these choices (or members, a list of them):
        what is drawn for its picture and placed."""
        ms = self.active(choices) if members is None else members
        return CI.Circuit(self.name, self.category, self.description,
                          [m["entity"] for m in ms], self.blocks, self.layers)

    def label(self, m, defs=None):
        """What a member is called before it is placed: its block and alternative."""
        e = m["entity"]
        what = e.get("block") if e.get("kind") == "insert" else e.get("kind", "object")
        if (defs or {}).get(what) is not None and e.get("kind") == "insert":
            what = defs[what].shown_name
        where = (" (%s: %s)" % (m["slot"], m["alt"])) if m["slot"] else ""
        return "%s%s" % (what, where)


def clean_rule(r):
    """A rating rule, its fields all there."""
    rule = str(r.get("rule") or "value")
    if rule not in RULES:
        rule = "value"
    try:
        pct = float(r.get("percent", 100.0))
    except (TypeError, ValueError):
        pct = 100.0
    rnd = str(r.get("round") or "none")
    return {"role": str(r["role"]), "attr": str(r["attr"]).strip().upper(), "rule": rule,
            "of": str(r.get("of") or ("FLC" if rule == "percent" else "HP")).upper(),
            "percent": pct, "round": rnd if rnd in NEC.ROUNDINGS else "none",
            "text": str(r.get("text") or "")}


def make(project, ents, base, name, category="", description=""):
    """A UDT of ents (a sheet's objects) with base as its base point: every object a member
    with no choice yet (the editor makes choices and optional parts of them)."""
    return from_circuit(CI.make(project, ents, base, name, category, description))


def from_circuit(c):
    """A UDT of a saved circuit's objects (circuits.Circuit), none of them in a choice yet."""
    members = [{"role": "r%d" % (i + 1), "entity": d} for i, d in enumerate(c.entities)]
    return Udt(c.name, c.category, c.description, members, c.blocks, c.layers,
               values=MOTOR_VALUES)


MOTOR_VALUES = [{"key": "HP", "label": "Horsepower", "default": "5"},
                {"key": "VOLTS", "label": "Volts", "default": "460"},
                {"key": "PHASE", "label": "Phase (1 or 3)", "default": "3"},
                {"key": "FLA", "label": "Motor FLA (nameplate; blank: the table's)",
                 "default": ""}]


# ---- editing a UDT (the editor's steps, no Qt) ---------------------------------------------------
def pin_pairs(defn):
    """The pins of a block a straight wire bridges when it is left out: those across from each
    other on its two sides (L1 and T1 of a 3-pole device, 1 and 2 of a fuse). [(a, b)] in the
    block's own coordinates."""
    pins = [tuple(p["pos"]) for p in defn.pins]
    if len(pins) < 2:
        return []
    xs = sorted({round(q[0], 6) for q in pins})
    left, right = xs[0], xs[-1]
    out = []
    for q in pins:
        if abs(q[0] - left) > TOL:
            continue
        across = [r for r in pins if abs(r[0] - right) <= TOL and abs(r[1] - q[1]) <= TOL]
        if across and abs(right - left) > TOL:
            out.append((q, across[0]))
    return out


def bridges(project, udt, m):
    """Wires (entity dicts, around the UDT's base point) bridging member m's pins across, for
    when it is left out."""
    e = M.Entity.from_dict(m["entity"], udt.defs())
    if not isinstance(e, M.Insert) or e.defn is None:
        return []
    lay = (project.settings.get("wire_layer") if project is not None else None) or "WIRES"
    out = []
    for a, b in pin_pairs(e.defn):
        d = M.Wire([e.to_world(a), e.to_world(b)], layer=lay).to_dict()
        d.pop("id", None)
        out.append(d)
    return out


def make_optional(udt, roles, name, project=None):
    """udt with the members of roles (devices, say a line reactor) made an optional part
    called name: Included as they are, Left out bridged by straight wires across their pins.
    Returns the new UDT."""
    u = udt.copy()
    if u.slot(name) is not None:
        raise ValueError("there is already a choice named %s" % name)
    picked = [m for m in u.members if m["role"] in roles]
    if not picked or any(m["slot"] for m in picked):
        raise ValueError("pick objects that aren't in a choice yet")
    for m in picked:
        m["slot"], m["alt"] = name, INCLUDED
    for m in picked:
        for d in bridges(project, u, m):
            u.members.append({"role": u.next_role(), "slot": name, "alt": LEFT_OUT,
                              "entity": d})
    u.slots.append({"name": name, "alternatives": [INCLUDED, LEFT_OUT], "default": INCLUDED,
                    "optional": True})
    return Udt.from_dict(u.to_dict())


def make_choice(udt, roles, name, first):
    """udt with the members of roles made the first alternative (called first) of a new
    choice called name."""
    u = udt.copy()
    if u.slot(name) is not None:
        raise ValueError("there is already a choice named %s" % name)
    picked = [m for m in u.members if m["role"] in roles]
    if not picked or any(m["slot"] for m in picked):
        raise ValueError("pick objects that aren't in a choice yet")
    for m in picked:
        m["slot"], m["alt"] = name, first
    u.slots.append({"name": name, "alternatives": [first], "default": first,
                    "optional": False})
    return Udt.from_dict(u.to_dict())


def add_alternative(udt, slot, alt, defn, project=None):
    """udt with a new alternative alt of a choice: the block defn put where the choice's first
    device is, turned as it is, and a short wire from each of its pins to where a pin of the
    same name of that device was (so the circuit's wires still reach it). Returns the new
    UDT."""
    u = udt.copy()
    s = u.slot(slot)
    if s is None:
        raise ValueError("no choice named %s" % slot)
    if alt in s["alternatives"]:
        raise ValueError("%s already has an alternative named %s" % (slot, alt))
    defs = u.defs()
    first = [m for m in u.members if m["slot"] == slot and m["alt"] == s["alternatives"][0]
             and m["entity"].get("kind") == "insert"]
    if not first:
        raise ValueError("the choice's first alternative has no symbol to stand in for")
    old = M.Entity.from_dict(first[0]["entity"], defs)
    new = M.Insert(defn.name, old.pos, old.angle, old.scale, old.mirror, {}, defn,
                   layer=old.layer)
    if old.defn is not None and old.pin_points() and new.pin_points():
        # (held by its first pin where the old one's first pin was, as Insert holds it)
        a, b = old.pin_points()[0][1], new.pin_points()[0][1]
        new = new.moved(a[0] - b[0], a[1] - b[1])
    d = new.to_dict()
    d.pop("id", None)
    if not any(b["name"] == defn.name for b in u.blocks):
        u.blocks.append(defn.to_dict())
    u.members.append({"role": u.next_role(), "slot": slot, "alt": alt, "entity": d})
    was = dict(old.pin_points()) if old.defn is not None else {}
    lay = (project.settings.get("wire_layer") if project is not None else None) or "WIRES"
    for name, q in new.pin_points():
        p = was.get(name)
        if p is not None and math.hypot(p[0] - q[0], p[1] - q[1]) > TOL:
            w = M.Wire([q, p], layer=lay).to_dict()
            w.pop("id", None)
            u.members.append({"role": u.next_role(), "slot": slot, "alt": alt, "entity": w})
    s["alternatives"].append(alt)
    return Udt.from_dict(u.to_dict())


def remove_slot(udt, name):
    """udt without the choice: its default alternative's members stay, always there; the
    others go."""
    u = udt.copy()
    s = u.slot(name)
    if s is None:
        return u
    keep = []
    for m in u.members:
        if m["slot"] != name:
            keep.append(m)
        elif m["alt"] == s["default"]:
            m["slot"], m["alt"] = "", ""
            keep.append(m)
    u.members = keep
    u.slots = [x for x in u.slots if x["name"] != name]
    u.ratings = [r for r in u.ratings if u.member(r["role"]) is not None]
    return Udt.from_dict(u.to_dict())


def remove_alternative(udt, slot, alt):
    """udt without one alternative of a choice (its members go; the last one can't)."""
    u = udt.copy()
    s = u.slot(slot)
    if s is None or alt not in s["alternatives"] or len(s["alternatives"]) < 2:
        raise ValueError("a choice keeps at least one alternative")
    u.members = [m for m in u.members if not (m["slot"] == slot and m["alt"] == alt)]
    s["alternatives"].remove(alt)
    if s["default"] == alt:
        s["default"] = s["alternatives"][0]
    u.ratings = [r for r in u.ratings if u.member(r["role"]) is not None]
    return Udt.from_dict(u.to_dict())


# ---- ratings ---------------------------------------------------------------------------------
def worked_out(rule, values):
    """(the value a rule gives with these values (text), or None when it can't, why not)."""
    kind = rule["rule"]
    if kind == "text":
        return rule.get("text", ""), ""
    if kind == "value":
        got = str(values.get(rule.get("of", "HP"), "")).strip()
        return (got or None), ("" if got else "no %s given" % rule.get("of", "HP"))
    table = NEC.flc(values.get("HP"), values.get("VOLTS"), values.get("PHASE", "3"))
    fla = NEC.number(values.get("FLA"))
    note = ""
    if kind == "fla":
        base = fla if fla else table
    elif kind == "percent" and rule.get("of") == "FLA":
        base = fla if fla else table
    else:
        base = table
        if base is None and fla:
            base, note = fla, "the FLA typed (no table current for this motor)"
    if base is None:
        return None, "no table current for %s HP at %s V %s-phase: type it as FLA" % (
            values.get("HP", ""), values.get("VOLTS", ""), values.get("PHASE", "3"))
    if kind in ("flc", "fla"):
        out = NEC.fmt(base)
    else:
        got = NEC.round_up(base * float(rule.get("percent", 100.0)) / 100.0,
                           rule.get("round", "none"))
        if got is None:
            return None, "past the largest standard size"
        out = NEC.fmt(got)
    if rule["attr"] not in M.RATING_FIELDS:
        out += "A"                      # (a fuse's RATING shows its unit: 15A)
    return out, note


def rule_text(r):
    """A rule as the windows describe it."""
    k = r["rule"]
    if k == "text":
        return "always %s" % r.get("text", "")
    if k == "value":
        return "the %s value" % r.get("of", "HP")
    if k == "percent":
        return "%g%% of the motor's %s, %s" % (r["percent"], "table current" if
                                              r.get("of") != "FLA" else "FLA",
                                              NEC.ROUNDINGS[r.get("round", "none")].lower())
    return {"flc": "the motor's table current", "fla": "the motor's FLA (typed, else the "
                                                       "table's)"}[k]


def _rated(inst, udt, role, attrs, existing, replace=False, cleared=()):
    """A member's rated attributes worked out for inst: ({attr: new value} to write,
    {attr: why it wasn't worked out}). It updates inst's overrides (a rating found typed over
    on the drawing since it was last worked out becomes one, unless replace) and what was
    last written. existing: attrs are those of an object already on the sheet; cleared: the
    attributes set back to automatic now (not taken for typed over)."""
    out, notes = {}, {}
    ov = inst["overrides"].setdefault(role, {})
    written = inst["written"].setdefault(role, {})
    for r in inst["ratings"]:
        if r["role"] != role:
            continue
        a = r["attr"]
        comp, why = worked_out(r, inst["values"])
        cur = attrs.get(a, "")
        if replace:
            ov.pop(a, None)
        if a in ov:
            want = ov[a]
        elif existing and not replace and a in written and cur != written[a] and \
                a not in cleared:
            ov[a] = want = cur          # (typed over on the drawing: an override now)
        elif comp is None:
            want = cur
            notes[a] = why
        else:
            want = comp
        if comp is not None:
            written[a] = comp
        if want != cur:
            out[a] = want
    if not ov:
        inst["overrides"].pop(role, None)
    if not written:
        inst["written"].pop(role, None)
    return out, notes


# ---- a project's symbol standard (the owner, Nov 27 2026) ------------------------------------
def _pins_of(defn):
    return sorted((p["name"], round(p["pos"][0], 6), round(p["pos"][1], 6)) for p in defn.pins)


def swaps(udt, standard, lookup):
    """{block of the UDT: its stand-in} for a project of this symbol standard ("iec": the
    JIC symbols that have an IEC 60617 equivalent, symbols_iec.IEC_FOR; "jic": the other
    way round), only where the stand-in's pins have the same names in the same places, so
    every wire still lands on its pin (one that doesn't line up stays as drawn).
    lookup(name): the BlockDef of a symbol (the library's), or None."""
    from .symbols_iec import IEC_FOR, iec_symbols
    if not IEC_FOR:
        iec_symbols()
    other = {j: i for i, j in IEC_FOR.items()} if standard == "iec" else dict(IEC_FOR)
    out = {}
    for name, d in udt.defs().items():
        to = other.get(name)
        got = lookup(to) if to else None
        if got is not None and got.kind == d.kind and _pins_of(got) == _pins_of(d):
            out[name] = got
    return out


def for_standard(udt, standard, lookup):
    """udt as it is placed in a project of this symbol standard: each device in the
    standard's own symbol where it has one with the same pins (swaps), else as drawn (the
    drive and the reactors, which IEC 60617 has no symbol of here, stay JIC). Its tags take
    the project's letters as any device's do (tags.prefix_for). The same UDT when nothing
    swaps."""
    got = swaps(udt, standard, lookup)
    if not got:
        return udt
    d = udt.to_dict()
    for m in d["members"]:
        ent = m["entity"]
        if ent.get("kind") == "insert" and ent.get("block") in got:
            ent["block"] = got[ent["block"]].name
    keep = [b for b in d["blocks"] if b["name"] not in got]
    have = {b["name"] for b in keep}
    for b in got.values():
        if b.name not in have:
            keep.append(b.to_dict())
            have.add(b.name)
    d["blocks"] = keep
    return Udt.from_dict(d, udt.builtin)


# ---- terminal strips (the owner, Nov 27 2026: Insert UDT asks which strip) -----------------
STRIP_SETTING = "udt_strip"     # (the project's last choice, offered first next time)


def is_terminal_def(defn):
    """A block placed as a terminal of a strip (a TERM attribute: the Terminal symbol)."""
    return defn is not None and defn.kind == "symbol" and \
        any(a.get("attr") == "TERM" for a in defn.attr_texts)


def has_terminals(udt):
    """Does any of the UDT's members (in any choice) put a terminal on the sheet?"""
    defs = udt.defs()
    return any(m["entity"].get("kind") == "insert" and
               is_terminal_def(defs.get(m["entity"].get("block"))) for m in udt.members)


def strip_prefix(project):
    """A strip's tag prefix in project: TB, X in a project of IEC 60617 symbols."""
    from .symbols_iec import standard_of
    from .tags import IEC_LETTERS
    return IEC_LETTERS["TB"] if standard_of(project) == "iec" else "TB"


def strip_tags(project):
    """[(tag, terminals)] of the project's terminal strips (strips.find; TB? left out)."""
    from . import strips
    return [(st.tag, len([r for r in st.rows if r.num or r.places]))
            for st in strips.find(project, wires=False) if st.tag != "TB?"]


def new_strip_tag(project, sheet):
    """The tag a new strip on sheet takes: the strip prefix, the page and the lowest count no
    device or strip there has (TB101, X101 on page 1), as a new device's tag is made."""
    from . import tags
    pre, page = strip_prefix(project), project.sheet_number(sheet)
    taken = tags.used_counts(project, pre, page)
    for tag, _n in strip_tags(project):
        got = tags.split(tag.upper(), pre)
        if got and got[0] == page:
            taken.add(got[1])
    return tags.make(pre, page, tags.lowest_free(taken))


def _role_n(role):
    """A role's place in its UDT (r2 before r10)."""
    return (int(role[1:]) if role[1:].isdigit() else 0, role)


def _onto_strip(ed, project, sheet, tag, terms):
    """In edit ed: terminals terms (just placed, in the UDT's order) put on the strip tagged
    tag, taking its lowest free numbers (a spare's number is taken); on a strip with a
    Terminal strip symbol, they link themselves to it by its tag as the edit ends, as any
    contact does (tags.sync_children). Returns the terminals changed."""
    from . import strips
    key = tag.strip().upper()
    # (every strip of that tag: a Terminal strip's, and terminals of the tag on none yet,
    # which link themselves to it)
    used = {r.num for st in strips.find(project, wires=False) if st.tag.upper() == key
            for r in st.rows if r.num}
    out, n = [], 1
    for e in terms:
        while str(n) in used:
            n += 1
        used.add(str(n))
        attrs = dict(e.attrs, TAG=tag.strip(), TERM=str(n))
        attrs.pop("PARENT", None)
        out.append(ed.change(sheet, e.copy(attrs=attrs)))
    return out


# ---- placed UDTs -------------------------------------------------------------------------------
_TYPES = {}         # (key -> Udt): a sheet's copies read once


def type_of(sheet, inst):
    """The UDT a placed one was made from (the sheet's copy)."""
    key = inst["type"]
    got = _TYPES.get(key)
    if got is None:
        d = sheet.udt_types.get(key)
        if d is None:
            return None
        got = _TYPES[key] = Udt.from_dict(d)
    return got


def find(sheet, eid):
    """The group id of the placed UDT an object is a member of, or None."""
    for gid, inst in sheet.udts.items():
        if eid in inst["members"].values():
            return gid
    return None


def members(sheet, gid):
    """{role: object} of a placed UDT's members still on the sheet."""
    inst = sheet.udts[gid]
    return {r: sheet.entities[i] for r, i in inst["members"].items() if i in sheet.entities}


def instances(project, name=None):
    """[(sheet, group id)] of the project's placed UDTs (of that UDT's name only), those with
    a member left."""
    out = []
    for s in project.sheets:
        got = []
        for gid, inst in s.udts.items():
            on = members(s, gid)
            if (name is None or inst["udt"] == name) and on:
                got.append((min(e.id for e in on.values()), gid))
        # (in the order they were drawn, their objects' ids: a group id is random)
        out += [(s, gid) for _i, gid in sorted(got)]
    return out


def tag_of(e):
    """What a member is called on the drawing: its tag, else its block, else its kind."""
    if isinstance(e, M.Insert):
        return e.attrs.get("TAG") or e.block_name
    return {"wire": "a wire"}.get(e.kind, e.kind)


def _names(project, udt):
    return CI._block_names(project, udt.circuit(members=udt.members))


def expected(project, udt, m, at, angle, scale, names=None):
    """Member m as the UDT puts it with this placing (its blocks the project's, as placed)."""
    names = names if names is not None else _names(project, udt)
    shown = {n: project.blocks.get(names[n]) or d for n, d in udt.defs().items()}
    e = CI.transformed(M.Entity.from_dict(m["entity"], shown), at, angle, scale)
    if isinstance(e, M.Insert):
        e.block = names.get(e.block, e.block)
    return e


def _close(x, y):
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) and \
            not isinstance(x, bool) and not isinstance(y, bool):
        return abs(x - y) <= TOL * max(1.0, abs(x), abs(y))
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
        return len(x) == len(y) and all(_close(p, q) for p, q in zip(x, y))
    if isinstance(x, dict) and isinstance(y, dict):
        return x.keys() == y.keys() and all(_close(x[k], y[k]) for k in x)
    return x == y


def _angle_close(a, b):
    d = (a - b) % 360.0
    return min(d, 360.0 - d) <= 1e-6


def hand_edited(cur, exp, managed=()):
    """Has a member been changed by hand from what its UDT puts there (exp)? Moved, turned,
    another block, its attributes typed (its tag, links and number aside: the program keeps
    those; and the ratings its rules write, managed: typed over, they are overrides)."""
    if type(cur) is not type(exp) or cur.layer != exp.layer:
        return True
    if isinstance(cur, M.Insert):
        if cur.block != exp.block or not _close(list(cur.pos), list(exp.pos)) or \
                not _angle_close(cur.angle, exp.angle) or not _close(cur.scale, exp.scale) \
                or cur.mirror != exp.mirror:
            return True
        skip = _OWN_ATTRS | set(managed)
        a = {k: v for k, v in cur.attrs.items() if k not in skip and v and not _pin_number(k)}
        b = {k: v for k, v in exp.attrs.items() if k not in skip and v and not _pin_number(k)}
        return a != b
    if isinstance(cur, M.Wire):
        p, q = [list(t) for t in cur.points], [list(t) for t in exp.points]
        return not (_close(p, q) or _close(p, q[::-1]))
    a, b = cur.to_dict(), exp.to_dict()
    a.pop("id", None)
    b.pop("id", None)
    return not _close(a, b)


def _pin_number(k):
    """An attribute holding a contact's pin number (TERM01, TERM02: pinnumbers.py, 0.28),
    which the program gives a contact as it is placed (95-96 on an overload's): not a hand
    edit."""
    return len(k) == 6 and k.startswith("TERM") and k[4:].isdigit()


def _left_there(project, sheet, exp):
    """An object of the sheet no placed UDT has, of exp's kind and block, exactly where exp
    is (a member left by hand), or None."""
    taken = {i for u in sheet.udts.values() for i in u["members"].values()}
    for e in sheet.query(exp.bbox()):
        if e.id in taken or type(e) is not type(exp):
            continue
        if isinstance(e, M.Insert):
            if e.block == exp.block and _close(list(e.pos), list(exp.pos)) and \
                    _angle_close(e.angle, exp.angle):
                return e
        elif isinstance(e, M.Wire):
            p, q = [list(t) for t in e.points], [list(t) for t in exp.points]
            if _close(p, q) or _close(p, q[::-1]):
                return e
    return None


def located(project, sheet, inst, udt, names=None):
    """(at, angle, scale) of a placed UDT as it is now: where it was put, or, when its symbols
    were moved or turned together since (Move, Rotate on all of it), where most of them say it
    is now."""
    at, angle, scale = tuple(inst["at"]), float(inst["angle"]), float(inst["scale"])
    votes, n, exact = _votes(udt, members(sheet, inst["id"]), scale)
    if not votes:
        return at, angle, scale
    here = (round(angle, 4) % 360.0, round(at[0], 6), round(at[1], 6))
    best = max(votes, key=lambda k: (votes[k], k == here))
    if best == here or votes.get(here, 0) >= votes[best] or 2 * votes[best] <= n:
        return at, angle, scale
    return exact[best], best[0], scale


def _votes(udt, on, scale):
    """({(angle, x, y): how many of its symbols put the UDT's base point there}, how many
    symbols voted, {(angle, x, y): where the first of them puts the base point, not
    rounded}) of a placed UDT's members on ({role: object}). (The keys are rounded to gather
    the votes; the base point kept is the exact one: a copy's, rounded to 6 places, was 4e-7"
    off its own wires, and rebuilt there it would be drawn off them; the long battery, 0.30,
    seed 5202.)"""
    votes, n, exact = {}, 0, {}
    for role, e in on.items():
        m = udt.member(role)
        if m is None or not isinstance(e, M.Insert) or m["entity"].get("kind") != "insert":
            continue
        d = m["entity"]
        if bool(d.get("mirror")) != e.mirror:
            continue
        n += 1
        a = (e.angle - float(d.get("angle", 0.0))) % 360.0
        px, py = d["pos"][0] * scale, d["pos"][1] * scale
        rx, ry = G.rotate_point((px, py), (0.0, 0.0), a)
        key = (round(a, 4) % 360.0, round(e.pos[0] - rx, 6), round(e.pos[1] - ry, 6))
        votes[key] = votes.get(key, 0) + 1
        exact.setdefault(key, (e.pos[0] - rx, e.pos[1] - ry))
    return votes, n, exact


class Plan:
    """What a rebuild will do to one placed UDT (lines: as the windows list it), and what
    apply needs to do it."""

    def __init__(self, sheet, gid, udt, inst):
        self.sheet, self.gid, self.udt, self.inst = sheet, gid, udt, inst
        self.remove = []        # [(role, id, what)]
        self.add = []           # [member]
        self.replace = []       # [(role, id, member)]
        self.left = []          # [(role, id, what)] edited by hand: left as they are, plain
        self.adopt = []         # [(role, id)] left by hand before, taken back where they are
        self.attrs = []         # [(role, id, what, {attr: (old, new)})]
        self.warnings = []
        self.notes = []
        self.replace_overrides = False

    def lines(self):
        out = []
        defs = self.udt.defs()
        wires = {"Remove": 0, "Add": 0, "Replace": 0}
        for what, items in (("Remove", [w for _r, _i, w in self.remove]),
                            ("Add", [self.udt.label(m, defs) for m in self.add]),
                            ("Replace", [self.udt.label(m, defs) for _r, _i, m in
                                         self.replace])):
            for w in items:
                if w in ("a wire", "wire") or w.startswith("wire ("):
                    wires[what] += 1
                else:
                    out.append("%s %s" % (what, w))
            if wires[what]:
                out.append("%s %d wire(s)" % (what, wires[what]))
        for _r, i in self.adopt:
            out.append("Take back %s, left by hand before" % tag_of(self.sheet.entities[i]))
        for _r, _i, what, ch in self.attrs:
            out.append("%s: %s" % (what, ", ".join("%s %s -> %s" % (a, o or "(none)", n or
                                                                   "(none)")
                                                  for a, (o, n) in sorted(ch.items()))))
        return out


def _new_inst(udt, at, angle, scale, choices, values, strip=""):
    return {"id": uuid.uuid4().hex[:12], "udt": udt.name, "type": udt.key(),
            "at": [float(at[0]), float(at[1])], "angle": float(angle) % 360.0,
            "scale": float(scale), "choices": udt.choices(choices),
            "values": udt.default_values(values), "ratings": copy.deepcopy(udt.ratings),
            "overrides": {}, "members": {}, "written": {}, "gone": [],
            "strip": str(strip or "").strip()}


def plan(project, sheet, gid, choices=None, values=None, ratings=None, overrides=None,
         udt=None, replace_overrides=False):
    """What rebuilding a placed UDT with these changes will do (None: as it is): choices
    {slot: alternative}, values {key: value}, ratings (its rules), overrides {role: {attr:
    value}} (a rating typed in UDT properties; "" there: back to automatic), udt (a new
    version of its UDT: Update from UDT). Nothing changes until apply."""
    old_inst = sheet.udts[gid]
    old = type_of(sheet, old_inst)
    new = udt or old
    inst = copy.deepcopy(old_inst)
    names_old = _names(project, old)
    at, angle, scale = located(project, sheet, inst, old, names_old)
    inst["at"], inst["angle"] = [at[0], at[1]], angle
    old_ch = old.choices(inst["choices"])
    inst["choices"] = new.choices(dict(old_ch, **(choices or {})))
    inst["values"] = new.default_values(dict(inst["values"], **(values or {})))
    if ratings is not None:
        inst["ratings"] = [clean_rule(r) for r in ratings]
    if udt is not None:
        # (a device the placed one had no rule for takes the UDT's; rules of devices gone go)
        have = {r["role"] for r in inst["ratings"]}
        inst["ratings"] = [r for r in inst["ratings"] if new.member(r["role"]) is not None] + \
            [copy.deepcopy(r) for r in new.ratings if r["role"] not in have]
        inst["type"], inst["udt"] = new.key(), new.name
    cleared = {}
    for role, got in (overrides or {}).items():
        for a, v in got.items():
            if v is None or str(v).strip() == "":
                inst["overrides"].get(role, {}).pop(a, None)
                cleared.setdefault(role, set()).add(a)
            else:
                inst["overrides"].setdefault(role, {})[a] = str(v).strip()
    p = Plan(sheet, gid, new, inst)
    p.replace_overrides = replace_overrides
    on_sheet = members(sheet, gid)
    managed = {}
    for r in inst["ratings"] + old_inst["ratings"]:
        managed.setdefault(r["role"], set()).add(r["attr"])
    new_ch = inst["choices"]
    gone = set(inst.get("gone", ()))       # (left by hand: not put back while chosen)
    for m in old.members:
        role = m["role"]
        e = on_sheet.get(role)
        n = new.member(role)
        now = n is not None and new.is_active(n, new_ch)
        if not old.is_active(m, old_ch):
            continue
        if e is None:
            if now and role in inst["members"]:
                p.warnings.append("%s was erased by hand: not put back (place the UDT again "
                                  "to have it)" % old.label(m, old.defs()))
            else:
                inst["members"].pop(role, None)         # (chosen again later: added again)
            continue
        edited = hand_edited(e, expected(project, old, m, at, angle, scale, names_old),
                             managed.get(role, ()))
        changed = now and udt is not None and not _close(n["entity"], m["entity"])
        if now and not changed:
            continue
        if edited:
            p.left.append((role, e.id, tag_of(e)))
            p.warnings.append("%s was edited by hand: left as it is, no longer part of the "
                              "UDT (erase it if it isn't wanted)" % tag_of(e))
        elif now:
            p.replace.append((role, e.id, n))
        else:
            p.remove.append((role, e.id, tag_of(e)))
    for m in new.members:
        role = m["role"]
        om = old.member(role)
        was = om is not None and old.is_active(om, old_ch)
        if not new.is_active(m, new_ch):
            gone.discard(role)
            continue
        if was and (role in inst["members"] or role in gone):
            continue            # (kept, replaced, erased or left by hand: not added again)
        if role in gone:
            # (left by hand once, chosen again: the object left is taken back when it is
            # still where the UDT puts it, not doubled)
            got = _left_there(project, sheet, expected(project, new, m, at, angle, scale))
            gone.discard(role)
            if got is not None:
                p.adopt.append((role, got.id))
                continue
        p.add.append(m)
    inst["gone"] = sorted(gone | {r for r, _i, _w in p.left})
    # ratings of the members that stay
    out = {r for r, _i, _w in p.remove + p.left} | {r for r, _i, _m in p.replace}
    for role, e in sorted(on_sheet.items()):
        if role in out or not isinstance(e, M.Insert):
            continue
        ch, notes = _rated(inst, new, role, e.attrs, True, replace_overrides,
                           cleared.get(role, ()))
        for a, why in notes.items():
            p.notes.append("%s %s: %s" % (tag_of(e), a, why))
        if ch:
            p.attrs.append((role, e.id, tag_of(e), {a: (e.attrs.get(a, ""), v)
                                                    for a, v in ch.items()}))
    return p


def apply(ed, project, p):
    """In edit ed: a plan carried out (plan, or place's). Returns the objects added."""
    from .tags import is_device
    from .wires import break_under
    sheet, inst, udt = p.sheet, p.inst, p.udt
    for role, eid, _w in p.remove:
        ed.remove(sheet, eid)
        inst["members"].pop(role, None)
    for role, _eid, _w in p.left:
        inst["members"].pop(role, None)
        inst["overrides"].pop(role, None)
        inst["written"].pop(role, None)
    for role, eid in p.adopt:
        inst["members"][role] = eid
    old = {}
    for role, eid, _m in p.replace:
        old[role] = sheet.entities[eid]
        ed.remove(sheet, eid)
    put = list(p.add) + [m for _r, _i, m in p.replace]
    made = []
    if put:
        made = CI.place(ed, project, sheet, udt.circuit(members=put), inst["at"],
                        inst["angle"], inst["scale"])
    by_role = {m["role"]: e for m, e in zip(put, made)}
    # a device replaced keeps its tag and its hidden id (its contacts stay its own), a wire
    # its locked number
    dev_back = {}
    for role, was in old.items():
        e = by_role[role]
        if isinstance(e, M.Insert) and isinstance(was, M.Insert) and is_device(e):
            attrs = dict(e.attrs)
            for k in ("TAG", "DEV", "TAG_LOCK"):
                if was.attrs.get(k):
                    attrs[k] = was.attrs[k]
            dev_back[e.attrs.get("DEV")] = attrs.get("DEV")
            by_role[role] = ed.change(sheet, e.copy(attrs=attrs))
        elif isinstance(e, M.Insert) and isinstance(was, M.Insert) and \
                is_terminal_def(e.defn) and was.attrs.get("TERM"):
            # (a terminal replaced: its strip and number kept)
            attrs = dict(e.attrs)
            for k in ("TAG", "PARENT", "TERM"):
                if was.attrs.get(k):
                    attrs[k] = was.attrs[k]
            by_role[role] = ed.change(sheet, e.copy(attrs=attrs))
        elif isinstance(e, M.Wire) and isinstance(was, M.Wire) and was.num_lock:
            by_role[role] = ed.change(sheet, e.copy(num=was.num, num_lock=True))
    # terminals added: on the strip picked when the UDT was placed (none: TB? for later)
    if inst.get("strip"):
        terms = [by_role[m["role"]] for m in p.add if isinstance(by_role[m["role"]], M.Insert)
                 and is_terminal_def(by_role[m["role"]].defn)]
        for e in _onto_strip(ed, project, sheet, inst["strip"], terms):
            by_role[next(r for r, x in by_role.items() if x.id == e.id)] = e
    # a contact added whose device stayed: linked to that device (place links only those whose
    # device came with them); one whose device was replaced: to its kept hidden id
    dev_role = {}
    for m in udt.members:
        dev = (m["entity"].get("attrs") or {}).get("DEV")
        if dev:
            dev_role[dev] = m["role"]
    for m in put:
        e = by_role[m["role"]]
        if not isinstance(e, M.Insert):
            continue
        parent = (m["entity"].get("attrs") or {}).get("PARENT")
        role = dev_role.get(parent)
        dev = None
        if parent and role is not None and role not in by_role:
            dev = sheet.entities.get(inst["members"].get(role))
        if dev is not None:
            attrs = dict(e.attrs, PARENT=dev.attrs.get("DEV", ""), TAG=dev.attrs.get("TAG", ""))
        elif e.attrs.get("PARENT") in dev_back:
            attrs = dict(e.attrs, PARENT=dev_back[e.attrs["PARENT"]])
        else:
            continue
        by_role[m["role"]] = ed.change(sheet, e.copy(attrs=attrs))
    for role, e in by_role.items():
        inst["members"][role] = e.id
        inst["written"].pop(role, None)
    # ratings: those of the members added worked out now (the others' are in the plan)
    for role, e in list(by_role.items()):
        if isinstance(e, M.Insert):
            ch, _notes = _rated(inst, udt, role, e.attrs, False, p.replace_overrides)
            if ch:
                by_role[role] = ed.change(sheet, e.copy(attrs=dict(e.attrs, **ch)))
    for _role, eid, _w, ch in p.attrs:
        e = sheet.entities.get(eid)
        if e is not None:
            new = dict(e.attrs, **{a: n for a, (_o, n) in ch.items()})
            ed.change(sheet, e.copy(attrs=new))
    for e in by_role.values():
        got = sheet.entities.get(e.id)
        if isinstance(got, M.Insert) and got.defn is not None and got.defn.kind == "symbol":
            break_under(ed, sheet, got)
    _keep(ed, sheet, p.gid, inst, udt)
    return [sheet.entities[e.id] for e in by_role.values() if e.id in sheet.entities]


def _keep(ed, sheet, gid, inst, udt):
    """The sheet's placed UDTs with inst as gid's (None: taken away), the copies of their UDTs
    those use, and none whose members are all gone."""
    udts = {k: v for k, v in sheet.udts.items()
            if any(i in sheet.entities for i in v["members"].values())}
    if inst is None:
        udts.pop(gid, None)
    else:
        inst["id"] = gid
        udts[gid] = inst
    types = dict(sheet.udt_types)
    if udt is not None and inst is not None:
        types.setdefault(inst["type"], udt.to_dict())
    used = {v["type"] for v in udts.values()}
    types = {k: v for k, v in types.items() if k in used}
    ed.sheet_meta(sheet, udts=udts, udt_types=types)


def place(ed, project, sheet, udt, at, angle=0.0, scale=1.0, choices=None, values=None,
          strip=""):
    """In edit ed: udt put on sheet with its base point at at, with these choices and values
    (the defaults for the rest), its terminals on the strip tagged strip (blank: on none yet,
    TB?). Returns (group id, the objects added)."""
    inst = _new_inst(udt, at, angle, scale, choices, values, strip)
    p = Plan(sheet, inst["id"], udt, inst)
    p.add = udt.active(inst["choices"])
    return inst["id"], apply(ed, project, p)


# ---- copies (the owner, Nov 27 2026: "Copy/paste of a placed UDT makes a new instance") ----
def copied(sheet, ids):
    """What a copy of objects ids of sheet takes along of its placed UDTs: [{"inst": the
    placed UDT, "type": its UDT}] of each whose every symbol is among them (its wires may be
    left behind: a copy of part of its symbols stays plain parts). Kept on the clipboard as
    it is (JSON) for Paste into any sheet or project."""
    ids = set(ids)
    out = []
    for gid, inst in sorted(sheet.udts.items()):
        on = members(sheet, gid)
        syms = [e.id for e in on.values() if isinstance(e, M.Insert)]
        if syms and set(syms) <= ids and inst["type"] in sheet.udt_types:
            # (its devices' hidden ids, by role: the copies' contacts are linked to the
            # copies of their devices by them)
            devs = {r: e.attrs["DEV"] for r, e in on.items()
                    if isinstance(e, M.Insert) and e.attrs.get("DEV")}
            out.append({"inst": copy.deepcopy(inst), "devs": devs,
                        "type": copy.deepcopy(sheet.udt_types[inst["type"]])})
    return out


def adopt_copies(ed, project, sheet, found, made):
    """In edit ed: the copies just added to sheet (made: {id copied: the copy}) of the placed
    UDTs found (copied()) made placed UDTs of their own: the same UDT, choices, values,
    rating rules and overridden ratings as the one copied, where the copies are (moved,
    turned), their own tags and wire numbers as any copy's; its contacts follow the copies
    of its devices (a plain copy's stay with the original: circuits._relinked links them),
    its terminals take the next free numbers of their strip. A member not copied (a wire
    left behind, one erased by hand before) is one erased by hand: not put back. Returns the
    new group ids."""
    if not found:
        return []
    from .tags import is_device
    out, adopted = [], []
    for f in found:
        old = copy.deepcopy(f["inst"])
        try:
            udt = Udt.from_dict(f["type"])
        except (ValueError, KeyError, TypeError):
            continue                # (a UDT this version can't read: the copies stay plain)
        was = {r: f.get("devs", {}).get(r) for r in old["members"]}
        got = {r: sheet.entities[made[i].id] for r, i in old["members"].items()
               if i in made and getattr(made[i], "id", None) in sheet.entities}
        if not any(isinstance(e, M.Insert) for e in got.values()):
            continue
        # contacts linked to the copies of their devices; terminals numbered on their strip
        new_dev = {was[r]: e for r, e in got.items() if was.get(r) and is_device(e)}
        for r, e in got.items():
            if not isinstance(e, M.Insert) or e.attrs.get("PARENT") not in new_dev:
                continue                # (a contact of a device outside the UDT stays its)
            attrs = CI._relinked(e, new_dev, {})
            if attrs is not None and attrs != e.attrs:
                got[r] = e = ed.change(sheet, e.copy(attrs=attrs))
        for tag in sorted({e.attrs.get("TAG", "") for e in got.values()
                           if isinstance(e, M.Insert) and is_terminal_def(e.defn) and
                           e.attrs.get("TAG") and not e.attrs.get("TERM")}):
            terms = [(r, e) for r, e in sorted(got.items(), key=lambda t: _role_n(t[0]))
                     if isinstance(e, M.Insert) and is_terminal_def(e.defn) and
                     e.attrs.get("TAG") == tag and not e.attrs.get("TERM")]
            for (r, _e), e in zip(terms, _onto_strip(ed, project, sheet, tag,
                                                     [e for _r, e in terms])):
                got[r] = e
        adopted.append((old, udt, got, f["type"]))
    udts, types = dict(sheet.udts), dict(sheet.udt_types)
    for old, udt, got, kind in adopted:
        inst = dict(old, id=uuid.uuid4().hex[:12], members={r: e.id for r, e in got.items()})
        inst["gone"] = sorted(set(old.get("gone", ())) |
                              (set(old["members"]) - set(got)))
        votes, _n, exact = _votes(udt, got, float(old["scale"]))
        if votes:
            best = max(votes, key=lambda k: votes[k])
            inst["at"], inst["angle"] = list(exact[best]), best[0]
        udts[inst["id"]] = inst
        types.setdefault(inst["type"], kind)            # (the copied one's, as it was kept)
        out.append(inst["id"])
    if out:
        ed.sheet_meta(sheet, udts=udts, udt_types=types)
    return out


def detach(ed, sheet, gid):
    """The placed UDT forgotten: its members stay where they are, plain parts."""
    _keep(ed, sheet, gid, None, None)


def rating_rows(project, sheet, gid, inst=None):
    """What UDT properties lists of a placed UDT's ratings: [{role, what, attr, rule, auto,
    value, overridden}] (inst: as it will be, the window's changes in it)."""
    inst = copy.deepcopy(inst or sheet.udts[gid])
    udt = type_of(sheet, sheet.udts[gid])
    on = members(sheet, gid)
    out = []
    for r in inst["ratings"]:
        e = on.get(r["role"])
        m = udt.member(r["role"])
        if m is None or not udt.is_active(m, inst["choices"]):
            continue
        auto, why = worked_out(r, inst["values"])
        ov = inst["overrides"].get(r["role"], {})
        cur = e.attrs.get(r["attr"], "") if isinstance(e, M.Insert) else ""
        typed = r["attr"] not in ov and isinstance(e, M.Insert) and \
            r["attr"] in inst["written"].get(r["role"], {}) and \
            cur != inst["written"][r["role"]][r["attr"]]
        out.append({"role": r["role"], "what": tag_of(e) if e is not None else
                    udt.label(m, udt.defs()), "attr": r["attr"], "rule": rule_text(r),
                    "auto": auto if auto is not None else "", "why": why,
                    "value": ov.get(r["attr"], cur if typed else (auto or cur)),
                    "overridden": r["attr"] in ov or typed})
    return out


def apply_all_plans(project, sheet, gid, values, ratings, overrides, replace_overrides=False):
    """Plans giving every other placed UDT of the same name the values, rating rules and
    ratings typed on this one (the owner's "option of being applied to all instances but not
    by default"): their own overridden ratings are left alone unless replace_overrides, when
    they take this one's (or automatic)."""
    name = sheet.udts[gid]["udt"]
    out = []
    for s, g in instances(project, name):
        if s is sheet and g == gid:
            continue
        if replace_overrides:
            mine = {r: {a: "" for a in got} for r, got in s.udts[g]["overrides"].items()}
            for r, got in (overrides or {}).items():
                mine.setdefault(r, {}).update(got)
        else:
            theirs = s.udts[g]["overrides"]
            mine = {r: {a: v for a, v in got.items() if a not in theirs.get(r, {})}
                    for r, got in (overrides or {}).items()}
        out.append(plan(project, s, g, values=values, ratings=ratings, overrides=mine,
                        replace_overrides=replace_overrides))
    return out


def update_plans(project, udt, apply_rules=False, replace_overrides=False, only=None):
    """Plans bringing every placed UDT of udt's name (only: [(sheet, gid)] of them) to this
    version of it. Each keeps its own values and rating rules unless apply_rules (then the
    UDT's defaults and rules replace them; their overridden ratings stay unless
    replace_overrides)."""
    out = []
    for s, g in (only if only is not None else instances(project, udt.name)):
        inst = s.udts[g]
        if inst["type"] == udt.key() and not apply_rules:
            continue
        values = udt.default_values() if apply_rules else None
        ratings = udt.ratings if apply_rules else None
        out.append(plan(project, s, g, values=values, ratings=ratings, udt=udt,
                        replace_overrides=replace_overrides and apply_rules))
    return out


def turned(angle):
    return CI.turned(angle)
