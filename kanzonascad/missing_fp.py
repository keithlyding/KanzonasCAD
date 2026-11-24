"""Devices without a footprint (0.25; the owner, Nov 2026: "make a check, so any schematic block
in the drawing that's not assigned to a panel footprint will give me some sort of alert"). No Qt.

Which devices need one: a schematic symbol that gets a tag of its own (tags.is_device: a device
or a parent, a coil or an operator, with a tag prefix). Left out:
- contacts and the other children of a device (a terminal, an outlet, a module's continued
  piece): their device's footprint is theirs;
- drawing aids: off-sheet connectors and source/destination arrows (no prefix, or wiring
  "link"), and everything that isn't a placed symbol (wire numbers, ladders, rails, ducts,
  title blocks, dashed boxes);
- devices in the field, by their location (pull.location_of: a device's own LOC, else its
  sheet's): a location that no panel sheet has (Sheet properties: Kind Panel, Location), once
  some panel sheet names one, or any location called FIELD (FIELD, FIELD-2...). With no panel
  sheet naming a location, the locations can't tell a panel from the field, and only FIELD
  does;
- devices ticked "No footprint needed" (their attribute NO_FP, the attributes window or the
  Properties panel).

Which have one: a footprint on a panel sheet linked to the device (its PARENT is the device's
hidden id, as a footprint placed for a device is: tags.link_footprint), or a footprint there not
linked to any device that has the device's tag (footprint_candidates counts those as taken too).

Worked out once per change of the project's sheets (their inserts, kinds and locations) and its
blocks, kept with the project until then, never on a paint or a mouse move."""

from . import tags
from .pull import location_of

FLAG = "NO_FP"                  # a device's attribute: "1", no footprint needed
SETTING = "fp_missing_marks"    # the project's: the orange marks on the drawing (on to start)
HEAD = ["Tag", "Description", "Block", "Sheet", "Where", "Location"]


def not_needed(e):
    """Whether a device is ticked "No footprint needed"."""
    return e.attrs.get(FLAG) == "1"


def with_flag(attrs, on):
    """attrs with "No footprint needed" ticked (on) or not."""
    out = dict(attrs or {})
    if on:
        out[FLAG] = "1"
    else:
        out.pop(FLAG, None)
    return out


def is_field(loc, panel_locs):
    """Whether a location is in the field: FIELD..., or (some panel sheet naming its location)
    one no panel sheet has. "" (no location) is not."""
    loc = (loc or "").strip().upper()
    if not loc:
        return False
    if loc.startswith("FIELD"):
        return True
    return bool(panel_locs) and loc not in panel_locs


def panel_locations(project):
    """The locations panel sheets name (upper case)."""
    return {s.location.strip().upper() for s in project.sheets
            if s.kind == "panel" and s.location.strip()}


def counts(e, sheet, panel_locs):
    """Whether a placed object is a device that needs a footprint (the rules above)."""
    if not tags.is_device(e) or e.defn.wiring == "link" or not_needed(e):
        return False
    return not is_field(location_of(sheet, e), panel_locs)


def _signature(project):
    return (tuple((s.id, s.net_version, s.kind, s.location) for s in project.sheets),
            tuple((n, d.kind, d.role, d.prefix, d.wiring) for n, d in project.blocks.items()))


class Result:
    """What the check found: missing [(sheet, device)] in page order, and by sheet id."""

    def __init__(self, missing):
        self.missing = missing
        self.by_sheet = {}
        for s, e in missing:
            self.by_sheet.setdefault(s.id, []).append(e)

    def __len__(self):
        return len(self.missing)


def find(project):
    """The devices that need a footprint and have none (a Result), kept with the project until
    its sheets or blocks change."""
    sig = _signature(project)
    got = getattr(project, "_missing_fp", None)
    if got is not None and got[0] == sig:
        return got[1]
    linked, tagged = set(), set()
    for s in project.sheets:
        if s.kind != "panel":
            continue
        for e in s.inserts():
            if not tags.is_footprint(e):
                continue
            par = e.attrs.get("PARENT")
            if par:
                linked.add(par)
            else:
                t = (e.attrs.get("TAG", "") or "").strip().upper()
                if t:
                    tagged.add(t)
    panel_locs = panel_locations(project)
    missing = []
    for s in project.sheets:
        for e in s.inserts():
            if not counts(e, s, panel_locs):
                continue
            if e.attrs.get("DEV") in linked:
                continue
            if (e.attrs.get("TAG", "") or "").strip().upper() in tagged:
                continue
            missing.append((s, e))
    res = Result(missing)
    project._missing_fp = (sig, res)
    return res


def marks_on(project):
    """Whether the project shows the orange marks (Project properties, Panel)."""
    return bool(project.settings.get(SETTING, True))


def marks(project, sheet):
    """[(x0, y0, x1, y1)]: the boxes of the devices on sheet without a footprint (none when
    the marks are off)."""
    if not marks_on(project):
        return []
    return [e.bbox() for e in find(project).by_sheet.get(sheet.id, ())]


def describe(n):
    """The status bar's words: "12 devices without a footprint"."""
    return "%d device%s without a footprint" % (n, "" if n == 1 else "s")


def rows(project):
    """[[tag, description, block, sheet, where, location]] of the devices without a
    footprint, in page order (the report)."""
    out = []
    for s, e in find(project).missing:
        out.append([e.attrs.get("TAG", "") or "?", e.attrs.get("DESC", ""), e.block,
                    str(project.sheet_number(s)),
                    project.zone_text(s, e.pos[0], e.pos[1]) or str(project.sheet_number(s)),
                    location_of(s, e)])
    return out


def table(project):
    """(header, rows) for a report sheet and Excel."""
    return HEAD, rows(project)
