"""Cross-references, worked out from the drawing (no Qt), never stored as text while they're
automatic.

- Under a device that has contacts (a coil, a pushbutton operator...): one line per contact,
  "NO 6-D3" / "NC 7-B2", in sheet order then zone order.
- Under each contact: where its device is ("6-D1"), or "?" when it isn't linked to one.
- Under an off-sheet connector: where the connectors of the same name are ("7-A2"), or "?"
  when it has no other end yet.
- A device's listing can be switched off (attribute XREF = "0" on the device), and each
  contact can be left out of its device's listing (XREF = "0" on the contact).

They follow every change. Two ways to hold them still:
- the project setting "Update cross-references automatically" off: every sheet shows what
  the last Update cross-references worked out;
- a sheet's Freeze cross-references (an issued sheet): it shows what they were when it was
  frozen, until it is unfrozen.
Either way, out_of_date() lists the sheets whose shown references differ from the drawing
(the status bar says so).

A reference is a plain tuple (x, y, text, height): saved in the sheet as it is while held.
"""

from .model import Text
from . import tags

MARK = {"NO": "NO", "NC": "NC", "NOTC": "NO", "NOTO": "NO", "NCTO": "NC", "NCTC": "NC"}
GAP = 0.05                      # between a symbol's box and its first line
LINE = 1.35                     # line spacing, as a share of the text height

_cache = {"sig": None, "by_sheet": {}}


def _signature(project):
    return (tuple((s.id, s.version, project.sheet_number(s), s.size, s.cols, s.rows,
                   s.col_start, s.row_start) for s in project.sheets),
            project.zone_format, project.settings.get("xref_height"))


def _where(project, sheet, e):
    return project.zone_text(sheet, e.pos[0], e.pos[1]) or "%s-?" % project.sheet_number(sheet)


def _order(project):
    pos = {s.id: i for i, s in enumerate(project.sheets)}

    def key(item):
        s, e = item
        k = tags.order_key(s, "across")(e.pos)
        return (pos.get(s.id, 0), k)
    return key


def live_all(project):
    """{sheet id: [(x, y, text, height)]} worked out from the drawing now (kept until the
    project changes)."""
    sig = _signature(project)
    if _cache["sig"] == sig:
        return _cache["by_sheet"]
    h = float(project.settings.get("xref_height", 0.08))
    index = tags.devices(project)
    children = {}                                   # parent DEV -> [(sheet, contact)]
    contacts = []
    for s in project.sheets:
        for e in s.inserts():
            if tags.is_child(e):
                contacts.append((s, e))
                dev = e.attrs.get("PARENT")
                if dev in index:
                    children.setdefault(dev, []).append((s, e))
    out = {s.id: [] for s in project.sheets}
    key = _order(project)
    for dev, (s, parent) in index.items():
        if parent.attrs.get("XREF") == "0":
            continue
        items = sorted((c for c in children.get(dev, []) if c[1].attrs.get("XREF") != "0"),
                       key=key)
        if not items:
            continue
        bb = parent.bbox()
        x = (bb[0] + bb[2]) / 2.0
        y = bb[1] - GAP - h
        for cs, c in items:
            mark = MARK.get(c.defn.contact, "")
            text = ("%s %s" % (mark, _where(project, cs, c))).strip()
            out[s.id].append((round(x, 6), round(y, 6), text, h))
            y -= h * LINE
    # off-sheet connectors: where the same name's other ends are
    from .wirenums import connectors
    for name, ends in connectors(project).items():
        for s, c in ends:
            others = [_where(project, os_, oc) for os_, oc in ends if oc is not c]
            bb = c.bbox()
            out[s.id].append((round((bb[0] + bb[2]) / 2.0, 6), round(bb[1] - GAP - h, 6),
                              ", ".join(others) if others else "?", h))
    for s, c in contacts:
        if tags.numbered(c):
            continue                    # (a terminal shows its number, not where its strip is)
        got = index.get(c.attrs.get("PARENT")) if c.attrs.get("PARENT") else None
        text = _where(project, got[0], got[1]) if got is not None else "?"
        bb = c.bbox()
        out[s.id].append((round((bb[0] + bb[2]) / 2.0, 6), round(bb[1] - GAP - h, 6), text, h))
    _cache["sig"], _cache["by_sheet"] = sig, out
    return out


def live(project, sheet):
    return live_all(project).get(sheet.id, [])


def held(project, sheet):
    """True when the sheet shows kept references instead of live ones."""
    return bool(sheet.xref_frozen) or not project.settings.get("xref_auto", True)


def shown(project, sheet):
    """The references drawn on the sheet."""
    if sheet is project.title_block:
        return []
    if held(project, sheet):
        return list(sheet.xref_shown or [])
    return live(project, sheet)


def out_of_date(project):
    """The sheets whose drawn references aren't what the drawing says now."""
    return [s for s in project.sheets
            if held(project, s) and list(s.xref_shown or []) != live(project, s)]


def texts(project, sheet):
    """The references drawn on the sheet, as centered texts."""
    return [Text((x, y), t, hh, 0.0, "center") for x, y, t, hh in shown(project, sheet)]


def update(ed, project, sheets=None):
    """Update cross-references: the held sheets (all but frozen ones, unless named) take what
    the drawing says now. Returns how many sheets changed."""
    n = 0
    for s in (sheets if sheets is not None else project.sheets):
        if sheets is None and s.xref_frozen:
            continue
        now = live(project, s)
        if list(s.xref_shown or []) != now:
            ed.sheet_meta(s, xref_shown=[list(t) for t in now])
            n += 1
    return n


def freeze(ed, project, sheet, on):
    """Freeze (keep the references as they are now) or unfreeze a sheet."""
    if on:
        ed.sheet_meta(sheet, xref_frozen=True,
                      xref_shown=[list(t) for t in live(project, sheet)])
    else:
        ed.sheet_meta(sheet, xref_frozen=False)


def set_auto(ed, project, on):
    """Turn automatic cross-references on or off; turned off, every sheet keeps what it shows
    now (frozen sheets keep theirs)."""
    if not on:
        for s in project.sheets:
            if not s.xref_frozen:
                ed.sheet_meta(s, xref_shown=[list(t) for t in live(project, s)])
    ed.project_settings({"xref_auto": bool(on)})
