"""Contact blocks on a dashed line show no tag of their own, as in the owner's print (the
owner, 0.19.11: "Yes" to hiding them); taken off the line, it shows again; one hidden by hand
stays hidden."""
import unittest

from tests.test_0200_contact_blocks import ContactBlocksTest


class BlockTagsTest(ContactBlocksTest):
    def now(self, e):
        return self.s.entities[e.id]

    def test_joined_blocks_hide_their_tag(self):
        es, nc, no = self.stack()
        self.assertIn("TAG", self.now(nc).hidden)
        self.assertIn("TAG", self.now(no).hidden)
        self.assertNotIn("TAG", self.now(es).hidden)            # (the operator shows it)
        self.assertEqual(self.now(no).attrs.get("TAG"), self.now(es).attrs.get("TAG"))

    def test_off_the_line_the_tag_comes_back_and_undo_hides_it_again(self):
        es, nc, no = self.stack()
        with self.p.edit("aside") as ed:
            ed.change(self.s, self.now(no).moved(3.0, 0.0))
        self.assertNotIn("TAG", self.now(no).hidden)
        self.assertNotIn("TAGLINK", self.now(no).attrs)
        self.assertIn("TAG", self.now(nc).hidden)               # (still on the line)
        self.p.undo()
        self.assertIn("TAG", self.now(no).hidden)

    def test_a_tag_hidden_by_hand_stays_hidden(self):
        es, nc, no = self.stack()
        # (taken off the line, its tag back; hidden by hand; then on and off the line again)
        with self.p.edit("aside") as ed:
            ed.change(self.s, self.now(no).moved(3.0, 0.0))
        with self.p.edit("hide by hand") as ed:
            e = self.now(no)
            ed.change(self.s, e.copy(hidden=frozenset(e.hidden) | {"TAG"}))
        with self.p.edit("back") as ed:
            ed.change(self.s, self.now(no).moved(-3.0, 0.0))
        with self.p.edit("away") as ed:
            ed.change(self.s, self.now(no).moved(3.0, 0.0))
        self.assertIn("TAG", self.now(no).hidden)

    def test_a_tag_shown_by_hand_on_the_line_stays_shown(self):
        # (seed 5042: ticking Tag in the Properties panel for a block on the line did
        # nothing, the line hid it again at once)
        es, nc, no = self.stack()
        win = self.win
        e = self.now(no)
        with self.p.edit("show by hand") as ed:
            for sh, c in win.attribute_changes(self.p, self.s, e, dict(e.attrs),
                                               {"hidden": frozenset(e.hidden) - {"TAG"}}):
                ed.change(sh, c)
        self.assertNotIn("TAG", self.now(no).hidden)
        with self.p.edit("nudge") as ed:                    # (still on the line)
            ed.change(self.s, self.now(no).moved(0.0, 0.0))
        self.assertNotIn("TAG", self.now(no).hidden)
        self.assertIn("TAG", self.now(nc).hidden)           # (the other one: as it was)
        e = self.now(no)
        with self.p.edit("hide by hand") as ed:
            for sh, c in win.attribute_changes(self.p, self.s, e, dict(e.attrs),
                                               {"hidden": frozenset(e.hidden) | {"TAG"}}):
                ed.change(sh, c)
        self.assertIn("TAG", self.now(no).hidden)
        self.assertNotIn("TAGLINK", self.now(no).attrs)

    def test_saved_and_opened(self):
        import os
        import tempfile
        from kanzonascad import model as M
        es, nc, no = self.stack()
        fd, path = tempfile.mkstemp(suffix=".kcad")
        os.close(fd)
        try:
            self.p.save(path)
            q = M.Project.load(path)
        finally:
            os.remove(path)
        self.assertIn("TAG", q.sheets[0].entities[no.id].hidden)


if __name__ == "__main__":
    unittest.main()
