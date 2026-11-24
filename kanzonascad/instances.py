"""The other copies of KanzonasCAD running on this computer for this user (the owner, 0.16:
"When updating, if I have two instances of the application running, only one quits").

Each copy started normally (not the self-test) listens on a local socket of its own (a named
pipe on Windows) and leaves a note with its process id in the data folder's "running"
folder; it takes the note away when it ends. Update asks every other copy to close, as Quit
would (each asks to save its changes), before it replaces the program:

  close-for-update        ->  "closed <JSON list of the files it had open>" or "kept"

A note whose copy doesn't answer (it ended without taking it away) is removed. The files
the others had open come back with the reply, so "Open the files that were open when it
last closed" reopens them all after an update."""

import json
import os

from PySide6.QtCore import QEventLoop, QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

ASK = b"close-for-update\n"


def _server_name(folder, pid):
    # (one name per data folder: a portable copy and the installed one are separate programs)
    import hashlib
    h = hashlib.sha1(os.path.normcase(os.path.abspath(folder)).encode("utf-8")).hexdigest()
    return "kanzonascad-%s-%d" % (h[:12], pid)


class Instances(QObject):
    """This copy's place among the running copies. asked() is emitted when another copy asks
    this one to close for an update: the handler (MainWindow) answers with answer(closed,
    files)."""
    asked = Signal()

    def __init__(self, folder=None, pid=None, parent=None):
        super().__init__(parent)
        if folder is None:
            from .paths import data_dir
            folder = data_dir("running")
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.pid = os.getpid() if pid is None else pid
        self.name = _server_name(folder, self.pid)
        self.server = QLocalServer(self)
        QLocalServer.removeServer(self.name)        # (left by a copy that crashed)
        self.server.setSocketOptions(QLocalServer.UserAccessOption)
        if not self.server.listen(self.name):
            raise OSError("can't listen for the other copies (%s)" % self.server.errorString())
        self.server.newConnection.connect(self._connected)
        self._asking = None
        # (written whole, then put in place: a copy reading a note half written saw no name,
        # took this copy for gone and removed its note; CI, Nov 2026)
        tmp = self._note(self.pid) + ".new"
        with open(tmp, "w", encoding="ascii") as f:
            f.write(self.name)
        os.replace(tmp, self._note(self.pid))

    def _note(self, pid):
        return os.path.join(self.folder, str(pid))

    def stop(self):
        """This copy is ending: no more questions, its note taken away."""
        self.server.close()
        try:
            os.remove(self._note(self.pid))
        except OSError:
            pass                    # (already gone: nothing to take away)

    # ---- asked by another copy ------------------------------------------------------------
    def _connected(self):
        while self.server.hasPendingConnections():
            s = self.server.nextPendingConnection()
            s.readyRead.connect(lambda s=s: self._read(s))

    def _read(self, s):
        if not s.canReadLine():
            return
        line = bytes(s.readLine())
        if line == ASK:
            self._asking = s
            self.asked.emit()

    def answer(self, closed, files=()):
        """Tell the copy that asked whether this one closed (and the files it had open)."""
        s, self._asking = self._asking, None
        if s is None:
            return
        reply = ("closed " + json.dumps(list(files)) + "\n") if closed else "kept\n"
        s.write(reply.encode("utf-8"))
        s.flush()
        s.waitForBytesWritten(2000)

    # ---- asking the others ----------------------------------------------------------------
    def others(self):
        """The process ids with a note, other than this one."""
        out = []
        for n in os.listdir(self.folder):
            if n.isdigit() and int(n) != self.pid:
                out.append(int(n))
        return sorted(out)

    def running_others(self):
        """How many other copies are running now (notes of copies that ended without taking
        them away are removed)."""
        n = 0
        for pid in self.others():
            try:
                with open(self._note(pid), encoding="ascii") as f:
                    name = f.read().strip()
            except OSError:
                continue
            s = QLocalSocket()
            s.connectToServer(name)
            if s.waitForConnected(500):
                n += 1
                s.disconnectFromServer()
            else:
                try:
                    os.remove(self._note(pid))
                except OSError:
                    pass            # (the copy took it away itself)
        return n

    def close_others(self, wait_ms=600000):
        """Ask every other copy to close. Returns (closed, kept, files): how many closed, how
        many stayed open (asked to save, the question was cancelled), and the files the
        closed ones had open. A copy that doesn't answer at all (gone) has its note
        removed."""
        closed = kept = 0
        files = []
        for pid in self.others():
            try:
                with open(self._note(pid), encoding="ascii") as f:
                    name = f.read().strip()
            except OSError:
                continue            # (it ended while we were looking)
            got = self._ask(name, wait_ms)
            if got is None:
                try:
                    os.remove(self._note(pid))
                except OSError:
                    pass            # (the copy took it away itself)
                continue
            if got[0]:
                closed += 1
                files += got[1]
            else:
                kept += 1
        return closed, kept, files

    def _ask(self, name, wait_ms):
        """(closed, files), or None when nothing answers at that name."""
        s = QLocalSocket(self)
        loop = QEventLoop()
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        got = {"line": None, "gone": False}

        def read():
            if s.canReadLine():
                got["line"] = bytes(s.readLine()).decode("utf-8", "replace").strip()
                loop.quit()

        def gone():
            got["gone"] = True
            loop.quit()
        s.readyRead.connect(read)
        s.disconnected.connect(gone)
        s.errorOccurred.connect(lambda _e: gone())
        s.connectToServer(name)
        if s.state() == QLocalSocket.UnconnectedState:
            s.deleteLater()
            return None
        if s.state() != QLocalSocket.ConnectedState:
            s.connected.connect(loop.quit)
            timer.start(3000)
            loop.exec()
            if s.state() != QLocalSocket.ConnectedState:
                s.abort()
                s.deleteLater()
                return None
        s.write(ASK)
        s.flush()
        timer.start(wait_ms)            # (it may be asking its user to save)
        if got["line"] is None and not got["gone"]:
            loop.exec()
        timer.stop()
        alive = s.state() == QLocalSocket.ConnectedState and not got["gone"]
        if got["line"] is None and alive:
            # (the wait ran out: its answer may be here already, behind other work in the queue
            # (in the unit tests, a slow event left by an earlier test made a copy that had
            # answered "kept" count as gone): what is waiting is handled, briefly, then read.
            # Not waitForReadyRead: Qt warns it may fail on Windows)
            loop.processEvents(QEventLoop.AllEvents, 50)
            read()
        line = got["line"]
        s.abort()
        s.deleteLater()
        if line is None:
            # (still there but silent: it is running, asking its user, say; it stays open, and
            # its note with it: only a copy that's gone is taken off the list)
            return (False, []) if alive else None
        if line.startswith("closed"):
            try:
                files = json.loads(line[len("closed"):].strip() or "[]")
            except ValueError:
                files = []
            return True, [f for f in files if isinstance(f, str)]
        return False, []
