# Release notes

Short, plain-language notes for each version. The full details are in
[CHANGELOG.md](CHANGELOG.md).

Every version gets a section `## <version>` (a few lines under **New** and **Fixed**). The
build fails without them.

## 0.10.6

**New**
- Scoot: slide devices along their wire, as in AutoCAD Electrical. The wires follow, and the
  device never leaves its wire.
- Align devices: line devices up on their own wires (the same column on rungs), as AutoCAD
  Electrical's Align.

## 0.10.2

**New**
- A bigger CAD on the icon (and on the installer's blue one).

## 0.10.1

**New**
- KanzonasCAD has its own icon: the KanzonasPDF cactus and sunflower with a green CAD tag. It
  shows in the window, the taskbar, the Start menu and on .kzcad files. The installer's icon is
  the same in blue, as KanzonasPDF's is.

## 0.10

**New**
- DIN rail (TS35 x 7.5, TS35 x 15, TS15) and wire duct (2 x 3, 50 x 75 mm... any size) at
  real size: click both ends or type the length, and stretch them with their grips.
- Panel materials: how much rail and duct the project takes, how many stock lengths that is,
  and the cut lengths. Save it as CSV.

## 0.9

**New**
- Panel sheets have a scale (1:4, 3" = 1'-0"...): draw the panel at real size and it prints at
  that scale, with the border, title block and text at their normal size. Sheet scale... on
  the Panel tab, or click Scale in the status bar.
- Dimensions: Linear dimension (DLI) and Aligned dimension (DAL) measure the real distance.
- {Scale} for the title block. Footprints can't be scaled by accident on a panel sheet.

## 0.8

**New**
- Open and import AutoCAD DWG drawings directly (AutoCAD 2018 format and older, which is what
  every current AutoCAD saves), with nothing to install. File > Open... or Import DXF or DWG
  into this sheet....
- If a DWG can't be read and the free ODA File Converter is installed, KanzonasCAD uses it by
  itself.

## 0.7

**New**
- Three-phase symbols: 3-pole breaker, disconnect and fuses, contactor power contacts, overload
  heaters, a 3-phase motor and a VFD. Their poles line up with a 3-wire bus.
- Terminal strips: terminals belong to a strip, show its tag and number themselves 1, 2, 3.
- PLC I/O: input and output points belong to a PLC card, list under it and show their address.
- A power supply (AC in, DC out).

## 0.6

**New**
- Wire numbers: every wire gets its number by itself (6001, 6002 on page 6), one per connected
  wire, and keeps it. Double-click a wire to type your own; Renumber sheet puts them in order.
- Distribution blocks: the wires coming out take the incoming number with A, B, C added.
- Off-sheet connectors: a wire continuing on another sheet keeps its number, and each end
  shows where the other one is.

**Fixed**
- Trimming a wire turned the pieces into plain lines.

## 0.5

**New**
- Contacts belong to their coil: place a contact and press Enter to take the nearest coil, or
  type a tag. The contact shows the coil's tag and follows it when it changes.
- Cross-references: under each coil, a list of its contacts and where they are (NO 6-D3);
  under each contact, where its coil is (6-D1). They update by themselves.
- Freeze cross-references on an issued sheet, or turn automatic updates off for the project
  and use Update cross-references. The status bar tells you when they're out of date.

## 0.4.1

**New**
- A Windows installer: download `KanzonasCAD-v0.4.1-setup.exe` and run it. Install it for
  yourself (no administrator rights needed) or for everyone on the PC. You get a Start menu
  entry, and .kzcad projects open with a double-click.
- An installed KanzonasCAD updates itself with Update now. A copy installed for everyone asks
  for administrator rights first.

## 0.4

**New**
- Devices tag themselves by page: CR601, CR602, M601 on page 6. Copies get their own tag, and
  tags follow when a sheet's page number changes.
- Type a tag yourself and it stays (locked). Renumber sheet puts the rest in order, across then
  down or down then across.

**Fixed**
- Mirror, keeping the originals, could replace an original instead of adding the copy.

## 0.3.3

**Fixed**
- The tool icons vanished when Windows was in dark mode. Light, Dark and Same as system now
  mean exactly that, and the icons always stand out from what's behind them.

## 0.3.2

**New**
- KanzonasCAD now updates itself: it checks for new versions once a day, shows what changed,
  and Update now installs it (Help > Check for updates...).
- Each new version is published on the Releases page with a Windows download.

## 0.3.1

**New**
- The Library opens as a popup (Insert symbol, Insert footprint) instead of taking room at
  the side of the drawing, as AutoCAD Electrical's icon menu does.
- Circle has AutoCAD's other ways: center and diameter, 2-point, 3-point, tangent to two
  objects with a radius; the ribbon button shows the one used last.
- Bus: several wires side by side, as many turns as you need, all turning together.
- Lines on screen are drawn crisp, as in AutoCAD.

## 0.3

**New**
- Wires (W): click to click, straight across and up or down; a wire ends by itself on a pin
  or another wire, with a dot where wires join.
- Moving a symbol drags its wires along; dropping a symbol onto a wire wires it in.

**Fixed**
- Starting another command no longer throws away a wire or polyline being drawn.

## 0.2

**New**
- Your own library of schematic symbols, panel footprints and parts, kept in a folder outside
  the program (Documents\KanzonasCAD Library), for every project from now on.
- 27 built-in JIC/NFPA symbols: coils, contacts, pushbuttons, switches, fuses, breakers,
  overloads, lights, motor and more.
- Make block (B) turns a drawing into a symbol (with pins and a tag) or a panel footprint;
  parts link a manufacturer and catalog number to both.
- Scale by Reference brings a manufacturer's drawing to its real size; lengths can be typed in
  millimeters (45mm).
- Sheets start with rows A to H; the zones along the top and down the left are editable
  (how many, and where they start), and references follow them.
- Project properties (General, Schematic, Panel) and Sheet properties, as in AutoCAD
  Electrical: sheets follow the project's size and zones unless they have their own, and can
  have their own revision.
- Automatic backups: each Save keeps the version before it (the last 10), and unsaved work
  is autosaved every 5 minutes and offered back if KanzonasCAD didn't close normally.
- Sheets have a type (Schematic, Panel, Report, Other) that brings up the matching ribbon tab.
- Schematic and Panel ribbon tabs; objects take their layer's color unless you give them
  their own (Color...); wire, symbol, footprint and dimension colors in Project properties.
- Text justification like AutoCAD's (top, middle, bottom; left, center, right), and
  double-click a text to change its wording, height, angle or justification.

## 0.1

**New**
- The first version of KanzonasCAD, a free electrical CAD program for Windows and Linux.
- Projects with as many sheets as you need, each with a grid of zones (6-D1) along the top and
  left, and a title block you can redraw yourself (Sheets > Edit title block), with fields
  like {Customer} and {Sheet} OF {Sheets} filled in on every sheet.
- A black drawing area like AutoCAD's; PDFs always print black on white.
- AutoCAD-style drawing: command line (L, PL, C, M, CO, RO, TR...), object snaps, ortho, polar
  tracking at the angles you choose, grid snap, grips, undo and redo.
- Selecting like AutoCAD: the object under the cursor lights up, window and crossing
  selection, and the lasso (hold the button and draw around objects).
- Drag selected objects to move them (hold Ctrl to copy); the cursor shows a move arrow
  when you are over something you can drag.
- Layers, copy and paste, DXF import and export, PDF export.
- The same look as KanzonasPDF: menus, ribbon tabs and light or dark theme.
