"""Wire list and terminal strip list (no Qt): the project's wires by number with what each
lands on, and its terminal strips terminal by terminal with the wires on each side. Worked
out from the drawing each time (wire numbers, pins, terminals), never kept as text.

A landing is a pin a wire ends on: a terminal by its strip and number (TB1-12), anything else
by its tag and pin (CR1:A1); off-sheet connectors carry a wire on and are not landings
(pull.landing_name, pull._sheet_landings)."""

import csv

from . import pull
from . import wirenums

WIRE_HEAD = ["Wire", "Size and color", "Lands on", "Sheets"]
TERM_HEAD = ["Strip", "Terminal", "Wires (left)", "Wires (right)", "Where"]


def _where(project, sheet, ins):
    """Page and zone of a placed symbol (6-B3), or the page alone."""
    return project.zone_text(sheet, ins.pos[0], ins.pos[1]) or project.sheet_number(sheet)


def wire_rows(project):
    """[[wire number, size and color, landings, sheets]] for every numbered wire, in number
    order; landings each with where it is: "CR1:A1 (6-B3)"."""
    if not wirenums.enabled(project):
        return []
    gs, info, _dist, _taps, _conns = wirenums._assemble(project)
    out = []
    for g, nodes in gs.items():
        nums = info[g][2]
        num = nums[0] if nums else ""
        if not num:
            continue
        lands, sheets, sizes = [], [], []
        for s, ws in nodes:
            page = project.sheet_number(s)
            if page not in sheets:
                sheets.append(page)
            table = pull._sheet_landings(s)
            roots = wirenums._sheet_groups(s)
            for r in sorted({roots[w.id] for w in ws}):
                for ins, pin in table.get(r, ()):
                    name = "%s (%s)" % (pull.landing_name(ins, pin), _where(project, s, ins))
                    if name not in lands:
                        lands.append(name)
            for w in ws:
                lay = project.layers.get(w.layer)
                label = (str(w.awg) + " AWG").strip() if w.awg else (
                    lay.wire_label() if lay is not None else "")
                if label and label not in sizes:
                    sizes.append(label)
        out.append([num, ", ".join(sizes), ", ".join(sorted(lands, key=pull._natural)),
                    ", ".join(sheets)])
    out.sort(key=lambda r: pull._natural(r[0]))
    return out


def _numbers_at(sheet, ins, roots, num_of):
    """{pin: [wire numbers]} of the wires ending on each pin of a placed symbol."""
    out = {}
    for name, q in ins.pin_points():
        for o in sheet.query_point(q, wirenums.TOL):
            if getattr(o, "kind", "") == "wire" and o.id in roots and o.touches(q, wirenums.TOL):
                n = num_of.get(roots[o.id], "") or o.num or "?"
                got = out.setdefault(name, [])
                if n not in got:
                    got.append(n)
    return out


def terminal_rows(project):
    """[[strip, terminal, wires on its left pin, wires on its right pin, where]] for every
    terminal, by strip then terminal number; a terminal with no number yet as "?"."""
    out = []
    for s in project.sheets:
        roots = wirenums._sheet_groups(s)
        num_of = {}
        for w in s.wires():
            r = roots.get(w.id)
            if r is not None and w.num and r not in num_of:
                num_of[r] = w.num
        for ins in s.inserts():
            if not pull.is_terminal(ins):
                continue
            pins = ins.pin_points()
            if not pins:
                continue
            at = _numbers_at(s, ins, roots, num_of)
            # (left and right as drawn: the pin nearer the symbol's left in its own drawing)
            names = [n for n, _q in sorted(
                ins.defn.pins and [(p["name"], p["pos"]) for p in ins.defn.pins] or [],
                key=lambda t: (t[1][0], -t[1][1]))]
            left = names[0] if names else None
            right = names[-1] if len(names) > 1 else None
            tag = (ins.attrs.get("TAG", "") or "").strip() or "TB?"
            term = (ins.attrs.get("TERM", "") or "").strip() or "?"
            out.append([tag, term, ", ".join(at.get(left, [])) if left else "",
                        ", ".join(at.get(right, [])) if right else "",
                        _where(project, s, ins)])
    out.sort(key=lambda r: (pull._natural(r[0]), pull._natural(r[1])))
    return out


XLSX = "Excel workbook (*.xlsx)"
SAVE_TYPES = "CSV (*.csv);;" + XLSX         # (a report's Save box: CSV or Excel)


def write_csv(path, head, rows, title="Report"):
    """A report to a file: an Excel workbook when the name ends .xlsx (the roadmap's item 8:
    its header bold and kept in sight, columns wide enough, whole numbers as numbers), else CSV.
    The number of rows written."""
    if path.lower().endswith(".xlsx"):
        return write_xlsx(path, head, rows, title)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    return len(rows)


def _cell(v):
    t = str(v)
    if t.isdigit() and (len(t) == 1 or not t.startswith("0")) and len(t) < 15:
        return int(t)                   # (a count; a wire number "0012" stays as written)
    return t


def write_xlsx(path, head, rows, title="Report"):
    """A report as an Excel workbook of one sheet (openpyxl, imported only here)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "".join(ch for ch in title if ch not in '[]:*?/\\')[:31] or "Report"
    ws.append([str(h) for h in head])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in rows:
        ws.append([_cell(v) for v in r])
    ws.freeze_panes = "A2"
    for i, h in enumerate(head):
        width = max([len(str(h))] + [len(str(r[i])) for r in rows if i < len(r)])
        ws.column_dimensions[ws.cell(row=1, column=i + 1).column_letter].width = \
            min(60, width + 2)
    wb.save(path)
    return len(rows)
