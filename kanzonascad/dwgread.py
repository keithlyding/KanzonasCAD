"""DWG files read object by object (ezdwg's decoders, MIT) into an ezdxf document, which
fileio's DXF reader then reads like any DXF.

ezdwg's own DWG-to-DXF conversion explodes every block reference and then drops or moves
what looks "implausible" to it: on real drawings (a panel layout of terminal and I/O blocks,
a scaled A0 border) blocks lost their scale, attributes went missing and pieces landed in the
wrong place. Here nothing is guessed: each object keeps the block or layout it belongs to,
blocks keep their base points, block references their scale and rotation, attributes their
text, a dimension its own drawing (its anonymous block). No Qt here; ezdwg and ezdxf are
imported only when a DWG is read."""

ANON_PREFIX = "KZ_ANON_"        # ("*D1" and other anonymous block names, made plain names)


def _block_name(name):
    name = str(name or "")
    return ANON_PREFIX + name[1:] if name.startswith("*") else name


def _attribs(dxf, layers):
    """The common properties of an object: its layer and its color (ByLayer when none)."""
    out = {"layer": layers.get(dxf.get("layer_handle"), "0")}
    c = dxf.get("color_index")
    if isinstance(c, int) and 0 <= c <= 255:
        out["color"] = c
    tc = dxf.get("true_color")
    if isinstance(tc, int) and tc > 0:
        out["true_color"] = tc
    ext = dxf.get("extrusion")
    if ext and (abs(ext[0]) > 1e-12 or abs(ext[1]) > 1e-12 or ext[2] < 0):
        out["extrusion"] = tuple(ext)
    return out


def _xy(p):
    return (float(p[0]), float(p[1]))


def _add(layout, t, dxf, kw, names, skipped):
    """One object into an ezdxf layout (model space, paper space or a block). False when it
    can't be (counted in skipped)."""
    if t == "LINE":
        layout.add_line(dxf["start"], dxf["end"], dxfattribs=kw)
    elif t == "ARC":
        layout.add_arc(dxf["center"], dxf["radius"], dxf["start_angle"], dxf["end_angle"],
                       dxfattribs=kw)
    elif t == "CIRCLE":
        layout.add_circle(dxf["center"], dxf["radius"], dxfattribs=kw)
    elif t == "ELLIPSE":
        layout.add_ellipse(dxf["center"], dxf["major_axis"], dxf["axis_ratio"],
                           dxf.get("start_angle", 0.0), dxf.get("end_angle", 6.283185307179586),
                           dxfattribs=kw)
    elif t in ("LWPOLYLINE", "POLYLINE_2D", "POLYLINE_3D"):
        pts = dxf.get("points") or []
        if dxf.get("is_3d_polyline") or t == "POLYLINE_3D":
            layout.add_polyline3d([tuple(p) for p in pts], dxfattribs=kw)
            return True
        if dxf.get("is_3d_mesh") or dxf.get("is_polyface_mesh"):
            skipped[t] = skipped.get(t, 0) + 1
            return False
        if dxf.get("should_interpolate") and dxf.get("interpolated_points"):
            pts, bulges = dxf["interpolated_points"], [0.0] * len(dxf["interpolated_points"])
        else:
            bulges = list(dxf.get("bulges") or [0.0] * len(pts))
        widths = dxf.get("widths") or [(0.0, 0.0)] * len(pts)
        rows = []
        for i, p in enumerate(pts):
            w = widths[i] if i < len(widths) else (0.0, 0.0)
            rows.append((p[0], p[1], w[0], w[1], bulges[i] if i < len(bulges) else 0.0))
        if len(rows) < 2:
            return False
        kw = dict(kw)
        if dxf.get("elevation"):
            kw["elevation"] = dxf["elevation"]
        layout.add_lwpolyline(rows, format="xyseb", close=bool(dxf.get("closed")),
                              dxfattribs=kw)
    elif t == "SPLINE":
        cps = [tuple(p) for p in dxf.get("control_points") or []]
        fit = [tuple(p) for p in dxf.get("fit_points") or []]
        sp = layout.add_spline(dxfattribs=kw)
        sp.dxf.degree = int(dxf.get("degree") or 3)
        if cps:
            sp.control_points = cps
            knots = dxf.get("knots") or []
            if len(knots) == len(cps) + sp.dxf.degree + 1:
                sp.knots = list(knots)
            else:
                from ezdxf.math import open_uniform_knot_vector
                sp.knots = list(open_uniform_knot_vector(len(cps), sp.dxf.degree + 1))
            w = dxf.get("weights") or []
            if dxf.get("rational") and len(w) == len(cps):
                sp.weights = list(w)
        elif len(fit) >= 2:
            sp.fit_points = fit
        else:
            layout.delete_entity(sp)
            return False
        if dxf.get("closed"):
            sp.closed = True
    elif t in ("TEXT", "ATTRIB"):
        if t == "ATTRIB" and (int(dxf.get("attribute_flags") or 0) & 1 or dxf.get("invisible")):
            return True                                   # (an invisible attribute)
        kw = dict(kw, insert=dxf["insert"], height=dxf.get("height") or 0.125,
                  rotation=dxf.get("rotation") or 0.0, width=dxf.get("width") or 1.0,
                  oblique=dxf.get("oblique") or 0.0, halign=int(dxf.get("halign") or 0),
                  valign=int(dxf.get("valign") or 0))
        if dxf.get("align_point") is not None:
            kw["align_point"] = dxf["align_point"]
        layout.add_text(str(dxf.get("text") or ""), dxfattribs=kw)
    elif t == "MTEXT":
        kw = dict(kw, insert=dxf["insert"], char_height=dxf.get("char_height") or 0.125,
                  attachment_point=int(dxf.get("attachment_point") or 1),
                  text_direction=dxf.get("text_direction") or (1.0, 0.0, 0.0))
        if dxf.get("rect_width"):
            kw["width"] = dxf["rect_width"]
        layout.add_mtext(str(dxf.get("raw_text") or dxf.get("text") or ""), dxfattribs=kw)
    elif t in ("SOLID", "TRACE", "3DFACE"):
        pts = [tuple(p) for p in dxf.get("points") or []]
        if len(pts) < 3:
            return False
        if t == "3DFACE":
            layout.add_3dface(pts[:4], dxfattribs=kw)
        elif t == "TRACE":
            layout.add_trace(pts[:4], dxfattribs=kw)
        else:
            layout.add_solid(pts[:4], dxfattribs=kw)
    elif t == "HATCH":
        h = layout.add_hatch(dxfattribs=kw)
        n = 0
        for path in dxf.get("paths") or []:
            pts = [_xy(p) for p in path.get("points") or []]
            if len(pts) >= 2:
                h.paths.add_polyline_path(pts, is_closed=bool(path.get("closed", True)))
                n += 1
        if not n:
            layout.delete_entity(h)
            return False
    elif t in ("INSERT", "DIMENSION"):
        if t == "INSERT":
            name, ins = dxf.get("name"), dxf.get("insert", (0, 0, 0))
            xs, ys, zs = dxf.get("xscale", 1.0), dxf.get("yscale", 1.0), dxf.get("zscale", 1.0)
            rot = dxf.get("rotation", 0.0)
        else:
            # a dimension is drawn by its own anonymous block (lines, arrows, its value)
            name, ins = dxf.get("anonymous_block_name"), dxf.get("insert", (0, 0, 0))
            xs, ys, zs = tuple(dxf.get("insert_scale") or (1.0, 1.0, 1.0))
            rot = dxf.get("insert_rotation", 0.0)
        name = names.get(_block_name(name))
        if name is None:
            return False
        return layout.add_blockref(name, ins, dxfattribs=dict(
            kw, xscale=xs or 1.0, yscale=ys or 1.0, zscale=zs or 1.0, rotation=rot or 0.0))
    elif t == "LEADER":
        pts = [tuple(p) for p in dxf.get("points") or dxf.get("vertices") or []]
        if len(pts) < 2:
            return False
        layout.add_lwpolyline([_xy(p) for p in pts], dxfattribs=kw)
    elif t == "MLINE":
        pts = [tuple(p) for p in dxf.get("points") or []]
        if len(pts) < 2:
            return False
        layout.add_mline(pts, close=bool(dxf.get("closed")), dxfattribs=dict(
            kw, scale_factor=float(dxf.get("scale") or 1.0),
            justification=int(dxf.get("justification") or 0)))
    elif t == "ATTDEF":
        # a block's field: kept for the block (its copies show their own values there)
        kw = dict(kw, height=dxf.get("height") or 0.125, rotation=dxf.get("rotation") or 0.0,
                  halign=int(dxf.get("halign") or 0), valign=int(dxf.get("valign") or 0),
                  flags=int(dxf.get("attribute_flags") or 0))
        if dxf.get("align_point") is not None:
            kw["align_point"] = dxf["align_point"]
        layout.add_attdef(str(dxf.get("tag") or ""), dxf["insert"], str(dxf.get("text") or ""),
                          dxfattribs=kw)
    else:
        return False
    return True


def block_records(write_blocks, header_names):
    """{block record handle: (name, base point)} from ezdwg's block rows and header names.
    Anonymous blocks come in the rows as "*D", "*U"...: their full name ("*D12") is in the
    header names (without it every dimension shared one, empty, block)."""
    full = {}
    for h, name in header_names:
        full.setdefault(h, str(name))
    records = {}
    for b in write_blocks:
        name = str(b["name"])
        f = full.get(b["handle"], "")
        if name.startswith("*") and len(f) > len(name) and f.startswith(name):
            name = f
        records[b["handle"]] = (name, tuple(b.get("base_point") or (0, 0, 0)))
    for h, name in full.items():
        records.setdefault(h, (name, (0.0, 0.0, 0.0)))
    return records


def read(path):
    """The DWG at path as an ezdxf document, and what was left out {type: count}."""
    import ezdwg
    import ezdxf
    raw = ezdwg.raw
    src = ezdwg.read(path)
    doc = ezdxf.new("R2018")
    units = int(src.header_variables().get("insunits") or 0)
    doc.header["$INSUNITS"] = units
    layers = {}
    colors = {h: c for h, c, *_ in raw.decode_layer_colors(path)}
    for h, name in raw.decode_layer_names(path):
        name = str(name) or "0"
        layers[h] = name
        if name not in doc.layers:
            lay = doc.layers.add(name)
            c = colors.get(h)
            if isinstance(c, int) and 1 <= abs(c) <= 255:
                lay.color = abs(c)
    # the block definitions: their record's handle -> (name, base point)
    records = block_records(raw.decode_write_blocks(path),
                            raw.decode_block_header_names(path))
    names, layouts = {}, {}
    msp, psp = doc.modelspace(), doc.paperspace()
    for h, (name, base) in records.items():
        # (model and paper space: their objects can name them as their owner too)
        if name.lower().startswith("*model_space"):
            layouts[h] = msp
            continue
        if name.lower().startswith("*paper_space"):
            layouts[h] = psp
            continue
        plain = _block_name(name)
        if plain not in names:
            blk = doc.blocks.new(plain, base_point=base)
            names[plain] = plain
            layouts[h] = blk
        else:
            layouts[h] = doc.blocks.get(plain)
    ents = list(src.entities().query())
    # where each object goes: model space, paper space or a block (an attribute: where
    # its block reference is)
    where = {}
    for e in ents:
        pl = src.entity_placement(e.handle)
        mode, owner = (pl if pl else (None, e.dxf.get("owner_handle")))
        if mode == 2:
            where[e.handle] = msp
        elif mode == 1:
            where[e.handle] = psp
        elif owner in layouts:
            where[e.handle] = layouts[owner]
        elif owner in records:
            where[e.handle] = None                      # (model or paper space's own record)
    skipped = {}
    attribs = []
    refs = {}                           # an INSERT's handle -> its ezdxf block reference
    for e in ents:
        t = e.dxftype
        if t == "ATTRIB":
            attribs.append(e)
            continue
        target = where.get(e.handle)
        if target is None:
            mode = (src.entity_placement(e.handle) or (None, None))[0]
            if mode is None:
                skipped[t] = skipped.get(t, 0) + 1
            continue
        try:
            ok = _add(target, t, e.dxf, _attribs(e.dxf, layers), names, skipped)
        except (KeyError, TypeError, ValueError, IndexError, ezdxf.DXFError) as ex:
            ok = False
            skipped[t + " (unreadable)"] = skipped.get(t + " (unreadable)", 0) + 1
            del ex
            continue
        if not ok:
            skipped[t] = skipped.get(t, 0) + 1
        elif t == "INSERT" and ok is not True:
            refs[e.handle] = ok
    # a dimension ezdwg doesn't list (its own writer's, for one) still has its drawing, in
    # place, in its anonymous "*D" block: drawn where it stands when nothing refers to it
    # (AutoCAD drops unreferenced ones when it saves, so none is drawn twice)
    used = set()
    for lay in [msp, psp] + [b for b in doc.blocks]:
        for x in lay:
            if x.dxftype() == "INSERT":
                used.add(x.dxf.name)
    for h, (name, _base) in records.items():
        plain = _block_name(name)
        if name.startswith("*D") and plain in names and plain not in used and \
                len(doc.blocks.get(plain)):
            msp.add_blockref(plain, (0.0, 0.0, 0.0))
            used.add(plain)
    # attributes: drawn where their block reference is (their points are already there)
    # (attached to their block reference, as in the DWG, so the block keeps its values: a
    # tag, a catalog number; one whose reference isn't known: a text where it stands)
    for e in attribs:
        owner = e.dxf.get("owner_handle")
        ref = refs.get(owner) if e.dxf.get("owner_type") == "INSERT" else None
        try:
            if ref is not None:
                d = e.dxf
                kw = dict(_attribs(d, layers), height=d.get("height") or 0.125,
                          rotation=d.get("rotation") or 0.0, halign=int(d.get("halign") or 0),
                          valign=int(d.get("valign") or 0),
                          flags=int(d.get("attribute_flags") or 0))
                if d.get("align_point") is not None:
                    kw["align_point"] = d["align_point"]
                ref.add_attrib(str(d.get("tag") or ""), str(d.get("text") or ""),
                               d["insert"], dxfattribs=kw)
                continue
            target = where.get(owner) or where.get(e.handle) or msp
            _add(target, "ATTRIB", e.dxf, _attribs(e.dxf, layers), names, skipped)
        except (KeyError, TypeError, ValueError, ezdxf.DXFError):
            skipped["ATTRIB (unreadable)"] = skipped.get("ATTRIB (unreadable)", 0) + 1
    return doc, units, skipped
