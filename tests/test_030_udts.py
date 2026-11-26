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

    def test_copies_are_plain_parts(self):
        gid = self.place(self.udt(), (2.0, 10.0))
        ids = set(self.s.udts[gid]["members"].values())
        self.v.set_selection(ids)
        self.v.run(C.CopyCmd)
        type_in(self.v, "0,0", "0,-5")
        new = set(self.s.entities) - ids
        self.assertTrue(new)
        self.assertTrue(all(U.find(self.s, i) is None for i in new))
        self.assertEqual(len(self.s.udts), 1)

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
            udt, choices, values = dlg.chosen
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
