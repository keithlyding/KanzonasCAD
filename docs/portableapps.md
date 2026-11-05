# KanzonasCAD on PortableApps.com

Every Windows build makes the artifact `KanzonasCAD-v<version>-portableapps-layout` (a build
artifact, not a release download; one zip that opens to the `KanzonasCADPortable` folder): KanzonasCAD in the PortableApps.com Format, tested in the build (it runs, keeps its
settings in the package's `Data` folder, leaves the registry alone, and its own updater is off
because the PortableApps.com Platform updates it).

Two steps need PortableApps.com's own Windows tools, so they are done by hand:

1. Download the artifact from the build's page and unzip it.
2. Run the **PortableApps.com Launcher Generator** on the `KanzonasCADPortable` folder. It makes
   `KanzonasCADPortable.exe` from `App\AppInfo\Launcher\KanzonasCADPortable.ini`.
3. Run the **PortableApps.com Installer** on the folder. It makes
   `KanzonasCADPortable_<version>.paf.exe`.
4. Try it (install it into the PortableApps.com Platform, open a project, change a setting, close
   and reopen it), then post it in the portableapps.com forum's Development Test section.

The package follows PortableApps.com Format 3.9 (2026-03-02): `appinfo.ini` (with
Requires64bitOS=yes), PNG icons at 16/32/75/128/256 px and an `appicon.ico` with 256-color
16/32/48 px and true-color 16/32/48/256 px images (`assets/portableapps-appicon.ico`, made by
`tools/make_paf_icon.py`). Both PortableApps.com tools also work from the command line (pass
the package folder), so a later build can run them itself. Don't run the AppCompactor: it's
deprecated for releases, and compressed Python/Qt files can break or trip antivirus scanners.

How the package points the program at `Data`: `App\KanzonasCAD\portable.txt` contains
`data=..\..\Data` and `updates=off` (see `kanzonascad/paths.py`).
