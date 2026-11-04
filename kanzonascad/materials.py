"""What a project's DIN rail and wire duct take to build (no Qt): per size and part, the
pieces cut, their total length and how many stock lengths that is.

Pieces are packed into stock lengths largest first (first-fit decreasing), so the count is
what you'd actually cut, not just the total divided by the stock length; a piece longer
than a stock length takes as many whole lengths as it needs (butted together). Saw cuts take
no width here (round up yourself if your cuts lose material).
"""

from .model import Rail, Duct, fmt_inches, size_text, RAIL_PROFILES

TOL = 1e-6


def stock_of(project, e):
    if e.stock > 0:
        return e.stock
    key = "rail_stock" if isinstance(e, Rail) else "duct_stock"
    return float(project.settings.get(key, 39.37 if isinstance(e, Rail) else 72.0))


def pack(cuts, stock):
    """(stock lengths used, [[cuts in each length]]), largest cut first into the first length
    with room."""
    sticks = []                         # [room left, [cuts]]
    extra = 0
    for c in sorted(cuts, reverse=True):
        if c > stock + TOL:
            whole = int(c // stock)
            extra += whole
            c -= whole * stock
            if c <= TOL:
                continue
        for s in sticks:
            if s[0] + TOL >= c:
                s[0] -= c
                s[1].append(c)
                break
        else:
            sticks.append([stock - c, [c]])
    return len(sticks) + extra, [s[1] for s in sticks]


def rows(project):
    """One row per kind, size and part: {"item", "size", "mfr", "cat", "desc", "cuts" (lengths,
    longest first), "total", "stock", "sticks", "sheets"}."""
    groups = {}
    for s in project.sheets:
        for e in s.entities.values():
            if not isinstance(e, (Rail, Duct)):
                continue
            if isinstance(e, Rail):
                prof = RAIL_PROFILES.get(e.size)
                item, size = "DIN rail", prof[0] if prof else e.size
            else:
                item, size = "Wire duct", size_text(e.width, e.depth)
            key = (item, size, e.attrs.get("MFR", ""), e.attrs.get("CAT", ""),
                   round(stock_of(project, e), 6))
            g = groups.setdefault(key, {"item": item, "size": size, "mfr": key[2],
                                        "cat": key[3], "desc": e.attrs.get("DESC", ""),
                                        "cuts": [], "stock": key[4], "sheets": set()})
            g["cuts"].append(e.length())
            g["sheets"].add(project.sheet_number(s))
    out = []
    for key in sorted(groups):
        g = groups[key]
        g["cuts"].sort(reverse=True)
        g["total"] = sum(g["cuts"])
        g["sticks"], _plan = pack(g["cuts"], g["stock"])
        g["sheets"] = sorted(g["sheets"], key=lambda n: (len(n), n))
        out.append(g)
    return out


def table(project):
    """The rows as text cells, for a dialog or a CSV file: (headers, rows)."""
    head = ["Item", "Size", "Manufacturer", "Catalog number", "Pieces", "Cut lengths",
            "Total length", "Stock length", "Stock pieces", "Sheets"]
    body = []
    for r in rows(project):
        body.append([r["item"], r["size"], r["mfr"], r["cat"], str(len(r["cuts"])),
                     ", ".join(fmt_inches(c) for c in r["cuts"]), fmt_inches(r["total"]),
                     fmt_inches(r["stock"]), str(r["sticks"]), ", ".join(r["sheets"])])
    return head, body


def write_csv(project, path):
    import csv
    head, body = table(project)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(body)
    return len(body)
