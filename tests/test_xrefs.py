import unittest

from tests.util import APP, window, type_in

from kanzonascad import commands as C
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import xrefs


class XrefTest(unittest.TestCase):
    """Contacts linked to their device; cross-references worked out from the drawing."""

    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = False
        lib = self.win.library
        self.coil = lib.get("symbol", "Relay coil")
        self.motor_coil = lib.get("symbol", "Contactor coil")
        self.no = lib.get("symbol", "Contact NO")
        self.nc = lib.get("symbol", "Contact NC")
        self.p = self.v.project
        with self.p.edit("pages") as ed:
            ed.sheet_meta(self.v.sheet(), number="6")
            ed.add_sheet(self.p.make_sheet("Second"))
        self.s6, self.s7 = self.p.sheets[0], self.p.sheets[1]
        with self.p.edit("page 7") as ed:
            ed.sheet_meta(self.s7, number="7")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def place(self, defn, at, *more):
        self.v.run(C.InsertCmd, defn, {})
        type_in(self.v, "%g,%g" % at, *more)
        return max((e for e in self.v.sheet().entities.values() if isinstance(e, M.Insert)),
                   key=lambda e: e.id)

    def now(self, sheet, e):
        return sheet.entities[e.id]

    def test_contacts_follow_their_device(self):
        coil = self.place(self.coil, (3, 9))
        motor = self.place(self.motor_coil, (3, 6))
        a = self.place(self.no, (8, 9), "")                 # Enter: the nearest CR coil
        b = self.place(self.nc, (8, 6), "m601")             # a typed tag (any case)
        self.assertEqual(self.now(self.s6, a).attrs["TAG"], "CR601")
        self.assertEqual(self.now(self.s6, a).attrs["PARENT"], coil.attrs["DEV"])
        self.assertEqual(self.now(self.s6, b).attrs["PARENT"], motor.attrs["DEV"])
        # the coil renamed: its contact follows; undo puts both back
        with self.p.edit("retag") as ed:
            ed.change(self.s6, self.now(self.s6, coil).copy(
                attrs=dict(coil.attrs, TAG="CR650", TAG_LOCK="1")))
        self.assertEqual(self.now(self.s6, a).attrs["TAG"], "CR650")
        self.p.undo()
        self.assertEqual(self.now(self.s6, a).attrs["TAG"], "CR601")
        # its sheet renumbered: coil and contact both become CR8xx
        with self.p.edit("page 8") as ed:
            ed.sheet_meta(self.s6, number="8")
        self.assertEqual(self.now(self.s6, a).attrs["TAG"], "CR801")
        self.assertEqual(self.now(self.s6, b).attrs["TAG"], "M801")

    def test_a_tag_typed_before_its_device_links_later(self):
        a = self.place(self.coil, (3, 9))
        c = self.place(self.no, (8, 9), "CR605")            # no CR605 yet
        self.assertNotIn("PARENT", self.now(self.s6, c).attrs)
        with self.p.edit("retag") as ed:
            ed.change(self.s6, self.now(self.s6, a).copy(
                attrs=dict(a.attrs, TAG="CR605", TAG_LOCK="1")))
        self.assertEqual(self.now(self.s6, c).attrs.get("PARENT"), a.attrs["DEV"])

    def test_a_contact_with_nothing_to_link_to_is_placed_unlinked(self):
        c = self.place(self.no, (8, 9))
        self.assertIsNone(self.v.cmd)
        self.assertNotIn("PARENT", self.now(self.s6, c).attrs)
        self.assertEqual([t[2] for t in xrefs.live(self.p, self.s6)], ["?"])

    def test_cross_references(self):
        coil = self.place(self.coil, (3, 9))
        self.place(self.no, (8, 9), "")
        self.place(self.nc, (8, 4), "")
        self.v.show_sheet(self.s7.id)
        self.place(self.no, (5, 9), "CR601")                # on page 7
        here = self.p.zone_text(self.s6, 3, 9)
        texts6 = [t[2] for t in xrefs.live(self.p, self.s6)]
        # under the coil, in sheet then zone order; under each contact, the coil's place
        z1, z2 = self.p.zone_text(self.s6, 8, 9), self.p.zone_text(self.s6, 8, 4)
        z3 = self.p.zone_text(self.s7, 5, 9)
        self.assertEqual(texts6[:3], ["NO " + z1, "NC " + z2, "NO " + z3])
        self.assertEqual(texts6[3:], [here, here])
        self.assertEqual([t[2] for t in xrefs.live(self.p, self.s7)], [here])
        self.assertTrue(z3.startswith("7-"))
        # the coil's listing switched off; a contact left out of it
        with self.p.edit("off") as ed:
            ed.change(self.s6, self.now(self.s6, coil).copy(attrs=dict(coil.attrs, XREF="0")))
        self.assertEqual([t[2] for t in xrefs.live(self.p, self.s6)], [here, here])
        # drawn on the sheet (and into DXF and PDF through the same texts)
        self.assertTrue(all(isinstance(t, M.Text) for t in xrefs.texts(self.p, self.s6)))

    def test_freeze_and_manual_updates(self):
        self.place(self.coil, (3, 9))
        c = self.place(self.no, (8, 9), "")
        before = xrefs.live(self.p, self.s6)
        with self.p.edit("freeze") as ed:
            xrefs.freeze(ed, self.p, self.s6, True)
        with self.p.edit("move") as ed:
            ed.change(self.s6, self.now(self.s6, c).copy(pos=[12.0, 3.0]))
        self.assertEqual(xrefs.shown(self.p, self.s6), before)          # held
        self.assertEqual(xrefs.out_of_date(self.p), [self.s6])
        self.win._update_ui()
        self.assertTrue(self.win.xref_warning.isVisibleTo(self.win))
        # Update cross-references leaves frozen sheets alone
        with self.p.edit("update") as ed:
            self.assertEqual(xrefs.update(ed, self.p), 0)
        with self.p.edit("unfreeze") as ed:
            xrefs.freeze(ed, self.p, self.s6, False)
        self.assertEqual(xrefs.out_of_date(self.p), [])
        # automatic off: every sheet holds until Update cross-references
        with self.p.edit("auto off") as ed:
            xrefs.set_auto(ed, self.p, False)
        with self.p.edit("move back") as ed:
            ed.change(self.s6, self.now(self.s6, c).copy(pos=[8.0, 9.0]))
        self.assertEqual(xrefs.out_of_date(self.p), [self.s6])
        self.win.update_xrefs()
        self.assertEqual(xrefs.out_of_date(self.p), [])
        self.assertEqual(xrefs.shown(self.p, self.s6), xrefs.live(self.p, self.s6))
        # all of it is undoable and survives saving
        d = M.Project.from_dict(self.p.to_dict())
        self.assertFalse(d.settings["xref_auto"])
        self.assertEqual(xrefs.shown(d, d.sheets[0]), xrefs.shown(self.p, self.s6))

    def test_candidates_order(self):
        far = self.place(self.coil, (14, 2))
        near = self.place(self.coil, (6, 9))
        m = self.place(self.motor_coil, (7, 9))
        got = [e.attrs["TAG"] for _s, e in tags.candidates(self.p, self.s6, "CR", (8, 9))]
        self.assertEqual(got, [near.attrs["TAG"], far.attrs["TAG"], m.attrs["TAG"]])


if __name__ == "__main__":
    unittest.main()
