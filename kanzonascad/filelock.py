"""A project open for editing, marked so (the owner, 0.25: "I was able to open two instances
of the same file in two different instances of KanzonasCAD. I think we need something to say
locked for editing, open as read only?").

Opening a project for editing writes a small note beside it, named as LibreOffice names its
own: ".~lock.<file name>#" (Plant.kzcad: ".~lock.Plant.kzcad#"), the same name on Windows and
Linux. On Linux the dot hides it; on Windows the note also gets the hidden attribute. It holds
JSON: the program, its version, the user, the computer, the process id, when it was opened,
and an id of its own (two windows of one program on one computer told apart). Closing the
project takes it away; a note is only ever taken away by the copy whose id it holds.

The note is made with O_CREAT | O_EXCL (one call that fails when the file is there), so two
people opening a project on a network share at the same moment can't both have it. A note
whose copy is gone (from this computer, its process no longer running: a crash, a power cut)
is taken over: renamed out of the way first (only one copy's rename can succeed), then made
anew as above. A note from another computer can't be checked from here.

No Qt here: main_window.py asks the questions."""

import json
import os
import sys
import time
import uuid

PREFIX = ".~lock."
SUFFIX = "#"
PROGRAM = "KanzonasCAD"
STALE_UNREADABLE = 10.0         # seconds: a note still half written after this is a leftover

_held = []                      # the notes this program holds (taken away at exit: release_all)


def note_path(path):
    """The lock note of a project file."""
    folder, name = os.path.split(os.path.abspath(path))
    return os.path.join(folder, PREFIX + name + SUFFIX)


class Who:
    """Who opens: this user on this computer in this process (the tests make others)."""

    def __init__(self, user=None, computer=None, pid=None):
        self.user = user or _user()
        self.computer = computer or _computer()
        self.pid = os.getpid() if pid is None else int(pid)

    def same_computer(self, info):
        # (Windows' computer names aren't case sensitive; nor are most networks' names)
        return (info.get("computer") or "").casefold() == self.computer.casefold()


def _user():
    import getpass
    try:
        return getpass.getuser()
    except (OSError, KeyError, ImportError):    # (no user name from the system: the env's)
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown user"


def _computer():
    import platform
    return platform.node() or os.environ.get("COMPUTERNAME") or "unknown computer"


def running(pid):
    """Whether a process of that id is running on this computer (without other libraries:
    on Windows OpenProcess and its exit code, elsewhere signal 0)."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if sys.platform == "win32":
        return _running_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                 # (someone else's process: it is running)
    return True


def _running_windows(pid):
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    h = k.OpenProcess(0x1000, False, pid)       # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ctypes.get_last_error() == 5     # (ERROR_ACCESS_DENIED: it is there)
    try:
        code = wintypes.DWORD()
        if not k.GetExitCodeProcess(h, ctypes.byref(code)):
            return True
        return code.value == 259                # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


def _hide(path):
    """The Windows hidden attribute on a note (elsewhere its dot hides it)."""
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.SetFileAttributesW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD)
    k.SetFileAttributesW(path, 0x2)             # FILE_ATTRIBUTE_HIDDEN (shown or not: no harm)


class Lock:
    """A note this program wrote and holds."""

    def __init__(self, path, info):
        self.path = os.path.abspath(path)       # (the project's file)
        self.info = info

    @property
    def note(self):
        return note_path(self.path)

    def ours(self):
        """Whether the note beside the project is still this one (False: it is gone, or
        someone chose Open anyway and wrote theirs)."""
        got = read(self.path)
        return got is not None and got.get("id") == self.info["id"]

    def release(self):
        """Take the note away (only if it is still ours)."""
        if self in _held:
            _held.remove(self)
        if self.ours():
            os.remove(self.note)


class Held(Exception):
    """The project is open for editing elsewhere: info is the note's (user, computer,
    pid, opened)."""

    def __init__(self, path, info):
        super().__init__(describe(path, info))
        self.path, self.info = path, info


class Unwritable(Exception):
    """The note couldn't be written (a read-only folder or share, no permission)."""


def _new_info(who):
    from . import __version__
    return {"program": PROGRAM, "version": __version__, "user": who.user,
            "computer": who.computer, "pid": who.pid,
            "opened": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "id": uuid.uuid4().hex}


def _raw(path):
    with open(note_path(path), "rb") as f:
        return f.read()


def _parse(raw):
    try:
        got = json.loads(raw.decode("utf-8"))
    except ValueError:
        return {}
    return got if isinstance(got, dict) else {}


def read(path):
    """The note beside a project as a dict, or None when there is none. A note that isn't
    one of ours (half written, or garbled) comes back as {} (held by someone unknown)."""
    try:
        return _parse(_raw(path))
    except FileNotFoundError:
        return None


def _create(path, info):
    """Make the note, failing when one is there (FileExistsError): the one atomic step."""
    note = note_path(path)
    fd = os.open(note, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0),
                 0o644)
    try:
        os.write(fd, json.dumps(info, indent=1).encode("utf-8"))
    finally:
        os.close(fd)
    _hide(note)


def stale(info, who):
    """Whether a note can be taken over without asking: from this computer, and its
    process isn't running."""
    if not who.same_computer(info):
        return False
    pid = info.get("pid")
    return not running(pid if isinstance(pid, int) else -1)


def _old_unreadable(path):
    try:
        return time.time() - os.path.getmtime(note_path(path)) > STALE_UNREADABLE
    except OSError:
        return False


def _take_over(path, seen):
    """Move a stale note out of the way, if it is still the one seen (raw bytes): True when
    it was (or was already gone); False when another copy's note is there now."""
    note = note_path(path)
    aside = note + "." + uuid.uuid4().hex[:8] + ".old"
    try:
        os.rename(note, aside)
    except FileNotFoundError:
        return True
    with open(aside, "rb") as f:
        got = f.read()
    if got == seen:
        os.remove(aside)
        return True
    # (another copy took it over between our look and our move: its note goes back, unless
    # yet another one is there by now)
    try:
        if sys.platform == "win32":
            os.rename(aside, note)          # (fails when one is there)
        else:
            os.link(aside, note)            # (fails when one is there)
            os.remove(aside)
    except FileExistsError:
        os.remove(aside)
    except OSError:
        # (a share with no hard links: put back unless one is there; the gap is a moment)
        if not os.path.exists(note):
            os.replace(aside, note)
        else:
            os.remove(aside)
    return False


def acquire(path, who=None, tries=4):
    """Mark a project open for editing: returns the Lock; raises Held when it is open for
    editing elsewhere (another computer, or a copy still running here), Unwritable when the
    note can't be written."""
    who = who or Who()
    info = _new_info(who)
    for _i in range(tries):
        try:
            _create(path, info)
        except FileExistsError:
            pass                            # (someone's note: looked at below)
        except OSError as ex:
            raise Unwritable(str(ex)) from ex
        else:
            lock = Lock(path, info)
            _held.append(lock)
            return lock
        try:
            raw = _raw(path)
        except FileNotFoundError:
            continue                        # (taken away meanwhile: try again)
        except OSError as ex:
            raise Unwritable(str(ex)) from ex
        got = _parse(raw)
        if got == {} and not _old_unreadable(path):
            time.sleep(0.05)                # (being written this moment: look again)
            continue
        if got != {} and not stale(got, who):
            raise Held(path, got)
        try:
            _take_over(path, raw)
        except OSError as ex:
            raise Unwritable(str(ex)) from ex
    raise Held(path, read(path) or {})


def force(path, who=None):
    """Open anyway: the note made ours whoever's it was (the other copy keeps running and
    may save over this one's changes: main_window warns first). Returns the Lock."""
    who = who or Who()
    for _i in range(4):
        try:
            os.remove(note_path(path))
        except FileNotFoundError:
            pass                            # (gone already: made below)
        except OSError as ex:
            raise Unwritable(str(ex)) from ex
        info = _new_info(who)
        try:
            _create(path, info)
        except FileExistsError:
            continue
        except OSError as ex:
            raise Unwritable(str(ex)) from ex
        lock = Lock(path, info)
        _held.append(lock)
        return lock
    raise Held(path, read(path) or {})


def when(info):
    """When a note was made, as people read it (2026-11-24 15:20)."""
    t = info.get("opened") or ""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return t or "an unknown time"


def describe(path, info):
    """"Plant.kzcad is open on DESK-7 by keith since 2026-11-24 15:20." """
    return "%s is %s." % (os.path.basename(path), where(path, info))


def where(path, info):
    """Where a note says the project is open: "open on DESK-7 by keith since ..."."""
    if not info:
        return "open for editing somewhere else (its lock note %s can't be read)" % (
            os.path.basename(note_path(path)))
    return "open on %s by %s since %s" % (
        info.get("computer") or "another computer", info.get("user") or "someone", when(info))


def release_all():
    """Every note this program holds taken away (at exit: a window not closed normally)."""
    for lock in list(_held):
        try:
            lock.release()
        except OSError:
            continue        # (at exit, nobody left to tell: the next open finds it stale)
