"""Cables between locations (the owner: "what cables need to be pulled between panels and where
all the wires need to be landed on both sides"). No Qt.

Each sheet has a location (Sheet properties: MCP, JB-1, FIELD...), and a device can have its own
(its LOC attribute, which wins). A wire, with every wire joined to it on its sheet and across
sheets by off-sheet connectors (one wire number), lands on the pins of the symbols at its ends.
When its landings are in two or more locations, it has to be pulled between them: it is a
conductor of the run between those locations (MCP <-> JB-1). Each run lists its conductors in
wire number order, and for each location where the conductor lands: on a terminal (TB1-12),
or, where it lands on no terminal there, on the devices' pins (CR1:A1).

What the field decides is kept per run in the project's settings ("cables"): the cable's tag
and type (W101, 12C #14 TC), whether its conductors are numbered (black, with the wire number
on them) or color coded, and each conductor's color or marking. Lengths are left to the job.
"""

from . import wirenums
from .model import Insert

MARKINGS = {"numbered": "Numbered (black, wire numbers on them)",
            "colors": "Color coded"}
SEP = " | "                     # between a run's locations in its key ("MCP | JB-1")
ARROW = " ↔ "              # between them where it is shown (MCP <-> JB-1)


def run_key(locs):
    return SEP.join(locs)


def run_name(locs):
    return ARROW.join(locs)


def location_of(sheet, ins):
    """Where a placed symbol is: its own LOC, else its sheet's location ("" when neither)."""
    return (ins.attrs.get("LOC", "") or "").strip() or sheet.location


def landing_name(ins, pin):
    """A wire's landing: a terminal by its strip and number (TB1-12, TB1 when it has no number
    yet); anything else by its tag and pin (CR1:A1; the block's name when it has no tag)."""
    tag = (ins.attrs.get("TAG", "") or "").strip()
    if is_terminal(ins):
        term = (ins.attrs.get("TERM", "") or "").strip()
        return "%s-%s" % (tag or "TB?", term) if term else (tag or "TB?")
    return "%s:%s" % (tag or ins.block, pin)


def is_terminal(ins):
    d = ins.defn
    return d is not None and any(a.get("attr") == "TERM" for a in d.attr_texts)


def _sheet_landings(sheet):
    """{sheet-local wire group root: [(insert, pin)]} of the symbols' pins wires end on (off-sheet
    connectors are not landings: they carry the wire on), kept until the sheet changes."""
    got = getattr(sheet, "_pull_landings", None)
    if got is not None and got[0] == sheet.version:
        return got[1]
    roots = wirenums._sheet_groups(sheet)
    out = {}
    for ins in sheet.inserts():
        d = ins.defn
        if d is None or not d.pins or d.kind != "symbol" or d.wiring == "link":
            continue
        for pin, r in wirenums._pin_wires(sheet, ins, roots).items():
            out.setdefault(r, []).append((ins, pin))
    sheet._pull_landings = (sheet.version, out)
    return out


def _natural(num):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", num or "")]


def runs(project):
    """The runs between locations: [{"locs": [location...], "key", "name", "conductors":
    [{"num", "lands": {location: [landing...]}}]}], in the order the locations first come in
    the project; and how many wires land in one location and on a sheet or device with none
    (they may need a location to show)."""
    gs, info, _dist = wirenums._assemble(project)
    order = {}
    for s in project.sheets:
        if s.location and s.location not in order:
            order[s.location] = len(order)
        for ins in s.inserts():
            loc = (ins.attrs.get("LOC", "") or "").strip()
            if loc and loc not in order:
                order[loc] = len(order)
    by_run = {}
    unplaced = 0
    for g, nodes in gs.items():
        lands = {}
        blank = False
        for s, ws in nodes:
            table = _sheet_landings(s)
            roots = wirenums._sheet_groups(s)
            for r in {roots[w.id] for w in ws}:
                for ins, pin in table.get(r, ()):
                    loc = location_of(s, ins)
                    if not loc:
                        blank = True
                        continue
                    lands.setdefault(loc, []).append((ins, pin))
        if len(lands) < 2:
            if blank and lands:
                unplaced += 1
            continue
        locs = sorted(lands, key=lambda k: (order.get(k, len(order)), k))
        shown = {}
        for loc in locs:
            here = lands[loc]
            terms = [(i, p) for i, p in here if is_terminal(i)]
            names = []
            for ins, pin in (terms or here):
                n = landing_name(ins, pin)
                if n not in names:
                    names.append(n)
            shown[loc] = sorted(names, key=_natural)
        nums = info[g][2]
        by_run.setdefault(tuple(locs), []).append(
            {"num": nums[0] if nums else "", "lands": shown, "partial": blank})
    out = []
    for locs in sorted(by_run, key=lambda t: [(order.get(k, len(order)), k) for k in t]):
        conds = sorted(by_run[locs], key=lambda c: (c["num"] == "", _natural(c["num"]),
                                                     [x for v in c["lands"].values() for x in v]))
        out.append({"locs": list(locs), "key": run_key(locs), "name": run_name(locs),
                    "conductors": conds})
    return out, unplaced


def cable(project, key):
    """What is kept of a run: {"tag", "type", "marking", "colors": {wire number: text}}."""
    got = (project.settings.get("cables") or {}).get(key) or {}
    return {"tag": str(got.get("tag", "") or ""), "type": str(got.get("type", "") or ""),
            "marking": got.get("marking") if got.get("marking") in MARKINGS else "numbered",
            "colors": {str(k): str(v) for k, v in (got.get("colors") or {}).items()}}


def clean_cable(c):
    """A run's settings as kept: empty colors left out."""
    return {"tag": c.get("tag", "").strip(), "type": c.get("type", "").strip(),
            "marking": c.get("marking") if c.get("marking") in MARKINGS else "numbered",
            "colors": {k: v.strip() for k, v in (c.get("colors") or {}).items() if v.strip()}}


def marking_of(c, num):
    """A conductor's color or marking: the one typed, else for numbered wires "BLK, #6001"."""
    got = c["colors"].get(num, "")
    if got:
        return got
    if c["marking"] == "numbered":
        return "BLK, #%s" % num if num else "BLK"
    return ""


def table(project, cables=None):
    """(header, rows) of the pull list: a row per conductor, its run, cable, marking and
    landings in each location (a run of three locations or more lists them one after
    another). cables: {key: cable} being edited (else the project's)."""
    head = ["From", "To", "Cable", "Cable type", "Wire", "Color / marking",
            "Lands at (from)", "Lands at (to)"]
    rows = []
    for r in runs(project)[0]:
        c = (cables or {}).get(r["key"]) or cable(project, r["key"])
        a, b = r["locs"][0], ", ".join(r["locs"][1:])
        for cd in r["conductors"]:
            far = "; ".join("%s: %s" % (loc, ", ".join(cd["lands"][loc]))
                            for loc in r["locs"][1:]) if len(r["locs"]) > 2 else \
                ", ".join(cd["lands"][r["locs"][1]])
            rows.append([a, b, c["tag"], c["type"], cd["num"] or "(no number)",
                         marking_of(c, cd["num"]), ", ".join(cd["lands"][a]), far])
    return head, rows


def write_csv(project, path, cables=None):
    import csv
    head, rows = table(project, cables)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    return len(rows)


def html(project, cables=None, title=""):
    """The pull list as a page per run (for Save as PDF...): the cable, then a line per
    conductor with where it lands on each side."""
    from html import escape as E
    parts = ["<html><body style='font-family: Arial, sans-serif; font-size: 9pt'>"]
    rs = runs(project)[0]
    for i, r in enumerate(rs):
        c = (cables or {}).get(r["key"]) or cable(project, r["key"])
        brk = " style='page-break-before: always'" if i else ""
        parts.append("<h2%s>%s</h2>" % (brk, E(r["name"])))
        parts.append("<p>%s<b>Cable:</b> %s &nbsp; <b>Type:</b> %s &nbsp; <b>Conductors:</b> %d"
                     " &nbsp; (%s)</p>" % (E(title + " - ") if title else "",
                                           E(c["tag"] or "-"), E(c["type"] or "-"),
                                           len(r["conductors"]), E(MARKINGS[c["marking"]])))
        parts.append("<table border='1' cellspacing='0' cellpadding='3' width='100%'><tr>"
                     "<th>#</th><th>Wire</th><th>Color / marking</th>"
                     + "".join("<th>Lands at %s</th>" % E(loc) for loc in r["locs"])
                     + "<th>Pulled</th><th>Landed</th></tr>")
        for n, cd in enumerate(r["conductors"], 1):
            parts.append("<tr><td>%d</td><td>%s</td><td>%s</td>%s<td></td><td></td></tr>" % (
                n, E(cd["num"] or "(no number)"), E(marking_of(c, cd["num"])),
                "".join("<td>%s</td>" % E(", ".join(cd["lands"][loc])) for loc in r["locs"])))
        parts.append("</table>")
    parts.append("</body></html>")
    return "".join(parts)
