"""Wire layers: the owner's preset of them and their wires' colors (the owner, 0.18.2: "I'll
need a lot of different ones...480, 120, 24vdc, Ethernet and others"; asked: 480 V in black,
red, orange, brown and yellow with a white neutral and a green ground, 12 AWG; 120 V red and
black with a white neutral, 14 AWG; 24 VDC blue, its common blue with white stripes, 16 AWG;
Ethernet green, a cable with no size).

A wire's size is its layer's (AWG in Layers) unless the wire has one of its own (Wire size).
A wire color of two names ("BLU/WHT") is drawn striped: the layer's color with the second
name's color in stripes along it.

No Qt here (the model's side)."""

from .model import Layer, gauge_text

# the insulation colors the Layers window offers, as drawn (the first of two names is the
# layer's color; the second, the stripes)
COLORS = {"BLK": "#000000", "WHT": "#ffffff", "RED": "#ff3030", "BLU": "#3070ff",
          "GRN": "#00b050", "YEL": "#ffd700", "BRN": "#a0522d", "ORG": "#ff8c00",
          "GRY": "#909090", "VIO": "#9040ff", "PNK": "#ff80c0"}

# (layer, its color on the drawing, gauge, wire color): "7" is black on paper, white on the
# dark drawing
PRESET = [
    ("480 V", [("480V BLK", "7", "12", "BLK"),
               ("480V RED", "#ff3030", "12", "RED"),
               ("480V ORG", "#ff8c00", "12", "ORG"),
               ("480V BRN", "#a0522d", "12", "BRN"),
               ("480V YEL", "#ffd700", "12", "YEL"),
               ("480V WHT", "#e0e0e0", "12", "WHT"),        # (neutral)
               ("480V GRN", "#00b050", "12", "GRN")]),      # (ground)
    ("120 V", [("120V RED", "#ff3030", "14", "RED"),
               ("120V BLK", "7", "14", "BLK"),
               ("120V WHT", "#e0e0e0", "14", "WHT")]),      # (neutral)
    ("24 VDC", [("24VDC BLU", "#3070ff", "16", "BLU"),
                ("24VDC BLU-WHT", "#3070ff", "16", "BLU/WHT")]),   # (common: striped)
    ("Ethernet", [("ETHERNET", "#00b050", "", "")]),        # (a cable: no size)
]
PRESET_NAMES = frozenset(name for _g, lays in PRESET for name, _c, _a, _w in lays)


def preset_groups():
    """The preset's groups' names, in order."""
    return [g for g, _lays in PRESET]


def add_preset(ed, project, groups=None):
    """The preset's layers of these groups (all when None) added to the project; a layer it
    already has is left as it is (its color, size and wire color may be the user's own).
    Returns the names added."""
    added = []
    for g, lays in PRESET:
        if groups is not None and g not in groups:
            continue
        for name, color, awg, wire_color in lays:
            if name in project.layers:
                continue
            ed.layer(name, None, Layer(name, color, awg=awg, wire_color=wire_color).to_dict())
            added.append(name)
    return added


def is_preset(name):
    return name in PRESET_NAMES


def is_wire_layer(project, name):
    """Is this layer one wires go on: WIRES, one named WIRE..., one with a gauge or wire color
    (Layers), one of the preset (Add wire layers), or one made a wire layer (Project
    properties: Wire layers, New)? The Schematic tab's layer box lists these."""
    lay = project.layers.get(name)
    if lay is None:
        return False
    return name.upper().startswith("WIRE") or bool(lay.awg or lay.wire_color or lay.wire) \
        or is_preset(name)


def wire_layers(project):
    """The project's wire layers' names, in the layers' order."""
    return [n for n in project.layers if is_wire_layer(project, n)]


def project_wire_layer(project):
    """The layer new wires go on on a sheet with none of its own (Project properties)."""
    name = project.settings.get("wire_layer") or "WIRES"
    return name if is_wire_layer(project, name) else "WIRES"


def sheet_wire_layer(project, sheet):
    """The layer new wires go on on this sheet: its own (Sheet properties, or picked on the
    Schematic tab) while it is still a wire layer, else the project's."""
    own = getattr(sheet, "wire_layer", None) if sheet is not None else None
    if own and is_wire_layer(project, own):
        return own
    return project_wire_layer(project)


def stripe(wire_color):
    """The stripes' color of a two-color wire ("BLU/WHT": white), or None."""
    parts = [p.strip().upper() for p in str(wire_color or "").split("/")]
    if len(parts) != 2 or not parts[0] or parts[1] not in COLORS:
        return None
    return COLORS[parts[1]]


def wire_label(lay, awg=""):
    """What a wire on layer lay shows beside it: its own gauge (awg) in place of the layer's
    when it has one ("10 AWG BLK", "250 kcmil BLK")."""
    g = str(awg or "").strip() or (lay.awg if lay is not None else "")
    color = lay.wire_color if lay is not None else ""
    return " ".join(([gauge_text(g)] if g else []) + ([color] if color else []))
