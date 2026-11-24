"""MainWindow's side of file locking (filelock.py has the note itself): the question when a
project is open elsewhere, read-only projects, the lock moved by Save As, taken away on close.

Read-only, as AutoCAD's read-only drawings: everything works (looking, printing, exporting,
copying, even editing, to try something out), but Save never writes over the original: it
says so on the command line, and Save As makes your own copy, which is then yours to edit
(and locked). Its autosave copy goes to the recovery folder under a name of its own, so it
can't take the place of the other copy's, and comes back from a crash as an unsaved project."""

import os

from PySide6.QtWidgets import QMessageBox

from . import filelock

APP = "KanzonasCAD"
READ_ONLY_SAVE = "read-only: use Save As..."


def is_read_only(project):
    return bool(getattr(project, "read_only", False))


class Locking:
    """MainWindow's lock commands (see main_window.py for the actions and menus)."""

    lock_who = None             # (who this window opens as: filelock.Who(); the tests set it)

    def _who(self):
        main = self.family[0] if getattr(self, "family", None) else self
        return getattr(main, "lock_who", None) or filelock.Who()

    def ask_locked(self, path, info):
        """The question when a project is open for editing elsewhere: "read_only" (the
        default), "anyway" or None (Cancel)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(APP)
        box.setText(filelock.describe(path, info))
        box.setInformativeText("Open it read-only to look at it, print or copy from it (Save "
                               "As makes your own copy), or open it anyway to edit it.")
        ro = box.addButton("Open read-only", QMessageBox.AcceptRole)
        anyway = box.addButton("Open anyway", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(ro)
        box.exec()
        got = box.clickedButton()
        if got is ro:
            return "read_only"
        if got is anyway:
            return "anyway"
        return None

    def _confirm_anyway(self, path, info):
        r = QMessageBox.warning(
            self, APP, "%s\n\nIf you both save, each copy saves over the other's changes. "
            "Open it for editing anyway?" % filelock.describe(path, info),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return r == QMessageBox.Yes

    def lock_for_open(self, path):
        """Before a project is read: (lock, read-only reason or None), or None when the
        user cancelled. lock is None for a read-only project."""
        why = None
        if os.path.exists(path) and not os.access(path, os.W_OK):
            return None, "the file itself is read-only"
        try:
            return filelock.acquire(path, self._who()), None
        except filelock.Unwritable as ex:
            why = "its folder can't be written (%s), so it can't be marked as open for " \
                  "editing" % ex
            return None, why
        except filelock.Held as held:
            info = held.info
        got = self.ask_locked(path, info)
        if got is None:
            return None
        if got == "anyway" and self._confirm_anyway(path, info):
            try:
                return filelock.force(path, self._who()), None
            except (filelock.Unwritable, filelock.Held) as ex:
                return None, "its lock note couldn't be taken (%s)" % ex
        return None, "it is " + filelock.where(path, info)

    def set_read_only(self, d, why):
        """A project shown read-only, and the user told why (on the command line)."""
        d.project.read_only = True
        # (its autosave copy under a name of its own: never the editing copy's, never the file)
        import uuid
        d.autosave_key = "read-only-" + uuid.uuid4().hex
        self._project_changed(d)
        self._say("%s is read-only (%s): Save As makes your own copy. File > Reopen for "
                  "editing opens it for editing once the other copy has closed it." % (
                      os.path.basename(d.project.path), why), 12000)

    def drop_lock(self, project):
        """The project closed (no window shows it any more): its note taken away."""
        lock = getattr(project, "lock", None)
        project.lock = None
        if lock is not None:
            try:
                lock.release()
            except OSError as ex:
                self.statusBar().showMessage("Couldn't take away the lock note %s: %s" % (
                    lock.note, ex), 8000)

    def refuse_read_only_save(self, d):
        """Save on a read-only project: said, nothing written. True when refused."""
        if not is_read_only(d.project):
            return False
        self._say(READ_ONLY_SAVE)
        return True

    def lock_for_save(self, d, path):
        """Before saving to path: True to go on (the lock moved there when the path is a new
        one, the old one kept until the save is done: finish_save_lock), False to stop."""
        from .paths import path_key
        p = d.project
        lock = getattr(p, "lock", None)
        if lock is not None and path_key(lock.path) == path_key(path):
            if lock.ours():
                return True
            got = filelock.read(path)
            if got:
                r = QMessageBox.warning(
                    self, APP, "%s\nSomeone opened it anyway since you opened it. Save over it "
                    "anyway?" % filelock.describe(path, got),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if r != QMessageBox.Yes:
                    return False
            try:
                p.lock = filelock.force(path, self._who())
            except (filelock.Unwritable, filelock.Held) as ex:
                self._say("Saved without a lock note (%s)" % ex)
                p.lock = None
            lock.release()
            return True
        try:
            p.new_lock = filelock.acquire(path, self._who())
        except filelock.Held as held:
            QMessageBox.warning(self, APP, "%s\nIt can't be saved over while it is open there: "
                                "choose another name." % filelock.describe(path, held.info))
            return False
        except filelock.Unwritable as ex:
            p.new_lock = None
            self._say("Saved without a lock note: its folder can't take one (%s)" % ex)
        return True

    def finish_save_lock(self, d, ok):
        """After a save: the lock is the new file's (and the project editable), or, the save
        failed, the new note taken away."""
        p = d.project
        if not hasattr(p, "new_lock"):
            return
        new = p.new_lock
        del p.new_lock
        if not ok:
            if new is not None:
                new.release()
            return
        old = getattr(p, "lock", None)
        p.lock = new
        if old is not None:
            old.release()
        if is_read_only(p):
            p.read_only = False
            self._say("%s is your own copy: it can be edited and saved" % os.path.basename(
                p.path))

    def reopen_for_editing(self):
        """File > Reopen for editing: a read-only project opened again for editing, once the
        other copy has closed it (the file as it is now: unsaved changes made here asked
        about first)."""
        d = self.doc()
        if d is None or not is_read_only(d.project) or not d.project.path:
            self._say("Reopen for editing: the project shown isn't read-only")
            return None
        path = d.project.path
        got = filelock.read(path)
        if got and not filelock.stale(got, self._who()):
            self._say("Reopen for editing: " + filelock.describe(path, got))
            return None
        if d.project.is_modified():
            r = QMessageBox.question(self, APP, "Reopen %s for editing? The changes made here "
                                     "(read-only) are lost: it opens as it is saved now." %
                                     os.path.basename(path),
                                     QMessageBox.Yes | QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return None
            d.project.saved_at = len(d.project.undo_stack)      # (answered: closes quietly)
        main = self.family[0] if self.family else self
        for win, o in list(self.documents()):
            if o.project is d.project:
                win.close_tab(win.tabs.indexOf(o))
        return main.open_path(path)
