"""Updates through the app, as in KanzonasPDF: ask GitHub for KanzonasCAD's releases (once a
day at most, in the background, silently when offline), tell the user about a newer one with
the notes of every version since theirs, and update when they say so.

How it updates depends on how KanzonasCAD runs:
- From source (a git clone, as the README sets up): `git checkout main`, `git pull` and
  `pip install` (SourceUpdater), then it starts again.
- Installed on Windows with KanzonasCAD's setup (its uninstaller unins000.exe sits beside the
  program): the release's setup is downloaded into a new private folder, used only if its
  sha256 matches the digest GitHub publishes, and run quietly over this copy once KanzonasCAD
  has closed, for this user or for all users as it was installed (all users: Windows'
  administrator prompt); it starts KanzonasCAD again (ZipUpdater with setup=True,
  installer_command).
- The Windows zip (a folder with KanzonasCAD.exe, unpacked by hand): the release's zip is
  downloaded and checked the same way; it is unpacked beside the program and, once
  KanzonasCAD has closed, a small script copies it over the old files and starts the new
  version (ZipUpdater).
- The Linux build: tells, and opens the release page (no self-update yet).
"""

import hashlib
import json
import math
import os
import shutil
import sys
import time
import zipfile
from urllib.parse import urlparse

from PySide6.QtCore import QCoreApplication, QObject, QProcess, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__

REPO = "keithlyding/KanzonasCAD"
API = "https://api.github.com/repos/" + REPO + "/releases?per_page=30"
RELEASES_PAGE = "https://github.com/" + REPO + "/releases"
DAY = 24 * 3600
STAGING = "_update"              # folder beside KanzonasCAD.exe holding the unpacked version
GITHUB_HOSTS = ("github.com", "objects.githubusercontent.com",
                "release-assets.githubusercontent.com")
NOTES_OPEN = "<!-- kanzonascad-notes -->"
NOTES_CLOSE = "<!-- /kanzonascad-notes -->"


# ---- versions and notes -------------------------------------------------------------------------
def version_tuple(text):
    """'v0.3.1' -> (0, 3, 1). The first part that isn't a number ends it."""
    parts = []
    for p in str(text).strip().lstrip("vV").split("."):
        digits = ""
        for ch in p:
            if not ch.isdigit():
                break
            digits += ch
        if not digits or len(digits) > 9:
            break
        parts.append(int(digits))
    return tuple(parts)


def _order(v):
    v = list(v)
    while v and v[-1] == 0:              # 1.5.0 is 1.5
        v.pop()
    return tuple(v)


def _usable(r):
    return isinstance(r, dict) and not r.get("draft") and _order(version_tuple(
        r.get("tag_name", "")))


def newest_release(releases, current=None):
    """GitHub's entry for the newest release newer than current, or None."""
    cur = _order(version_tuple(current or __version__))
    best = None
    for r in releases or []:
        if not _usable(r):
            continue
        v = _order(version_tuple(r["tag_name"]))
        if v > cur and (best is None or v > best[0]):
            best = (v, r)
    return best[1] if best else None


def release_notes(release):
    """The short notes in a release's text (between the kanzonascad-notes marks), or None."""
    body = (release or {}).get("body") if isinstance(release, dict) else None
    if not isinstance(body, str):
        return None
    a = body.find(NOTES_OPEN)
    if a < 0:
        return None
    a += len(NOTES_OPEN)
    b = body.find(NOTES_CLOSE, a)
    return body[a:b if b >= 0 else len(body)].strip() or None


def notes_since(releases, current=None):
    """[(version, notes or None, page)] of every release newer than current, newest first."""
    cur = _order(version_tuple(current or __version__))
    found = []
    for r in releases or []:
        if _usable(r):
            v = _order(version_tuple(r["tag_name"]))
            if v > cur:
                found.append((v, r))
    found.sort(key=lambda x: x[0], reverse=True)
    return [(str(r["tag_name"]).lstrip("vV"), release_notes(r), page(r)) for _v, r in found]


def page(release):
    url = (release or {}).get("html_url")
    return url if isinstance(url, str) and url.startswith("https://github.com/") \
        else RELEASES_PAGE


# ---- release files ----------------------------------------------------------------------------
def windows_asset_name(version):
    return "KanzonasCAD-v%s-windows.zip" % version


def setup_asset_name(version):
    return "KanzonasCAD-v%s-setup.exe" % version


def _sha256_hex(asset):
    digest = (asset or {}).get("digest") or ""
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        return None
    h = digest[len("sha256:"):]
    if len(h) != 64 or any(c not in "0123456789abcdefABCDEF" for c in h):
        return None
    return h.lower()


def asset(release, name):
    """(download url, sha256 hex) of the release file called name, or None: only from a
    GitHub host over https, and only when GitHub published its sha256."""
    for a in (release or {}).get("assets") or []:
        if not isinstance(a, dict) or a.get("name") != name:
            continue
        url = a.get("browser_download_url") or ""
        p = urlparse(url)
        if p.scheme != "https" or p.username or p.password \
                or (p.hostname or "").lower() not in GITHUB_HOSTS:
            return None
        h = _sha256_hex(a)
        return (url, h) if h else None
    return None


# ---- how this copy runs ------------------------------------------------------------------------
def source_folder():
    """The git clone KanzonasCAD runs from, or None (a built copy, or not a clone)."""
    if getattr(sys, "frozen", False):
        return None
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root if os.path.isdir(os.path.join(root, ".git")) else None


def app_folder():
    """The folder holding KanzonasCAD.exe (a built Windows copy), else None."""
    if os.name == "nt" and getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return None


def installed(folder):
    """True for a copy installed by KanzonasCAD's setup (its uninstaller sits beside it)."""
    return bool(folder) and os.path.isfile(os.path.join(folder, "unins000.exe"))


def how():
    """'source', 'installer' (installed with the setup: the next setup updates it), 'windows'
    (the zip build: it can replace itself), or 'tell'."""
    if source_folder():
        return "source"
    folder = app_folder()
    if installed(folder):
        return "installer"
    if folder and os.access(folder, os.W_OK):
        return "windows"
    return "tell"


# the setup's AppId (installer/KanzonasCAD.iss): its uninstall entry says who it was installed for
UNINSTALL_KEY = (r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
                 r"\{3D7B9E24-6A1C-4F85-B2E0-9C4D7A15E863}_is1")


def _installed_in(hive, app_dir):
    """The setup's uninstall entry under hive (winreg.HKEY_LOCAL_MACHINE / _CURRENT_USER)
    names app_dir as where it installed: True; an entry naming another folder: False; no entry
    (or not Windows): None."""
    try:
        import winreg
    except ImportError:
        return None
    here = os.path.normcase(os.path.abspath(app_dir)).rstrip("\\/")
    found = None
    for view in (getattr(winreg, "KEY_WOW64_64KEY", 0), getattr(winreg, "KEY_WOW64_32KEY", 0)):
        try:
            with winreg.OpenKey(hive, UNINSTALL_KEY, 0, winreg.KEY_READ | view) as k:
                where = winreg.QueryValueEx(k, "InstallLocation")[0]
        except OSError:
            continue
        found = False
        if not str(where or "").strip():
            continue                    # (an empty entry names no folder)
        if os.path.normcase(os.path.abspath(str(where))).rstrip("\\/") == here:
            return True
    return found


def for_all_users(app_dir):
    """The copy in app_dir was installed for all users, so its update needs Windows'
    administrator prompt (and the setup's /ALLUSERS, or it would install a second copy for
    this user). The setup's own uninstall entry says so (also for a folder of one's own
    choosing); without one, a folder under Program Files does."""
    try:
        import winreg
        mine = _installed_in(winreg.HKEY_CURRENT_USER, app_dir)
        everyone = _installed_in(winreg.HKEY_LOCAL_MACHINE, app_dir)
    except ImportError:
        mine = everyone = None
    if everyone:
        return True
    if mine:
        return False
    here = os.path.normcase(os.path.abspath(app_dir))
    for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base and here.startswith(os.path.normcase(os.path.abspath(base)) + os.sep):
            return True
    return False


def installer_command(setup_path, app_dir):
    """How Update now runs the new setup: quietly (a progress window only, no questions), over
    the installed copy with its options kept, closing anything still using its files, for this
    user or for all users as it was installed (all users: Windows' administrator prompt), and
    starting KanzonasCAD again when done (/RELAUNCH, see installer/KanzonasCAD.iss; the Windows
    build tests this exact command line both ways)."""
    return [setup_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-",
            "/CLOSEAPPLICATIONS", "/ALLUSERS" if for_all_users(app_dir) else "/CURRENTUSER",
            "/RELAUNCH"]


def source_steps(root):
    """The commands a source update runs, in order: (program, arguments)."""
    git = shutil.which("git") or "git"
    return [(git, ["-C", root, "checkout", "main"]),
            (git, ["-C", root, "pull", "--ff-only"]),
            (sys.executable, ["-m", "pip", "install", "-r",
                              os.path.join(root, "requirements.txt"), "-c",
                              os.path.join(root, "constraints.txt"), "--quiet",
                              "--disable-pip-version-check"])]


def restart_command():
    """(program, arguments) that start KanzonasCAD again."""
    if getattr(sys, "frozen", False):
        return sys.executable, []
    exe = sys.executable
    if os.name == "nt" and exe.lower().endswith("python.exe"):
        w = exe[:-len("python.exe")] + "pythonw.exe"      # no console window
        if os.path.exists(w):
            exe = w
    return exe, ["-m", "kanzonascad"]


# ---- the Windows zip ---------------------------------------------------------------------------
def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def unpack(zip_path, app_dir):
    """Unpack a downloaded Windows zip into app_dir/_update; return the folder with the new
    KanzonasCAD.exe. Refuses a zip that would write outside that folder, or isn't
    KanzonasCAD."""
    stage = os.path.join(app_dir, STAGING)
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    root = os.path.realpath(stage)
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            raise ValueError("The download is damaged (%s). Try again." % bad)
        for name in z.namelist():
            target = os.path.realpath(os.path.join(stage, name))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError("The download contains an unsafe file name: %s" % name)
        z.extractall(stage)
    new = os.path.join(stage, "KanzonasCAD")
    if not os.path.isfile(os.path.join(new, "KanzonasCAD.exe")):
        shutil.rmtree(stage, ignore_errors=True)
        raise ValueError("The download isn't a KanzonasCAD Windows build.")
    return new


def swap_script(pid, new, app_dir):
    """Windows batch text: wait for process pid to end, copy new over app_dir, remove the
    staging folder, start KanzonasCAD again, delete itself."""
    exe = os.path.join(app_dir, "KanzonasCAD.exe")
    stage = os.path.join(app_dir, STAGING)
    return "\r\n".join([
        "@echo off",
        ":wait",
        'tasklist /FI "PID eq %d" 2>nul | find "%d" >nul' % (pid, pid),
        "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)",
        'robocopy "%s" "%s" /MIR /R:5 /W:1 /NFL /NDL /NJH /NJS >nul'
        % (os.path.join(new, "_internal"), os.path.join(app_dir, "_internal")),
        "set rc=%errorlevel%",
        'robocopy "%s" "%s" /E /XD "%s" /R:5 /W:1 /NFL /NDL /NJH /NJS >nul'
        % (new, app_dir, os.path.join(new, "_internal")),
        "if errorlevel 8 set rc=8",
        'rmdir /s /q "%s"' % stage,
        'if %%rc%% GEQ 8 (echo Updating KanzonasCAD failed. Download it again from %s & pause)'
        % RELEASES_PAGE,
        'start "" "%s"' % exe,
        '(goto) 2>nul & del "%~f0"',
        ""])


# ---- checking ----------------------------------------------------------------------------------
class UpdateChecker(QObject):
    """found(release, notes_since) when a newer release exists; result(text) after a check the
    user asked for (nothing newer, or it couldn't check)."""
    found = Signal(object, object)
    result = Signal(str)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.net = None
        self._reply = None

    def enabled(self):
        return self.settings.value("update_check", "true") not in (False, "false")

    def check_if_due(self):
        if not self.enabled():
            return
        try:
            last = float(self.settings.value("update_last", 0) or 0)
        except (TypeError, ValueError):
            last = 0
        now = time.time()
        if not math.isfinite(last) or last > now or now - last >= DAY:
            self.check(manual=False)

    def check(self, manual=True):
        if self._reply is not None and self._reply.isRunning():
            if not manual:
                return
            self._reply.abort()
        if self.net is None:
            self.net = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(API))
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setRawHeader(b"User-Agent", ("KanzonasCAD/" + __version__).encode())
        req.setTransferTimeout(15000)
        reply = self._reply = self.net.get(req)
        reply.finished.connect(lambda: self._done(reply, manual))

    def _done(self, reply, manual):
        reply.deleteLater()
        if self._reply is reply:
            self._reply = None
        if reply.error() != QNetworkReply.NoError:
            if manual and reply.error() != QNetworkReply.OperationCanceledError:
                self.result.emit("Couldn't reach GitHub to check for updates (%s)."
                                 % reply.errorString())
            return
        try:
            data = json.loads(bytes(reply.readAll()).decode("utf-8"))
        except (ValueError, RecursionError):
            data = None
        self.handle(data, manual)

    def handle(self, data, manual):
        """What GitHub answered (a list of releases)."""
        if not isinstance(data, list):
            if manual:
                self.result.emit("GitHub sent an unexpected answer. Try again later.")
            return
        self.settings.setValue("update_last", time.time())
        rel = newest_release(data)
        if rel is None:
            if manual:
                self.result.emit("You have the latest version (%s)." % __version__)
            return
        v = str(rel["tag_name"]).lstrip("vV")
        if not manual and self.settings.value("update_skip", "") == v:
            return
        self.found.emit(rel, notes_since(data))


# ---- updating ----------------------------------------------------------------------------------
class SourceUpdater(QObject):
    """Runs source_steps one after another. line(text) as they print; finished(ok, text)."""
    line = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.steps = source_steps(root)
        self.proc = None

    def start(self):
        self._next()

    def _next(self):
        if not self.steps:
            self.finished.emit(True, "Updated.")
            return
        prog, args = self.steps.pop(0)
        self.line.emit("> %s %s" % (os.path.basename(prog), " ".join(args)))
        p = self.proc = QProcess(self)
        p.setProcessChannelMode(QProcess.MergedChannels)
        p.readyReadStandardOutput.connect(
            lambda: self.line.emit(bytes(p.readAllStandardOutput()).decode(errors="replace")
                                   .rstrip()))
        p.errorOccurred.connect(lambda err: self._failed(
            "Couldn't run %s (%s). Is it installed?" % (os.path.basename(prog), p.errorString()))
            if err == QProcess.FailedToStart else None)
        p.finished.connect(lambda code, _status: self._next() if code == 0 else self._failed(
            "%s stopped with an error (code %d): see the messages above. README.md (If "
            "something goes wrong) explains the usual ones." % (os.path.basename(prog), code)))
        p.start(prog, args)

    def _failed(self, text):
        self.steps = []
        self.finished.emit(False, text)


class ZipUpdater(QObject):
    """Downloads the Windows zip, checks its sha256, unpacks it beside the program; or, with
    setup=True, downloads the setup into a new folder only this user can write to and checks
    it. progress(received, total); ready(folder of the new version, or the checked setup's
    path); failed(text)."""
    progress = Signal(int, int)
    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, url, sha256, app_dir, parent=None, setup=False):
        super().__init__(parent)
        self.url, self.sha256, self.app_dir, self.setup = url, sha256, app_dir, setup
        self.net = QNetworkAccessManager(self)
        self.reply = None
        self.file = None
        self.path = None if setup else os.path.join(app_dir, STAGING + ".zip")
        self._keep = False

    def start(self):
        try:
            if self.setup:
                # (a fresh folder of this user's, under a name nobody can guess: nobody else
                # can put a file there between the check and the run)
                import tempfile
                folder = tempfile.mkdtemp(prefix="kzcadsetup")
                self.path = os.path.join(folder, os.path.basename(urlparse(self.url).path)
                                         or "KanzonasCAD-setup.exe")
            self.file = open(self.path, "wb")
        except OSError as e:
            self.failed.emit("Can't write the download (%s)." % e)
            return
        req = QNetworkRequest(QUrl(self.url))
        req.setRawHeader(b"User-Agent", ("KanzonasCAD/" + __version__).encode())
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute,
                         QNetworkRequest.NoLessSafeRedirectPolicy)
        req.setTransferTimeout(60000)
        r = self.reply = self.net.get(req)
        r.readyRead.connect(lambda: self.file.write(bytes(r.readAll())))
        r.downloadProgress.connect(lambda a, b: self.progress.emit(int(a), int(b)))
        r.finished.connect(self._done)
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.cancel)

    def cancel(self):
        if self.reply is not None and self.reply.isRunning():
            self.reply.abort()

    def _done(self):
        r = self.reply
        r.deleteLater()
        try:
            self.file.write(bytes(r.readAll()))
            self.file.close()
            if r.error() != QNetworkReply.NoError:
                if r.error() != QNetworkReply.OperationCanceledError:
                    self.failed.emit("The download failed (%s)." % r.errorString())
                return
            if file_sha256(self.path) != self.sha256:
                self.failed.emit("The download was not used: its sha256 doesn't match the "
                                 "release.")
                return
            if self.setup:
                self._keep = True               # checked: kept for running
                self.ready.emit(self.path)
            else:
                self.ready.emit(unpack(self.path, self.app_dir))
        except (OSError, ValueError, zipfile.BadZipFile) as e:
            self.failed.emit(str(e))
        finally:
            if not self._keep:
                try:
                    os.remove(self.path)
                except OSError:
                    pass            # (only the download: it may already be gone)
                if self.setup:
                    try:
                        os.rmdir(os.path.dirname(self.path))
                    except OSError:
                        pass        # (its own empty folder only)


def start_swap(new, app_dir):
    """Write the swap script and start it, detached: it waits for this process to end."""
    import subprocess
    script = os.path.join(app_dir, "_update.bat")
    with open(script, "w", encoding="ascii", errors="replace") as f:
        f.write(swap_script(os.getpid(), new, app_dir))
    subprocess.Popen(["cmd", "/c", script], cwd=app_dir,
                     creationflags=0x00000008 | 0x00000200)   # DETACHED | NEW_PROCESS_GROUP


def start_setup(setup_path, app_dir):
    """Start the checked setup, detached: it closes anything still using KanzonasCAD's files,
    updates it and starts it again (for an all-users copy, it asks Windows for administrator
    rights itself)."""
    import subprocess
    subprocess.Popen(installer_command(setup_path, app_dir), close_fds=True)
