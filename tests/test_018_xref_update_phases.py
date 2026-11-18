"""The owner, 0.18: "Can symbols be further filtered by whether they're 3ph or not? I would like
source and destination arrows for wire cross references. There needs to be a way to add cross
references from the ribbon in schematic. I also would like a way to update wire numbers and
cross references, tag numbers and cross references, and both. Also need to be able to say for
specific sheets or for the whole project" (asked: worked out with an override; AutoCAD
Electrical's way, number and place on the arrows; renumber or keep, asked each time).

- The Library's phase filter: Three-phase shows the 3-pole and 3-phase symbols only; a block
  set to single-phase in Properties isn't, and the setting is kept.
- Source/destination arrows: a click on a wire's open end, then on another sheet's: a Source
  arrow and a Destination arrow of one name, one wire with the source's number, "num / place"
  under each.
- Update numbers and cross-references: tags and wire numbers, renumbered or only fixed, on the
  sheets picked, cross-references with them, one step."""
import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import xrefs


class PhaseFilterTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()

    def tearDown(self):
        self.win.close()

    def shown(self):
        t = self.win.library_panel.trees["symbol"]
        out = []
        for i in range(t.topLevelItemCount()):
            cat = t.topLevelItem(i)
            out += [cat.child(j).text(0).replace("  (built in)", "")
                    for j in range(cat.childCount())]
        return set(out)

    def test_three_phase_only(self):
        lp = self.win.library_panel
        lp.phase_filter.setCurrentIndex(lp.phase_filter.findData("3"))
        got = self.shown()
        self.assertIn("Motor 3-phase", got)
        self.assertIn("Circuit breaker 3-pole", got)
        self.assertIn("Variable frequency drive", got)
        self.assertNotIn("Relay coil", got)
        self.assertNotIn("Motor", got)
        lp.phase_filter.setCurrentIndex(lp.phase_filter.findData("1"))
        got = self.shown()
        self.assertIn("Relay coil", got)
        self.assertNotIn("Motor 3-phase", got)

    def test_the_setting_wins_and_is_kept(self):
        d = self.win.library.get("symbol", "Circuit breaker 3-pole")
        self.assertEqual(M.phases_of(d), "3")
        one = M.BlockDef.from_dict(dict(d.to_dict(), phases="1"))
        self.assertEqual(M.phases_of(one), "1")
        self.assertEqual(M.BlockDef.from_dict(one.to_dict()).phases, "1")
        mine = M.BlockDef("Mine", pins=[{"name": "A", "pos": (0, 0)}], description="3ph heater")
        self.assertEqual(M.phases_of(mine), "3")


class ArrowsAndUpdateTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        v = self.v
        v.osnap_on = v.snap_on = v.ortho_on = v.polar_on = False
        self.p = v.project
        self.s1 = v.sheet()
        self.win.add_sheet()
        self.s2 = self.p.sheets[1]
        v.show_sheet(self.s1.id)
        with self.p.edit("wires") as ed:
            self.a = ed.add(self.s1, M.Wire([(1.0, 5.0), (6.0, 5.0)]))
            self.b = ed.add(self.s2, M.Wire([(2.0, 3.0), (8.0, 3.0)]))
        v.center, v.scale = (4.0, 4.0), 100.0

    def tearDown(self):
        self.win.__dict__.pop("ask_update_numbers", None)
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def test_arrows_across_sheets(self):
        num = self.s1.entities[self.a.id].num
        self.v.run(C.SignalArrowsCmd)
        self.v.cmd.pick((5.95, 5.0))                     # (near the end at 6, 5)
        self.v.show_sheet(self.s2.id)                    # (the command goes on)
        self.assertIsInstance(self.v.cmd, C.SignalArrowsCmd)
        self.v.center = (5.0, 3.0)
        self.v.cmd.pick((2.05, 3.0))
        self.v.enter()
        src = [e for e in self.s1.inserts() if e.block == "Source arrow"]
        dst = [e for e in self.s2.inserts() if e.block == "Destination arrow"]
        self.assertEqual((len(src), len(dst)), (1, 1))
        self.assertEqual(src[0].attrs["TAG"], dst[0].attrs["TAG"])
        self.assertEqual(src[0].pin_points()[0][1], (6.0, 5.0))
        self.assertEqual(dst[0].pin_points()[0][1], (2.0, 3.0))
        self.assertEqual(self.s2.entities[self.b.id].num, num)       # (the source's number)
        here = [t.text for t in xrefs.texts(self.p, self.s1)]
        self.assertTrue(any(t.startswith(num + " / " + str(self.p.sheet_number(self.s2)))
                            for t in here), here)
        self.p.undo()
        self.assertEqual([e for e in self.s1.inserts() if e.block == "Source arrow"], [])

    def test_a_connected_end_is_refused(self):
        with self.p.edit("x") as ed:
            ed.add(self.s1, M.Wire([(6.0, 5.0), (6.0, 8.0)]))
        said = []
        self.v.messaged.connect(said.append)
        self.v.run(C.SignalArrowsCmd)
        self.v.cmd.pick((5.95, 5.0))
        self.assertTrue(any("connected" in m for m in said), said)
        self.assertIsNone(self.v.cmd.src)
        self.v.cancel()

    def devices(self):
        lib = self.win.library
        with self.p.edit("devices") as ed:
            d = lib.get("symbol", "Relay coil")
            ed.block(d)
            pd = self.p.blocks[d.name]
            out = []
            for s, x, tag in ((self.s1, 9.0, "CR105"), (self.s1, 3.0, "CR109"),
                              (self.s2, 4.0, "CR733")):
                out.append((s, ed.add(s, M.Insert(d.name, (x, 7.0), defn=pd,
                                                  attrs={"TAG": tag, "DEV": tag}))))
        return out

    def run_update(self, **opts):
        o = {"tags": True, "wires": True, "xrefs": True, "renumber": True,
             "sheets": list(self.p.sheets)}
        o.update(opts)
        self.win.ask_update_numbers = lambda project, sheet: o
        self.win.update_numbers()

    def test_renumber_the_whole_project(self):
        devs = self.devices()
        self.run_update()
        tags = {(s.id, e.id): s.entities[e.id].attrs["TAG"] for s, e in devs}
        p1, p2 = self.p.sheet_number(self.s1), self.p.sheet_number(self.s2)
        self.assertEqual(sorted(tags.values()), sorted(["CR%s01" % p1, "CR%s02" % p1,
                                                        "CR%s01" % p2]))
        # (in the sheet's order: across, the one on the left first)
        self.assertEqual(tags[(self.s1.id, devs[1][1].id)], "CR%s01" % p1)
        self.p.undo()                                                # (one step)
        self.assertEqual(self.s1.entities[devs[0][1].id].attrs["TAG"], "CR105")

    def test_keep_only_fixes_and_only_the_sheets_picked(self):
        devs = self.devices()
        self.run_update(renumber=False, sheets=[self.s2])
        p2 = self.p.sheet_number(self.s2)
        self.assertEqual(self.s1.entities[devs[0][1].id].attrs["TAG"], "CR105")  # (not picked)
        got = self.s2.entities[devs[2][1].id].attrs["TAG"]
        # CR733 isn't of sheet 2's page: fixed, its count kept when free
        self.assertEqual(got, "CR%s33" % p2 if p2 != "7" else "CR733")

    def test_same_ids_on_two_sheets_dont_share_a_tag(self):
        # (ids are a sheet's own: renumbering one sheet skipped the other sheet's device of
        # the same id when it counted the numbers taken; the long battery, seed 3152)
        lib = self.win.library
        d = lib.get("symbol", "Disconnect 1-pole")
        p2 = self.p.sheet_number(self.s2)
        with self.p.edit("x") as ed:
            ed.block(d)
            pd = self.p.blocks[d.name]
            mine = [ed.add(self.s2, M.Insert(d.name, (1.0 + 1.5 * i, 7.0), defn=pd,
                                             attrs={"TAG": "DS?", "DEV": "b%d" % i}))
                    for i in range(5)]
            # a device on sheet 1 with the first one's id, holding a count of sheet 2's page
            ed.add(self.s1, M.Insert(d.name, (4.0, 7.0), defn=pd, id=mine[0].id,
                                     attrs={"TAG": "DS%s03" % p2, "DEV": "a"}))
        self.run_update(sheets=[self.s2], wires=False, xrefs=False)
        tags_now = [e.attrs.get("TAG") for s in self.p.sheets for e in s.inserts()
                    if e.block == d.name]
        self.assertEqual(len(tags_now), len(set(tags_now)), tags_now)

    def test_keep_fixes_a_tag_two_devices_have(self):
        lib = self.win.library
        d = lib.get("symbol", "Disconnect 1-pole")
        p1 = self.p.sheet_number(self.s1)
        with self.p.edit("x") as ed:
            ed.block(d)
            pd = self.p.blocks[d.name]
            for x in (3.0, 9.0):
                ed.add(self.s1, M.Insert(d.name, (x, 7.0), defn=pd,
                                         attrs={"TAG": "DS%s04" % p1, "DEV": "d%g" % x}))
        self.run_update(renumber=False, sheets=[self.s1], wires=False, xrefs=False)
        got = sorted(e.attrs["TAG"] for e in self.s1.inserts() if e.block == d.name)
        self.assertEqual(len(set(got)), 2, got)
        self.assertIn("DS%s04" % p1, got)                    # (the first in order keeps it)

    def test_the_window(self):
        from PySide6.QtWidgets import QDialog, QRadioButton, QCheckBox
        from kanzonascad import dialogs

        def answer(dlg):
            dlg.findChild(QRadioButton, "whole_project").setChecked(True)
            dlg.findChild(QRadioButton, "renumber").setChecked(True)
            dlg.findChild(QCheckBox, "xrefs").setChecked(False)
            return QDialog.Accepted
        real = dialogs.QDialog.exec
        dialogs.QDialog.exec = answer
        try:
            got = dialogs.update_numbers_dialog(self.win, self.p, self.s1)
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual((got["tags"], got["wires"], got["xrefs"], got["renumber"]),
                         (True, True, False, True))
        self.assertEqual(got["sheets"], list(self.p.sheets))

    def test_on_the_schematic_tab(self):
        from PySide6.QtWidgets import QToolButton
        r = self.win.ribbon
        for i in range(r.count()):
            if r.tabText(i).replace("&", "") == "Schematic":
                acts = {b.defaultAction() for b in r.widget(i).findChildren(QToolButton)}
                self.assertIn(self.win.acts["sig_arrows"], acts)
                self.assertIn(self.win.acts["update_numbers"], acts)
                return
        self.fail("no Schematic tab")


class ScootCornerTest(unittest.TestCase):
    """Found by the battery (0.18, seed 21): a wire turning a corner on a coil's pin (not cut
    there); scooted with what's attached, the pin slid off the wire's corner."""

    def test_a_pin_on_a_wire_corner_doesnt_slide_off(self):
        from kanzonascad import scoot
        win, v = window()
        try:
            s, p = v.sheet(), v.project
            d = win.library.get("symbol", "Relay coil")
            with p.edit("x") as ed:
                ed.block(d)
                e = ed.add(s, M.Insert(d.name, (12.5, 5.0), defn=p.blocks[d.name]))
                a1 = dict(e.pin_points())["A1"]
                ed.add(s, M.Wire([(8.75, a1[1]), a1, (a1[0], 1.75)]))   # (a corner on A1)
            # right: off the corner (the wire is on its left and below): refused
            self.assertIsNone(scoot.branch_moved(s, [e], 0.5, 0.0))
            # left, along the wire's piece there: the pin stays on it
            self.assertIsNotNone(scoot.branch_moved(s, [e], -0.5, 0.0))
        finally:
            v.project.saved_at = len(v.project.undo_stack)
            win.close()


if __name__ == "__main__":
    unittest.main()
