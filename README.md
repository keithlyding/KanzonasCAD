# KanzonasCAD

![KanzonasCAD](assets/kanzonascad-logo.png)

A free, open-source electrical CAD program for Windows and Linux, for people who know
AutoCAD but want fewer commands, fewer settings and fewer surprises.

- AutoCAD-style drawing: command line, object snaps, ortho, polar tracking, grips,
  window/crossing/lasso selection.
- Projects of ANSI sheets with a grid of zones (`6-D1` references) and an editable title block.
- A library of your own: JIC/NFPA schematic symbols, panel footprints and parts.
- Wires that stay attached to symbols, and buses.
- Device tags by page number (`CR601`), contacts linked to their coil, and cross-references
  that update themselves.
- Three-phase power symbols, terminal strips that number their terminals, PLC I/O points.
- Wire numbers (`6001`) that number themselves, with distribution blocks (`6001A`) and
  off-sheet connectors.
- DXF in and out, DWG in (AutoCAD R13-2018), PDF out.

Coming next: panel layouts with
DIN rail and wire duct, and reports. The plan is in [docs/ROADMAP.md](docs/ROADMAP.md).

Press **F1** in the app for the user manual.

## Install on Windows (the easy way)

1. Open the **[Releases page](https://github.com/keithlyding/KanzonasCAD/releases)** and, under
   the newest version, download **`KanzonasCAD-v<version>-setup.exe`**.
2. Run it. It asks whether to install for you only (no administrator rights needed) or for
   everyone on the PC (Windows asks for administrator rights). Windows may warn
   about an unknown publisher (the app isn't code-signed yet): **More info** > **Run anyway**.
3. Start KanzonasCAD from the Start menu. Double-clicking a `.kzcad` project opens it too.

**Updates:** KanzonasCAD tells you when a new version is out (or use **Help > Check for
updates...**). **Update now** downloads it, checks it, and installs it over your copy. Your
projects, library and settings stay as they are. A copy installed for everyone is updated
for everyone, after Windows' administrator prompt.

**Uninstall:** Windows **Settings > Apps > Installed apps > KanzonasCAD > Uninstall**. Your
projects and your library (in Documents) are kept.

The rest of this page runs KanzonasCAD from its source code instead: for trying changes before
they're released, or on a PC where you can't run a setup.

---

## Command line basics (if you've never used it)

The steps below are typed into **Command Prompt**, a window where you give Windows commands
by typing instead of clicking. Nothing you type there can harm your drawings.

- **Opening it:** press the **Windows key**, type `cmd`, and click **Command Prompt**. (Not
  "PowerShell" or "Terminal": they work a bit differently and some lines below won't work as
  written there. If a window's title says PowerShell, close it and open Command Prompt.)
- **The prompt:** the window shows a line like `C:\Users\keith>`. That is the folder you're
  "in"; commands act on it. The `>` means it's waiting for you.
- **Typing a command:** type (or paste) **one line** from below and press **Enter**. Don't type
  the spaces at the start of the lines here; they're just how this page shows commands.
- **Pasting:** copy a line here, then in Command Prompt **right-click** (or press **Ctrl+V**)
  and press Enter.
- **Waiting:** a command is finished when the `C:\...>` line comes back. Some take a few
  minutes and print a lot (that's normal); don't type the next one until the prompt is back.
- **Red text or "error":** stop there, and copy what it printed (drag over it with the mouse,
  then press **Enter** or Ctrl+C to copy) to ask for help. See *If something goes wrong* below.
- **`cd`** means "change directory": go into a folder. `cd %USERPROFILE%\KanzonasCAD` goes
  into the KanzonasCAD folder in your user folder (`%USERPROFILE%` stands for
  `C:\Users\<you>`).
- **Up arrow** brings back the last command, so you don't have to retype it.

## Install from source on Windows (once)

This runs KanzonasCAD from its source code, so updating is one double-click. You need
**Python** (runs the program) and **Git** (downloads it and its updates).

**1. Install Python and Git.** Open **Command Prompt** (Start menu, type `cmd`) and run:

    winget install -e --id Python.Python.3.12
    winget install -e --id Git.Git

Accept the prompts. If `winget` is "not recognized", install them from the websites instead:
[Python 3.12](https://www.python.org/downloads/windows/) (tick **"Add python.exe to PATH"**)
and [Git](https://git-scm.com/download/win) (the default choices are fine).

**2. Close Command Prompt and open a new one.** A window opened before the installs doesn't
know about them yet; skipping this gives "'py' is not recognized".

**3. Check both work:**

    py --version
    git --version

You should see `Python 3.12.x` and `git version 2.x`.

**4. Download KanzonasCAD and what it needs:**

    cd %USERPROFILE%
    git clone https://github.com/keithlyding/KanzonasCAD.git
    cd KanzonasCAD
    py -m pip install -r requirements.txt -c constraints.txt

This makes the folder `C:\Users\<you>\KanzonasCAD`. The last line downloads about 200 MB (Qt,
the window toolkit) and takes a few minutes the first time only.

**5. Start it:**

    py -m kanzonascad

Or double-click **`KanzonasCAD.bat`** in the `KanzonasCAD` folder. For a desktop icon:
right-click `KanzonasCAD.bat` > **Show more options** > **Send to** > **Desktop (create
shortcut)**.

## Update from source on Windows

Double-click **`update.bat`** in the `KanzonasCAD` folder. It gets the newest tested version
(`main`) and anything new it needs, then says **Done**.

Or the same from Command Prompt:

    cd %USERPROFILE%\KanzonasCAD
    git checkout main
    git pull
    py -m pip install -r requirements.txt -c constraints.txt

Your projects (`.kzcad` files) and your symbol library are not touched by updating: they live
outside this folder. **Don't save projects inside the `KanzonasCAD` folder.**

### Trying a version that isn't finished yet

Work in progress lives on its own branch until it's built and merged into `main`. To try one
(the name comes from the person or agent working on it, for example `claude/tags`):

    cd %USERPROFILE%\KanzonasCAD
    git fetch
    git checkout claude/tags
    git pull
    py -m kanzonascad

Back to the tested version: `git checkout main` (or double-click `update.bat`).

### If something goes wrong

| What you see | What to do |
| --- | --- |
| `'py'` or `'git' is not recognized` | Open a **new** Command Prompt. Still there: install it again from the website above. |
| `Your local changes to the following files would be overwritten` | You (or something) changed a file in the folder. Throw those changes away with `git checkout -- .` and run the update again. |
| `fatal: not a git repository` | You're not in the folder: run `cd %USERPROFILE%\KanzonasCAD` first. |
| `cd %USERPROFILE%...` says the path can't be found, or `%USERPROFILE%` shows up as text | You're in PowerShell, not Command Prompt. Open Command Prompt (Windows key, type `cmd`), or in PowerShell type `cd ~\KanzonasCAD` instead. |
| Nothing happens, the cursor just blinks | The command is still working (downloads take minutes). Wait for the `C:\...>` line to come back. |
| `No module named ...` when starting | Run `py -m pip install -r requirements.txt -c constraints.txt` again. |
| Anything else | Start it from Command Prompt with `py -m kanzonascad` and send the last lines it prints. |

Starting over is always safe: delete the `KanzonasCAD` folder and repeat step 4.

## Install on Linux

    sudo apt install python3 python3-pip python3-venv git      # Debian/Ubuntu
    git clone https://github.com/keithlyding/KanzonasCAD.git
    cd KanzonasCAD
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt -c constraints.txt
    .venv/bin/python -m kanzonascad

Update: `git checkout main && git pull && .venv/bin/pip install -r requirements.txt -c
constraints.txt`.

## Windows without installing (the zip)

Each version on the **[Releases page](https://github.com/keithlyding/KanzonasCAD/releases)**
also has `KanzonasCAD-v<version>-windows.zip`: unzip it anywhere (a USB stick, a shared
drive) and run `KanzonasCAD\KanzonasCAD.exe`. Windows may warn about an unknown publisher (the app isn't
code-signed): **More info** > **Run anyway**. KanzonasCAD then tells you about new versions and updates
itself (Help > Check for updates...).

---

## For developers

Self-test: `py -m kanzonascad --selftest selftest.log` (exit code 0 = passed).
Tests: `py -m unittest discover -s tests -p "test_*.py" -t .`
Rules for contributors (people and AI agents): [AGENTS.md](AGENTS.md).

MIT License. See [NOTICE.md](NOTICE.md) for the libraries it is built on.
