"""0.29 (the owner, Nov 27 2026): switching a project's symbol standard (Project properties,
Schematic) asks "Retag the unlocked devices with the <new> letters?" when unlocked devices have
tags of the other standard's letters. Yes retags them in the same Undo step (contacts,
terminals and the arrows' devices follow; locked tags stay); No keeps them; Cancel cancels the
whole change; with no such tags it doesn't ask. And a device or contact with no tag yet shows
the project's letter and "?" (K? in an IEC project, CR? in a JIC one)."""

import os
import tempfile
import unittest
from unittest import mock

from PySide6.QtWidgets import QComboBox, QDialog, QMessageBox

from tests.util import window, type_in

from kanzonascad import commands as C
from kanzonascad import dialogs
from kanzonascad import model as M
from kanzonascad import tags
from kanzonascad import xrefs


def norm(p):
    return [s.to_dict() for s in p.sheets], dict(p.settings)


class RetagTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p = self.v.project
        self.lib = self.win.library
        with self.p.edit("sheets") as ed:
            ed.add_sheet(self.p.make_sheet("Two"))
        self.s1, self.s2 = self.p.sheets
        with self.p.edit("w") as ed:
            ed.add(self.s1, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
            ed.add(self.s2, M.Wire([(2.0, 5.0), (6.0, 5.0)]))
        self.coil = self.place(self.s1, "Relay coil", (1.75, 5.0))
        self.timer = self.place(self.s1, "Timer coil", (8.0, 3.0))
        self.src = self.place(self.s1, "Source arrow", (6.0, 5.0))
        self.dst = self.place(self.s2, "Destination arrow", (2.0, 5.0), "")
        self.k = self.place(self.s2, "Contact NO", (3.0, 2.0), self.coil.attrs["TAG"])
        self.strip = self.place(self.s2, "Terminal strip", (12.0, 7.0))
        self.term = self.place(self.s2, "Terminal", (12.0, 4.0), self.strip.attrs["TAG"])
        self.locked = self.place(self.s2, "Relay coil", (8.0, 2.0))
        with self.p.edit("lock") as ed:
            tags.set_locks(ed, self.s2, [self.s2.entities[self.locked.id]], True)
        self.assertEqual(self.tag(self.coil), "CR101")
        self.assertEqual(self.tag(self.timer), "TR101")
        self.assertEqual(self.tag(self.strip), "TB201")
        self.assertEqual(self.tag(self.locked), "CR201")
        self.assertEqual(self.tag(self.k), "CR101")
        self.assertEqual(self.tag(self.term), "TB201")

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def place(self, sheet, name, at, *typed):
        self.v.show_sheet(sheet.id)
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, "%g,%g" % at, *typed)
        return [e for e in sheet.inserts() if e.block == name][-1]

    def now(self, e):
        return next(s.entities[e.id] for s in self.p.sheets
                    if e.id in s.entities and s.entities[e.id].block == e.block)

    def tag(self, e):
        return self.now(e).attrs.get("TAG")

    def arrow_device(self):
        """What the destination arrow says is at its wire's far end (the coil, on page 1)."""
        got = [it[2] for it in xrefs.live(self.p, self.s2)]
        return [t for t in got if t in (self.tag(self.coil), "CR101", "K101")]

    def switch(self, answer, standard="iec"):
        """Project properties, Schematic: the standard set; the question answered with answer
        (a QMessageBox button), or the test failing if it is asked when answer is None."""
        asked = []

        def exec_(dlg):
            box = dlg.findChild(QComboBox, "symbol_standard")
            box.setCurrentIndex(box.findData(standard))
            return QDialog.Accepted

        def question(_parent, _title, text, *_a):
            asked.append(text)
            if answer is None:
                raise AssertionError("asked: %s" % text)
            return answer
        with mock.patch.object(dialogs.QDialog, "exec", exec_), \
                mock.patch.object(QMessageBox, "question", side_effect=question):
            self.win.project_properties(1)
        return asked

    def test_yes_retags_in_one_undo_step(self):
        before, steps = norm(self.p), len(self.p.undo_stack)
        self.assertEqual(self.arrow_device(), ["CR101"])
        asked = self.switch(QMessageBox.Yes)
        self.assertEqual(len(asked), 1)
        self.assertTrue(asked[0].startswith(
            "Retag the unlocked devices with the IEC 81346-2 letters?"), asked[0])
        self.assertIn("3 devices", asked[0])
        self.assertEqual(self.p.settings["symbol_standard"], "iec")
        self.assertEqual(len(self.p.undo_stack), steps + 1)
        # (relays and timers share K: the timer takes the next free count)
        self.assertEqual([self.tag(e) for e in (self.coil, self.timer, self.strip)],
                         ["K101", "K102", "X201"])
        self.assertEqual(self.tag(self.locked), "CR201")               # (locked: kept)
        self.assertEqual(self.tag(self.k), "K101")                     # (its contact)
        term = self.now(self.term)
        self.assertEqual((term.attrs["TAG"], term.attrs.get("TERM")), ("X201", "1"))
        self.assertEqual(self.arrow_device(), ["K101"])               # (the arrow's device)
        self.assertEqual(tags.to_retag(self.p), [])
        self.p.undo()
        self.assertEqual(norm(self.p), before)
        self.assertEqual(self.arrow_device(), ["CR101"])
        self.p.redo()
        self.assertEqual(self.tag(self.coil), "K101")
        # (and back to JIC: the same question, with the JIC letters)
        asked = self.switch(QMessageBox.Yes, "jic")
        self.assertTrue(asked[0].startswith("Retag the unlocked devices with the JIC letters?"))
        # (each count kept: the timer's K102 is TR102, not the TR101 it was before)
        self.assertEqual([self.tag(e) for e in (self.coil, self.timer, self.strip, self.k)],
                         ["CR101", "TR102", "TB201", "CR101"])

    def test_no_keeps_the_tags(self):
        before = norm(self.p)[0]
        self.assertEqual(len(self.switch(QMessageBox.No)), 1)
        self.assertEqual(self.p.settings["symbol_standard"], "iec")
        self.assertEqual(norm(self.p)[0], before)
        self.p.undo()
        self.assertEqual(self.p.settings.get("symbol_standard", "jic"), "jic")

    def test_cancel_cancels_the_whole_change(self):
        before, steps = norm(self.p), len(self.p.undo_stack)
        self.assertEqual(len(self.switch(QMessageBox.Cancel)), 1)
        self.assertEqual(norm(self.p), before)
        self.assertEqual(len(self.p.undo_stack), steps)

    def test_not_asked_without_such_tags(self):
        with self.p.edit("lock all") as ed:
            for s in self.p.sheets:
                tags.set_locks(ed, s, list(s.entities.values()), True)
        before = norm(self.p)[0]
        self.assertEqual(self.switch(None), [])
        self.assertEqual(self.p.settings["symbol_standard"], "iec")
        self.assertEqual(norm(self.p)[0], before)
        # (nor going back: the locked tags are of the JIC letters, the project's again)
        self.assertEqual(self.switch(None, "jic"), [])

    def test_a_tag_of_your_own_prefix_is_not_asked_about(self):
        mine = M.BlockDef("Horn", "symbol", [], [], (0, 0.2), 0.1, "Mine", "", "device", "",
                          "HN")
        h = M.Insert("Horn", (5, 5), defn=mine, attrs={"TAG": "HN101", "DEV": "h1"})
        self.assertFalse(tags.other_letters(self.p, h, "iec"))
        self.assertTrue(tags.other_letters(self.p, self.now(self.coil), "iec"))
        self.assertFalse(tags.other_letters(self.p, self.now(self.coil), "jic"))
        self.assertFalse(tags.other_letters(self.p, self.now(self.locked), "iec"))


class PlaceholderTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.v.osnap_on = self.v.snap_on = self.v.polar_on = self.v.ortho_on = False
        self.p, self.s = self.v.project, self.v.sheet()
        self.lib = self.win.library

    def tearDown(self):
        self.p.saved_at = len(self.p.undo_stack)
        self.win.close()

    def standard(self, std):
        with self.p.edit("standard") as ed:
            ed.project_settings(dict(self.p.settings, symbol_standard=std))

    def unlinked(self, name, at):
        self.v.run(C.InsertCmd, self.lib.get("symbol", name), {})
        type_in(self.v, at)
        if self.v.cmd is not None:
            self.v.cmd.enter()                  # (on its own)
        return [e for e in self.s.inserts() if e.block == name][-1]

    def shown(self, e):
        return self.s.entities[e.id].tag_text().text

    def test_jic_unchanged(self):
        k = self.unlinked("Contact NO", "3,5")
        self.assertEqual(self.shown(k), "CR?")
        t = self.unlinked("Terminal", "6,5")
        self.assertEqual(self.shown(t), "TB?")

    def test_iec_project_shows_its_letter(self):
        self.standard("iec")
        k = self.unlinked("Contact NO (IEC)", "3,5")
        t = self.unlinked("Terminal", "6,5")
        jic = self.unlinked("Contact NO", "9,5")          # (a JIC symbol in it: K too)
        self.assertEqual([self.shown(e) for e in (k, t, jic)], ["K?", "X?", "K?"])
        # (a device with no tag: one from before tags, or its tag cleared)
        coil = self.unlinked("Relay coil", "8,3")
        with self.p.edit("no tag") as ed:
            ed.change(self.s, self.s.entities[coil.id].copy(attrs={}))
        self.assertEqual(self.shown(coil), "K?")
        # (drawn so: the entity's drawing, its box)
        texts = [w.text for w in self.s.entities[k.id].world_entities()
                 if isinstance(w, M.Text)]
        self.assertIn("K?", texts)
        # (switched back, and undone: they follow at once)
        self.standard("jic")
        self.assertEqual([self.shown(e) for e in (k, t, jic, coil)], ["CR?", "TB?", "CR?", "CR?"])
        self.p.undo()
        self.assertEqual([self.shown(e) for e in (k, t, jic, coil)], ["K?", "X?", "K?", "K?"])
        # (saved and opened)
        path = os.path.join(tempfile.mkdtemp(), "iec.kzcad")
        self.p.save(path, backups=0)
        q = M.Project.load(path)
        self.assertEqual(q.sheets[0].entities[k.id].tag_text().text, "K?")
        self.assertEqual(q.sheets[0].entities[t.id].tag_text().text, "X?")

    def test_ghost_shows_the_letter(self):
        self.standard("iec")
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Contact NO (IEC)"), {})
        ghost = self.v.cmd.preview((3.0, 5.0))[0]
        self.assertEqual(ghost.tag_text().text, "K?")
        self.v.cancel()
        # (a contact waiting to be told its device, with one to offer)
        self.unlinked("Relay coil (IEC)", "8,5")
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Contact NO (IEC)"), {})
        type_in(self.v, "3,5")
        self.assertIsNotNone(self.v.cmd.pending)
        self.assertEqual(self.v.cmd.preview((4.0, 5.0))[0].tag_text().text, "K?")
        self.v.cancel()
        self.standard("jic")
        self.v.run(C.InsertCmd, self.lib.get("symbol", "Contact NO"), {})
        self.assertEqual(self.v.cmd.preview((3.0, 5.0))[0].tag_text().text, "CR?")
        self.v.cancel()


if __name__ == "__main__":
    unittest.main()
