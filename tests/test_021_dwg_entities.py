"""DWG files KanzonasCAD writes itself (dwgwrite.py, AutoCAD 2000), milestone 2: layers and the
entities of model space (lines, lightweight polylines, circles, arcs, texts). Read back by ezdwg
(an independent reader) kind by kind, and the structure checked with our own bit reader: every
object whole, the object map, the layer table, each entity's layer and the chain of model
space from its block header's first entity to its last."""
import datetime
import math
import os
import struct
import tempfile
import unittest

from kanzonascad import dwgbits as D
from kanzonascad import dwgwrite as W
from tests.test_021_dwg_write import read_map, read_ms

WHEN = datetime.datetime(2026, 11, 20, 9, 30)
GUIDS = ["{A}", "{B}"]

LAYERS = [dict(name="WIRES", color=1), dict(name="SYMBOLS", color=3),
          dict(name="NOTES", color=5), dict(name="HIDDEN", color=4, on=False),
          dict(name="ICE", color=6, frozen=True), dict(name="KEPT", color=2, locked=True)]

ENTITIES = [
    dict(type="LINE", start=(0.5, 8.0), end=(4.0, 8.0), layer="WIRES"),
    dict(type="LINE", start=(0.5, 7.5, 1.0), end=(4.0, 7.5, 2.0), layer="WIRES", color=2),
    dict(type="LWPOLYLINE", points=[(0.5, 5.5), (1.5, 6.5), (2.5, 5.5)], layer="SYMBOLS"),
    dict(type="LWPOLYLINE", points=[(0.5, 4.0), (3.5, 4.0), (3.5, 5.0)], closed=True,
         layer="SYMBOLS", color=0),
    dict(type="LWPOLYLINE", points=[(6.0, 4.0), (8.0, 4.0)], bulges=[1.0, 0.0],
         layer="SYMBOLS"),
    dict(type="CIRCLE", center=(1.5, 2.5), radius=0.75, layer="SYMBOLS", color=30),
    dict(type="ARC", center=(5.0, 2.0), radius=1.0, start_angle=0.0,
         end_angle=math.pi / 2, layer="HIDDEN"),
    dict(type="TEXT", text="LEFT", insert=(8.0, 3.0), height=0.15, layer="NOTES"),
    dict(type="TEXT", text="CENTER", insert=(8.0, 2.5), height=0.2, align="center",
         layer="NOTES"),
    dict(type="TEXT", text="RIGHT", insert=(8.0, 2.0), height=0.25, align="right",
         layer="KEPT"),
    dict(type="TEXT", text="UP", insert=(10.5, 0.5), height=0.15, rotation=math.pi / 2,
         layer="ICE"),
    dict(type="LINE", start=(0, 0), end=(1, 1), layer="NEW ONE"),
]


def parse(data):
    """{handle: (type, reader after the handle, reader at the handle references)} for every
    object of the map, after checking each one's size and checksum."""
    n = struct.unpack_from("<I", data, 0x15)[0]
    locs = [struct.unpack_from("<BII", data, 0x19 + 9 * i) for i in range(n)]
    entries, _end = read_map(data, locs[2][1], locs[2][2])
    out = {}
    for h, at in entries:
        size, p = read_ms(data, at)
        crc = struct.unpack_from("<H", data, p + size)[0]
        if crc != D.crc8(0xC0C1, data[at:p + size]):
            raise AssertionError("object %X: checksum wrong" % h)
        body = data[p:p + size]
        r = D.BitReader(body)
        t = r.BS()
        bits = r.RL()
        if r.H() != (0, h):
            raise AssertionError("object %X: its own handle differs" % h)
        out[h] = (t, r, D.BitReader(body, bits))
    return out


def entity_links(r, refs):
    """An entity's (color, prev, next, layer, more refs) from model space."""
    r.BS()                                  # (no extended data)
    r.B()                                   # (no graphic)
    mode = r.BB()
    if mode != 2:
        raise AssertionError("not in model space: entity mode %d" % mode)
    r.BL()
    r.B()
    color = r.BS()
    links = [refs.H() for _k in range(4)]   # (dictionary, previous, next, layer)
    return color, links[1][1], links[2][1], links[3][1]


class EntitiesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.folder.name, "kinds.dwg")
        W.write_dwg(cls.path, ENTITIES, LAYERS)
        with open(cls.path, "rb") as f:
            cls.data = f.read()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def ezdwg(self):
        try:
            import ezdwg
        except ImportError:
            self.skipTest("ezdwg isn't installed")
        return ezdwg

    def read_back(self):
        ezdwg = self.ezdwg()
        names = dict(ezdwg.raw.decode_layer_names(self.path))
        ents = sorted(ezdwg.read(self.path).entities().query(), key=lambda e: e.handle)
        return [(e.dxftype, names[e.dxf["layer_handle"]], e.dxf) for e in ents]

    def test_every_kind_comes_back_through_ezdwg(self):
        back = self.read_back()
        self.assertEqual([k for k, _l, _d in back],
                         ["LINE", "LINE", "LWPOLYLINE", "LWPOLYLINE", "LWPOLYLINE", "CIRCLE",
                          "ARC", "TEXT", "TEXT", "TEXT", "TEXT", "LINE"])
        self.assertEqual([la for _k, la, _d in back], [e["layer"] for e in ENTITIES])
        self.assertEqual([d["color_index"] for _k, _l, d in back],
                         [256, 2, 256, 0, 256, 30, 256, 256, 256, 256, 256, 256])
        line, line3d, open_, closed, bulged, circle, arc = (d for _k, _l, d in back[:7])
        self.assertEqual((line["start"], line["end"]), ((0.5, 8.0, 0.0), (4.0, 8.0, 0.0)))
        self.assertEqual((line3d["start"], line3d["end"]), ((0.5, 7.5, 1.0), (4.0, 7.5, 2.0)))
        self.assertEqual(open_["points"], [(0.5, 5.5, 0.0), (1.5, 6.5, 0.0), (2.5, 5.5, 0.0)])
        self.assertFalse(open_["closed"])
        self.assertTrue(closed["closed"])
        self.assertEqual(closed["points"][2], (3.5, 5.0, 0.0))
        self.assertEqual(bulged["bulges"], [1.0, 0.0])
        self.assertEqual((circle["center"], circle["radius"]), ((1.5, 2.5, 0.0), 0.75))
        self.assertEqual((arc["center"], arc["radius"]), ((5.0, 2.0, 0.0), 1.0))
        self.assertAlmostEqual(arc["start_angle"], 0.0)
        self.assertAlmostEqual(arc["end_angle"], 90.0)        # (ezdwg gives degrees)
        texts = [d for k, _l, d in back if k == "TEXT"]
        self.assertEqual([t["text"] for t in texts], ["LEFT", "CENTER", "RIGHT", "UP"])
        self.assertEqual([t["height"] for t in texts], [0.15, 0.2, 0.25, 0.15])
        self.assertEqual([t["halign"] for t in texts], [0, 1, 2, 0])
        self.assertEqual([t["rotation"] for t in texts], [0.0, 0.0, 0.0, 90.0])
        self.assertEqual(texts[0]["insert"], (8.0, 3.0, 0.0))
        self.assertIsNone(texts[0]["align_point"])
        self.assertEqual(texts[1]["align_point"], (8.0, 2.5, 0.0))
        self.assertEqual(texts[2]["align_point"], (8.0, 2.0, 0.0))
        # (the start worked out from the estimated width: right-aligned ends at its anchor)
        self.assertAlmostEqual(texts[2]["insert"][0], 8.0 - (5 - 1 / 3) * 0.25)
        self.assertAlmostEqual(texts[1]["insert"][0], 8.0 - (6 - 1 / 3) * 0.2 / 2)
        self.assertEqual(texts[3]["insert"], (10.5, 0.5, 0.0))
        self.assertEqual({t["style_handle"] for t in texts}, {W.H["STANDARD"]})

    def test_layers_with_their_colors_and_states(self):
        ezdwg = self.ezdwg()
        names = dict(ezdwg.raw.decode_layer_names(self.path))
        self.assertEqual(sorted(names.values()),
                         sorted(["0", "WIRES", "SYMBOLS", "NOTES", "HIDDEN", "ICE", "KEPT",
                                 "NEW ONE"]))
        by_name = {v: k for k, v in names.items()}
        colors = {names[h]: c for h, c, _t in ezdwg.raw.decode_layer_colors(self.path)}
        states = {names[r[0]]: r[1:6] for r in ezdwg.raw.decode_layer_states(self.path)}
        self.assertEqual(by_name["0"], W.H["LAYER0"])
        for la in LAYERS:
            frozen, off, _new, locked, plotted = states[la["name"]]
            self.assertEqual((frozen, off, locked, plotted),
                             (la.get("frozen", False), not la.get("on", True),
                              la.get("locked", False), True), la["name"])
            # (an off layer's color is kept negative, read here as an unsigned short)
            want = la["color"] if la.get("on", True) else 0x10000 - la["color"]
            self.assertEqual(colors[la["name"]], want, la["name"])
        self.assertEqual((colors["0"], colors["NEW ONE"]), (7, 7))

    def test_true_colors_become_the_nearest_index(self):
        self.assertEqual(W.nearest_aci((255, 0, 0)), 1)
        self.assertEqual(W.nearest_aci((0, 0, 255)), 5)
        self.assertEqual(W.nearest_aci((250, 250, 250)), 7)
        data = W.dwg_bytes([dict(type="CIRCLE", center=(0, 0), radius=1, color=(0, 250, 5),
                                 layer="L")],
                           [dict(name="L", color=(10, 10, 250))], when=WHEN, guids=GUIDS)
        objs = parse(data)
        layer = [h for h, (t, _r, _s) in objs.items() if t == W.T_LAYER and h != W.H["LAYER0"]]
        t, r, _s = objs[layer[0]]
        r.BS()
        r.BL()
        self.assertEqual((r.T(), r.B(), r.BS(), r.B()), ("L", 0, 0, 0))
        r.BS()
        self.assertEqual(r.BS(), 5)
        circle = [o for o in objs.values() if o[0] == W.T_CIRCLE][0]
        self.assertEqual(entity_links(circle[1], circle[2])[0], 3)

    def test_structure_read_with_our_own_bits(self):
        objs = parse(self.data)
        # (the layer table: its control object lists every layer, each owned by it)
        t, r, refs = objs[W.H["LAYER_CONTROL"]]
        self.assertEqual(t, W.T_LAYER_CONTROL)
        r.BS()
        r.BL()
        count = r.BL()
        refs.H()
        refs.H()
        listed = [refs.H() for _k in range(count)]
        layers = sorted(h for h, (t, _r, _s) in objs.items() if t == W.T_LAYER)
        self.assertEqual(sorted(h for _c, h in listed), layers)
        self.assertEqual({c for c, _h in listed}, {W.SOFT_OWNER})
        self.assertEqual(count, len(LAYERS) + 2)
        for h in layers:
            self.assertEqual(objs[h][2].H(), (W.SOFT_PTR, W.H["LAYER_CONTROL"]))
        # (model space: its block header's first and last entity, and the chain between)
        t, _r, refs = objs[W.H["MSPACE"]]
        self.assertEqual(t, W.T_BLOCK_HEADER)
        hs = [refs.H()[1] for _k in range(5)]   # (owner, dictionary, xref, BLOCK, first)
        first, last = hs[4], refs.H()[1]
        kinds = {W.T_LINE: "LINE", W.T_LWPLINE: "LWPOLYLINE", W.T_CIRCLE: "CIRCLE",
                 W.T_ARC: "ARC", W.T_TEXT: "TEXT"}
        chain, h, prev = [], first, 0
        while h:
            t, r, refs = objs[h]
            _color, p, nxt, lay = entity_links(r, refs)
            self.assertEqual(p, prev)
            self.assertEqual(objs[lay][0], W.T_LAYER)
            if t == W.T_TEXT:
                self.assertEqual(refs.H(), (W.HARD_PTR, W.H["STANDARD"]))
            chain.append(kinds[t])
            prev, h = h, nxt
        self.assertEqual(prev, last)
        self.assertEqual(chain, [e["type"] for e in ENTITIES])
        # (the header's seed is above every handle used)
        self.assertEqual(max(objs) + 1, W.FIRST_FREE + len(LAYERS) + 1 + len(ENTITIES))

    def test_extents_hold_every_entity(self):
        ezdwg = self.ezdwg()
        data = W.dwg_bytes([dict(type="ARC", center=(5, 2), radius=1, start_angle=0,
                                 end_angle=math.pi / 2),
                            dict(type="LWPOLYLINE", points=[(0, 0), (2, 0)], bulges=[1, 0])],
                           when=WHEN, guids=GUIDS)
        path = os.path.join(self.folder.name, "ext.dwg")
        with open(path, "wb") as f:
            f.write(data)
        hv = ezdwg.read(path).header_variables()
        # (the bulge of 1 is a half circle below the chord, going counterclockwise)
        lo, hi = hv["extmin"], hv["extmax"]
        self.assertEqual([round(v, 9) for v in lo], [0.0, -1.0, 0.0])
        self.assertEqual([round(v, 9) for v in hi], [6.0, 3.0, 0.0])

    def test_what_autocad_could_not_take_is_refused(self):
        bad = [([dict(type="SPLINE")], []),
               ([], [dict(name="A/B")]),
               ([], [dict(name="0", frozen=True)]),
               ([], [dict(name="X"), dict(name="x")]),
               ([], [dict(name="X", color=0)]),
               ([dict(type="CIRCLE", center=(0, 0), radius=0)], []),
               ([dict(type="LINE", start=(0, 0), end=(float("nan"), 0))], []),
               ([dict(type="LWPOLYLINE", points=[(0, 0)])], []),
               ([dict(type="TEXT", text="A\nB", insert=(0, 0), height=1)], []),
               ([dict(type="TEXT", text="A", insert=(0, 0), height=1, align="fit")], [])]
        for ents, lays in bad:
            with self.assertRaises(ValueError, msg=repr((ents, lays))):
                W.dwg_bytes(ents, lays, when=WHEN, guids=GUIDS)


class ManyEntitiesTest(unittest.TestCase):
    def test_two_thousand_mixed_entities_round_trip(self):
        try:
            import ezdwg
        except ImportError:
            self.skipTest("ezdwg isn't installed")
        layers = [dict(name="L%d" % k, color=k + 1) for k in range(10)]
        ents = []
        for i in range(2000):
            x, y, lay = (i % 50) * 0.25, (i // 50) * 0.25, "L%d" % (i % 10)
            kind = i % 5
            if kind == 0:
                ents.append(dict(type="LINE", start=(x, y), end=(x + 0.2, y + 0.1),
                                 layer=lay))
            elif kind == 1:
                ents.append(dict(type="LWPOLYLINE", points=[(x, y), (x + 0.1, y),
                                                            (x + 0.1, y + 0.1)],
                                 closed=bool(i % 2), layer=lay, color=i % 256))
            elif kind == 2:
                ents.append(dict(type="CIRCLE", center=(x, y), radius=0.05 + i * 1e-5,
                                 layer=lay))
            elif kind == 3:
                ents.append(dict(type="ARC", center=(x, y), radius=0.1, start_angle=0.5,
                                 end_angle=2.5, layer=lay))
            else:
                ents.append(dict(type="TEXT", text="T%d" % i, insert=(x, y), height=0.05,
                                 rotation=(i % 4) * math.pi / 2, layer=lay,
                                 align=("left", "center", "right")[i % 3]))
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "many.dwg")
            W.write_dwg(path, ents, layers)
            with open(path, "rb") as f:
                self.assertEqual(len(parse(f.read())), W.FIRST_FREE - 2 + 10 + 2000)
            names = dict(ezdwg.raw.decode_layer_names(path))
            back = sorted(ezdwg.read(path).entities().query(), key=lambda e: e.handle)
        self.assertEqual(len(back), 2000)
        for e, b in zip(ents, back):
            d = b.dxf
            self.assertEqual(b.dxftype, e["type"])
            self.assertEqual(names[d["layer_handle"]], e["layer"])
            if e["type"] == "LINE":
                self.assertEqual(d["end"], (e["end"][0], e["end"][1], 0.0))
            elif e["type"] == "LWPOLYLINE":
                self.assertEqual([p[:2] for p in d["points"]], e["points"])
                self.assertEqual(d["closed"], e["closed"])
                self.assertEqual(d["color_index"], e["color"])
            elif e["type"] in ("CIRCLE", "ARC"):
                self.assertEqual(d["center"][:2], e["center"])
                self.assertEqual(d["radius"], e["radius"])
            else:
                self.assertEqual(d["text"], e["text"])
                self.assertAlmostEqual(math.radians(d["rotation"]), e["rotation"])
                self.assertEqual(d["halign"], ("left", "center", "right").index(e["align"]))
                anchor = d["insert"] if e["align"] == "left" else d["align_point"]
                self.assertEqual(anchor[:2], e["insert"])


if __name__ == "__main__":
    unittest.main()
