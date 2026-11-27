"""0.30: UDTs (udts.py, udt_builtin.py, nec_tables.py, udt_window.py): circuit types with
choices, optional parts and ratings, placed as ordinary devices and wires tied together,
rebuilt in place (tags and wire numbers of what stays kept, an optional part left out bridged),
hand edits kept with a warning, Detach, Update from UDT, built-in UDTs and your own, ratings
worked out from the NEC tables and overridable, per placed UDT unless applied to all."""

import os
import tempfile
import unittest

from tests.util import window, type_in
from tests import battery_checks as BC

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import nec_tables as NEC
from kanzonascad import udts as U
from kanzonascad.library import Library

VFD = "Motor circuit, VFD"
DOL = "Motor circuit, full-voltage starter"


class NecTablesTest(unittest.TestCase):
    def test_table_currents(self):
        # (Table 430.250 and 430.248, as printed)
        self.assertEqual(NEC.flc("10", "460"), 14.0)
        self.assertEqual(NEC.flc("5", "480"), 7.6)          # (440-480 V: the 460 V column)
        self.assertEqual(NEC.flc("7-1/2", "208"), 24.2)
        self.assertEqual(NEC.flc("1/2", "575"), 0.9)
        self.assertEqual(NEC.flc("100", "230"), 248.0)
        self.assertEqual(NEC.flc("1", "230", "1"), 8.0)
        self.assertEqual(NEC.flc("1/3", "115", "1"), 7.2)
        self.assertIsNone(NEC.flc("4", "460"))              # (no such row: no guess)
        self.assertIsNone(NEC.flc("5", "380"))              # (no such column)

    def test_standard_sizes(self):
        self.assertEqual(NEC.round_up(24.5, "fuse"), 25)
        self.assertEqual(NEC.round_up(1.925, "fuse"), 3)    # (fuses only: 1, 3, 6, 10)
        self.assertEqual(NEC.round_up(1.925, "breaker"), 15)
        self.assertEqual(NEC.round_up(35.0, "breaker"), 35)
        self.assertEqual(NEC.round_up(16.1, "switch"), 30)
        self.assertEqual(NEC.round_up(16.14, "none"), 16.1)

    def test_rules(self):
        vals = {"HP": "10", "VOLTS": "460", "PHASE": "3", "FLA": ""}
        fuse = U.clean_rule({"role": "r", "attr": "RATING", "rule": "percent", "of": "FLC",
                             "percent": 175, "round": "fuse"})
        self.assertEqual(U.worked_out(fuse, vals), ("25A", ""))
        cb = dict(fuse, attr="AMPS", percent=250.0, round="breaker")
        self.assertEqual(U.worked_out(cb, vals)[0], "35")
        # (the owner's own percent: 150 % of 14 A is 21 A, the next fuse 25 A)
        self.assertEqual(U.worked_out(dict(fuse, percent=150.0), vals)[0], "25A")
        fla = U.clean_rule({"role": "r", "attr": "FLA", "rule": "fla"})
        self.assertEqual(U.worked_out(fla, vals)[0], "14")
        self.assertEqual(U.worked_out(fla, dict(vals, FLA="13.2"))[0], "13.2")
        got, why = U.worked_out(fuse, dict(vals, HP="4"))
        self.assertIsNone(got)
        self.assertIn("type it as FLA", why)


class UdtTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library = Library(tempfile.mkdtemp())

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def udt(self, name=VFD):
        return self.lib.udts()[0][name]

    def insert(self, udt, at, choices=None, values=None, *typed):
        self.win.ask_udt = lambda: (udt, choices or {}, values or {})
        try:
            self.win.insert_udt()
        finally:
            self.win.__dict__.pop("ask_udt", None)
        self.assertIsInstance(self.v.cmd, C.InsertUdtCmd)
        type_in(self.v, *(typed + ("%g,%g" % at,)))
        self.assertIsNone(self.v.cmd)

    def place(self, udt, at, choices=None, values=None, *typed):
        before = set(self.s.udts)
        self.insert(udt, at, choices, values, *typed)
        new = set(self.s.udts) - before
        self.assertEqual(len(new), 1)
        return new.pop()

    def props(self, gid, choices=None, values=None, overrides=None, all_=False,
              replace=False, confirm=True):
        """UDT properties... on gid's objects, the window answered."""
        inst = self.s.udts[gid]
        self.v.set_selection({list(inst["members"].values())[0]})
        self.win.ask_udt_properties = lambda p, s, g, n: {
            "choices": dict(inst["choices"], **(choices or {})),
            "values": dict(inst["values"], **(values or {})),
            "overrides": overrides or {}, "all": all_, "replace": replace}
        shown = []
        self.win.confirm_udt_changes = lambda title, intro, plans, *a, **k: (
            shown.append(plans) or ((plans, {}) if confirm else None))
        try:
            return self.win.udt_properties(), shown
        finally:
            self.win.__dict__.pop("ask_udt_properties", None)
            self.win.__dict__.pop("confirm_udt_changes", None)

    def by_role(self, gid):
        return U.members(self.s, gid)

    def blocks_of(self, gid):
        return sorted(e.block for e in self.by_role(gid).values() if isinstance(e, M.Insert))

    # ---- built in, placed --------------------------------------------------------------------
    def test_builtins_listed_read_only(self):
        got = self.lib.udts()[0]
        self.assertTrue({VFD, DOL} <= set(got))
        self.assertEqual(self.lib.udt_where(VFD), "builtin")
        self.assertFalse(self.lib.delete_udt(VFD))
        # (edited, a built-in is saved as your own copy, which takes its place)
        mine = got[VFD].copy(description="mine")
        self.lib.save_udt(mine)
        self.assertEqual(self.lib.udt_where(VFD), "first")
        self.assertEqual(self.lib.udts()[0][VFD].description, "mine")
        self.assertTrue(os.path.exists(os.path.join(self.lib.folder, "udts", VFD + ".kzudt")))
        self.assertTrue(self.lib.delete_udt(VFD))
        self.assertEqual(self.lib.udt_where(VFD), "builtin")

    def test_placed_as_ordinary_parts_one_step(self):
        n_undo = len(self.p.undo_stack)
        gid = self.place(self.udt(), (2.0, 10.0), values={"HP": "10"})
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)
        inst = self.s.udts[gid]
        self.assertEqual(self.blocks_of(gid), sorted(
            ["Disconnect 3-pole", "Motor protection circuit breaker 3-pole",
             "Variable frequency drive", "Terminal", "Terminal", "Terminal",
             "Motor 3-phase"]))
        tags = sorted(e.attrs.get("TAG", "") for e in self.s.inserts() if e.attrs.get("TAG"))
        self.assertEqual(tags, ["CB101", "DS101", "MTR101", "VFD101"])
        nums = {w.num for w in self.s.wires()}
        self.assertEqual(len(nums), 15)                     # (five groups a phase)
        self.assertTrue(all(n.startswith("1") for n in nums))
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        motor = [e for e in self.s.inserts() if e.block == "Motor 3-phase"][0]
        self.assertEqual((motor.attrs["HP"], motor.attrs["VOLTS"], motor.attrs["FLA"]),
                         ("10", "460", "14"))
        ds = [e for e in self.s.inserts() if e.block == "Disconnect 3-pole"][0]
        self.assertEqual(ds.attrs["AMPS"], "30")
        self.p.undo()
        self.assertEqual(self.s.entities, {})
        self.assertEqual(self.s.udts, {})

    def test_turned_any_way(self):
        gid = self.place(self.udt(DOL), (20.0, 5.0), None, None, "R")
        inst = self.s.udts[gid]
        self.assertEqual(inst["angle"], 90.0)
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        motor = [e for e in self.s.inserts() if e.block == "Motor 3-phase"][0]
        self.assertEqual(motor.angle, 90.0)
        # (5.75" along from the base point, turned: straight up)
        self.assertAlmostEqual(motor.pos[0], 20.0 + 0.5)
        self.assertAlmostEqual(motor.pos[1], 5.0 + 5.75)
        # contacts linked to their own coil and overload
        coil = [e for e in self.s.inserts() if e.block == "Contactor coil"][0]
        k = [e for e in self.s.inserts() if e.block == "Contactor power contacts 3-pole"][0]
        self.assertEqual(k.attrs["PARENT"], coil.attrs["DEV"])
        self.assertEqual(k.attrs["TAG"], coil.attrs["TAG"])

    def test_turned_ratings_stay_readable(self):
        # (a UDT turned 90 degrees: its devices' ratings, stacked under them, were drawn side
        # by side, one over the next; now one under the other on the drawing, read across)
        cb = self.lib.get("symbol", "Circuit breaker 3-pole")
        for angle in (0.0, 90.0, 180.0, 270.0):
            e = M.Insert(cb.name, (5.0, 5.0), angle, defn=cb, attrs={"AMPS": "20",
                                                                     "VOLTS": "460"})
            spots = {n: q for n, q, _a, _s in e.attr_spots()}
            a, b = spots["AMPS"], spots["VOLTS"]
            self.assertAlmostEqual(a[0], b[0], msg=angle)
            self.assertGreater(abs(a[1] - b[1]), 0.1, msg=angle)

    def test_saved_and_opened(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        path = os.path.join(tempfile.mkdtemp(), "u.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(q.sheets[0].udts[gid], self.s.udts[gid])
        self.assertEqual(set(q.sheets[0].udt_types), {self.s.udts[gid]["type"]})

    # ---- rebuilt in place --------------------------------------------------------------------
    def test_choice_rebuilds_in_place_keeping_tags_and_numbers(self):
        gid = self.place(self.udt(), (2.0, 10.0), values={"HP": "10"})
        kept = {r: (e.attrs.get("TAG"), e.attrs.get("DEV")) for r, e in self.by_role(gid).items()
                if isinstance(e, M.Insert) and e.block != "Motor protection circuit breaker "
                                                         "3-pole"}
        wires = {e.id: e.num for e in self.by_role(gid).values() if isinstance(e, M.Wire)}
        ids = {r: e.id for r, e in self.by_role(gid).items()}
        before = self.p.to_dict()
        n_undo = len(self.p.undo_stack)
        self.props(gid, {"Protection": "Fuses"})
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)
        now = self.by_role(gid)
        self.assertIn("Fuses 3-pole", self.blocks_of(gid))
        self.assertNotIn("Motor protection circuit breaker 3-pole", self.blocks_of(gid))
        self.assertEqual({r: (now[r].attrs.get("TAG"), now[r].attrs.get("DEV")) for r in kept},
                         kept)
        fu = [e for e in now.values() if getattr(e, "block", "") == "Fuses 3-pole"][0]
        self.assertEqual(fu.attrs["TAG"], "FU101")
        self.assertEqual(fu.attrs["RATING"], "25A")         # (175 % of 14 A: 24.5, next 25)
        # (what stayed wasn't touched: the same objects, the wires' numbers kept)
        u = U.type_of(self.s, self.s.udts[gid])
        stay = {r for r in kept if not u.member(r)["slot"]}
        self.assertTrue(stay)
        self.assertTrue(all(now[r].id == ids[r] for r in stay))
        for i, n in wires.items():
            if U.find(self.s, i) is not None and i in self.s.entities:
                self.assertEqual(self.s.entities[i].num, n)
        self.assertGreaterEqual(len([i for i in wires if i in self.s.entities]), 12)
        inst = self.s.udts[gid]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        self.p.undo()
        self.assertEqual(BC_norm(self.p.to_dict()), BC_norm(before))

    def test_optional_part_left_out_is_bridged(self):
        gid = self.place(self.udt(), (2.0, 10.0), {"Line reactor": U.INCLUDED})
        self.assertIn("Reactor 3-pole", self.blocks_of(gid))
        self.props(gid, {"Line reactor": U.LEFT_OUT, "Load reactor": U.INCLUDED})
        self.assertEqual(self.blocks_of(gid).count("Reactor 3-pole"), 1)
        inst = self.s.udts[gid]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        lr = [e for e in self.s.inserts() if e.block == "Reactor 3-pole"][0]
        self.assertAlmostEqual(lr.pos[0], 2.0 + 6.5)        # (the load reactor's place)
        self.assertEqual(lr.attrs["TAG"], "LR101")

    def test_bridge_needed(self):
        # (put the bug back: a part left out with nothing in its place breaks every phase)
        u = self.udt()
        cut = u.copy(members=[m for m in u.to_dict()["members"]
                              if not (m["slot"] == "Line reactor" and m["alt"] == U.LEFT_OUT)])
        gid = self.place(cut, (2.0, 10.0))
        inst = self.s.udts[gid]
        with self.assertRaises(AssertionError):
            BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)

    def test_hand_edit_kept_and_warned(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0))
        fu = [e for e in self.by_role(gid).values() if getattr(e, "block", "") ==
              "Fuses 3-pole"][0]
        with self.p.edit("by hand") as ed:
            ed.change(self.s, fu.copy(attrs=dict(fu.attrs, CAT="FRS-R-30")))
        plans, shown = self.props(gid, {"Protection": "Circuit breaker"})
        self.assertTrue(shown, "the warning wasn't shown first")
        self.assertTrue(any("edited by hand" in w for w in plans[0].warnings))
        self.assertIn(fu.id, self.s.entities)               # (left as it is)
        self.assertNotIn(fu.id, self.s.udts[gid]["members"].values())
        self.assertIn("Circuit breaker 3-pole", self.blocks_of(gid))
        # (and not put back when chosen again: it is still there, the user's)
        self.props(gid, {"Protection": "Fuses"})
        self.assertEqual(len([e for e in self.s.inserts() if e.block == "Fuses 3-pole"]), 1)
        self.assertIn(fu.id, self.s.udts[gid]["members"].values())   # (taken back)
        # (a rebuild that takes nothing away asks nothing)
        _plans, shown = self.props(gid, values={"HP": "15"})
        self.assertEqual(shown, [])

    def test_moved_whole_rebuilds_where_it_is(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        ids = set(self.s.udts[gid]["members"].values())
        self.v.set_selection(ids)
        self.v.run(C.MoveCmd)
        type_in(self.v, "0,0", "3,-4")
        self.v.set_selection(ids)
        self.v.run(C.RotateCmd)
        type_in(self.v, "5,6", "90")
        plans, _shown = self.props(gid, {"Protection": "Fuses"})
        self.assertEqual(plans[0].warnings, [])
        inst = self.s.udts[gid]
        self.assertEqual(inst["angle"], 90.0)
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)

    # ---- copies (the owner, Nov 27 2026: "Copy/paste of a placed UDT makes a new instance") --
    def udt_tags(self, gid, sheet=None):
        return sorted(e.attrs.get("TAG", "") for e in U.members(sheet or self.s, gid).values()
                      if isinstance(e, M.Insert) and e.defn.role != "child")

    def assert_new_instance(self, src, gid, sheet=None, src_sheet=None):
        """gid (on sheet) a placed UDT of its own copied from src: the same UDT, choices,
        values, rating rules and overrides; its own objects, tags and wire numbers; its
        contacts on its own devices; wired as its UDT draws it."""
        sheet, src_sheet = sheet or self.s, src_sheet or self.s
        a, b = src_sheet.udts[src], sheet.udts[gid]
        for k in ("udt", "type", "choices", "values", "ratings", "overrides", "strip"):
            self.assertEqual(b.get(k), a.get(k), k)
        self.assertEqual(set(b["members"]), set(a["members"]))
        self.assertEqual(sheet.udt_types[b["type"]], src_sheet.udt_types[a["type"]])
        mine = U.members(sheet, gid)
        self.assertEqual(len(mine), len(a["members"]))
        theirs = U.members(src_sheet, src)
        if sheet is src_sheet:
            self.assertFalse(set(e.id for e in mine.values()) &
                             set(e.id for e in theirs.values()))
        tags_all = [e.attrs.get("TAG") for x in self.p.sheets for e in x.inserts()
                    if e.attrs.get("TAG") and e.defn.role != "child"]
        self.assertFalse(set(self.udt_tags(gid, sheet)) & set(self.udt_tags(src, src_sheet)))
        self.assertEqual(len(tags_all), len(set(tags_all)), tags_all)
        nums = [e.num for e in mine.values() if isinstance(e, M.Wire)]
        self.assertFalse(set(nums) & {e.num for e in theirs.values() if isinstance(e, M.Wire)})
        devs = {e.attrs["DEV"]: e for e in mine.values()
                if isinstance(e, M.Insert) and e.attrs.get("DEV")}
        for e in mine.values():
            if isinstance(e, M.Insert) and e.attrs.get("PARENT"):
                self.assertIn(e.attrs["PARENT"], devs, "a contact left on the original")
                self.assertEqual(e.attrs["TAG"], devs[e.attrs["PARENT"]].attrs["TAG"])
        BC.udt_motor_circuit(self.p, sheet, U.type_of(sheet, b), b)

    def copy_cmd(self, gid, to=(0.0, -5.0)):
        ids = set(self.s.udts[gid]["members"].values())
        before = set(self.s.udts)
        self.v.set_selection(ids)
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "%.12g,%.12g" % to)
        if self.v.cmd is not None:
            self.v.cmd.enter()
        new = set(self.s.udts) - before
        self.assertEqual(len(new), 1)
        return new.pop()

    def test_copy_makes_a_new_instance(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0), {"Protection": "Circuit breaker"},
                         {"HP": "10"})
        ol = [r for r, e in self.by_role(gid).items() if getattr(e, "block", "") ==
              "Overload heaters 3-pole"][0]
        self.props(gid, overrides={ol: {"AMPS": "13"}})
        n_undo = len(self.p.undo_stack)
        new = self.copy_cmd(gid)
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)        # (one step)
        self.assertEqual(self.s.udts[new]["at"], [2.0, 5.0])
        self.assert_new_instance(gid, new)
        self.assertEqual(self.by_role(new)[ol].attrs["AMPS"], "13")
        # (its own: UDT properties on the copy rebuilds the copy only)
        before = self.blocks_of(gid)
        self.props(new, {"Protection": "Fuses"})
        self.assertIn("Fuses 3-pole", self.blocks_of(new))
        self.assertEqual(self.blocks_of(gid), before)
        inst = self.s.udts[new]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        # (and Apply to all and Update from UDT see it as any other)
        self.assertEqual(len(U.instances(self.p, DOL)), 2)
        plans, _shown = self.props(gid, values={"HP": "25"}, all_=True)
        self.assertEqual(len(plans), 2)
        self.assertEqual(self.s.udts[new]["values"]["HP"], "25")
        self.p.undo()
        self.p.undo()
        self.p.undo()
        self.assertEqual(len(self.s.udts), 1)

    def test_copy_far_off_keeps_its_exact_place(self):
        # (the long battery, 0.30, seed 5202: a copy put 3155.51210538" off took its place
        # rounded to 6 places, 4e-7" off its own parts: its phases no longer met the points
        # the UDT starts them from, and a rebuild would have drawn the new parts there)
        gid = self.place(self.udt(), (2.0, 10.0))
        dx = 3155.51210538
        new = self.copy_cmd(gid, (dx, 0.0))
        inst = self.s.udts[new]
        self.assertAlmostEqual(inst["at"][0], 2.0 + dx, places=9)
        self.assertAlmostEqual(inst["at"][1], 10.0, places=9)
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        # (rebuilt with a part added, the new part's wires meet the copy's own)
        self.props(new, {"Line reactor": U.INCLUDED})
        inst = self.s.udts[new]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)

    def test_copy_turned_rebuilds_where_it_is(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        ids = set(self.s.udts[gid]["members"].values())
        self.v.set_selection(ids)
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "20,0")
        if self.v.cmd is not None:
            self.v.cmd.enter()
        new = [g for g in self.s.udts if g != gid][0]
        made = set(self.s.udts[new]["members"].values())
        self.v.set_selection(made)
        self.v.run(C.RotateCmd)
        type_in(self.v, "22,10", "90")
        plans, _shown = self.props(new, {"Protection": "Fuses"})
        self.assertEqual(plans[0].warnings, [])
        inst = self.s.udts[new]
        self.assertEqual(inst["angle"], 90.0)
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)

    def test_copy_of_part_of_it_stays_plain_parts(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        syms = [e.id for e in self.by_role(gid).values() if isinstance(e, M.Insert)]
        self.v.set_selection(set(syms[:3]))
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "0,-5")
        self.assertEqual(len(self.s.udts), 1)

    def test_copy_without_its_wires_leaves_them_out(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        syms = {r for r, e in self.by_role(gid).items() if isinstance(e, M.Insert)}
        ids = {e.id for r, e in self.by_role(gid).items() if r in syms}
        self.v.set_selection(ids)
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "0,-5")
        new = [g for g in self.s.udts if g != gid][0]
        inst = self.s.udts[new]
        self.assertEqual(set(inst["members"]), syms)
        self.assertEqual(set(inst["gone"]), set(self.s.udts[gid]["members"]) - syms)
        # (a rebuild doesn't put the wires back: left behind, as erased by hand)
        plans, _shown = self.props(new, values={"HP": "15"})
        self.assertEqual(plans[0].add, [])

    def test_clipboard_paste_and_paste_in_place(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        gid = self.place(self.udt(DOL), (2.0, 10.0), {"Protection": "Circuit breaker"})
        self.v.set_selection(set(self.s.udts[gid]["members"].values()))
        self.assertTrue(self.win.copy_clip())
        self.win.paste()
        type_in(self.v, "%g,%g" % (self.v.cmd.base_pt[0], self.v.cmd.base_pt[1] - 6.0))
        self.assertEqual(len(self.s.udts), 2)
        new = [g for g in self.s.udts if g != gid][0]
        self.assert_new_instance(gid, new)
        self.assertAlmostEqual(self.s.udts[new]["at"][1], 4.0)
        # (pasted with Enter on another sheet: where it was, a placed UDT of that sheet)
        with self.p.edit("sheet") as ed:
            other = self.p.make_sheet("Two")
            ed.add_sheet(other)
        self.v.show_sheet(other.id)
        self.win.paste()
        QTest.keyClick(self.v, Qt.Key_Return)
        self.assertIsNone(self.v.cmd)
        self.assertEqual(len(other.udts), 1)
        g2 = list(other.udts)[0]
        self.assertEqual(other.udts[g2]["at"], [2.0, 10.0])
        self.assert_new_instance(gid, g2, other)
        self.assertTrue(all(t.startswith(("CB2", "DS2", "MTR2", "M2", "OL2"))
                            for t in self.udt_tags(g2, other)), self.udt_tags(g2, other))

    def test_paste_into_another_project(self):
        from tests.util import window as new_window
        gid = self.place(self.udt(DOL), (2.0, 10.0))
        self.v.set_selection(set(self.s.udts[gid]["members"].values()))
        self.assertTrue(self.win.copy_clip())
        win2, v2 = new_window()
        try:
            win2.paste()
            type_in(v2, "5,5")
            s2 = v2.sheet()
            self.assertEqual(len(s2.udts), 1)
            g2 = list(s2.udts)[0]
            inst = s2.udts[g2]
            self.assertEqual(inst["type"], self.s.udts[gid]["type"])
            self.assertEqual(U.type_of(s2, inst).name, DOL)
            BC.udt_motor_circuit(v2.project, s2, U.type_of(s2, inst), inst)
            # (UDT properties there works on it)
            v2.set_selection({list(inst["members"].values())[0]})
            plan = U.plan(v2.project, s2, g2, {"Protection": "Circuit breaker"})
            self.assertEqual(plan.warnings, [])
        finally:
            v2.project.saved_at = len(v2.project.undo_stack)
            win2.close()

    def test_duplicate_sheet_and_ctrl_drag(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        self.win.duplicate_sheet()
        other = self.v.sheet()
        self.assertIsNot(other, self.s)
        self.assertEqual(len(other.udts), 1)
        g2 = list(other.udts)[0]
        self.assertNotEqual(g2, gid)
        self.assertEqual(set(other.udts[g2]["members"].values()) - set(other.entities), set())
        self.assert_new_instance(gid, g2, other)
        # (Ctrl+drag: a copy, a placed UDT of its own too; let go with Ctrl held)
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        self.v.show_sheet(self.s.id)
        ids = set(self.s.udts[gid]["members"].values())
        self.v.set_selection(ids)
        self.v._drag = {"start": (2.0, 10.0), "moved": True,
                        "ents": [self.s.entities[i] for i in sorted(ids)]}
        at = self.v.to_screen((2.0, 4.0))
        self.v.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPointF(at),
                                             QPointF(at), Qt.LeftButton, Qt.NoButton,
                                             Qt.ControlModifier))
        self.assertEqual(len(self.s.udts), 2)
        new = [g for g in self.s.udts if g != gid][0]
        self.assert_new_instance(gid, new)

    # ---- the terminals' strip (the owner, Nov 27 2026) ---------------------------------------
    def terms(self, gid):
        u = U.type_of(self.s, self.s.udts[gid])
        on = self.by_role(gid)
        return [on[m["role"]] for m in u.members if m["role"] in on and
                getattr(on[m["role"]], "block", "").startswith("Terminal")]

    def insert_on(self, udt, at, strip, choices=None):
        self.win.ask_udt = lambda: (udt, choices or {}, {}, strip)
        before = set(self.s.udts)
        try:
            self.win.insert_udt()
        finally:
            self.win.__dict__.pop("ask_udt", None)
        type_in(self.v, "%g,%g" % at)
        return (set(self.s.udts) - before).pop()

    def test_terminals_blank_strip_left_for_later(self):
        gid = self.insert_on(self.udt(), (2.0, 10.0), "")
        got = self.terms(gid)
        self.assertEqual(len(got), 3)
        self.assertTrue(all(not t.attrs.get("TAG") and not t.attrs.get("TERM") for t in got))
        from kanzonascad import strips
        self.assertEqual([st.tag for st in strips.find(self.p, wires=False)], ["TB?"])
        self.assertEqual(self.p.settings.get(U.STRIP_SETTING, ""), "")

    def test_terminals_on_a_new_strip_then_its_next_numbers(self):
        new = U.new_strip_tag(self.p, self.s)
        self.assertEqual(new, "TB101")
        a = self.insert_on(self.udt(), (2.0, 10.0), new)
        self.assertEqual([(t.attrs["TAG"], t.attrs["TERM"]) for t in self.terms(a)],
                         [("TB101", "1"), ("TB101", "2"), ("TB101", "3")])
        self.assertEqual(self.p.settings[U.STRIP_SETTING], "TB101")    # (remembered)
        self.assertEqual(U.new_strip_tag(self.p, self.s), "TB102")
        b = self.insert_on(self.udt(DOL), (2.0, 4.0), "TB101")
        self.assertEqual([t.attrs["TERM"] for t in self.terms(b)], ["4", "5", "6"])
        from kanzonascad import strips
        st = [x for x in strips.find(self.p) if x.tag == "TB101"][0]
        self.assertEqual([r.num for r in st.rows], ["1", "2", "3", "4", "5", "6"])
        # (a copy's terminals: the strip's next numbers)
        c = self.copy_cmd(a, (12.0, 0.0))
        self.assertEqual([(t.attrs["TAG"], t.attrs["TERM"]) for t in self.terms(c)],
                         [("TB101", "7"), ("TB101", "8"), ("TB101", "9")])
        self.p.undo()
        # (a rebuild keeps them: on their strip, their numbers)
        self.props(b, {"Protection": "Circuit breaker"})
        self.assertEqual([t.attrs["TERM"] for t in self.terms(b)], ["4", "5", "6"])
        # (Update from UDT replacing a terminal: its strip and number kept)
        d = self.udt(DOL).to_dict()
        t = [m for m in d["members"] if m["entity"].get("block") == "Terminal"][1]
        t["entity"]["attrs"] = {"DESC": "Field"}
        plans = U.update_plans(self.p, U.Udt.from_dict(d))
        with self.p.edit("update") as ed:
            for pl in plans:
                U.apply(ed, self.p, pl)
        self.assertEqual([(x.attrs["TAG"], x.attrs["TERM"]) for x in self.terms(b)],
                         [("TB101", "4"), ("TB101", "5"), ("TB101", "6")])
        # (undone: the project's last choice back as it was)
        self.p.undo()
        self.p.undo()
        self.p.undo()
        self.p.undo()
        self.assertEqual(self.p.settings.get(U.STRIP_SETTING, ""), "")

    def test_terminals_on_a_strip_device_after_its_spares(self):
        from kanzonascad import strips, tags
        sd = self.lib.get("symbol", "Terminal strip")
        with self.p.edit("strip") as ed:
            ed.block(sd)
            dev = ed.add(self.s, M.Insert(sd.name, (1, 1), defn=self.p.blocks[sd.name],
                                          attrs=tags.new_attrs(self.p, self.s, sd, {})))
            ed.project_settings({strips.SETTING: {dev.attrs["DEV"]: {"spares": ["1", "3"]}}})
        gid = self.insert_on(self.udt(), (2.0, 10.0), dev.attrs["TAG"])
        got = self.terms(gid)
        self.assertEqual([t.attrs["TERM"] for t in got], ["2", "4", "5"])
        self.assertTrue(all(t.attrs["PARENT"] == dev.attrs["DEV"] and
                            t.attrs["TAG"] == dev.attrs["TAG"] for t in got))
        st = [x for x in strips.find(self.p) if x.tag == dev.attrs["TAG"]][0]
        self.assertIs(st.dev[1].id, dev.id)

    def test_terminals_on_a_tag_two_strips_share(self):
        # (two strips of one tag, a strip symbol's typed twice, say: the numbers of both taken)
        from kanzonascad import tags
        sd, td = self.lib.get("symbol", "Terminal strip"), self.lib.get("symbol", "Terminal")
        with self.p.edit("strips") as ed:
            for b in (sd, td):
                ed.block(b)
            for i in range(2):
                dev = ed.add(self.s, M.Insert(sd.name, (1, 1 + i), defn=self.p.blocks[sd.name],
                                              attrs=tags.new_attrs(self.p, self.s, sd, {
                                                  "TAG": "TB9", "TAG_LOCK": "1"})))
                ed.add(self.s, M.Insert(td.name, (3, 1 + i), defn=self.p.blocks[td.name],
                                        attrs={"TAG": "TB9", "PARENT": dev.attrs["DEV"],
                                               "TERM": str(1 + 3 * i)}))
        gid = self.insert_on(self.udt(), (2.0, 10.0), "TB9")
        self.assertEqual([t.attrs["TERM"] for t in self.terms(gid)], ["2", "3", "5"])

    def test_loose_terminals_numbered_in_the_strip_window(self):
        # (a UDT's terminals on no strip yet: three without a number, TB?; one numbered in the
        # Terminal strips window was shown where it was, under the other two, but the strip
        # read back from the drawing has it first: a strip's order is kept by number)
        from kanzonascad import strip_window, strips
        self.insert_on(self.udt(), (2.0, 10.0), "")
        dlg = strip_window.StripEditorDialog(self.win, self.p)
        try:
            dlg.show_strip(0)
            t = dlg.table
            self.assertEqual([t.item(i, 0).text() for i in range(3)], ["?", "?", "?"])
            t.item(2, 0).setText("7")
            shown = [t.item(i, 0).text() for i in range(t.rowCount())]
            self.assertEqual(shown, ["7", "?", "?"])
            self.assertEqual(dlg.picked(), [0])                # (the row typed, still picked)
            lay = dlg.layout_of(0)
            lay.move([0], 1)                                   # (down among the loose: stays)
            self.assertEqual([r["num"] for r in lay.rows], ["7", "", ""])
            at = lay.add_spare(1)                              # (after a loose one)
            self.assertEqual((at, lay.rows[at]["num"]), (1, "8"))
            self.assertEqual([r["num"] for r in lay.rows], ["7", "8", "", ""])
            with self.p.edit("strips") as ed:
                strips.apply(ed, self.p, dlg.changed())
        finally:
            dlg.deleteLater()
        st = strips.find(self.p, wires=False)[0]
        self.assertEqual([r.num for r in st.rows], ["7", "8", "", ""])

    def test_browser_offers_the_strips_and_the_last_choice(self):
        from kanzonascad.udt_window import UdtBrowser
        self.insert_on(self.udt(), (2.0, 10.0), "TB101")
        dlg = UdtBrowser(self.win, self.lib, project=self.p, sheet=self.s)
        try:
            items = [dlg.strip.itemData(i) for i in range(dlg.strip.count())]
            self.assertEqual(items, ["", "TB101", "TB102"])      # (none, TB101, a new one)
            self.assertEqual(dlg.strip.currentData(), "TB101")    # (the last choice)
            self.assertFalse(dlg.strip_box.isHidden())
            dlg.strip.setCurrentIndex(2)
            dlg.insert()
            self.assertEqual(dlg.chosen[3], "TB102")
        finally:
            dlg.deleteLater()
        mine = self.udt().copy(name="No terminals", members=[
            m for m in self.udt().to_dict()["members"]
            if m["entity"].get("block") != "Terminal"])
        self.assertFalse(U.has_terminals(mine))
        self.lib.save_udt(mine)
        dlg = UdtBrowser(self.win, self.lib, project=self.p, sheet=self.s)
        try:
            it = [dlg.tree.topLevelItem(0).child(i) for i in
                  range(dlg.tree.topLevelItem(0).childCount())]
            dlg.tree.setCurrentItem([x for x in it if x.data(0, 0x0100) == "No terminals"][0])
            self.assertTrue(dlg.strip_box.isHidden())
            self.assertIsNone(dlg.strip_choice())
        finally:
            dlg.deleteLater()

    # ---- an IEC 60617 project (the owner, Nov 27 2026) --------------------------------------
    def iec(self):
        with self.p.edit("standard") as ed:
            ed.project_settings({"symbol_standard": "iec"})

    def test_iec_project_takes_iec_symbols_and_letters(self):
        self.iec()
        gid = self.insert_on(self.udt(DOL), (2.0, 10.0), "")
        blocks = self.blocks_of(gid)
        self.assertEqual(blocks, sorted([
            "Disconnector 3-pole (IEC)", "Fuses 3-pole (IEC)",
            "Contactor main contacts 3-pole (IEC)", "Thermal overload 3-pole (IEC)",
            "Terminal (IEC)", "Terminal (IEC)", "Terminal (IEC)", "Motor 3-phase (IEC)",
            "Contactor coil (IEC)", "Overload contact NC (IEC)"]))
        tags_ = self.udt_tags(gid)
        self.assertEqual(tags_, ["F101", "F102", "M101", "Q101", "Q102"], tags_)
        inst = self.s.udts[gid]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        # (the drive and reactors have no IEC symbol here: JIC, tagged with IEC letters)
        g2 = self.insert_on(self.udt(VFD), (2.0, 4.0), "", {"Line reactor": U.INCLUDED})
        self.assertIn("Variable frequency drive", self.blocks_of(g2))
        lr = [e for e in self.by_role(g2).values() if getattr(e, "block", "") ==
              "Reactor 3-pole"][0]
        self.assertEqual(lr.attrs["TAG"], "R101")       # (81346-2's R: a reactor)
        self.assertIn("Motor protection circuit breaker 3-pole", self.blocks_of(g2))
        self.assertIn("Motor 3-phase (IEC)", self.blocks_of(g2))
        vfd = [e for e in self.by_role(g2).values() if getattr(e, "block", "") ==
               "Variable frequency drive"][0]
        self.assertEqual(vfd.attrs["TAG"], "T101")
        inst = self.s.udts[g2]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)
        # (its choice rebuilt, as in a JIC project; Update from UDT finds nothing changed)
        self.props(gid, {"Protection": "Circuit breaker"})
        self.assertIn("Circuit breaker 3-pole (IEC)", self.blocks_of(gid))
        seen = []
        self.win.confirm_udt_changes = lambda title, intro, plans, *a, **k: (
            seen.append(plans) or (plans, {}))
        try:
            self.v.set_selection(set())
            self.assertIsNone(self.win.update_from_udt())
        finally:
            self.win.__dict__.pop("confirm_udt_changes", None)
        self.assertEqual(seen, [[]])
        self.assertEqual(U.new_strip_tag(self.p, self.s), "X101")

    def test_jic_udt_brought_to_iec_by_update(self):
        gid = self.insert_on(self.udt(DOL), (2.0, 10.0), "")
        tags_ = self.udt_tags(gid)
        self.iec()
        self.win.confirm_udt_changes = lambda title, intro, plans, *a, **k: (plans, {})
        try:
            self.v.set_selection(set())
            plans = self.win.update_from_udt()
        finally:
            self.win.__dict__.pop("confirm_udt_changes", None)
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].warnings, [])
        self.assertIn("Motor 3-phase (IEC)", self.blocks_of(gid))
        self.assertEqual(self.udt_tags(gid), tags_)        # (kept: Retag gives the letters)
        inst = self.s.udts[gid]
        BC.udt_motor_circuit(self.p, self.s, U.type_of(self.s, inst), inst)

    def test_swap_only_where_the_pins_line_up(self):
        u = self.udt(DOL)

        def lookup(name):
            d = self.lib.get("symbol", name)
            if d is not None and name == "Fuses 3-pole (IEC)":
                d = M.BlockDef.from_dict(dict(d.to_dict(), pins=[
                    dict(p, pos=(p["pos"][0] - 0.25, p["pos"][1])) for p in d.to_dict()["pins"]]))
            return d
        got = U.swaps(u, "iec", lookup)
        self.assertNotIn("Fuses 3-pole", got)             # (moved pins: left JIC)
        self.assertEqual(got["Motor 3-phase"].name, "Motor 3-phase (IEC)")
        def sym(name):
            return self.lib.get("symbol", name)
        self.assertIs(U.for_standard(u, "jic", sym), u)
        back = U.for_standard(U.for_standard(u, "iec", sym), "jic", sym)
        self.assertEqual(back.key(), u.key())

    # ---- with 0.28's pin numbers and 0.27's near misses --------------------------------------
    def test_contact_pin_numbers_are_not_hand_edits(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0))
        olc = [e for e in self.by_role(gid).values() if getattr(e, "block", "") ==
               "Overload contact NC"][0]
        self.assertEqual((olc.attrs["TERM01"], olc.attrs["TERM02"]), ("95", "96"))
        d = self.udt(DOL).to_dict()
        m = [m for m in d["members"] if m["entity"].get("block") == "Overload contact NC"][0]
        m["entity"]["attrs"] = dict(m["entity"]["attrs"], DESC="OL trip")
        plans = U.update_plans(self.p, U.Udt.from_dict(d))
        self.assertEqual(plans[0].warnings, [])
        self.assertEqual([r for r, _i, _m in plans[0].replace], [m["role"]])
        with self.p.edit("update") as ed:
            U.apply(ed, self.p, plans[0])
        olc = self.by_role(gid)[m["role"]]
        self.assertEqual((olc.attrs["TERM01"], olc.attrs["TERM02"], olc.attrs["DESC"]),
                         ("95", "96", "OL trip"))

    def test_no_near_misses_placed_any_way(self):
        from kanzonascad import nearmiss
        for i, (name, typed) in enumerate(((VFD, ()), (DOL, ("R",)), (VFD, ("R", "R")))):
            self.place(self.udt(name), (2.0 + 12 * i, 10.0), None, None, *typed)
        self.iec()
        self.place(self.udt(DOL), (2.0, 2.0))
        self.assertEqual(nearmiss.found(self.s), [])

    def test_detach(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        ids = set(self.s.udts[gid]["members"].values())
        self.v.set_selection({min(ids)})
        self.assertEqual(self.win.detach_udt(), 1)
        self.assertEqual(self.s.udts, {})
        self.assertEqual(self.s.udt_types, {})
        self.assertTrue(ids <= set(self.s.entities))
        self.p.undo()
        self.assertIn(gid, self.s.udts)

    # ---- ratings -----------------------------------------------------------------------------
    def test_override_kept_through_rebuilds(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0), values={"HP": "10"})
        fu = [r for r, e in self.by_role(gid).items() if getattr(e, "block", "") ==
              "Fuses 3-pole"][0]
        self.props(gid, overrides={fu: {"RATING": "20A"}})
        self.assertEqual(self.by_role(gid)[fu].attrs["RATING"], "20A")
        self.props(gid, values={"HP": "25"})
        self.assertEqual(self.by_role(gid)[fu].attrs["RATING"], "20A")
        rows = [r for r in U.rating_rows(self.p, self.s, gid) if r["role"] == fu and
                r["attr"] == "RATING"]
        self.assertTrue(rows[0]["overridden"])
        self.assertEqual(rows[0]["auto"], "60A")            # (175 % of 34 A: 59.5)
        self.props(gid, overrides={fu: {"RATING": ""}})     # (back to automatic)
        self.assertEqual(self.by_role(gid)[fu].attrs["RATING"], "60A")

    def test_rating_typed_on_the_drawing_is_an_override(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0), values={"HP": "10"})
        ol = [e for e in self.by_role(gid).values() if getattr(e, "block", "") ==
              "Overload heaters 3-pole"][0]
        self.assertEqual(ol.attrs["AMPS"], "14")
        with self.p.edit("typed") as ed:
            ed.change(self.s, ol.copy(attrs=dict(ol.attrs, AMPS="13.1")))
        plans, shown = self.props(gid, values={"HP": "5"})
        self.assertEqual(self.s.entities[ol.id].attrs["AMPS"], "13.1")
        self.assertEqual(shown, [])                         # (not a hand edit: a rating)
        motor = [e for e in self.by_role(gid).values() if getattr(e, "block", "") ==
                 "Motor 3-phase"][0]
        self.assertEqual(motor.attrs["FLA"], "7.6")

    # ---- the owner's rule: ratings per placed UDT, all of them only when asked ---------------
    def test_values_change_only_this_one_unless_applied_to_all(self):
        a = self.place(self.udt(DOL), (2.0, 10.0), values={"HP": "10"})
        b = self.place(self.udt(DOL), (2.0, 4.0), values={"HP": "10"})
        c = self.place(self.udt(DOL), (14.0, 4.0), values={"HP": "10"})

        def hp(g):
            return [e for e in self.by_role(g).values() if getattr(e, "block", "") ==
                    "Motor 3-phase"][0].attrs["HP"]

        def fuse(g):
            return [(r, e) for r, e in self.by_role(g).items() if getattr(e, "block", "") ==
                    "Fuses 3-pole"][0]
        self.props(a, values={"HP": "5"})
        self.assertEqual((hp(a), hp(b), hp(c)), ("5", "10", "10"))
        # (an override of its own on c)
        rc, _e = fuse(c)
        self.props(c, overrides={rc: {"RATING": "40A"}})
        n_undo = len(self.p.undo_stack)
        plans, shown = self.props(a, values={"HP": "25"}, all_=True)
        self.assertEqual(len(self.p.undo_stack), n_undo + 1)         # (one step)
        self.assertEqual(len(shown), 1)                              # (shown first)
        self.assertEqual(len(plans), 3)
        self.assertEqual((hp(a), hp(b), hp(c)), ("25", "25", "25"))
        self.assertEqual(fuse(b)[1].attrs["RATING"], "60A")
        self.assertEqual(fuse(c)[1].attrs["RATING"], "40A")         # (its own override kept)
        self.props(a, values={"HP": "10"}, all_=True, replace=True)
        self.assertEqual(fuse(c)[1].attrs["RATING"], "25A")         # (replaced when asked)
        self.p.undo()
        self.assertEqual(fuse(c)[1].attrs["RATING"], "40A")

    def test_cancelled_apply_to_all_changes_nothing(self):
        a = self.place(self.udt(DOL), (2.0, 10.0))
        self.place(self.udt(DOL), (2.0, 4.0))
        n = len(self.p.undo_stack)
        got, _shown = self.props(a, values={"HP": "25"}, all_=True, confirm=False)
        self.assertIsNone(got)
        self.assertEqual(len(self.p.undo_stack), n)

    # ---- your own, Update from UDT -------------------------------------------------------------
    def test_make_your_own_from_a_selection(self):
        lib = self.lib
        v = self.v
        for name, at in (("Disconnect 3-pole", "2,5"), ("Fuses 3-pole", "4,5"),
                         ("Motor 3-phase", "8,5")):
            v.run(C.InsertCmd, lib.get("symbol", name), {})
            type_in(v, at)
        for x0, x1 in ((0.5, 2.0), (2.5, 4.0), (4.5, 8.0)):
            for dy in (0.0, -0.5, -1.0):
                v.run(C.WireCmd)
                type_in(v, "%g,%g" % (x0, 5 + dy), "%g,%g" % (x1, 5 + dy))
                if v.cmd is not None:
                    v.cmd.enter()
        ids = set(self.s.entities)
        v.set_selection(ids)
        made = []

        def editor(udt):
            # (as in the UDT editor: the fuses made an optional part, a breaker their
            # alternative... then saved)
            fu = [m["role"] for m in udt.members if m["entity"].get("block") == "Fuses 3-pole"]
            u = U.make_choice(udt, set(fu), "Protection", "Fuses")
            u = U.add_alternative(u, "Protection", "Breaker",
                                  lib.get("symbol", "Circuit breaker 3-pole"), self.p)
            made.append(u)
            return self.win.save_udt(u)
        self.win.ask_udt_details = lambda: ("My motor", "Mine", "")
        self.win.edit_udt_definition = editor
        try:
            v.run(C.MakeUdtCmd)
            type_in(v, "0.5,5")
        finally:
            self.win.__dict__.pop("ask_udt_details", None)
            self.win.__dict__.pop("edit_udt_definition", None)
        self.assertEqual(lib.udt_where("My motor"), "first")
        mine = lib.udts()[0]["My motor"]
        self.assertEqual(mine.slots[0]["alternatives"], ["Fuses", "Breaker"])
        gid = self.place(mine, (2.0, 12.0), {"Protection": "Breaker"})
        self.assertIn("Circuit breaker 3-pole", self.blocks_of(gid))
        self.assertNotIn("Fuses 3-pole", self.blocks_of(gid))
        motor = [e for e in self.by_role(gid).values() if getattr(e, "block", "") ==
                 "Motor 3-phase"][0]
        joined = BC.connected(self.s, (0, 10, 12, 13))
        for i in range(3):
            self.assertTrue(joined((2.0, 12.0 - 0.5 * i), dict(motor.pin_points())[
                "T%d" % (i + 1)]))

    def test_editor_steps(self):
        u = self.udt(DOL)
        cb = [m["role"] for m in u.members if m["entity"].get("block") == "Disconnect 3-pole"]
        got = U.make_optional(u, set(cb), "Disconnect", self.p)
        s = got.slot("Disconnect")
        self.assertTrue(s["optional"])
        self.assertEqual(len([m for m in got.members if m["alt"] == U.LEFT_OUT]), 3)
        with self.assertRaises(ValueError):
            U.make_optional(got, set(cb), "Again", self.p)
        back = U.remove_slot(got, "Disconnect")
        self.assertEqual(len(back.members), len(u.members))
        with self.assertRaises(ValueError):
            U.remove_alternative(got.copy(slots=[dict(s, alternatives=[U.INCLUDED])]),
                                 "Disconnect", U.INCLUDED)
        self.assertEqual(U.pin_pairs(self.lib.get("symbol", "Fuse")),
                         [((-0.25, 0.0), (0.25, 0.0))])

    def test_editor_window(self):
        from kanzonascad.udt_window import UdtEditor
        blocks, _bad = self.lib.blocks("symbol")
        dlg = UdtEditor(self.win, self.udt(DOL), blocks, self.p)
        try:
            it = dlg.tree.topLevelItem(0)
            self.assertEqual(it.text(0), "Always there")
            ds = [it.child(i) for i in range(it.childCount())
                  if "Disconnect" in it.child(i).text(0)][0]
            ds.setSelected(True)
            self.assertTrue(dlg.make_optional("Disconnect"))
            self.assertIsNotNone(dlg.udt.slot("Disconnect"))
            role = [m["role"] for m in dlg.udt.members
                    if m["entity"].get("block") == "Disconnect 3-pole"][0]
            self.assertTrue(dlg.add_rule(role, attr="RATING"))
            dlg.e_name.setText("Starter, my style")
            dlg.save()
            got = dlg.result_udt
            self.assertEqual(got.name, "Starter, my style")
            self.assertEqual(len(got.ratings), len(self.udt(DOL).ratings) + 1)
            self.assertTrue(dlg.picture.pixmap() is not None)
        finally:
            dlg.deleteLater()

    def test_update_from_udt_shows_first_keeps_own_values(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0), values={"HP": "10"})
        old = self.udt(DOL)
        fu = [m["role"] for m in old.members if m["entity"].get("block") == "Fuses 3-pole"][0]
        # (the library's copy changed: the fuses' percent 150, a load reactor's place left
        # out of it... and its defaults 20 HP)
        rules = [dict(r, percent=150.0) if r["role"] == fu and r["attr"] == "RATING" else r
                 for r in old.ratings]
        vals = [dict(x, default="20") if x["key"] == "HP" else x for x in old.values]
        self.lib.save_udt(old.copy(ratings=rules, values=vals, description="v2"))
        seen = []

        def confirm(title, intro, plans, options=(), recompute=None):
            seen.append((plans, options))
            return (recompute({"rules": self.rules}) if recompute else plans), {}
        self.win.confirm_udt_changes = confirm
        try:
            self.rules = False
            self.v.set_selection(set())
            got = self.win.update_from_udt()
            self.assertEqual(len(got), 1)
            self.assertEqual([k for k, _t in seen[0][1]], ["rules", "replace"])
            inst = self.s.udts[gid]
            self.assertEqual(inst["type"], self.udt(DOL).key())
            self.assertEqual(inst["values"]["HP"], "10")    # (its own kept)
            fus = self.by_role(gid)[fu]
            self.assertEqual(fus.attrs["RATING"], "25A")    # (its own rule kept: 175 %)
            self.rules = True
            self.win.update_from_udt()
            inst = self.s.udts[gid]
            self.assertEqual(inst["values"]["HP"], "20")
            self.assertEqual(self.by_role(gid)[fu].attrs["RATING"], "45A")  # (150 % of 27)
        finally:
            self.win.__dict__.pop("confirm_udt_changes", None)

    def test_update_from_udt_adds_and_replaces(self):
        gid = self.place(self.udt(DOL), (2.0, 10.0))
        tags = {e.attrs.get("TAG") for e in self.s.inserts() if e.attrs.get("TAG")}
        old = self.udt(DOL)
        d = old.to_dict()
        ds = [m for m in d["members"] if m["entity"].get("block") == "Disconnect 3-pole"][0]
        ds["entity"]["attrs"] = dict(ds["entity"].get("attrs", {}), DESC="Main disconnect")
        new = U.Udt.from_dict(d)
        plans = U.update_plans(self.p, new)
        self.assertEqual(len(plans), 1)
        self.assertEqual([r for r, _i, _m in plans[0].replace], [ds["role"]])
        with self.p.edit("update") as ed:
            U.apply(ed, self.p, plans[0])
        got = self.by_role(gid)[ds["role"]]
        self.assertEqual(got.attrs["DESC"], "Main disconnect")
        self.assertEqual({e.attrs.get("TAG") for e in self.s.inserts() if e.attrs.get("TAG")},
                         tags)

    def test_browser(self):
        from kanzonascad.udt_window import UdtBrowser
        dlg = UdtBrowser(self.win, self.lib)
        try:
            names = [dlg.tree.topLevelItem(0).child(i).data(0, 0x0100)
                     for i in range(dlg.tree.topLevelItem(0).childCount())]
            self.assertEqual(sorted(names), sorted([VFD, DOL]))
            dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0).child(names.index(VFD)))
            self.assertFalse(dlg.b_delete.isEnabled())          # (built in)
            _s, w = dlg.form.widgets["Line reactor"]
            w.setChecked(True)
            dlg.form.edits["HP"].setText("7-1/2")
            dlg.insert()
            udt, choices, values, strip = dlg.chosen
            self.assertIsNone(strip)                            # (no project: not asked)
            self.assertEqual(udt.name, VFD)
            self.assertEqual(choices["Line reactor"], U.INCLUDED)
            self.assertEqual(values["HP"], "7-1/2")
        finally:
            dlg.deleteLater()

    def test_properties_window(self):
        from kanzonascad.udt_window import UdtPropertiesDialog
        gid = self.place(self.udt(DOL), (2.0, 10.0), values={"HP": "10"})
        dlg = UdtPropertiesDialog(self.win, self.p, self.s, gid, others=0)
        try:
            self.assertFalse(dlg.all.isChecked())               # (off to start)
            self.assertFalse(dlg.all.isEnabled())
            rows = {(r["what"], r["attr"]): i for i, r in enumerate(dlg.rows)}
            i = rows[("FU101", "RATING")]
            self.assertEqual(dlg.table.item(i, 3).text(), "25A")
            dlg.form.edits["HP"].setText("25")
            self.assertEqual(dlg.table.item(i, 3).text(), "60A")
            dlg.table.item(i, 3).setText("50A")
            self.assertEqual(dlg.table.item(i, 4).text(), "overridden")
            dlg.ok()
            self.assertEqual(dlg.result["values"]["HP"], "25")
            role = dlg.rows[i]["role"]
            self.assertEqual(dlg.result["overrides"], {role: {"RATING": "50A"}})
            self.assertFalse(dlg.result["all"])
        finally:
            dlg.deleteLater()


def BC_norm(d):
    """A project's dict with each sheet's objects in id order (undo puts one back at the end)."""
    import json
    d = json.loads(json.dumps(d, sort_keys=True))
    for s in d["sheets"]:
        s["entities"].sort(key=lambda e: e["id"])
    return d


if __name__ == "__main__":
    unittest.main()
