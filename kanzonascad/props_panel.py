"""The Properties panel (Ctrl+1; the owner, Nov 2026: "Can text properties be in the block panel,
so I don't have to right click it each time?", and asked what it shows: "Everything of the
selection"), as AutoCAD's Properties palette: docked at the right (or the left, the bottom, or
floating, put back where it was left), it shows what is selected, grouped (General: its kind,
layer, color, position and rotation; then a symbol's or footprint's tag, description,
attributes and text lines, a wire's number, gauge and color label, a text's wording and
height, a line's length and angle...), and a change made in it applies at once, as one step
of Undo.

- Several selected: a field they all have shows their one value, or *varies*; set, it is set
  on all of them in one step. Objects of different kinds show General only.
- Edits apply on Enter or when the field loses focus (number boxes then too, never at every
  key); ticks and lists at once. A placed block's fields go through the attributes window's
  own code (MainWindow.attribute_changes), a wire's number through the Wire number window's
  (MainWindow.apply_wire_number), so the two always do the same.
- It follows the selection as Trace does: a click only starts a short timer, and the panel is
  filled once the selection has settled, from what is selected only (never a walk of the
  sheet); nothing at all while it is closed. The owner's rule for Trace holds for it too:
  "make sure that the loading ... doesn't prevent any interaction with the sheet itself".
- It refreshes after Undo, Redo and changes made anywhere else.

A mixin of MainWindow (main_window.py), as trace_panel.py is; the fields are worked out here
(fields_for), a field's widget named "prop_" + its key, so tests and the battery find it."""

import math

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from . import model as M

NAME = "Properties"
VARIES = "*varies*"
HINT = "Select something on the drawing to see its properties here"
FOLLOW_MS = 40              # the panel filled this long after the last selection change
REFRESH_MS = 120            # ...and this long after the last change to the project
NA = object()               # (a field an object doesn't have)
OTHER = "__other__"         # (the color list's Other...)
COLORS = (("ByLayer", M.BYLAYER), ("White/black", M.ADAPTIVE), ("Red", "#ff0000"),
          ("Yellow", "#ffff00"), ("Green", "#00ff00"), ("Cyan", "#00ffff"),
          ("Blue", "#0000ff"), ("Magenta", "#ff00ff"))
COLOR_LABELS = (("As the project", None), ("Shown", True), ("Off", False))
KIND_NAMES = {"symbol": "Symbol", "footprint": "Footprint", "block": "Block", "wire": "Wire",
              "text": "Text", "mtext": "Multiline text", "line": "Line", "circle": "Circle",
              "arc": "Arc", "polyline": "Polyline", "dimension": "Dimension",
              "hatch": "Hatch", "leader": "Leader", "dashbox": "Dashed box",
              "ladder": "Ladder", "rail": "DIN rail", "duct": "Wire duct",
              "picture": "Picture", "wirecross": "Wire crossing"}


class Field:
    """One property: its key (the widget's name is "prop_" + key), label, widget kind ("text",
    "size": a paper size or blank, "number", "check", "choice", "info"), how it reads an
    object (get: its value, or NA when it hasn't one) and how it is set (put(ed, s, cur, value),
    inside the panel's one step; or alone(cur, value), a step of its own: a wire's number)."""

    def __init__(self, key, label, kind, get, put=None, alone=None, choices=(), lo=-1e9,
                 hi=1e9, step=0.125, decimals=4, suffix="", tip="", blank="", row=None,
                 single=False):
        self.key, self.label, self.kind = key, label, kind
        self.get, self.put, self.alone = get, put, alone
        self.choices = tuple(choices)
        self.lo, self.hi, self.step, self.decimals = lo, hi, step, decimals
        self.suffix, self.tip, self.blank = suffix, tip, blank
        self.row = row              # (fields of one row: a text line's Shown, size, angle...)
        self.single = single        # (only set with one object selected: shown, not set, else)

    def editable(self, n):
        return (self.put is not None or self.alone is not None) and not (self.single and n > 1)


def kind_of(e):
    """An object's kind for the panel: symbol, footprint, wire, text, line..."""
    if isinstance(e, M.Insert):
        if e.defn is None:
            return "block"
        return "footprint" if e.defn.kind == "footprint" else "symbol"
    return e.kind


def kind_name(e):
    k = kind_of(e)
    return KIND_NAMES.get(k, k.capitalize())


def common(values):
    """(value, varies) of a field over the selection: their one value, or (None, True)."""
    first = values[0]
    for x in values[1:]:
        if x != first:
            return None, True
    return first, False


# ---- the fields ------------------------------------------------------------------------------
def _position(e):
    if isinstance(e, (M.Insert, M.Text, M.MText)):
        return e.pos
    if isinstance(e, M.Circle):
        return e.center
    return None


def _angle(e):
    return e.angle if isinstance(e, (M.Insert, M.Text, M.MText)) else NA


def _moved_to(cur, axis, value):
    q = _position(cur)
    return cur.moved(value - q[0], 0.0) if axis == 0 else cur.moved(0.0, value - q[1])


def general_fields(project):
    layers = [(n, n) for n in project.layers]

    def put_layer(ed, s, cur, value):
        if cur.layer != value:
            ed.change(s, cur.copy(layer=value))

    def put_color(ed, s, cur, value):
        if cur.color != value:
            ed.change(s, cur.copy(color=value))

    def pos_get(axis):
        return lambda e: (_position(e)[axis] if _position(e) is not None else NA)

    def pos_put(axis):
        def put(ed, s, cur, value):
            if abs(_position(cur)[axis] - value) > 1e-12:
                ed.change(s, _moved_to(cur, axis, value))
        return put

    def put_angle(ed, s, cur, value):
        d = (value - cur.angle + 180.0) % 360.0 - 180.0
        if abs(d) > 1e-9:
            ed.change(s, cur.rotated(_position(cur), d))

    return [
        Field("kind", "Kind", "info", kind_name),
        Field("layer", "Layer", "choice", lambda e: e.layer, put_layer, choices=layers,
              tip="The layer it is on (its color, if ByLayer, and whether it shows)"),
        Field("color", "Color", "choice", lambda e: e.color, put_color, choices=COLORS,
              tip="ByLayer: its layer's color; or a color of its own (Other...: any)"),
        Field("x", "Position X", "number", pos_get(0), pos_put(0), suffix=" in",
              tip="Where it is on the sheet, in drawing inches (its insertion point)"),
        Field("y", "Position Y", "number", pos_get(1), pos_put(1), suffix=" in"),
        Field("rotation", "Rotation", "number", _angle, put_angle, lo=0.0, hi=359.99,
              step=90.0, decimals=2, suffix=" deg",
              tip="Its angle on the sheet; turned about its insertion point"),
    ]


def _attr_put(win, project, k):
    """A put changing one attribute of a placed block through the attributes window's code
    (Location left blank: none of its own, its sheet's)."""
    from . import tags

    def put(ed, s, cur, value):
        attrs = dict(cur.attrs)
        value = (value or "").strip()
        attrs[k] = value
        if k == "LOC" and not value:
            attrs.pop(k)
        if k == "TAG" and tags.is_device(cur) and attrs.get("TAG") != cur.attrs.get("TAG"):
            attrs["TAG_LOCK"] = "1"         # (a tag typed is meant: as in the window)
        shown = {}
        if k in tags.LINKED_ATTRS and tags.is_footprint(cur) and \
                tags.parent_of(project, cur) is not None:
            shown["device"] = {k: value}    # (a linked footprint's rating is its device's)
        apply_changes(ed, win.attribute_changes(project, s, cur, attrs, shown))
    return put


def _shown_put(win, project, n):
    def put(ed, s, cur, value):
        hidden = set(cur.hidden)
        (hidden.discard if value else hidden.add)(n)
        apply_changes(ed, win.attribute_changes(project, s, cur, dict(cur.attrs),
                                                {"hidden": frozenset(hidden)}))
    return put


def _angle_put(win, project, n, label=False):
    def put(ed, s, cur, value):
        name = "@" + n if label else n
        if abs((value - cur.attr_angle(name) + 180.0) % 360.0 - 180.0) <= 1e-9:
            return
        shown = {"label_angles" if label else "angles": {name: value}}
        apply_changes(ed, win.attribute_changes(project, s, cur, dict(cur.attrs),
                                                shown))
    return put


def apply_changes(ed, changes):
    for sh, e in changes:
        ed.change(sh, e)


def _text_size(e, sheet, n):
    """A symbol's text line's size on paper (its tag's, an attribute's), read only."""
    d = e.defn
    k = sheet.k() or 1.0
    if n == "TAG":
        return round((e.tag_h or d.tag_height) * e.scale / k, 4)
    for a in d.attr_texts:
        if a["attr"] == n:
            return round(a["height"] * e.scale / k, 4)
    return NA


def block_fields(win, project, sheet, ents):
    """A symbol's or footprint's fields (every selected one a symbol, or every one a
    footprint)."""
    from . import missing_fp, tags
    fp = kind_of(ents[0]) == "footprint"
    out = [Field("block", "Block", "info", lambda e: e.block_name)]
    names = {"TAG": "Tag", "DESC": "Description", "MFR": "Manufacturer",
             "CAT": "Catalog number"}

    def tag_get(e):
        return NA if tags.is_child(e) else e.attrs.get("TAG", "")
    out.append(Field("TAG", "Tag", "text", tag_get, _attr_put(win, project, "TAG"),
                     tip="Its device tag; typed, it is locked (numbering leaves it alone)"
                     if not fp else "The device it is: typed, the device with that tag"))
    out.append(Field("parent", "Belongs to", "info",
                     lambda e: (e.attrs.get("TAG", "") or "?") if tags.is_child(e) else NA,
                     tip="A contact's device (its attributes window chooses it)"))

    def has_desc_lines(e):
        return any(a["attr"] in ("DESC1", "DESC2", "DESC3") for a in e.defn.attr_texts)
    for k in ("DESC", "MFR", "CAT"):
        def get(e, k=k):
            if k == "DESC" and has_desc_lines(e):
                return NA
            return e.attrs.get(k, "")
        blank = ""
        if fp and k in tags.OWN_FIELDS:
            own = {tags.own_default(e.defn, k) for e in ents}
            if len(own) == 1 and next(iter(own)):
                blank = "%s (the footprint's)" % next(iter(own))
        out.append(Field(k, names[k], "text", get, _attr_put(win, project, k), blank=blank))
    # each attribute's value (a terminal's number, a PLC point's address, ratings...)
    seen = set(names)
    attr_names = []
    for e in ents:
        for a in e.defn.attr_texts:
            if a["attr"] not in seen:
                seen.add(a["attr"])
                attr_names.append(a["attr"])
    if fp:
        # (a linked footprint: its device's ratings, edited here or on the device: the same)
        for e in ents:
            got = tags.parent_of(project, e)
            if got is None:
                continue
            for k in tags.LINKED_ATTRS:
                if k not in seen and (got[1].attrs.get(k) or any(
                        a["attr"] == k for a in (got[1].defn.attr_texts if got[1].defn
                                                 else []))):
                    seen.add(k)
                    attr_names.append(k)
    for k in attr_names:
        def get(e, k=k):
            if any(a["attr"] == k for a in e.defn.attr_texts):
                return e.attrs.get(k, "")
            if fp:
                got = tags.parent_of(project, e)
                if got is not None and (k in got[1].attrs or any(
                        a["attr"] == k for a in (got[1].defn.attr_texts if got[1].defn
                                                 else []))):
                    return got[1].attrs.get(k, "")
            return NA
        unit = M.RATING_FIELDS.get(k)
        label = {"TERM": "Terminal number", "ADDR": "Address", "RATING": "Rating"}.get(
            k, unit[0] if unit else k)
        out.append(Field("attr_" + k, label, "text", get, _attr_put(win, project, k),
                         blank=("a number shows as %s" % M.attr_display(k, "5"))
                         if unit else ""))
    if not fp:
        out.append(Field("LOC", "Location", "text", lambda e: e.attrs.get("LOC", ""),
                         _attr_put(win, project, "LOC"),
                         blank="its sheet's: %s" % (sheet.location or "(none)"),
                         tip="Where this device is when it isn't where its sheet is (Cables "
                             "between locations; Devices without a footprint leaves the "
                             "field out)"))

    def lock_put(ed, s, cur, value):
        attrs = dict(cur.attrs)
        if value:
            attrs["TAG_LOCK"] = "1"
        else:
            attrs.pop("TAG_LOCK", None)
        apply_changes(ed, win.attribute_changes(project, s, cur, attrs, {}))

    def dev_get(fn):
        return lambda e: fn(e) if tags.is_device(e) else NA
    out.append(Field("lock", "Lock this tag", "check",
                     dev_get(lambda e: e.attrs.get("TAG_LOCK") == "1"), lock_put,
                     tip="Automatic numbering leaves its tag alone"))

    def nofp_put(ed, s, cur, value):
        apply_changes(ed, win.attribute_changes(project, s, cur,
                                                missing_fp.with_flag(cur.attrs, value), {}))
    out.append(Field("nofp", "No footprint needed", "check", dev_get(missing_fp.not_needed),
                     nofp_put, tip="Not listed or marked as a device without a footprint "
                                   "(one that goes on no panel)"))
    return out


def symbol_lines(win, project, sheet, ents):
    """A symbol's text lines (its tag, each attribute it can show): Shown, Text size (read
    only: a symbol's tag takes the project's Tag height, its attributes their block's) and
    Angle."""
    names = []
    for e in ents:
        for n in e.shown_names():
            if n not in names:
                names.append(n)
    out = []
    for n in names:
        title = "Pin names" if n == "PINS" else n
        out.append(Field("shown_" + n, title, "check",
                         lambda e, n=n: (n not in e.hidden) if n in e.shown_names() else NA,
                         _shown_put(win, project, n), row=title,
                         tip="Shown on the drawing (ticked)"))
        if n == "PINS":
            continue
        out.append(Field("size_" + n, title, "info",
                         lambda e, n=n: _text_size(e, sheet, n) if n in e.shown_names()
                         else NA, row=title,
                         tip="Its size on paper: a symbol's tag takes the project's Tag "
                             "height (Project properties), its attributes their block's "
                             "(Edit block)"))
        out.append(Field("angle_" + n, title, "number",
                         lambda e, n=n: round(e.attr_angle(n), 2) % 360.0
                         if n in e.shown_names() else NA,
                         _angle_put(win, project, n), lo=0.0, hi=359.99, step=90.0,
                         decimals=2, suffix=" deg", row=title,
                         tip="The angle it is drawn at; once turned, it turns with the symbol"))
    return out


def footprint_lines(win, project, sheet, ents):
    """A footprint's label lines (as its attributes window's Shown on it): Shown, Text size
    (paper inches; blank: its block's, else the project's), Angle, Keep readable."""
    from . import tags
    offer = list(M.LABELS)
    for e in ents:
        got = tags.parent_of(project, e)
        for k in tags.LINKED_ATTRS:
            if k not in offer and (e.attrs.get(k) or (got is not None and got[1].attrs.get(k))):
                offer.append(k)
        for k in M.label_keys(e.label):
            if k not in offer:
                offer.append(k)
    proj_h = float(project.settings.get("fp_label_height", 0.08))
    out = []
    for k in offer:
        key = M.label_size_key(k)
        title = M.label_name(k)

        def shown_put(ed, s, cur, value, k=k):
            keys = M.label_keys(cur.label)
            if value and k not in keys:
                keys.append(k)
            elif not value and k in keys:
                keys.remove(k)
            apply_changes(ed, win.attribute_changes(project, s, cur, dict(cur.attrs),
                                                    {"label": ",".join(keys)}))

        def size_put(ed, s, cur, value, key=key):
            sizes = dict(cur.label_sizes)
            if value:
                sizes[key] = value
            else:
                sizes.pop(key, None)
            apply_changes(ed, win.attribute_changes(project, s, cur, dict(cur.attrs),
                                                    {"label_sizes": sizes}))

        def readable_put(ed, s, cur, value, key=key):
            as_set = set(cur.label_as_set)
            (as_set.discard if value else as_set.add)(key)
            apply_changes(ed, win.attribute_changes(project, s, cur, dict(cur.attrs),
                                                    {"label_as_set": frozenset(as_set)}))
        blocks = {e.defn.label_sizes.get(key) for e in ents}
        if len(blocks) == 1 and next(iter(blocks)):
            blank = "%g block" % next(iter(blocks))
        elif len(blocks) == 1:
            blank = "%g project" % proj_h
        else:
            blank = "block's"
        out += [
            Field("label_" + k, title, "check", lambda e, k=k: k in M.label_keys(e.label),
                  shown_put, row=title, tip="Shown on it (ticked)"),
            Field("label_size_" + key, title, "size",
                  lambda e, key=key: e.label_sizes.get(key), size_put, blank=blank, row=title,
                  tip="Its text size on paper on this copy; blank: its block's (Block "
                      "properties), else Panel settings' Footprint label height"),
            Field("label_angle_" + key, title, "number",
                  lambda e, key=key: round(e.attr_angle("@" + key), 2) % 360.0,
                  _angle_put(win, project, key, label=True), lo=0.0, hi=359.99, step=90.0,
                  decimals=2, suffix=" deg", row=title,
                  tip="The angle it is drawn at; once turned, it turns with the footprint"),
            Field("label_readable_" + key, title, "check",
                  lambda e, key=key: key not in e.label_as_set, readable_put, row=title,
                  tip="Keep readable. Ticked: turned upside down or to read from the left, drawn facing "
                      "you (180 as 0, 270 as 90); unticked: exactly at its angle"),
        ]
    return out


def wire_fields(win, project, sheet, ents):
    from . import wirenums
    from .commands import wire_gauge

    def num_alone(cur, value):
        if not wirenums.enabled(project):
            raise ValueError("Wire numbers are off (Project properties, Schematic)")
        num = (value or "").strip()
        lock = cur.num_lock if num == (cur.num or "") else bool(num)
        v = win.view()
        was = "own" if cur.own_num else "same" if cur.same_num else ""
        win.apply_wire_number(v, cur, num, lock, was, was)

    def lock_put(ed, s, cur, value):
        # (its number's: every wire of its group, as the Wire number window's lock; one left
        # locked would keep the group's number locked)
        got = wirenums.group_of(project, s, cur)
        for sh, w in (got[1] if got is not None else [(s, cur)]):
            now = sh.entities.get(w.id)
            if now is not None and now.num and now.num_lock != bool(value):
                ed.change(sh, now.copy(num_lock=bool(value)))

    def gauge_put(ed, s, cur, value):
        value = (value or "").strip()
        got = "" if not value or value.upper() in ("L", "LAYER", "BYLAYER") else \
            wire_gauge(value)
        if got is None:
            raise ValueError("Not a wire gauge: type 14, 1/0 or 250 kcmil (blank: the "
                             "layer's)")
        if cur.awg != got:
            ed.change(s, cur.copy(awg=got))

    def color_put(ed, s, cur, value):
        if cur.show_color != value:
            ed.change(s, cur.copy(show_color=value))
    layer_g = {(project.layers[e.layer].awg if e.layer in project.layers else "")
               for e in ents}
    blank = "the layer's (%s)" % (M.gauge_text(next(iter(layer_g))) or "none") \
        if len(layer_g) == 1 else "the layer's"
    return [
        Field("wire_num", "Wire number", "text", lambda e: e.num or "", alone=num_alone,
              single=True, blank="(numbered by itself)",
              tip="Typed, it is locked; cleared, numbering gives it one (one wire at a time)"),
        Field("wire_lock", "Lock number", "check",
              lambda e: e.num_lock if e.num else NA, lock_put,
              tip="Numbering leaves its number alone (every wire of its number)"),
        Field("gauge", "Gauge", "text", lambda e: M.gauge_text(e.awg), gauge_put,
              blank=blank, tip="Its own size (14, 1/0, 250 kcmil); blank: its layer's"),
        Field("color_label", "Color in its label", "choice", lambda e: e.show_color,
              color_put, choices=COLOR_LABELS,
              tip="Its insulation color written in its gauge label: as Project properties "
                  "says, or this wire's own"),
        Field("wire_length", "Length", "info", lambda e: round(e.length(), 4)),
    ]


def text_fields(win, project, sheet, ents):
    k = sheet.k() or 1.0

    def text_put(ed, s, cur, value):
        if not value.strip():
            raise ValueError("A text can't be empty (Erase takes it away)")
        if cur.text != value:
            ed.change(s, cur.copy(text=value))

    def height_get(e):
        return round(e.height / (1.0 if e.fixed else k), 4)

    def height_put(ed, s, cur, value):
        h = value * (1.0 if cur.fixed else k)
        if abs(cur.height - h) > 1e-12:
            ed.change(s, cur.copy(height=h))
    out = []
    if all(isinstance(e, M.Text) for e in ents):
        out.append(Field("text", "Text", "text", lambda e: e.text, text_put))
    else:
        out.append(Field("mtext", "Text", "info",
                         lambda e: " / ".join(e.text.splitlines()) or "",
                         tip="Double-click it to edit its lines where it is"))
    out.append(Field("height", "Height (on paper)", "number", height_get, height_put,
                     lo=0.001, hi=100.0, step=0.025, suffix=" in"))
    return out


def line_fields(win, project, sheet, ents):
    def length_put(ed, s, cur, value):
        L = math.dist(cur.p1, cur.p2)
        if L < 1e-12 or value <= 0 or abs(L - value) < 1e-12:
            return
        f = value / L
        p2 = (cur.p1[0] + (cur.p2[0] - cur.p1[0]) * f, cur.p1[1] + (cur.p2[1] - cur.p1[1]) * f)
        ed.change(s, cur.copy(p2=list(p2)))

    def angle_get(e):
        return round(math.degrees(math.atan2(e.p2[1] - e.p1[1], e.p2[0] - e.p1[0])) % 360.0, 4)

    def angle_put(ed, s, cur, value):
        L = math.dist(cur.p1, cur.p2)
        if abs((value - angle_get(cur) + 180.0) % 360.0 - 180.0) < 1e-9:
            return
        a = math.radians(value)
        p2 = (cur.p1[0] + L * math.cos(a), cur.p1[1] + L * math.sin(a))
        ed.change(s, cur.copy(p2=list(p2)))
    return [Field("length", "Length", "number", lambda e: round(math.dist(e.p1, e.p2), 6),
                  length_put, lo=0.0, suffix=" in", tip="Kept from its first point"),
            Field("line_angle", "Angle", "number", angle_get, angle_put, lo=0.0, hi=359.99,
                  step=90.0, decimals=2, suffix=" deg", tip="Turned about its first point")]


def circle_fields(win, project, sheet, ents):
    def put(ed, s, cur, value):
        if value > 0 and abs(cur.radius - value) > 1e-12:
            ed.change(s, cur.copy(radius=value))
    return [Field("radius", "Radius", "number", lambda e: e.radius, put, lo=0.0,
                  suffix=" in")]


GROUPS = {"symbol": ("Symbol", block_fields, symbol_lines),
          "footprint": ("Footprint", block_fields, footprint_lines),
          "wire": ("Wire", wire_fields, None),
          "text": ("Text", text_fields, None),
          "mtext": ("Text", text_fields, None),
          "line": ("Line", line_fields, None),
          "circle": ("Circle", circle_fields, None)}


def fields_for(win, project, sheet, ents):
    """[(group title, [(field, value, varies)])] for the selected objects ents: General, and
    for objects all of one kind that kind's own (with its text lines, for a symbol or a
    footprint). A field shows when every one of them has it."""
    def shown(fields):
        out = []
        for f in fields:
            vals = [f.get(e) for e in ents]
            if any(x is NA for x in vals):
                continue
            value, varies = common(vals)
            out.append((f, value, varies))
        return out
    groups = [("General", shown(general_fields(project)))]
    kinds = {kind_of(e) for e in ents}
    if len(kinds) == 1 and next(iter(kinds)) in GROUPS:
        title, own, lines = GROUPS[next(iter(kinds))]
        groups.append((title, shown(own(win, project, sheet, ents))))
        if lines is not None:
            groups.append(("Text lines", shown(lines(win, project, sheet, ents))))
    elif kinds == {"text", "mtext"}:
        groups.append(("Text", shown(text_fields(win, project, sheet, ents))))
    return [(t, fs) for t, fs in groups if fs]


# ---- the widgets -----------------------------------------------------------------------------
class _Text(QLineEdit):
    """A text field: committed on Enter or when it loses focus, if typed in."""
    committed = Signal(object)

    def __init__(self, size=False):
        super().__init__()
        self.size = size
        self.varies = False
        self._shown = ""
        self.editingFinished.connect(self._done)

    def set_value(self, value, varies, blank):
        if self.hasFocus() and self.isModified():
            return                      # (being typed in: left alone)
        self.blockSignals(True)
        if varies or value is None:
            text = ""
        elif self.size:
            text = "%g" % value
        else:
            text = str(value)
        self.setText(text)
        self.setPlaceholderText(VARIES if varies else blank)
        self.setModified(False)
        self.varies = varies
        self._shown = text
        self.blockSignals(False)

    def _done(self):
        # (typed in: a *varies* field left blank sets them all blank)
        if not self.isModified() or (self.text() == self._shown and not self.varies):
            return
        self.setModified(False)
        self.varies = False
        self._shown = self.text()
        if self.size:
            t = self.text().strip().replace('"', "")
            if not t:
                self.committed.emit(None)
                return
            try:
                x = float(t)
            except ValueError:
                self.committed.emit(ValueError("Not a size: type it in inches (0.1), or "
                                               "leave it blank"))
                return
            self.committed.emit(x if x > 0 else None)
            return
        self.committed.emit(self.text())


class _Number(QDoubleSpinBox):
    """A number: committed on Enter or when it loses focus (never at every key)."""
    committed = Signal(object)

    def __init__(self, f):
        super().__init__()
        self.f = f
        self.setKeyboardTracking(False)
        self.setDecimals(f.decimals)
        self.setSingleStep(f.step)
        self.setSuffix(f.suffix)
        self.setRange(f.lo, f.hi)
        self.varies = False
        self._shown = None
        self.editingFinished.connect(self._done)

    def set_value(self, value, varies, _blank):
        if self.hasFocus() and self.lineEdit().isModified():
            return
        self.blockSignals(True)
        self.varies = varies
        if varies:
            self.setRange(self.f.lo - self.f.step, self.f.hi)
            self.setSpecialValueText(VARIES)
            self.setValue(self.minimum())
        else:
            self.setSpecialValueText("")
            self.setRange(self.f.lo, self.f.hi)
            self.setValue(float(value))
        self._shown = self.value()
        self.blockSignals(False)

    def _done(self):
        x = self.value()
        if abs(x - self._shown) < 0.5 * 10 ** -self.decimals():
            return
        if self.varies and x < self.f.lo:
            return
        self._shown = x
        self.committed.emit(x)


class _Check(QCheckBox):
    """A tick: set at once; *varies* shows it half ticked, a click then ticks it."""
    committed = Signal(object)

    def __init__(self, text=""):
        super().__init__(text)
        self.clicked.connect(lambda: self.committed.emit(self.checkState() == Qt.Checked))

    def nextCheckState(self):       # slop-ok: Qt calls it (QAbstractButton's own)
        self.setCheckState(Qt.Unchecked if self.checkState() == Qt.Checked else Qt.Checked)

    def set_value(self, value, varies, _blank):
        self.blockSignals(True)
        self.setTristate(varies)
        self.setCheckState(Qt.PartiallyChecked if varies else
                           Qt.Checked if value else Qt.Unchecked)
        self.blockSignals(False)


def _same(a, b):
    return type(a) is type(b) and a == b


class _Choice(QComboBox):
    """A list: set at once when picked; *varies* its first item. (Its values are kept here,
    not as the items' data: None and True would not come back as they went in.)"""
    committed = Signal(object)

    def __init__(self, f):
        super().__init__()
        self.f = f
        self.datas = []
        self._shown = -1
        self.activated.connect(self._picked)

    def _add(self, text, data):
        self.addItem(text)
        self.datas.append(data)

    def set_value(self, value, varies, _blank):
        self.blockSignals(True)
        self.clear()
        self.datas = []
        if varies:
            self._add(VARIES, NA)
        for text, data in self.f.choices:
            self._add(text, data)
        if not varies and not any(_same(d, value) for d in self.datas):
            self._add(str(value), value)       # (a color of its own, a layer gone...)
        if self.f.key == "color":
            self._add("Other...", OTHER)
        i = 0 if varies else next(j for j, d in enumerate(self.datas) if _same(d, value))
        self.setCurrentIndex(i)
        self._shown = i
        self.blockSignals(False)

    def value(self):
        return self.datas[self.currentIndex()]

    def _picked(self, i):
        data = self.datas[i]
        if data is NA or i == self._shown:
            return
        if data == OTHER:
            from . import no_wheel
            c = no_wheel.get_color(QColor("#ffffff"), self, "Color")
            if not c.isValid():
                self.setCurrentIndex(self._shown)
                return
            data = c.name()
        self._shown = i
        self.committed.emit(data)


class _Info(QLabel):
    def __init__(self):
        super().__init__()
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)

    def set_value(self, value, varies, _blank):
        if varies:
            self.setText(VARIES)
        elif isinstance(value, bool):
            self.setText("Yes" if value else "No")
        elif isinstance(value, float):
            self.setText("%g" % value)
        else:
            self.setText(str(value if value is not None else ""))


def make_widget(f, n):
    if not f.editable(n) or f.kind == "info":
        return _Info()
    if f.kind in ("text", "size"):
        return _Text(size=f.kind == "size")
    if f.kind == "number":
        return _Number(f)
    if f.kind == "check":
        return _Check()
    return _Choice(f)


class PropsPanel(QWidget):
    """What the dock holds: a line saying what is selected, and its fields in groups."""
    applyRequested = Signal(object, object)          # field, value (or a ValueError)

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        self.header = QLabel(HINT)
        self.header.setObjectName("props_header")
        self.header.setWordWrap(True)
        f = self.header.font()
        f.setBold(True)
        self.header.setFont(f)
        lay.addWidget(self.header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        lay.addWidget(self.scroll, 1)
        self.body = None
        self.widgets = {}           # key -> widget
        self.sig = None

    def show_groups(self, header, groups, n):
        """The fields shown (made again only when which fields they are changed; else their
        values put in the widgets there, so a field being used keeps its place)."""
        self.header.setText(header)
        sig = tuple((t, tuple((f.key, f.kind, f.editable(n), f.choices if f.key != "layer"
                               else len(f.choices)) for f, _v, _x in fs)) for t, fs in groups)
        if sig != self.sig:
            self._build(groups, n)
            self.sig = sig
        for _t, fs in groups:
            for f, value, varies in fs:
                w = self.widgets[f.key]
                if isinstance(w, _Choice):
                    w.f = f             # (the layer list as it is now)
                w.set_value(value, varies, f.blank)

    def clear(self, header=HINT):
        self.header.setText(header)
        self._build([], 0)
        self.sig = None

    def _build(self, groups, n):
        body = QWidget()
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        self.widgets = {}
        for title, fs in groups:
            box = QGroupBox(title)
            box.setObjectName("props_group_" + title.lower().replace(" ", "_"))
            form = QFormLayout(box)
            form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            rows = {}
            for f, _value, _varies in fs:
                w = make_widget(f, n)
                w.setObjectName("prop_" + f.key)
                if f.tip:
                    w.setToolTip(f.tip)
                if hasattr(w, "committed"):
                    w.committed.connect(lambda value, f=f: self.applyRequested.emit(f, value))
                self.widgets[f.key] = w
                if f.row is None:
                    form.addRow(f.label, w)
                    continue
                if f.row not in rows:
                    line = QWidget()
                    h = QHBoxLayout(line)
                    h.setContentsMargins(0, 0, 0, 0)
                    rows[f.row] = h
                    form.addRow(f.row, line)
                if isinstance(w, (_Text, _Number)):
                    w.setMinimumWidth(64)
                rows[f.row].addWidget(w, 0 if isinstance(w, _Check) else 1)
            if title == "Text lines":
                head = QLabel("Shown, text size, angle" + (", keep readable" if any(
                    f.key.startswith("label_readable_") for f, _v, _x in fs) else "") +
                    " (hold the mouse over one for more)")
                head.setWordWrap(True)
                form.insertRow(0, head)
            v.addWidget(box)
        v.addStretch(1)
        old = self.scroll.takeWidget()
        self.scroll.setWidget(body)
        if old is not None:
            old.deleteLater()
        self.body = body


def header_for(ents):
    """"Footprint (100-C09)", "3 selected: 2 Symbol, 1 Wire"."""
    if len(ents) == 1:
        e = ents[0]
        name = kind_name(e)
        return "%s (%s)" % (name, e.block_name) if isinstance(e, M.Insert) else name
    by = {}
    for e in ents:
        by[kind_name(e)] = by.get(kind_name(e), 0) + 1
    return "%d selected: %s" % (len(ents), ", ".join(
        "%d %s" % (n, k) for k, n in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))))


class Properties:
    """MainWindow's Properties panel: the dock, following the selection, applying a field."""

    def _build_props(self):
        self.props_panel = PropsPanel()
        self.props_panel.applyRequested.connect(self.props_apply)
        dock = self.props_dock = QDockWidget(NAME, self)
        dock.setObjectName("properties")
        dock.setWidget(self.props_panel)
        dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea |
                             Qt.RightDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.resizeDocks([dock], [340], Qt.Horizontal)
        dock.hide()
        dock.visibilityChanged.connect(self._props_shown)
        dock.visibilityChanged.connect(self._props_checked)
        self._props_ids = []                # (what the panel shows: ids on _props_sheet)
        self._props_sheet = None
        self._props_wait = QTimer(self, singleShot=True, interval=FOLLOW_MS)
        self._props_wait.timeout.connect(self.props_fill)

    def properties(self):
        """Properties (Ctrl+1): the panel opened, or brought to the front, and filled with
        what is selected. It never closes it."""
        dock = self.props_dock
        dock.show()
        dock.raise_()
        self._props_wait.stop()
        self.props_fill()
        self._props_checked()

    def toggle_props(self, _checked=False):
        """The Properties button (View tab's Panels, the View menu): the panel closed when it
        is open and in sight; otherwise opened or raised (a tab behind another panel), as
        Trace's button. Returns whether it is open."""
        dock = self.props_dock
        if not dock.isHidden() and self._props_in_sight():
            dock.hide()
        else:
            self.properties()
        self._props_checked()
        return not dock.isHidden()

    def _props_in_sight(self):
        dock = self.props_dock
        return dock.isVisible() and not self.isMinimized() and \
            not dock.visibleRegion().isEmpty()

    def _props_checked(self, _on=None):
        a = getattr(self, "acts", {}).get("props_panel")
        if a is not None:
            a.setChecked(not self.props_dock.isHidden())

    def _props_shown(self, on):
        if on:
            self._props_wait.start(FOLLOW_MS)
        else:
            self._props_wait.stop()         # (closed: nothing more to fill)

    def props_busy(self):
        return self._props_wait.isActive()

    def _props_follow(self):
        """The selection changed: while the panel is open, filled shortly (a newer change
        starts the wait again), never inside the click; nothing when it is closed."""
        if self.props_dock.isVisible():
            self._props_wait.start(FOLLOW_MS)

    def _props_changed(self, project):
        """The project changed (an edit, Undo, Redo): the panel filled again shortly."""
        v = self.view()
        if v is not None and v.project is project and self.props_dock.isVisible():
            self._props_wait.start(REFRESH_MS)

    def props_fill(self):
        """The panel filled from the view's selection (only it is read)."""
        v = self.view()
        if v is None:
            self._props_ids, self._props_sheet = [], None
            self.props_panel.clear()
            return
        s = v.sheet()
        ents = [s.entities[i] for i in sorted(v.sel) if i in s.entities]
        self._props_ids, self._props_sheet = [e.id for e in ents], s
        if not ents:
            self.props_panel.clear()
            return
        groups = fields_for(self, v.project, s, ents)
        self.props_panel.show_groups(header_for(ents), groups, len(ents))

    def props_apply(self, f, value):
        """A field set in the panel: on every object it shows, one step (a wire's number its
        own step, through the Wire number window's code); a value that can't be taken is said
        on the command line and in the status bar, and the field shows what is there again."""
        v = self.view()
        s = self._props_sheet
        if v is None or s is None or v.sheet() is not s:
            return
        ents = [s.entities[i] for i in self._props_ids if i in s.entities]
        if not ents:
            return
        try:
            if isinstance(value, ValueError):
                raise value
            if f.alone is not None:
                f.alone(ents[0], value)
            else:
                with v.project.edit("Properties: %s" % f.label) as ed:
                    s = s
                    for e in ents:
                        cur = s.entities.get(e.id)
                        if cur is not None:
                            f.put(ed, s, cur, value)
        except ValueError as ex:
            self._say("%s: %s" % (f.label, ex), 8000)
            self.statusBar().showMessage("%s: %s" % (f.label, ex), 8000)
        self.props_fill()
