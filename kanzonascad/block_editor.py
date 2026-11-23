"""Edit block... (AutoCAD's Block Editor): a library block's drawing opened on a sheet of its
own, edited with every normal command, and turned back into the block. No Qt here.

The sheet holds:
  - the block's entities, drawn around the base point, which sits at the middle of the
    paper, marked by a cross on the locked layer BLOCK BASE POINT;
  - each pin as a text on layer BLOCK PINS: its insertion point is the pin, its text the
    pin's name (the editor marks the exact point with a small circle);
  - the tag's place as a text on layer BLOCK TAG (centered on its baseline, as a placed tag);
  - the attributes shown besides the tag (a terminal's number...) as texts on layer
    BLOCK ATTRIBUTES, their text the attribute's name (TERM, ADDR...);
  - a footprint's label spot (Footprint label) as the text LABEL on layer BLOCK TAG,
    automatic (the middle of the drawing) while it stays where it opened;
  - a footprint's DIN rail point (the middle of its rail clip, which lines up with the rail's
    centerline) as the text DIN RAIL on layer BLOCK DIN RAIL: its insertion point is the
    point. Left where it opened on a footprint that had none, it stays automatic (the middle
    of the drawing).

Saving (to_block) reads them back: pins in their old order first (a deleted marker drops its
pin), new ones after; anything else on the sheet becomes the block's drawing. What wasn't
touched comes back exactly as it was (not moved there and back, which could change a digit in
the 16th place), so opening and saving gives the very same block.
"""

import math

from . import geometry as G
from . import model as M

LAYER_BASE = "BLOCK BASE POINT"
LAYER_PINS = "BLOCK PINS"
LAYER_TAG = "BLOCK TAG"
LAYER_ATTRS = "BLOCK ATTRIBUTES"
LAYER_RAIL = "BLOCK DIN RAIL"
MARKER_LAYERS = {LAYER_BASE: "#808080", LAYER_PINS: "#2f9e44", LAYER_TAG: "#00a0ff",
                 LAYER_ATTRS: "#c08000", LAYER_RAIL: "#d0308f"}
RAIL_TEXT = "DIN RAIL"
LABEL_TEXT = "LABEL"
PIN_HEIGHT = 0.06
PAPER = "ANSI A (11 x 8.5)"
ROOM = (4.5, 3.25)              # paper inches each way from the base point the block may use
PLACES = 9                      # a moved point is rounded to this many decimals (float noise)


def _round(v):
    r = round(v, PLACES)
    return 0.0 if r == 0 else r         # (no -0.0)


class Session:
    """What an open block editor knows: the block as last saved (or opened), where its base
    point sits on the sheet, and which entity on the sheet stands for what."""

    def __init__(self, defn, sheet_id, offset, scale):
        self.defn = BlockCopy(defn)
        self.sheet_id = sheet_id
        self.offset = offset            # the base point on the sheet
        self.scale = scale              # the sheet's 1:N (a big footprint): N
        self.base = {}                  # what was put on the sheet: eid -> (its dict there,
                                        # ("ent" | "pin" | "tag" | "attr", index))

    @property
    def name(self):
        return self.defn.name

    @property
    def kind(self):
        return self.defn.kind

    def set_meta(self, defn):
        """Properties... changed the block (name, category...): saving keeps those."""
        d = self.defn.to_dict()
        d.update({k: v for k, v in defn.to_dict().items()
                  if k not in ("entities", "pins", "tag_pos", "tag_height", "attr_texts",
                               "rail_pos")})
        new = M.BlockDef.from_dict(d)
        # (a pin renamed there keeps its place and marker)
        if len(defn.pins) == len(new.pins):
            for p, q in zip(new.pins, defn.pins):
                p["name"] = q["name"]
        self.defn = new


def BlockCopy(defn):
    """An independent copy of a block (its builtin mark kept)."""
    return M.BlockDef.from_dict(defn.to_dict(), builtin=defn.builtin)


def _scale_for(defn):
    """1:N so the block fits around the middle of the paper."""
    ax = ay = 0.0
    pts = []
    bb = defn.extents()
    pts += [(bb[0], bb[1]), (bb[2], bb[3])]
    if defn.tag_pos is not None:
        pts.append(defn.tag_pos)
    pts += [a["pos"] for a in defn.attr_texts]
    for x, y in pts:
        ax, ay = max(ax, abs(x)), max(ay, abs(y))
    return max(1, int(math.ceil(max(ax / ROOM[0], ay / ROOM[1]) - 1e-9)))


def pin_side(pos):
    """A pin name's justification worked out from where the pin is: right of its point for a
    pin left of the base point (clear of the drawing), else left."""
    return "right" if pos[0] < -1e-9 else "left"


def pin_justification(e, pos):
    """{"align", "valign"} of a pin marker that differ from what pin_side works out (kept
    with the pin), else {}."""
    out = {}
    if e.align != pin_side(pos):
        out["align"] = e.align
    if e.valign != "baseline":
        out["valign"] = e.valign
    return out


def open_block(defn):
    """A scratch project with one sheet showing the block, and its Session."""
    p = M.Project()
    n = _scale_for(defn)
    s = M.Sheet(title="Block: %s" % defn.name, size=PAPER, cols=1, rows=1)
    s.own_layout = True
    s.kind = "schematic" if defn.kind == "symbol" else "panel"
    s.scale = 1.0 / n
    s.id = p.new_sheet_id()
    p.sheets.append(s)
    p.settings.update({"size": PAPER, "cols": 1, "rows": 1, "xref_auto": False,
                       "wire_numbers": False})
    w, h = s.paper()
    ox, oy = w / 2, h / 2
    sess = Session(defn, s.id, (ox, oy), n)
    for name, color in MARKER_LAYERS.items():
        p.layers[name] = M.Layer(name, color, locked=(name == LAYER_BASE))

    def put(ent, what):
        ent.id = None
        s._put(ent)
        sess.base[ent.id] = (ent.to_dict(), what)

    def at(q):
        return (q[0] + ox, q[1] + oy)
    for i, e in enumerate(defn.entities):
        p.ensure_layer(e.layer)
        put(e.moved(ox, oy), ("ent", i))
    # the base point: a cross and a ring, locked (not part of the block)
    r = 0.08 * n
    for a, b in (((ox - r, oy), (ox + r, oy)), ((ox, oy - r), (ox, oy + r))):
        s._put(M.Line(a, b, layer=LAYER_BASE))
    s._put(M.Circle((ox, oy), r / 3, layer=LAYER_BASE))
    for i, pin in enumerate(defn.pins):
        # (a pin left of the base point: its name to the left of it, clear of the drawing)
        t = M.Text(at(pin["pos"]), pin["name"], PIN_HEIGHT * n,
                   align=pin.get("align") or pin_side(pin["pos"]),
                   valign=pin.get("valign", "baseline"), layer=LAYER_PINS)
        put(t, ("pin", i))
        if pin.get("layer"):
            s.pin_layers[t.id] = pin["layer"]       # (its own wire layer: Pins...)
    if defn.kind == "symbol" and defn.tag_pos is not None:
        put(M.Text(at(defn.tag_pos), (defn.prefix + "?") if defn.prefix else "TAG",
                   defn.tag_height, 0.0, "center", layer=LAYER_TAG), ("tag", 0))
    elif defn.kind == "footprint":
        # where its label goes (Footprint label): left alone, the middle of the drawing
        put(M.Text(at(defn.label_point()), LABEL_TEXT, PIN_HEIGHT * n, 0.0, "center", "middle",
                   layer=LAYER_TAG), ("tag", 0))
    for i, a in enumerate(defn.attr_texts):
        # (shown as it is set: its alignment and angle, so changing them sticks; the owner,
        # 0.18.5, a rating set to middle center went back to baseline)
        put(M.Text(at(a["pos"]), a["attr"], a["height"], float(a.get("angle", 0.0) or 0.0),
                   a.get("align", "center"), a.get("valign", "baseline"), layer=LAYER_ATTRS),
            ("attr", i))
    if defn.kind == "footprint":
        put(M.Text(at(defn.rail_point()), RAIL_TEXT, PIN_HEIGHT * n, 0.0, "left", "middle",
                   layer=LAYER_RAIL), ("rail", 0))
    p.undo_stack, p.redo_stack = [], []
    p.saved_at = 0
    s.touched = set()
    return p, sess


class Result:
    """What to_block read: the block, how the old pins' names map to the new ones (None: the
    pin is gone), warnings for the command line, and the sheet's new baseline."""

    def __init__(self, defn, pin_map, warnings, base):
        self.defn, self.pin_map, self.warnings, self.base = defn, pin_map, warnings, base


def to_block(project, sess):
    """The block the editor's sheet now shows (metadata as the session's block)."""
    s = project.sheet_by_id(sess.sheet_id)
    if s is None:
        raise ValueError("the block's sheet is gone")
    old = sess.defn
    ox, oy = sess.offset

    def back(q):
        return (_round(q[0] - ox), _round(q[1] - oy))
    ents, pins, attrs, tags, rails = [], [], [], [], []
    warnings = []
    measured = 0
    for eid, e in s.entities.items():
        if e.layer == LAYER_BASE:
            continue
        if isinstance(e, M.Dimension) and eid not in sess.base:
            # (a dimension drawn in the block's tab measures it: shown there, not made part
            # of the block, so its copies don't carry it; the owner, 0.22.2: "I need linear
            # measurement inside of the block edit tab as well". One the block had is kept)
            measured += 1
            continue
        got = sess.base.get(eid)
        same = got is not None and got[0] == e.to_dict()
        what = got[1] if got is not None else None
        # (a marker only renamed or resized keeps its point exactly)
        stays = got is not None and isinstance(e, M.Text) and got[0].get("pos") == list(e.pos)
        marker = isinstance(e, M.Text) and e.layer in (LAYER_PINS, LAYER_TAG, LAYER_ATTRS,
                                                       LAYER_RAIL)
        if marker and e.layer == LAYER_RAIL:
            if old.kind != "footprint":
                continue
            # left where it opened: as it was (automatic stays automatic)
            if what and what[0] == "rail" and stays:
                rails.append((0, eid, old.rail_pos))
            else:
                rails.append((1, eid, back(e.pos)))
        elif marker and e.layer == LAYER_PINS:
            name = e.text.strip()
            if not name:
                warnings.append("a pin marker with no name was left out")
                continue
            i = what[1] if what and what[0] == "pin" else None
            pos = old.pins[i]["pos"] if stays and i is not None else back(e.pos)
            pins.append((0 if i is not None else 1, i if i is not None else eid, eid,
                         {"name": name, "pos": pos} |
                         ({"layer": s.pin_layers[eid]} if s.pin_layers.get(eid) else {}) |
                         pin_justification(e, pos), i))
        elif marker and e.layer == LAYER_TAG and old.kind == "footprint":
            # a footprint's label spot: left where it opened, as it was (automatic stays so)
            if what and what[0] == "tag" and stays:
                tags.append((0, eid, old.tag_pos, old.tag_height))
            else:
                tags.append((1, eid, back(e.pos), old.tag_height))
        elif marker and e.layer == LAYER_TAG:
            if what and what[0] == "tag":
                tags.append((0, eid, old.tag_pos if stays else back(e.pos),
                             old.tag_height if same else e.height))
            else:
                tags.append((1, eid, back(e.pos), e.height))
        elif marker and e.layer == LAYER_ATTRS:
            i = what[1] if what and what[0] == "attr" else None
            if same and i is not None:
                a = dict(old.attr_texts[i])
            else:
                a = dict(old.attr_texts[i]) if stays and i is not None else \
                    {"pos": back(e.pos)}
                a.update(attr=e.text.strip().upper(), height=e.height)
                # (its alignment and angle as set on the marker: center and baseline left
                # out, as the block keeps them)
                a.pop("align", None)
                a.pop("valign", None)
                a.pop("angle", None)
                if e.align in ("left", "right"):
                    a["align"] = e.align
                if e.valign in ("bottom", "middle", "top"):
                    a["valign"] = e.valign
                if e.angle % 360.0:
                    a["angle"] = e.angle % 360.0
            if not a["attr"]:
                warnings.append("an attribute marker with no name was left out")
                continue
            attrs.append((0 if i is not None else 1, i if i is not None else eid, eid, a))
        else:
            i = what[1] if what and what[0] == "ent" else None
            if same and i is not None:
                ents.append((0, i, eid, [old.entities[i]]))
                continue
            parts = e.exploded() if isinstance(e, M.Insert) else [e]
            out = []
            for q in parts:
                c = q._map(back, rot=0.0)
                c.id = None
                c.layer, c.color = "0", None
                out.append(c)
            ents.append((0 if i is not None else 1, i if i is not None else eid, eid, out))
    ents.sort(key=lambda t: (t[0], t[1]))
    pins.sort(key=lambda t: (t[0], t[1]))
    if s.pin_order:
        # (the order set in Pins..., undone with it: markers it doesn't list after, as they
        # were)
        rank = {eid: i for i, eid in enumerate(s.pin_order)}
        pins.sort(key=lambda t: (rank.get(t[2], len(rank)),))
    attrs.sort(key=lambda t: (t[0], t[1]))
    _join_stack(attrs)
    tags.sort(key=lambda t: (t[0], t[1]))
    rails.sort(key=lambda t: (t[0], t[1]))
    if measured:
        warnings.append("%d dimension(s) drawn here left out of the block (measurements)"
                        % measured)
    if len(tags) > 1:
        warnings.append("%d %s markers: the first one was used"
                        % (len(tags), "label" if old.kind == "footprint" else "tag"))
    if len(rails) > 1:
        warnings.append("%d DIN rail markers: the first one was used" % len(rails))
    names = [p[3]["name"] for p in pins]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        warnings.append("pins with the same name: %s" % ", ".join(dup))
    d = old.to_dict()
    d["entities"] = []
    defn = M.BlockDef.from_dict(d)
    base = {}
    for _o, _k, eid, out in ents:
        for c in out:
            defn.entities.append(c)
        if len(out) == 1:
            base[eid] = (s.entities[eid].to_dict(), ("ent", len(defn.entities) - 1))
    defn.pins = [dict(p[3], pos=M._pt(p[3]["pos"])) for p in pins]
    pin_map = {q["name"]: None for q in old.pins}
    for k, p in enumerate(pins):
        if p[4] is not None:
            pin_map[old.pins[p[4]]["name"]] = p[3]["name"]
        base[p[2]] = (s.entities[p[2]].to_dict(), ("pin", k))
    if tags:
        defn.tag_pos = M._pt(tags[0][2]) if tags[0][2] is not None else None
        defn.tag_height = float(tags[0][3])
        base[tags[0][1]] = (s.entities[tags[0][1]].to_dict(), ("tag", 0))
    else:
        defn.tag_pos = None
    defn.rail_pos = M._pt(rails[0][2]) if rails and rails[0][2] is not None else None
    if rails:
        base[rails[0][1]] = (s.entities[rails[0][1]].to_dict(), ("rail", 0))
    defn.attr_texts = []
    for k, a in enumerate(attrs):
        # (its alignment, angle and place in a stack of ratings kept: 0.17.5)
        defn.attr_texts.append(dict(a[3], pos=M._pt(a[3]["pos"]),
                                    height=float(a[3]["height"])))
        base[a[2]] = (s.entities[a[2]].to_dict(), ("attr", k))
    defn.builtin = False
    return Result(defn, pin_map, warnings, base)


def _join_stack(attrs):
    """A new attribute put right under the block's stack of ratings (in its column, as
    Add attribute's Stack puts it, or a rating's marker copied down) joins the stack: it closes
    up with them when one above it is empty. attrs: to_block's [(new, key, eid, attribute)]."""
    stack = [t[3] for t in attrs if t[3].get("stack")]
    if not stack:
        return
    for t in attrs:
        a = t[3]
        if t[0] != 1 or a.get("stack"):
            continue
        low = stack[-1]
        same_col = abs(a["pos"][0] - low["pos"][0]) < 1e-6 and \
            a.get("align", "center") == low.get("align", "center")
        if same_col and a["pos"][1] < low["pos"][1] - 1e-6:
            a["stack"] = True
            stack.append(a)


def pin_markers(project, sess):
    """[(marker text, its pin's place in the block: x, y from the base point)] of the pins on
    the editor's sheet, in the order Save block would give them."""
    res = to_block(project, sess)
    s = project.sheet_by_id(sess.sheet_id)
    by_id = {}
    for eid, (_d, what) in res.base.items():
        if what[0] == "pin":
            by_id[what[1]] = eid
    return [(s.entities[by_id[k]], res.defn.pins[k]["pos"]) for k in range(len(res.defn.pins))
            if k in by_id]


def pin_marker(sess, point, name):
    """A new pin's marker (a text on BLOCK PINS) at point on the editor's sheet."""
    left = point[0] < sess.offset[0] - 1e-9
    return M.Text(point, name, PIN_HEIGHT * sess.scale, align="right" if left else "left",
                  layer=LAYER_PINS)


ATTR_HEIGHT = 0.08              # a new attribute's text (as the ratings: paper inches)


def attr_names(project, sess):
    """The names on the editor's attribute markers (BLOCK ATTRIBUTES)."""
    s = project.sheet_by_id(sess.sheet_id)
    return [e.text.strip().upper() for e in s.entities.values()
            if isinstance(e, M.Text) and e.layer == LAYER_ATTRS]


def attr_problem(project, sess, name):
    """Why name can't be a new attribute of the block open in the editor, or None."""
    if not name:
        return "Type the attribute's name (HP, VOLTS, KW...)"
    if any(ch.isspace() for ch in name):
        return "An attribute's name has no spaces (AutoCAD's don't): FLA, not FULL LOAD"
    if name == "TAG":
        return "The tag has its own marker (the blue text on BLOCK TAG)"
    if name in attr_names(project, sess):
        return "There's already an attribute %s: type another name" % name
    return None


def stack_end(project, sess):
    """Where the next rating goes under the block's stack of ratings (RATING, HP, VOLTS...: the
    ones that close up when one is empty), on the editor's sheet, and that stack's alignment;
    or None when the block has no stack."""
    res = to_block(project, sess)
    stack = [a for a in res.defn.attr_texts if a.get("stack")]
    if not stack:
        return None
    from .symbols_jic import RATING_STEP
    last = stack[-1]
    step = (stack[-2]["pos"][1] - last["pos"][1]) if len(stack) > 1 else RATING_STEP
    ox, oy = sess.offset
    return ((last["pos"][0] + ox, last["pos"][1] - step + oy), last.get("align", "center"),
            last["height"])


def attr_marker(sess, point, name, align="center", height=ATTR_HEIGHT):
    """A new attribute's marker (a text on BLOCK ATTRIBUTES, its text the attribute's name) at
    point on the editor's sheet."""
    return M.Text(point, name, height, 0.0, align, layer=LAYER_ATTRS)


def next_pin_name(names):
    """The name a new pin is offered: one more than the highest number among them (13, 14:
    15), else the next letter-number (A1, A2: A3), else how many there are, plus one."""
    import re
    best = None
    for n in names:
        m = re.fullmatch(r"([A-Za-z]*)(\d+)", n.strip())
        if m and (best is None or int(m.group(2)) > best[1]):
            best = (m.group(1), int(m.group(2)))
    if best is not None:
        return "%s%d" % (best[0], best[1] + 1)
    return str(len(names) + 1)


def pin_names(project, sess):
    """The names on the editor's pin markers."""
    s = project.sheet_by_id(sess.sheet_id)
    return [e.text.strip() for e in s.entities.values()
            if isinstance(e, M.Text) and e.layer == LAYER_PINS]


def apply_pins(project, sess, rows):
    """Pins... done: rows [(marker id, name, x, y[, wire layer])] in the order the pins take, x
    and y from the base point, the wire layer "" for none of its own (autolayer.py: worked out
    from the block). Markers left out are erased; the others renamed and moved; the order and
    the wire layers kept with the sheet (one step, undone as one). Returns what's wrong with
    the rows, or None."""
    s = project.sheet_by_id(sess.sheet_id)
    names = [str(r[1]).strip() for r in rows]
    if any(not n for n in names):
        return "Every pin needs a name"
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        return "Two pins can't have the same name (%s)" % ", ".join(dup)
    keep = [r[0] for r in rows]
    ox, oy = sess.offset
    with project.edit("Pins") as ed:
        for e in list(s.entities.values()):
            if isinstance(e, M.Text) and e.layer == LAYER_PINS and e.id not in keep:
                ed.remove(s, e.id)
        for (eid, _n, x, y, *_lay), name in zip(rows, names):
            cur = s.entities[eid]
            at = (_round(ox + float(x)), _round(oy + float(y)))
            if cur.text != name or G.dist(cur.pos, at) > 1e-9:
                # (a name justified by hand keeps it; one worked out from its side follows)
                was = (cur.pos[0] - ox, cur.pos[1] - oy)
                align = cur.align if cur.align != pin_side(was) else pin_side((float(x), 0.0))
                ed.change(s, cur.copy(text=name, pos=at, align=align))
        if list(s.pin_order) != keep:
            ed.sheet_meta(s, pin_order=keep)
        # (rows without a fifth column leave the pins' wire layers as they were)
        lays = {r[0]: str(r[4]).strip() for r in rows if len(r) > 4 and str(r[4]).strip()}
        if any(len(r) > 4 for r in rows) and lays != s.pin_layers:
            ed.sheet_meta(s, pin_layers={str(k): v for k, v in lays.items()})
    return None


def pin_layers(project, sess):
    """{pin marker id: its own wire layer} on the editor's sheet."""
    return dict(project.sheet_by_id(sess.sheet_id).pin_layers)


def saved(sess, result):
    """The block was saved: what the sheet shows now is the new starting point."""
    sess.defn = BlockCopy(result.defn)
    sess.base = dict(result.base)


# ---- placed copies ---------------------------------------------------------------------------
def copies(project, name):
    """[(sheet, insert)] of every copy of a block in a project."""
    out = []
    for s in project.sheets + [project.title_block]:
        for e in s.inserts():
            if e.block == name:
                out.append((s, e))
    return out


def update_copies(ed, project, defn, old_name=None, pin_map=None):
    """Give a project's copies of a block (named old_name, else defn.name) the new block, in
    the edit ed: the definition replaced, renamed copies renamed, and the wires on their pins
    taken along (pins matched by name, through pin_map {old name: new name or None}).
    Their tags, descriptions and other attributes stay. Returns (copies updated, wires left
    where they were because their pin is gone)."""
    from .wires import TOL
    old_name = old_name or defn.name
    found = copies(project, old_name)
    before = [(s, e.id, e.pin_points()) for s, e in found]
    ed.block(defn)
    if old_name != defn.name:
        n = len(ed.pin_moves)
        new_defn = project.blocks[defn.name]
        for s, e in found:
            c = s.entities[e.id].copy(block=defn.name)
            c.defn = new_defn
            ed.change(s, c)
        del ed.pin_moves[n:]                # (added below, with the pins' new names)
        ed.drop_block(old_name)
    stranded = 0
    for s, eid, old_pts in before:
        cur = s.entities.get(eid)
        if cur is None:
            continue
        new = M.pin_keys(cur.pin_points())
        old, seen = {}, {}
        for name, p in old_pts:
            to = pin_map.get(name, name) if pin_map is not None else name
            # (two pins of one name: the first to the first of its new name, and so on)
            k = seen.get(to, 0)
            seen[to] = k + 1
            if to is not None and (to, k) in new:
                old[(to, k)] = p
                continue
            # its pin is gone: a wire ending there stays where it is
            if any(G.dist(p, q) <= TOL for q in new.values()):
                continue
            for w in s.query_point(p, TOL):
                if isinstance(w, M.Wire) and (G.dist(w.points[0], p) <= TOL
                                              or G.dist(w.points[-1], p) <= TOL):
                    stranded += 1
        ed.pin_moves.append((s, old, new))
    return len(found), stranded
