"""Editing the title block in a tab of its own, as a block is (the owner, 0.22.5: "when editing the
title block, the tab goes back to schematic, and it's not intuitive on how to save the title
block and get back to the main screen ... the title block should be edited in its own
window/tab, just like editing a block"). Edit title block opens a copy of the project's title
block in a tab of its own, with the Title block ribbon tab; Save title block puts it back in the
project in one step (Undo takes it back), closes the tab and goes back to the drawing it was
opened from, on the Sheets ribbon tab; closing the tab with changes asks to save them. A mixin
of MainWindow (main_window.py), as block_window.py is."""

from PySide6.QtWidgets import QMessageBox

from . import model as M

TITLE = "KanzonasCAD"


def is_tb_doc(d):
    """Is this tab the title block's (Edit title block)?"""
    return getattr(d, "tb_source", None) is not None


def working_copy(project):
    """A project holding a copy of project's title block, with its settings, fields, layers and
    blocks (so it is drawn and placed as on the sheets), without its sheets' drawings."""
    d = project.to_dict()
    d["sheets"] = [dict(d["sheets"][0], entities=[])]
    return M.Project.from_dict(d)


def put_back(ed, project, copy):
    """In edit ed of project: its title block made the copy's (layers and blocks it uses that
    the project hasn't got brought in too)."""
    for name, lay in copy.layers.items():
        if name not in project.layers:
            ed.layer(name, None, lay.to_dict())
    tb = project.title_block
    for e in copy.title_block.entities.values():
        if isinstance(e, M.Insert) and e.block not in project.blocks and \
                e.block in copy.blocks:
            ed.block(copy.blocks[e.block])
    for eid in list(tb.entities):
        ed.remove(tb, eid)
    for e in copy.title_block.entities.values():
        d = e.to_dict()
        d.pop("id", None)
        ed.add(tb, M.Entity.from_dict(d, project.blocks))


class TitleBlockEditing:
    def edit_title_block(self):
        """Open the project's title block in a tab of its own (the one already open, if it
        is). Returns that tab or None."""
        src = self.doc()
        if src is None:
            return None
        if is_tb_doc(src):
            return src
        from .block_window import is_block_doc
        if is_block_doc(src):
            self._say("Edit title block works on a project: this tab is a block's")
            return None
        for win, d in self.documents():
            if is_tb_doc(d) and d.tb_source.project is src.project:
                win.tabs.setCurrentWidget(d)
                win.raise_()
                return d
        d = self.add_document(working_copy(src.project))
        d.tb_source = src
        d.project.saved_at = len(d.project.undo_stack)
        self._project_changed(d)            # (its tab's name: the title block's)
        v = d.view
        v.show_sheet(M.TITLE_BLOCK_ID)
        self.tabs.setCurrentWidget(d)
        self._show_tb_tab(select=True)
        self._fill_sheets()                 # (opened before it was the title block's: again)
        self._update_ui()
        v.zoom("sheet")
        self._say("Editing the title block of %s: draw and change it like any drawing; a text "
                  "with {Customer}, {Sheet}, {Sheets}, {Sheet title}... shows that field's "
                  "value on the sheets. Save title block (or Ctrl+S) puts it in the project "
                  "and goes back to the drawing; Close title block leaves it as it was."
                  % src.name(), 12000)
        return d

    def save_title_block(self, *, close=True):
        """Save title block: the title block's tab put back in its project (one step, Undo
        takes it back), then the tab closed and the drawing it was opened from shown, on the
        Sheets ribbon tab. close=False: the tab stays (closing it asked to save). True when
        saved. (Keyword only: a menu action's triggered(checked) never sets it.)"""
        d = self.doc()
        if not is_tb_doc(d):
            self._say("Save title block works in the title block's tab (Edit title block "
                      "opens it)")
            return False
        if d.view.cmd is not None:
            d.view.cancel()
        src = d.tb_source
        if not self._is_open(src):
            QMessageBox.warning(self, TITLE, "The project this title block came from is "
                                "closed: its changes can't go back into it.")
            return False
        if d.project.is_modified():
            with src.project.edit("Edit title block") as ed:
                put_back(ed, src.project, d.project)
            d.project.saved_at = len(d.project.undo_stack)
            self._say("Title block saved in %s (Undo there takes it back)" % src.name())
        if close:
            self._close_tb(d)
        return True

    def close_title_block(self):
        """Close title block: the title block's tab closed (asking to save its changes), back
        to the drawing it was opened from."""
        d = self.doc()
        if is_tb_doc(d):
            self._close_tb(d)

    def _close_tb(self, d):
        src = d.tb_source
        if self.close_tab(self.tabs.indexOf(d)) and self._is_open(src):
            for win, o in self.documents():
                if o is src:
                    win.tabs.setCurrentWidget(src)
                    win.ribbon.setCurrentIndex(win.ribbon.tab_index("Sheets"))
                    break

    def _ask_save_title_block(self, d):
        """Closing the title block's tab with changes: save them, leave them, or stay. True to
        go on closing."""
        if not d.project.is_modified():
            return True
        self.tabs.setCurrentWidget(d)
        r = QMessageBox.question(self, TITLE, "Save the changes to the title block?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self.save_title_block(close=False)
        return True

    def _show_tb_tab(self, select=False):
        """The Title block ribbon tab: there in the title block's tab only."""
        on = hasattr(self, "tabs") and is_tb_doc(self.doc())
        self.ribbon.show_tab("Title block", on, select=select and on)
