# Release notes

Short, plain-language notes for each version. The full details are in
[CHANGELOG.md](CHANGELOG.md).

Every version gets a section `## <version>` (a few lines under **New** and **Fixed**). The
build fails without them.

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
