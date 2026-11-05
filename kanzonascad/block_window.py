"""Changing library blocks from the main window: a block's Properties..., Duplicate..., Edit
block... (the block's drawing in a tab of its own, block_editor.py), Save block and Save block
as..., and then the copies
placed in the project open in the drawing tab, updated when you say so. A mixin of
MainWindow (main_window.py), kept apart so the window's own file stays about the window."""

from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from . import block_editor as BE
from . import model as M
from .geometry import bbox_union

TITLE = "KanzonasCAD"


def is_block_doc(d):
    """Is this tab a block editor (Edit block...)?"""
    return getattr(d, "block_session", None) is not None


def paint_pins(p, view):
    """The block editor's pin points: a small ring at each pin marker's insertion point (the
    exact spot a wire attaches); a footprint's DIN rail point: a ring and a dashed line
    across the block where the rail's centerline runs. Drawn into the view's picture of the
    drawing."""
    s = view.sheet()
    key = (s.id, s.version)
    got = getattr(view, "_pin_marks", None)
    if got is None or got[0] != key:
        texts = [e for e in s.entities.values() if isinstance(e, M.Text)]
        bb = None
        for e in s.entities.values():
            if e.layer not in BE.MARKER_LAYERS:
                bb = bbox_union(bb, e.bbox())
        got = view._pin_marks = (key, [e.pos for e in texts if e.layer == BE.LAYER_PINS],
                                 [e.pos for e in texts if e.layer == BE.LAYER_RAIL], bb)
    r = 4.0 / view.scale
    p.setBrush(Qt.NoBrush)
    lay = view.project.layers.get(BE.LAYER_PINS)
    if lay is None or lay.visible:
        pen = QPen(QColor(BE.MARKER_LAYERS[BE.LAYER_PINS]), 1.5)
        pen.setCosmetic(True)
        p.setPen(pen)
        for x, y in got[1]:
            p.drawEllipse(QPointF(x, y), r, r)
    lay = view.project.layers.get(BE.LAYER_RAIL)
    if got[2] and (lay is None or lay.visible):
        pen = QPen(QColor(BE.MARKER_LAYERS[BE.LAYER_RAIL]), 1.5, Qt.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        bb = got[3]
        for x, y in got[2]:
            p.drawEllipse(QPointF(x, y), r, r)
            if bb is not None:
                m = 12.0 / view.scale
                p.drawLine(QPointF(min(bb[0], x) - m, y), QPointF(max(bb[2], x) + m, y))


def zoom_block(view):
    """Zoom to the block with some room around it (a small symbol isn't blown up to fill the
    screen)."""
    s = view.sheet()
    bb = s.extents()
    if bb is None:
        view.zoom("sheet")
        return
    n = 1.0 / s.scale if s.scale > 0 else 1.0
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    w = max((bb[2] - bb[0]) * 1.6, 2.0 * n)
    h = max((bb[3] - bb[1]) * 1.6, 1.5 * n)
    vw, vh = max(view.width(), 100), max(view.height(), 100)
    view.scale = max(1e-3, min(vw / w, vh / h))
    view.center = (cx, cy)
    view.update()


class BlockEditing:
    """MainWindow's block commands (see main_window.py for the actions and menus)."""

    def _say(self, msg, ms=6000):
        self.cmdline.add_history(msg)
        self.statusBar().showMessage(msg, ms)

    def _is_open(self, d):
        return d is not None and any(self.tabs.widget(i) is d for i in range(self.tabs.count()))

    def _drawing_doc(self):
        """The project tab block changes offer to update: the current one, or the one a
        block editor was opened from."""
        d = self.doc()
        if is_block_doc(d):
            d = d.block_source
        return d if self._is_open(d) else None

    def _block_target(self, kind=None, name=None):
        """The block to work on: (kind, the library's copy or None, the drawing's copy or
        None), from the arguments, else the one block selected in the drawing, else the one
        selected in the Library popup (when it is open); None when there is none."""
        if kind and name:
            return kind, self.library.get(kind, name), None
        d = self.doc()
        v = self.view()
        if v is not None and not is_block_doc(d):
            sheet = v.sheet()
            ins = [e for e in (sheet.entities.get(i) for i in v.sel)
                   if isinstance(e, M.Insert) and e.defn is not None]
            if len({e.block for e in ins}) == 1:
                e = ins[0]
                return e.defn.kind, self.library.get(e.defn.kind, e.block), e.defn
        if self.library_dialog.isVisible():
            got = self.library_panel.current_block()
            if got is not None:
                return got[0], self.library.get(*got), None
        return None

    # ---- Properties... ---------------------------------------------------------------------
    def block_properties(self, kind=None, name=None):
        """A library block's details (name, category, description, manufacturer, family,
        series; a symbol's role, contact, prefix, wiring and pin names), saved to the library;
        then the drawing's copies updated if you say so. Returns the new BlockDef or None."""
        t = self._block_target(kind, name)
        if t is None:
            self._say("Block properties: select one symbol or footprint in the drawing, or "
                      "pick one in the Library")
            return None
        kind, lib, own = t
        defn = lib or own
        if defn is None:
            self._say("%s isn't in your library" % name)
            return None
        from .library_panel import block_details_dialog, block_with_details
        det = block_details_dialog(self, self.library, defn=defn, on_help=self.show_manual)
        if det is None:
            return None
        new, pin_map = block_with_details(defn, det)
        try:
            _path, moved = self.library.save_block_as(new, old_name=defn.name)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, TITLE, "Couldn't save %s to the library (%s):\n%s"
                                % (new.name, self.library.folder, ex))
            return None
        self._sync_editors(kind, defn.name, new, pin_map)
        self.library_panel.refresh()
        msg = "Saved %s to your library" % new.name
        if new.name != defn.name:
            msg += " (was %s)" % defn.name
            if moved:
                msg += "; %d part(s) now link to it" % moved
        self._say(msg)
        self._offer_update(self._drawing_doc(), new, defn.name, pin_map)
        return new

    def _sync_editors(self, kind, old_name, new, pin_map):
        """A block open in a block editor got new details: saving it there keeps them (its
        pin markers renamed as its pins were, one undoable step in that tab)."""
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if not is_block_doc(d):
                continue
            sess = d.block_session
            if sess.kind != kind or sess.name != old_name:
                continue
            sess.set_meta(new)
            sheet = d.project.sheet_by_id(sess.sheet_id)
            with d.project.edit("Block properties") as ed:
                for eid, (_dict, what) in list(sess.base.items()):
                    cur = sheet.entities.get(eid) if sheet is not None else None
                    if what[0] == "pin" and isinstance(cur, M.Text) and \
                            pin_map.get(cur.text, cur.text) != cur.text:
                        ed.change(sheet, cur.copy(text=pin_map[cur.text]))
                if sheet is not None and sheet.title != "Block: %s" % new.name:
                    ed.sheet_meta(sheet, title="Block: %s" % new.name)
            self._project_changed(d)

    # ---- Edit block... ---------------------------------------------------------------------
    def edit_block(self, kind=None, name=None):
        """Open the library's copy of a block in a tab of its own (the block selected in the
        drawing, or in the Library). Returns that tab or None."""
        t = self._block_target(kind, name)
        if t is None:
            self._say("Edit block: select one symbol or footprint in the drawing, or pick one "
                      "in the Library")
            return None
        kind, lib, own = t
        defn = lib or own
        if defn is None:
            self._say("%s isn't in your library" % name)
            return None
        for i in range(self.tabs.count()):
            d = self.tabs.widget(i)
            if is_block_doc(d) and d.block_session.kind == kind and \
                    d.block_session.name == defn.name:
                self.tabs.setCurrentIndex(i)
                return d
        source = self._drawing_doc()
        project, sess = BE.open_block(defn)
        d = self.add_document(project)
        d.block_session = sess
        d.block_source = source
        v = d.view
        v.overlay = paint_pins
        v.current_layer = "0"
        self._project_changed(d)
        QTimer.singleShot(0, v, lambda: zoom_block(v))
        self.settings.setValue("library_geometry", self.library_dialog.saveGeometry())
        self.library_dialog.hide()
        msg = ("Editing %s from your library: change it with any command. The green texts "
               "are its pins (each text's insertion point is the pin, its text the pin's "
               "name; copy one to add a pin, erase one to remove it)%s; the cross is the base "
               "point. Save block puts it back in the library."
               % (defn.name, ", the blue text is where its tag goes" if
                  defn.kind == "symbol" else ", the pink DIN RAIL text is the middle of its "
                  "rail clip (move it to where the rail's centerline crosses the part)"))
        if lib is None:
            msg += " (It wasn't in your library: Save block adds it.)"
        self._say(msg, 12000)
        return d

    def save_block(self):
        """Save block: the block editor's drawing back into the library; then the copies in
        the project it was opened from updated if you say so. True when saved."""
        d = self.doc()
        if not is_block_doc(d):
            self._say("Save block works in a block's tab (Edit block... opens one)")
            return False
        if d.view.cmd is not None:
            d.view.cancel()
        sess = d.block_session
        try:
            res = BE.to_block(d.project, sess)
        except ValueError as ex:
            QMessageBox.warning(self, TITLE, "Couldn't read the block back:\n%s" % ex)
            return False
        defn = res.defn
        try:
            self.library.save_block_as(defn)
        except OSError as ex:
            QMessageBox.warning(self, TITLE, "Couldn't save %s to the library (%s):\n%s"
                                % (defn.name, self.library.folder, ex))
            return False
        BE.saved(sess, res)
        d.project.saved_at = len(d.project.undo_stack)
        self._project_changed(d)
        self.library_panel.refresh()
        msg = "Saved %s to your library (%d pin(s))" % (defn.name, len(defn.pins))
        if res.warnings:
            msg += "; " + "; ".join(res.warnings)
        self._say(msg)
        src = d.block_source if self._is_open(d.block_source) else None
        self._offer_update(src, defn, defn.name, res.pin_map)
        return True

    # ---- Duplicate... and Save block as... ------------------------------------------------
    def _new_block_name(self, kind, base, title):
        """Ask for the name of a new library block (offered: "<base> copy", "<base> copy 2"
        ...); a name already in the library is asked again. None when cancelled."""
        n, name = 1, "%s copy" % base
        while self.library.get(kind, name) is not None:
            n += 1
            name = "%s copy %d" % (base, n)
        while True:
            name, ok = QInputDialog.getText(self, title, "Name of the new %s:" % kind,
                                            QLineEdit.Normal, name)
            name = (name or "").strip()
            if not ok or not name:
                return None
            if self.library.get(kind, name) is None:
                return name
            QMessageBox.information(self, title, "Your library already has a %s named %s: "
                                    "pick another name." % (kind, name))

    @staticmethod
    def _variant(defn, name):
        """A copy of a block under a new name: everything kept but the catalog number (a
        different block is a different part), never marked built-in."""
        d = defn.to_dict()
        d["name"] = name
        d["catalog"] = ""
        return M.BlockDef.from_dict(d)

    def duplicate_block(self, kind=None, name=None):
        """Duplicate...: a copy of a block saved to your library under a new name (its
        catalog number left blank), opened in Edit block right away to be changed. Returns
        the block editor's tab or None."""
        t = self._block_target(kind, name)
        if t is None:
            self._say("Duplicate: select one symbol or footprint in the drawing, or pick one "
                      "in the Library")
            return None
        kind, lib, own = t
        defn = lib or own
        if defn is None:
            self._say("%s isn't in your library" % name)
            return None
        new_name = self._new_block_name(kind, defn.name, "Duplicate %s" % kind)
        if new_name is None:
            return None
        new = self._variant(defn, new_name)
        try:
            self.library.save_block(new)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, TITLE, "Couldn't save %s to the library (%s):\n%s"
                                % (new_name, self.library.folder, ex))
            return None
        self.library_panel.refresh()
        d = self.edit_block(kind, new_name)
        self._say("Duplicated %s as %s in your library (catalog number left blank: "
                  "Block properties... sets it); change it here and Save block"
                  % (defn.name, new_name), 12000)
        return d

    def save_block_as(self):
        """Save block as...: the block editor's drawing saved to your library under a new
        name (its catalog number left blank); the block it was opened from stays as it was,
        and this tab goes on editing the new one. True when saved."""
        d = self.doc()
        if not is_block_doc(d):
            self._say("Save block as works in a block's tab (Edit block... opens one)")
            return False
        sess = d.block_session
        new_name = self._new_block_name(sess.kind, sess.name, "Save block as")
        if new_name is None:
            return False
        old = sess.defn
        sess.defn = self._variant(old, new_name)
        sheet = d.project.sheet_by_id(sess.sheet_id)
        if sheet is not None:
            with d.project.edit("Save block as") as ed:
                ed.sheet_meta(sheet, title="Block: %s" % new_name)
        if not self.save_block():
            sess.defn = old
            return False
        return True

    def _ask_save_block(self, d):
        """Closing a block editor with changes not saved: Save / Discard / Cancel."""
        if not d.project.is_modified():
            return True
        self.tabs.setCurrentWidget(d)
        r = QMessageBox.question(self, TITLE, "Save the changes to the block %s in your "
                                 "library?" % d.block_session.name,
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self.save_block()
        return True

    # ---- the copies in a project -------------------------------------------------------------
    def _offer_update(self, doc, defn, old_name, pin_map):
        """Ask whether the project's copies of the block take the new one (Yes first): one
        undoable step. Returns how many were updated."""
        if doc is None or is_block_doc(doc) or not self._is_open(doc):
            return 0
        n = len(BE.copies(doc.project, old_name))
        if not n:
            return 0
        what = "the %d copies of %s" % (n, old_name) if n > 1 else "the copy of %s" % old_name
        r = QMessageBox.question(self, "Update blocks", "Update %s in %s?" % (what, doc.name()),
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if r != QMessageBox.Yes:
            self._say("%s in %s keep%s the old drawing (other projects keep theirs too)"
                      % (what[0].upper() + what[1:], doc.name(), "" if n > 1 else "s"))
            return 0
        with doc.project.edit("Update %s" % defn.name) as ed:
            count, stranded = BE.update_copies(ed, doc.project, defn, old_name, pin_map)
        msg = "Updated %d cop%s of %s in %s" % (count, "ies" if count != 1 else "y", defn.name,
                                                 doc.name())
        if stranded:
            msg += "; %d wire(s) stay where they were: their pin is gone" % stranded
        self._say(msg)
        return count
