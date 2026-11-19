"""Block editor: an attribute's alignment and angle stick (the owner, 0.18.5: a rating set to
middle center "reverts back to baseline"); leaving a block's tab goes back to the ribbon tab
that was on ("my ribbon goes back to home instead of the tab I was already on")."""
import unittest

from tests.util import APP, window

from kanzonascad import block_editor as BE
from kanzonascad import model as M


class BlockAttrAlignTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()

    def tearDown(self):
        self.win.close()
        self.assertTrue(APP)

    def test_middle_center_kept(self):
        defn = self.win.library.get("symbol", "Fuses 3-pole").copy() \
            if hasattr(M.BlockDef, "copy") else M.BlockDef.from_dict(
                self.win.library.get("symbol", "Fuses 3-pole").to_dict())
        p, sess = BE.open_block(defn)
        s = p.sheets[0]
        marks = [e for e in s.entities.values() if isinstance(e, M.Text) and
                 e.layer == BE.LAYER_ATTRS and e.text == "RATING"]
        self.assertTrue(marks)
        with p.edit("middle") as ed:
            for m in marks:
                ed.change(s, m.copy(valign="middle", align="center"))
        got = BE.to_block(p, sess).defn
        ratings = [a for a in got.attr_texts if a["attr"] == "RATING"]
        self.assertTrue(ratings)
        self.assertTrue(all(a.get("valign") == "middle" for a in ratings), ratings)
        # (opened again: shown as set)
        p2, _s2 = BE.open_block(got)
        again = [e for e in p2.sheets[0].entities.values() if isinstance(e, M.Text) and
                 e.layer == BE.LAYER_ATTRS and e.text == "RATING"]
        self.assertTrue(again and all(e.valign == "middle" for e in again))
        # (and a placed copy draws it so)
        ins = M.Insert(got.name, (0.0, 0.0), 90.0, 1.0, False, {"RATING": "30A"}, got)
        texts = [t for t in ins.world_entities() if isinstance(t, M.Text) and t.text == "30A"]
        self.assertTrue(texts and all(t.valign == "middle" for t in texts))

    def test_ribbon_comes_back_to_its_tab(self):
        r = self.win.ribbon
        i = [k for k in range(r.count()) if r.tabText(k) not in ("Home", "Block") and
             r.isTabVisible(k)][0]
        r.setCurrentIndex(i)
        r.show_tab("Block", True, select=True)
        self.assertEqual(r.tabText(r.currentIndex()), "Block")
        r.show_tab("Block", False)
        self.assertEqual(r.currentIndex(), i)


if __name__ == "__main__":
    unittest.main()
