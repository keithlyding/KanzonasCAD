"""The bill of materials (no Qt): every part the project uses, once, grouped by manufacturer
and catalog number, with how many, their description, tags and sheets.

A part is a device placed on a schematic (a symbol that gets a tag: a coil, a pushbutton) or
a footprint on a panel; a device and its footprint share a tag, so they are one part, their
manufacturer, catalog number and description taken from whichever has them. A contact belongs
to its device (not a part of its own); symbols without a tag (an off-sheet connector, a
ground) are not parts. DIN rail and wire duct come in as the stock lengths to buy (Panel
materials).
"""

from . import materials, tags
from .model import Insert


def _sheet_key(n):
    return (len(n), n)


def parts(project, unnumbered=True):
    """The parts placed: [{"tag", "mfr", "cat", "desc", "block", "sheets"}], a tagged part once
    (its device and footprint together). unnumbered False: parts without a catalog number
    left out."""
    by_tag, loose = {}, []
    for s in project.sheets:
        num = project.sheet_number(s)
        for e in s.entities.values():
            if not isinstance(e, Insert) or e.defn is None:
                continue
            d = e.defn
            if d.kind == "symbol" and not tags.is_device(e):
                continue                # (a contact, a connector, a ground: not a part)
            a = e.attrs
            rec = {"tag": a.get("TAG", "").strip(), "mfr": a.get("MFR", "").strip() or
                   d.manufacturer, "cat": a.get("CAT", "").strip() or d.catalog,
                   "desc": a.get("DESC", "").strip() or d.description, "block": d.name,
                   "sheets": {num}}
            if rec["tag"] and not rec["tag"].endswith("?"):
                got = by_tag.get(rec["tag"])
                if got is None:
                    by_tag[rec["tag"]] = rec
                else:
                    for k in ("mfr", "cat", "desc"):
                        if not got[k] and rec[k]:
                            got[k] = rec[k]
                    if d.kind == "footprint":
                        got["block"] = rec["block"]     # (the panel part's name over the symbol's)
                    got["sheets"] |= rec["sheets"]
            else:
                loose.append(rec)
    out = list(by_tag.values()) + loose
    if not unnumbered:
        out = [r for r in out if r["cat"]]
    return out


def rows(project, unnumbered=True):
    """The lines of the bill of materials: [{"item", "qty", "mfr", "cat", "desc", "tags",
    "sheets", "kind"}], parts grouped by manufacturer and catalog number (those without one by
    their block and description), then DIN rail and wire duct; numbered from 1."""
    groups = {}
    for r in parts(project, unnumbered):
        key = (r["mfr"].upper(), r["cat"].upper()) if r["cat"] else \
            (r["mfr"].upper(), "", r["block"], r["desc"])
        g = groups.setdefault(key, {"qty": 0, "mfr": r["mfr"], "cat": r["cat"],
                                    "desc": r["desc"] or ("" if r["cat"] else r["block"]),
                                    "tags": [], "sheets": set(), "kind": "part"})
        g["qty"] += 1
        if r["tag"]:
            g["tags"].append(r["tag"])
        if not g["desc"] and r["desc"]:
            g["desc"] = r["desc"]
        g["sheets"] |= r["sheets"]
    lines = sorted(groups.values(), key=lambda g: (not g["cat"], g["mfr"].upper(),
                                                   g["cat"].upper(), g["desc"].upper()))
    for m in materials.rows(project):
        lines.append({"qty": m["sticks"], "mfr": m["mfr"], "cat": m["cat"],
                      "desc": "%s, %s (%s stock lengths of %s)" % (
                          m["item"], m["size"], m["sticks"], materials.fmt_inches(m["stock"])),
                      "tags": [], "sheets": set(m["sheets"]), "kind": "stock"})
    for i, g in enumerate(lines, 1):
        g["item"] = i
        g["tags"] = sorted(g["tags"], key=_natural)
        g["sheets"] = sorted(g["sheets"], key=_sheet_key)
    return lines


def _natural(t):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t)]


HEAD = ["Item", "Qty", "Manufacturer", "Catalog number", "Description", "Tags", "Sheets"]


def table(project, unnumbered=True):
    """(headers, rows of text cells), for the dialog and CSV."""
    body = []
    for g in rows(project, unnumbered):
        body.append([str(g["item"]), str(g["qty"]), g["mfr"], g["cat"] or "(none)"
                     if g["kind"] == "part" else g["cat"], g["desc"], ", ".join(g["tags"]),
                     ", ".join(g["sheets"])])
    return HEAD, body


def write_csv(project, path, unnumbered=True):
    import csv
    head, body = table(project, unnumbered)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(body)
    return len(body)
