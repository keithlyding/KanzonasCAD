"""Title blocks kept in the library (the owner, 0.22.5: "I don't want to lose the default title
block as an option though. I think I should be able to save as a new title block and then select
default ones or different variations I've made. I also want to be able to put my company's logo
in the title block"): the ready-made ones always there, yours saved by name with where they sit
and a logo picture in them, and either one put in a project in one step."""
import os
import tempfile
import unittest
from unittest import mock

from tests.util import APP, window

from kanzonascad import model as M
from kanzonascad import titleblocks as TB
from kanzonascad.library import Library
from kanzonascad.tb_window import is_tb_doc

LOGO = ("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAAN"
        "BAEBkYRf3AAAAABJRU5ErkJggg==")


class TitleBlockLibraryTest(unittest.TestCase):
    def setUp(self):
        self.win, self.v = window()
        self.p = self.v.project
        self.lib = Library(tempfile.mkdtemp())

    def tearDown(self):
        for i in range(self.win.tabs.count()):
            d = self.win.tabs.widget(i)
            d.project.saved_at = len(d.project.undo_stack)
        self.win.close()
        self.assertTrue(APP)

    def texts(self, project=None):
        return sorted(e.text for e in (project or self.p).title_block.entities.values()
                      if isinstance(e, M.Text))

    def mine(self):
        """The project's title block changed: Project Number for Customer, and a logo."""
        tb = self.p.title_block
        cust = next(e for e in tb.entities.values()
                    if isinstance(e, M.Text) and e.text == "{Customer}")
        with self.p.edit("mine") as ed:
            ed.change(tb, cust.copy(text="{Project Number}"))
            ed.add(tb, M.Picture((1.0, 1.0), 1.5, 0.75, LOGO, layer="LOGO"))
            ed.layer("LOGO", None, M.Layer("LOGO", "#ff0000").to_dict())

    def test_the_ready_made_ones_are_always_there(self):
        got = TB.names(self.lib)
        self.assertEqual([n for n, built in got if built], [n for n, _p in TB.BUILT_IN])
        self.assertEqual([n for n, built in got if not built], [])

    def test_saved_and_used_again_with_its_logo_and_place(self):
        self.mine()
        with self.p.edit("strip") as ed:
            ed.project_settings({"tb_position": "right"})
        TB.save(self.lib, "Acme, strip", self.p, "right")
        self.assertIn(("Acme, strip", False), TB.names(self.lib))
        mine = self.texts()
        # (back to a ready-made one: the corner's)
        with self.p.edit("standard") as ed:
            TB.use(ed, self.p, self.lib, "Standard, lower right corner")
        self.assertEqual(self.p.settings["tb_position"], "corner")
        self.assertIn("{Customer}", self.texts())
        self.assertFalse(any(isinstance(e, M.Picture)
                             for e in self.p.title_block.entities.values()))
        # (and yours again, in another project too: its logo, its layer, its place)
        w2, v2 = window()
        try:
            q = v2.project
            with q.edit("use") as ed:
                TB.use(ed, q, self.lib, "Acme, strip")
            self.assertEqual(self.texts(q), mine)
            self.assertEqual(q.settings["tb_position"], "right")
            pics = [e for e in q.title_block.entities.values() if isinstance(e, M.Picture)]
            self.assertEqual(len(pics), 1)
            self.assertEqual(pics[0].data, LOGO)
            self.assertIn("LOGO", q.layers)
            q.undo()
            self.assertEqual(q.settings["tb_position"], "corner")
            self.assertNotIn("{Project Number}", self.texts(q))
        finally:
            q.saved_at = len(q.undo_stack)
            w2.close()

    def test_saved_again_replaces_and_delete_removes(self):
        TB.save(self.lib, "Acme", self.p, "corner")
        self.mine()
        TB.save(self.lib, "Acme", self.p, "corner")
        self.assertEqual([n for n, b in TB.names(self.lib) if not b], ["Acme"])
        with self.p.edit("use") as ed:
            TB.use(ed, self.p, self.lib, "Acme")
        self.assertIn("{Project Number}", self.texts())
        TB.delete(self.lib, "Acme")
        self.assertEqual([n for n, b in TB.names(self.lib) if not b], [])
        with self.assertRaises(ValueError):
            TB.save(self.lib, "Standard, lower right corner", self.p, "corner")
        with self.assertRaises(ValueError):
            TB.save(self.lib, "  ", self.p, "corner")

    def test_a_damaged_file_is_left_out(self):
        os.makedirs(os.path.join(self.lib.folder, TB.FOLDER))
        with open(os.path.join(self.lib.folder, TB.FOLDER, "bad" + TB.SUFFIX), "w") as f:
            f.write("{not json")
        self.assertEqual([n for n, b in TB.names(self.lib) if not b], [])

    def test_save_as_from_its_tab_and_pick_from_the_sheets_tab(self):
        self.win.library = self.lib
        self.win.acts["edit_tb"].trigger()
        d = self.win.doc()
        self.assertTrue(is_tb_doc(d))
        self.assertTrue(self.win.acts["save_tb_as"].isVisible())
        tb = d.project.title_block
        cust = next(e for e in tb.entities.values()
                    if isinstance(e, M.Text) and e.text == "{Customer}")
        with d.project.edit("mine") as ed:
            ed.change(tb, cust.copy(text="{Project Number}"))
        with mock.patch.object(self.win, "ask_title_block_name", return_value="Acme"):
            self.win.acts["save_tb_as"].trigger()
        self.assertIn(("Acme", False), TB.names(self.lib))
        self.assertIs(self.win.doc(), d)                    # (still editing it)
        self.win.acts["save_tb"].trigger()
        # (the ready-made one picked again in the Sheets tab's Title blocks..., then yours)
        with mock.patch.object(self.win, "ask_title_block",
                               return_value="Standard, lower right corner"):
            self.win.acts["title_blocks"].trigger()
        self.assertIn("{Customer}", self.texts())
        with mock.patch.object(self.win, "ask_title_block", return_value="Acme"):
            self.win.acts["title_blocks"].trigger()
        self.assertIn("{Project Number}", self.texts())
        self.p.undo()
        self.assertIn("{Customer}", self.texts())

    def test_the_window(self):
        from PySide6.QtWidgets import QDialog, QListWidget, QPushButton
        from kanzonascad import dialogs
        TB.save(self.lib, "Acme", self.p, "corner")
        seen = {}

        def pick(name, then="use"):
            def answer(dlg):
                lst = dlg.findChild(QListWidget, "title_block_list")
                seen["items"] = [lst.item(i).text() for i in range(lst.count())]
                row = next(i for i in range(lst.count())
                           if lst.item(i).data(0x0100)[0] == name)
                lst.setCurrentRow(row)
                seen["delete on"] = dlg.findChild(QPushButton, "delete").isEnabled()
                if then == "delete":
                    with mock.patch.object(dialogs.QMessageBox, "question",
                                           return_value=dialogs.QMessageBox.Yes):
                        dlg.findChild(QPushButton, "delete").click()
                    seen["after"] = [lst.item(i).text() for i in range(lst.count())]
                    return QDialog.Rejected
                dlg.findChild(QPushButton, "use").click()
                return dlg.result()
            return answer
        real = dialogs.QDialog.exec
        try:
            dialogs.QDialog.exec = pick("Acme")
            self.assertEqual(dialogs.title_blocks_dialog(self.win, self.lib), "Acme")
            self.assertEqual(seen["items"][:3], [n + "  (ready-made)" for n, _p in TB.BUILT_IN])
            self.assertIn("Acme", seen["items"])
            self.assertTrue(seen["delete on"])
            dialogs.QDialog.exec = pick("Standard, right-hand strip")
            self.assertEqual(dialogs.title_blocks_dialog(self.win, self.lib),
                             "Standard, right-hand strip")
            self.assertFalse(seen["delete on"])             # (a ready-made one stays)
            dialogs.QDialog.exec = pick("Acme", "delete")
            self.assertIsNone(dialogs.title_blocks_dialog(self.win, self.lib))
            self.assertNotIn("Acme", seen["after"])
        finally:
            dialogs.QDialog.exec = real
        self.assertEqual([n for n, b in TB.names(self.lib) if not b], [])

    def test_the_logo_button_is_on_the_title_block_tab(self):
        r = self.win.ribbon
        self.win.acts["edit_tb"].trigger()
        self.assertEqual(r.tabText(r.currentIndex()), "Title block")
        from PySide6.QtWidgets import QToolButton
        page = r.widget(r.tab_index("Title block"))
        acts = {b.defaultAction() for b in page.findChildren(QToolButton)}
        for k in ("import_picture", "save_tb", "save_tb_as", "close_tb"):
            self.assertIn(self.win.acts[k], acts, k)


if __name__ == "__main__":
    unittest.main()
