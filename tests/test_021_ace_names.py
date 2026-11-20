"""DXF export with AutoCAD Electrical's attribute names (the roadmap's item 11, phase 2; Options:
"Use AutoCAD Electrical attribute names in DXF"): a symbol's tag as TAG1, its maker as MFG, its
catalog number as CAT, its description as DESC1; a footprint's tag as P_TAG1. Off, KanzonasCAD's
own names as in 0.20. Either way the DXF reads back as the same symbols."""
import os
import tempfile
import unittest

import ezdxf

from tests.util import APP, window

from kanzonascad import fileio, wirenums
from kanzonascad import model as M


class AceNamesTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.s = self.v.sheet()
        lib = self.win.library
        d = lib.get("symbol", "Relay coil")
        fp = next(iter(lib.blocks("footprint")[0].values()))
        with self.p.edit("parts") as ed:
            ed.add(self.s, M.Insert(d.name, (3.0, 3.0), 0.0, 1.0, False,
                                    {"TAG": "CR1", "DESC": "Run relay", "MFR": "AB",
                                     "CAT": "700-HC"}, d, 0.1))
            ed.add(self.s, M.Insert(fp.name, (8.0, 3.0), 0.0, 1.0, False, {"TAG": "CR1"},
                                    fp, 0.1))
        self.path = os.path.join(tempfile.mkdtemp(), "x.dxf")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def attribs(self, ace):
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=ace)
        refs = [r for r in ezdxf.readfile(self.path).modelspace().query("INSERT")
                if r.dxf.name not in fileio.ACE_OWN]
        return [{a.dxf.tag: a.dxf.text for a in r.attribs} for r in refs]

    def test_ace_names(self):
        coil, fp = self.attribs(True)
        self.assertEqual((coil.get("TAG1"), coil.get("MFG"), coil.get("CAT"),
                          coil.get("DESC1")), ("CR1", "AB", "700-HC", "Run relay"))
        self.assertNotIn("TAG", coil)
        self.assertEqual(fp.get("P_TAG1"), "CR1")
        ents, _rep = fileio.read_dxf(self.path)
        back = sorted((e for e in ents if isinstance(e, M.Insert)), key=lambda e: e.pos[0])
        self.assertEqual([e.attrs.get("TAG") for e in back], ["CR1", "CR1"])
        self.assertEqual((back[0].attrs.get("MFR"), back[0].attrs.get("CAT")), ("AB", "700-HC"))
        self.assertEqual(back[0].defn.kind, "symbol")
        self.assertIsNotNone(back[0].defn.tag_pos)          # (its tag spot, from TAG1's)

    def test_wires_as_lines(self):
        # (the owner, in AutoCAD Electrical: "the wires are registering as poly lines and not
        # wires", so Scoot didn't move them: a wire is one LINE a straight run, on its layer)
        with self.p.edit("wire") as ed:
            ed.add(self.s, M.Wire([(1.0, 1.0), (4.0, 1.0), (4.0, 3.0)], layer="WIRES"))
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        msp = ezdxf.readfile(self.path).modelspace()
        lines = [e for e in msp.query("LINE") if e.dxf.layer == "WIRES"]
        self.assertEqual(sorted((tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]) for e in lines),
                         [((1.0, 1.0), (4.0, 1.0)), ((4.0, 1.0), (4.0, 3.0))])
        self.assertEqual([e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "WIRES"], [])
        # (crossing wires: no polyline on their layer)
        with self.p.edit("cross") as ed:
            ed.project_settings({"wire_crossing": "loop"})
            ed.add(self.s, M.Wire([(2.0, 0.0), (2.0, 2.0)], layer="WIRES"))
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        msp = ezdxf.readfile(self.path).modelspace()
        self.assertEqual([e for e in msp.query("LWPOLYLINE") if e.dxf.layer == "WIRES"], [])
        # (KanzonasCAD's own names: a wire stays one polyline, as before)
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False)
        msp = ezdxf.readfile(self.path).modelspace()
        self.assertGreaterEqual(len([e for e in msp.query("LWPOLYLINE")
                                     if e.dxf.layer == "WIRES"]), 2)   # (cut where it jumps)

    def export(self, ace=True):
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=ace)
        return ezdxf.readfile(self.path)

    @staticmethod
    def ptr(e, app):
        """The handle an AutoCAD Electrical xdata of e points at, or None."""
        if not e.has_xdata(app):
            return None
        return next(t.value for t in e.get_xdata(app) if t.code == 1005)

    def test_drawing_settings(self):
        # (the owner in AutoCAD Electrical: with no WD_M it put in its own, whose wire layers
        # didn't list ours, and Scoot said "Line entity not on a Wire layer")
        with self.p.edit("wires") as ed:
            ed.layer("480V", None, M.Layer("480V").to_dict())
            ed.add(self.s, M.Wire([(1.0, 1.0), (4.0, 1.0)], layer="WIRES"))
            ed.add(self.s, M.Wire([(1.0, 2.0), (4.0, 2.0)], layer="480V"))
        doc = self.export()
        wdm = [r for r in doc.modelspace().query("INSERT") if r.dxf.name == "WD_M"]
        self.assertEqual(len(wdm), 1)
        vals = {a.dxf.tag: a.dxf.text for a in wdm[0].attribs}
        self.assertEqual(len(vals), 77)
        self.assertEqual(vals["WIRELAYS"].split(","), ["WIRES", "480V"])
        self.assertEqual((vals["GAP_STYLE"], vals["WIRENO_LAY"], vals["COMP_LAY"]),
                         ("1", "WIRENO", "SYMS"))
        self.assertTrue(all(a.is_invisible for a in wdm[0].attribs))
        self.assertEqual(len(doc.blocks.get("WD_M").query("ATTDEF")), 77)
        # (KanzonasCAD's own: none of AutoCAD Electrical's data)
        doc = self.export(False)
        self.assertNotIn("WD_M", doc.blocks)
        self.assertFalse([e for e in doc.modelspace() if e.dxftype() == "INSERT" and
                          e.dxf.name in fileio.ACE_OWN])
        self.assertFalse([e for e in doc.modelspace() if e.has_xdata("VIA_WD_WNPTR")])
        # (read back: WD_M is nothing on the sheet)
        doc = self.export()
        ents, _rep = fileio.read_dxf(self.path)
        self.assertFalse([e for e in ents if isinstance(e, M.Insert) and
                          e.block in fileio.ACE_OWN])
        self.assertFalse([e for e in ents if isinstance(e, M.Text) and e.text == "WIRES"])

    def test_crossing_as_ace_gap(self):
        # (as AutoCAD Electrical draws a crossing with its loops: the jumping wire in two LINEs
        # with a 0.1 gap centered on it, each knowing the other, and a half circle over it)
        with self.p.edit("cross") as ed:
            ed.project_settings({"wire_crossing": "loop"})
            ed.add(self.s, M.Wire([(1.0, 5.0), (4.0, 5.0)], layer="WIRES"))
            ed.add(self.s, M.Wire([(2.0, 6.0), (2.0, 4.0)], layer="WIRES"))
        msp = self.export().modelspace()
        down = sorted((e for e in msp.query("LINE") if e.dxf.layer == "WIRES" and
                       abs(e.dxf.start[0] - 2.0) < 1e-9 and abs(e.dxf.end[0] - 2.0) < 1e-9),
                      key=lambda e: -e.dxf.start[1])
        self.assertEqual(len(down), 2)
        a, b = down
        self.assertAlmostEqual(a.dxf.end[1], 5.05)
        self.assertAlmostEqual(b.dxf.start[1], 4.95)
        h = a.dxf.handle, b.dxf.handle
        self.assertEqual((self.ptr(a, "VIA_WD_HDL"), self.ptr(b, "VIA_WD_HDL")), h)
        self.assertEqual(self.ptr(a, "VIA_WD_GAP11"), h[1])
        self.assertEqual(self.ptr(b, "VIA_WD_GAP10"), h[0])
        self.assertIsNone(self.ptr(a, "VIA_WD_GAP10"))
        self.assertIsNone(self.ptr(b, "VIA_WD_GAP11"))
        across = [e for e in msp.query("LINE") if abs(e.dxf.start[1] - 5.0) < 1e-9 and
                  abs(e.dxf.end[1] - 5.0) < 1e-9]
        self.assertEqual(len(across), 1)                # (the crossed wire: whole)
        self.assertIsNone(self.ptr(across[0], "VIA_WD_HDL"))
        arcs = list(msp.query("ARC"))
        self.assertEqual(len(arcs), 1)
        self.assertAlmostEqual(arcs[0].dxf.radius, 0.05)
        self.assertEqual(tuple(arcs[0].dxf.center)[:2], (2.0, 5.0))
        self.assertEqual((arcs[0].dxf.start_angle % 360, arcs[0].dxf.end_angle % 360),
                         (90.0, 270.0))
        self.assertEqual(arcs[0].dxf.layer, "WIRES")
        self.assertFalse(list(msp.query("LWPOLYLINE")))

    def test_dots_and_numbers(self):
        # (a tee: AutoCAD Electrical's dot WDDOT; each wire number its block WD_WNH on the wire,
        # every LINE of its wires pointing at it)
        with self.p.edit("tee") as ed:
            ed.add(self.s, M.Wire([(1.0, 7.0), (5.0, 7.0)], layer="WIRES", num="101",
                                  num_lock=True))
            ed.add(self.s, M.Wire([(3.0, 7.0), (3.0, 9.0), (4.0, 9.0)], layer="WIRES",
                                  num="101", num_lock=True))
            ed.add(self.s, M.Wire([(1.0, 10.0), (5.0, 10.0)], layer="WIRES", num="102",
                                  num_lock=True))
        doc = self.export()
        msp = doc.modelspace()
        dots = [r for r in msp.query("INSERT") if r.dxf.name == "WDDOT"]
        self.assertEqual([(tuple(r.dxf.insert)[:2], r.dxf.layer) for r in dots],
                         [((3.0, 7.0), "SYMS")])
        self.assertEqual(len(doc.blocks.get("WDDOT").query("CIRCLE")), 3)
        nums = {}
        for r in msp.query("INSERT"):
            if r.dxf.name == "WD_WNH":
                self.assertEqual(r.dxf.layer, "WIRENO")
                nums[r.get_attrib_text("WIRENO")] = r
        self.assertEqual(sorted(nums), ["101", "102"])
        lines = [e for e in msp.query("LINE") if e.dxf.layer == "WIRES"]
        self.assertEqual(len(lines), 4)
        for e in lines:
            num = "102" if e.dxf.start[1] == 10.0 else "101"
            self.assertEqual(self.ptr(e, "VIA_WD_WNPTR"), nums[num].dxf.handle)
        # (its point on its wire, its number where the program shows it)
        shown = {t.text: t for t in wirenums.labels(self.p, self.s)}
        for num, r in nums.items():
            q = tuple(r.dxf.insert)[:2]
            self.assertTrue(any(e.dxf.start[1] == q[1] == e.dxf.end[1] and
                                min(e.dxf.start[0], e.dxf.end[0]) <= q[0] <=
                                max(e.dxf.start[0], e.dxf.end[0]) for e in lines) or
                            any(e.dxf.start[0] == q[0] == e.dxf.end[0] for e in lines), num)
            att = r.get_attrib("WIRENO")
            self.assertAlmostEqual(att.dxf.align_point[0], shown[num].pos[0])
            self.assertAlmostEqual(att.dxf.align_point[1], shown[num].pos[1])
            self.assertEqual(att.dxf.rotation, shown[num].angle)
        self.assertFalse([t for t in msp.query("TEXT") if t.dxf.text in ("101", "102")])
        # (read back: no symbol made of AutoCAD Electrical's dots or numbers)
        ents, _rep = fileio.read_dxf(self.path)
        self.assertFalse([e for e in ents if isinstance(e, M.Insert) and
                          e.block in fileio.ACE_OWN])
        self.assertEqual(sorted(e.text for e in ents if isinstance(e, M.Text) and
                                e.layer == "WIRENO"), ["101", "102"])

    def test_only_wires_on_wire_layers(self):
        # (the owner in AutoCAD Electrical: "found a component with >2 wires": the lines out to
        # numbers set off to the side were on layer WIRES, so it took them for wires)
        with self.p.edit("busy") as ed:
            ed.add(self.s, M.Wire([(1.0, 12.0), (1.6, 12.0)], layer="WIRES", num="201",
                                  num_lock=True))
            for i in range(6):
                ed.add(self.s, M.Line((1.0 + 0.1 * i, 11.9), (1.0 + 0.1 * i, 12.3),
                                      layer="SYMBOLS"))
            ed.add(self.s, M.Line((7.0, 12.0), (8.0, 12.0), layer="WIRES"))
            ed.add(self.s, M.Polyline([(7.0, 13.0), (8.0, 13.0), (8.0, 14.0)], layer="WIRES"))
        self.assertTrue(wirenums.label_leaders(self.p, self.s))      # (a number set off to the side)
        msp = self.export().modelspace()
        wire_lays = {"WIRES"}
        on = [e for e in msp if e.dxftype() in ("LINE", "LWPOLYLINE", "POLYLINE", "INSERT")
              and e.dxf.layer.upper() in wire_lays]
        self.assertTrue(on)
        for e in on:
            self.assertEqual(e.dxftype(), "LINE")
            self.assertTrue(e.has_xdata("VIA_WD_WNPTR"), (e.dxf.start, e.dxf.end))
        self.assertTrue([e for e in msp.query("LINE") if e.dxf.layer == "WIRENO"])

    def test_pins_as_wire_connections(self):
        # (the owner, in AutoCAD Electrical's block editor: "the pins have a pretext of kz on all
        # of them"; its wire connections are X?TERMnn, ? the side a wire comes from: 1 right,
        # 2 top, 4 left, 8 bottom, with TERMnn the pin's label)
        fileio.export_dxf(self.p, self.s, self.path, include_frame=False, ace_names=True)
        doc = ezdxf.readfile(self.path)
        coil = doc.blocks.get("Relay coil")
        tags = {a.dxf.tag: a.dxf.text for a in coil.query("ATTDEF")}
        self.assertFalse(any(t.startswith("KZPIN") for t in tags))
        d = self.win.library.get("symbol", "Relay coil")
        for i, pin in enumerate(d.pins):
            side = fileio.pin_side(d, pin["pos"])
            self.assertIn("X%dTERM%02d" % (side, i + 1), tags)
            self.assertEqual(tags["TERM%02d" % (i + 1)], pin["name"])
        sides = sorted(fileio.pin_side(d, q["pos"]) for q in d.pins)
        self.assertEqual(sides, [1, 4])     # (a coil: A1 on the left, A2 on the right)
        # (X?TERMnn exactly at its pin, where AutoCAD Electrical connects a wire; TERMnn beside
        # it, not on top: the owner saw X4TERM02 written over TERM02 over the VFD's pin label)
        by_tag = {a.dxf.tag: a for a in coil.query("ATTDEF")}
        for i, pin in enumerate(d.pins):
            x = by_tag["X%dTERM%02d" % (fileio.pin_side(d, pin["pos"]), i + 1)]
            t = by_tag["TERM%02d" % (i + 1)]
            self.assertAlmostEqual(x.dxf.insert[0], pin["pos"][0])
            self.assertAlmostEqual(x.dxf.insert[1], pin["pos"][1])
            self.assertLess(x.dxf.height, d.tag_height)
            bx, bt = self.box(x), self.box(t)
            self.assertFalse(bx[0] < bt[2] and bt[0] < bx[2] and bx[1] < bt[3] and
                             bt[1] < bx[3], "%s over %s" % (x.dxf.tag, t.dxf.tag))
        ref = next(r for r in doc.modelspace().query("INSERT") if r.dxf.name == "Relay coil")
        self.assertIn("TERM01", {a.dxf.tag for a in ref.attribs})
        # (each copy's X?TERMnn at its pin on the sheet)
        mine = next(e for e in self.s.inserts() if e.block == "Relay coil")
        at = dict(mine.pin_points())
        for a in ref.attribs:
            if a.dxf.tag.startswith("X"):
                n = int(a.dxf.tag[-2:])
                q = at[d.pins[n - 1]["name"]]
                self.assertAlmostEqual(a.dxf.insert[0], q[0])
                self.assertAlmostEqual(a.dxf.insert[1], q[1])
        # (read back: the same pins, where they were, and no TERM attributes on it)
        ents, _rep = fileio.read_dxf(self.path)
        back = next(e for e in ents if isinstance(e, M.Insert) and e.block == "Relay coil")
        mine = next(e for e in self.s.inserts() if e.block == "Relay coil")
        self.assertEqual(sorted(back.pin_points()), sorted(mine.pin_points()))
        self.assertFalse([k for k in back.attrs if "TERM" in k])

    def test_corner_pins_take_their_side(self):
        # (the owner's VFD in AutoCAD Electrical's block editor: its top-left pin, wired from
        # the left, was X2TERM01, as if wired from the top; a tall symbol's corner pins are on
        # its left and right edges)
        d = self.win.library.get("symbol", "Variable frequency drive")
        xs = [q["pos"][0] for q in d.pins]
        mid = (min(xs) + max(xs)) / 2.0
        for q in d.pins:
            self.assertEqual(fileio.pin_side(d, q["pos"]), 4 if q["pos"][0] < mid else 1,
                             q["name"])

    @staticmethod
    def box(a):
        """The box an attribute's text takes (its text's width as the program measures it)."""
        w = M.text_width(a.dxf.tag, a.dxf.height)
        h = a.dxf.height
        if a.dxf.halign == 2:                   # (right-aligned: it ends at its point)
            x1, y = a.dxf.align_point[0], a.dxf.align_point[1]
            return (x1 - w, y, x1, y + h)
        x, y = a.dxf.insert[0], a.dxf.insert[1]
        return (x, y, x + w, y + h)

    def test_own_names_by_default(self):
        coil, fp = self.attribs(False)
        self.assertEqual((coil.get("TAG"), coil.get("MFR")), ("CR1", "AB"))
        self.assertNotIn("TAG1", coil)
        self.assertEqual(fp.get("TAG"), "CR1")


if __name__ == "__main__":
    unittest.main()
